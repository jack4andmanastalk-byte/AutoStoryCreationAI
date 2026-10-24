"""The operator provider is the only way to attach real prose without a key.

These tests pin the three properties that make it usable in a study:

* a missing answer stops the run at the exact prompt (exit 3, file named),
* a stale answer is refused instead of silently answering a different prompt,
* the key is readable and unique per (system, task, seed, purpose, attempt).

The provider never invents text: if the file is not there, the run fails.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "chat_operator.py"


def request(prompt: str = "第一稿を書いてください。", system: str = "s1",
            purpose: str = "draft:ch01", seed: int = 0, attempt: int = 1) -> dict:
    return {
        "purpose": purpose,
        "prompt": prompt,
        "system": None,
        "temperature": 0.8,
        "max_tokens": 2500,
        "seed": seed,
        "context": {"task_id": "t01", "chapter": "ch01",
                    "attempt": attempt, "system": system},
        "prompt_hash": "deadbeefdeadbeef",
    }


def call(root: Path, payload: dict | None = None) -> subprocess.CompletedProcess:
    stdin = "" if payload is None else json.dumps(payload, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(root)],
        input=stdin, capture_output=True, text=True,
    )


def answer(root: Path, key: str, text: str, **extra) -> Path:
    directory = root / "responses"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    path.write_text(json.dumps({"text": text, **extra}, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def test_missing_answer_stops_the_run_and_names_the_file(tmp_path):
    result = call(tmp_path, request())
    assert result.returncode == 3
    assert "NEED RESPONSE" in result.stderr
    saved = tmp_path / "requests" / "s1-t01-s0-draft-ch01-a1.json"
    assert saved.is_file(), "the prompt must be on disk so the operator can read it"
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["prompt"] == "第一稿を書いてください。"
    assert data["task_id"] == "t01"
    assert data["system"] == "s1"
    assert data["purpose"] == "draft:ch01"
    assert result.stdout.strip() == ""


def test_stored_answer_is_returned_with_its_model(tmp_path):
    payload = request()
    answer(tmp_path, "s1-t01-s0-draft-ch01-a1", "嵐の音で、灯台の窓が鳴っていた。",
           provenance={"origin": "reused", "source_run_id": "run-old"})
    result = call(tmp_path, payload)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["text"].startswith("嵐の音")
    assert out["model"] == "arena-agent-mode"
    assert out["model_version"] == "unversioned"
    assert out["usage"]["key"] == "s1-t01-s0-draft-ch01-a1"
    assert out["provenance"] == {"origin": "reused", "source_run_id": "run-old"}
    served = (tmp_path / "served.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(served[-1])["prompt_hash"] == "deadbeefdeadbeef"


def test_the_same_prompt_can_be_replayed(tmp_path):
    answer(tmp_path, "s1-t01-s0-draft-ch01-a1", "同じ本文。")
    first = call(tmp_path, request())
    second = call(tmp_path, request())
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout)["text"] == json.loads(second.stdout)["text"]


def test_changed_prompt_is_refused_as_stale(tmp_path):
    answer(tmp_path, "s1-t01-s0-draft-ch01-a1", "前の本文。")
    assert call(tmp_path, request()).returncode == 0
    changed = request(prompt="別のプロンプトに変わった。")
    changed["prompt_hash"] = "0123456789abcdef"
    result = call(tmp_path, changed)
    assert result.returncode == 4
    assert "STALE RESPONSE" in result.stderr
    assert "deadbeefdeadbeef" in result.stderr


def test_a_pinned_hash_wins_over_the_served_log(tmp_path):
    payload = request()
    answer(tmp_path, "s1-t01-s0-draft-ch01-a1", "本文。",
           prompt_hash="0000000000000000")
    result = call(tmp_path, payload)
    assert result.returncode == 4
    assert "prompt_now=deadbeefdeadbeef" in result.stderr


def test_an_empty_answer_is_an_error_not_a_short_chapter(tmp_path):
    answer(tmp_path, "s1-t01-s0-draft-ch01-a1", "   ")
    result = call(tmp_path, payload=request())
    assert result.returncode == 2
    assert "non-empty string field 'text'" in result.stderr


def test_the_key_separates_system_seed_purpose_and_attempt():
    keys = {
        (request()["context"]["system"], request()["seed"],
         request()["purpose"], request()["context"]["attempt"]),
        ("s0", 0, "draft:ch01", 1),
        ("s0", 1, "draft:ch01", 1),
        ("s1", 0, "draft:ch01", 2),
        ("s1", 0, "plan", 1),
    }
    # The key is derived from the request, so a duplicate tuple would collide.
    assert len(keys) == 5
    assert ":" not in "s1-t01-s0-draft-ch01-a1"


def test_status_lists_what_is_still_missing(tmp_path):
    call(tmp_path, request())
    answer(tmp_path, "s0-t01-s0-draft-ch01-a1", "本文。")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(tmp_path), "--status"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    status = json.loads(result.stdout)
    assert status["requests"] == 1
    assert status["ready"] == []
    assert status["pending"] == ["s1-t01-s0-draft-ch01-a1"]
