"""The model adapter is the only path that satisfies G5, so its contract is pinned.

These tests run against a local stub endpoint, not a real model: they check the
request that leaves the machine (path, auth header, body), the mapping back into
the provider contract, and the failure modes that would otherwise show up as an
empty or truncated chapter three steps later.

Nothing here asserts model quality. A key in the environment would make the
tests depend on a network and a bill.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "model_adapter.py"
SECRET = "sk-test-do-not-print-4f2a"

REPLY = {
    "model": "stub-2025-04-14",
    "choices": [{"message": {"role": "assistant", "content": "嵐の音で、灯台の窓が鳴っていた。"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
}


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server's spelling
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        self.server.records.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(raw or b"{}"),
        })
        status, payload = self.server.replies.pop(0) if self.server.replies else (200, REPLY)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep pytest output clean
        pass


class Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        self.httpd.records = []
        self.httpd.replies = []
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def records(self):
        return self.httpd.records

    def enqueue(self, status: int, payload: dict):
        self.httpd.replies.append((status, payload))


def request(**overrides) -> dict:
    payload = {
        "purpose": "draft:ch01",
        "prompt": "3 章構成の 1 章目を書いてください。",
        "system": None,
        "temperature": 0.8,
        "max_tokens": 2500,
        "seed": 3,
        "context": {"task_id": "t01", "chapter": "ch01", "attempt": 1, "system": "s1"},
        "prompt_hash": "deadbeefdeadbeef",
    }
    payload.update(overrides)
    return payload


def call(server: Server, payload: dict, *extra: str, key: str | None = SECRET):
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if key is not None:
        env["MODEL_API_KEY"] = key
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--model", "gpt-4.1",
         "--base-url", server.base_url, "--api-key-env", "MODEL_API_KEY",
         "--retry-delay", "0", "--max-retries", "1", *extra],
        input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
        env=env,
    )


def test_one_call_has_the_expected_body_and_maps_the_answer():
    with Server() as server:
        result = call(server, request())
        assert result.returncode == 0, result.stderr
        record = server.records[0]
        assert record["path"] == "/v1/chat/completions"
        assert record["authorization"] == f"Bearer {SECRET}"
        body = record["body"]
        assert body["model"] == "gpt-4.1"
        assert body["messages"] == [{"role": "user", "content": "3 章構成の 1 章目を書いてください。"}]
        assert body["temperature"] == 0.8
        assert body["max_tokens"] == 2500
        assert body["seed"] == 3

        out = json.loads(result.stdout)
        assert out["text"].startswith("嵐の音")
        assert out["model"] == "gpt-4.1"
        assert out["model_version"] == "stub-2025-04-14"
        assert out["usage"]["total_tokens"] == 160


def test_the_system_prompt_is_sent_first_when_present():
    with Server() as server:
        result = call(server, request(system="乾いた三人称で書く。"))
        assert result.returncode == 0, result.stderr
        messages = server.records[0]["body"]["messages"]
        assert messages[0] == {"role": "system", "content": "乾いた三人称で書く。"}
        assert messages[1]["role"] == "user"


def test_a_pinned_version_wins_over_the_endpoint_field():
    with Server() as server:
        result = call(server, request(), "--model-version", "2025-04-14")
        assert json.loads(result.stdout)["model_version"] == "2025-04-14"


def test_a_rate_limit_is_retried_then_succeeds():
    with Server() as server:
        server.enqueue(429, {"error": "slow down"})
        result = call(server, request())
        assert result.returncode == 0, result.stderr
        assert len(server.records) == 2


def test_a_server_error_fails_with_the_status_and_no_secret():
    with Server() as server:
        server.enqueue(500, {"error": "boom"})
        server.enqueue(500, {"error": "boom"})
        result = call(server, request())
        assert result.returncode == 1
        assert "HTTP 500" in result.stderr
        assert SECRET not in result.stderr
        assert SECRET not in result.stdout


def test_a_missing_key_is_a_configuration_error_not_an_empty_chapter():
    with Server() as server:
        result = call(server, request(), key=None)
        assert result.returncode == 2
        assert "MODEL_API_KEY is not set" in result.stderr
        assert server.records == []


def test_an_answer_without_text_is_an_error():
    with Server() as server:
        server.enqueue(200, {"model": "stub", "choices": [{"message": {"content": ""},
                                                           "finish_reason": "length"}]})
        result = call(server, request())
        assert result.returncode == 1
        assert "finish_reason='length'" in result.stderr


def test_dry_run_shows_the_body_without_a_key():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--model", "gpt-4.1", "--dry-run",
         "--json-mode", "on", "--max-tokens-param", "max_completion_tokens"],
        input=json.dumps(request(), ensure_ascii=False), capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["model"] == "gpt-4.1"
    assert body["max_completion_tokens"] == 2500
    assert body["response_format"] == {"type": "json_object"}


def dry_run(payload: dict, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--model", "gpt-4.1", "--dry-run", *extra],
        input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_json_mode_is_on_for_the_plan_purposes_and_off_for_drafts():
    assert dry_run(request(purpose="plan"))["response_format"] == {"type": "json_object"}
    assert dry_run(request(purpose="plan-repair"))["response_format"] == {"type": "json_object"}
    assert "response_format" not in dry_run(request(purpose="draft:ch01"))
    assert "response_format" not in dry_run(request(purpose="plan"), "--json-mode", "off")
    assert dry_run(request(purpose="draft:ch01"), "--json-mode", "on")["response_format"] == {
        "type": "json_object"}


def test_seed_can_be_omitted_for_endpoints_that_reject_it():
    with Server() as server:
        result = call(server, request(), "--no-seed")
        assert result.returncode == 0, result.stderr
        assert "seed" not in server.records[0]["body"]


def test_the_pipeline_command_provider_accepts_this_adapter(monkeypatch):
    """The two halves must fit: the pipeline shells out, the adapter answers."""
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "src"))
    from asc.pipeline import CommandProvider, GenerationRequest

    with Server() as server:
        monkeypatch.setenv("MODEL_API_KEY", SECRET)
        command = (f"{_sys.executable} {SCRIPT} --model gpt-4.1 "
                   f"--base-url {server.base_url} --api-key-env MODEL_API_KEY "
                   f"--retry-delay 0 --model-version 2025-04-14")
        provider = CommandProvider(command, model="gpt-4.1",
                                   model_version="2025-04-14")
        result = provider.generate(GenerationRequest(
            purpose="draft:ch01", prompt="3 章構成の 1 章目を書いてください。",
            temperature=0.8, max_tokens=2500, seed=3,
            context={"task_id": "t01", "chapter": "ch01", "attempt": 1, "system": "s1"},
        ))
        assert result.provider == "command"
        assert result.text.startswith("嵐の音")
        assert result.model == "gpt-4.1"
        assert result.model_version == "2025-04-14"
        assert result.usage["total_tokens"] == 160
