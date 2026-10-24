#!/usr/bin/env python3
"""A provider that hands the prompt to an operator (a person or a chat) and
replays the answer that the operator stored on disk.

The repository never holds an API key, so a model can be attached in three
ways: a scripted fixture, an external command, or this file. Here the "model"
is whoever reads ``requests/<key>.json`` and writes ``responses/<key>.json``.
That is enough to run the pipeline with real prose, but it is **not** a
reproducible model: :mod:`docs.protocol` G5 (same seed, same output) cannot be
met, so the numbers are reference values only.

Contract with the pipeline
--------------------------
The command reads one ``GenerationRequest`` JSON object on stdin and prints
``{"text": ..., "model": ..., "model_version": ...}`` on stdout. If the answer
is missing it exits 3 and says which file to write, so the caller can stop at
the exact prompt that has no text yet instead of inventing one.

A response can declare ``provenance: {"origin": "fresh"}`` or
``{"origin": "reused", "source_run_id": "..."}``. The experiment summary
counts these origins. Missing provenance stays ``unspecified``; it is never
assumed to be fresh.

The ``--dir`` must not live under ``build/``: ``build/`` is scratch and is not
kept across sessions, and losing ``responses/`` means paying for the same text
twice. ``runs/operator/<name>`` is git-ignored and survives.

    # one call, as the pipeline makes it
    python3 scripts/chat_operator.py --dir runs/operator/pilot < request.json

    # what is still missing
    python3 scripts/chat_operator.py --dir runs/operator/pilot --status

Exit codes: 0 ok, 2 bad input, 3 response missing, 4 response is stale
(the prompt changed after the answer was written, so the text no longer
answers the question that is being asked).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "arena-agent-mode"
DEFAULT_MODEL_VERSION = "unversioned"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def request_key(request: dict) -> str:
    """A readable key: system, task, seed, purpose, attempt.

    Content hashes are recorded next to it, not inside it, because the operator
    has to be able to find the file by name.
    """
    context = request.get("context") or {}
    raw = "-".join([
        str(context.get("system") or "none"),
        str(context.get("task_id") or "task"),
        f"s{request.get('seed', 0)}",
        str(request.get("purpose") or "generate"),
        f"a{context.get('attempt', 1)}",
    ])
    return re.sub(r"[^0-9A-Za-z._-]+", "-", raw)


class Operator:
    def __init__(self, root: str | Path, model: str = DEFAULT_MODEL,
                 model_version: str = DEFAULT_MODEL_VERSION):
        self.root = Path(root)
        self.model = model
        self.model_version = model_version

    # -- paths ------------------------------------------------------------
    @property
    def requests(self) -> Path:
        return self.root / "requests"

    @property
    def responses(self) -> Path:
        return self.root / "responses"

    @property
    def served_log(self) -> Path:
        return self.root / "served.jsonl"

    def request_path(self, key: str) -> Path:
        return self.requests / f"{key}.json"

    def response_path(self, key: str) -> Path:
        return self.responses / f"{key}.json"

    # -- bookkeeping ------------------------------------------------------
    def record_request(self, key: str, request: dict, prompt_hash: str) -> Path:
        self.requests.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": key,
            "purpose": request.get("purpose"),
            "system": (request.get("context") or {}).get("system"),
            "task_id": (request.get("context") or {}).get("task_id"),
            "seed": request.get("seed"),
            "attempt": (request.get("context") or {}).get("attempt", 1),
            "prompt_hash": prompt_hash,
            "temperature": request.get("temperature"),
            "max_tokens": request.get("max_tokens"),
            "recorded_at": now(),
            "prompt": request.get("prompt"),
        }
        path = self.request_path(key)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return path

    def last_served_hash(self, key: str) -> str | None:
        if not self.served_log.is_file():
            return None
        seen = None
        for line in self.served_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("key") == key:
                seen = entry.get("prompt_hash")
        return seen

    def log_served(self, key: str, prompt_hash: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        entry = {"key": key, "prompt_hash": prompt_hash, "served_at": now()}
        with self.served_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- the provider call ------------------------------------------------
    def generate(self, request: dict) -> dict:
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("request has no prompt")
        prompt_hash = request.get("prompt_hash") or digest(prompt)
        key = request_key(request)
        self.record_request(key, request, prompt_hash)

        path = self.response_path(key)
        if not path.is_file():
            raise MissingResponse(key, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{path}: expected a non-empty string field 'text'")
        provenance = payload.get("provenance", {}) or {}
        if not isinstance(provenance, dict):
            raise ValueError(f"{path}: expected an object field 'provenance'")
        pinned = payload.get("prompt_hash")
        served = self.last_served_hash(key)
        if pinned and pinned != prompt_hash:
            raise StaleResponse(key, path, pinned, prompt_hash)
        if not pinned and served and served != prompt_hash:
            raise StaleResponse(key, path, served, prompt_hash)

        self.log_served(key, prompt_hash)
        return {
            "text": text,
            "model": payload.get("model") or self.model,
            "model_version": payload.get("model_version") or self.model_version,
            "usage": {"operator": True, "key": key},
            "provenance": provenance,
        }

    def status(self) -> dict:
        keys = sorted(path.stem for path in self.requests.glob("*.json")) \
            if self.requests.is_dir() else []
        ready, pending = [], []
        for key in keys:
            (ready if self.response_path(key).is_file() else pending).append(key)
        return {"requests": len(keys), "ready": ready, "pending": pending}


class MissingResponse(RuntimeError):
    def __init__(self, key: str, path: Path):
        super().__init__(f"NEED RESPONSE key={key} file={path}")
        self.key = key
        self.path = path


class StaleResponse(RuntimeError):
    def __init__(self, key: str, path: Path, written_for: str, now_needed: str):
        super().__init__(
            f"STALE RESPONSE key={key} file={path} "
            f"written_for={written_for} prompt_now={now_needed} "
            f"(the prompt changed; delete the response or write a new one)")
        self.key = key
        self.path = path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, help="operator directory (requests/, responses/)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--status", action="store_true",
                        help="print which prompts have an answer and exit")
    args = parser.parse_args(argv)

    operator = Operator(args.dir, model=args.model, model_version=args.model_version)

    if args.status:
        print(json.dumps(operator.status(), ensure_ascii=False, indent=2))
        return 0

    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        result = operator.generate(request)
    except MissingResponse as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except StaleResponse as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"chat-operator: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
