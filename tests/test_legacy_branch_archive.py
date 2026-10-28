"""Protect a historical diff without running its uncompleted experiment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PATCH = (Path(__file__).resolve().parents[1] / "experiments" / "archives"
         / "legacy-fixed-canon-b-2026-10-27" / "source-change.patch")
PREFIX = "experiments/2026-10-realrun-b-t01/"


def _new_file(patch: bytes, path: str) -> bytes:
    header = f"diff --git a/{path} b/{path}\n".encode()
    assert patch.count(header) == 1
    section = patch.split(header, 1)[1].split(b"diff --git ", 1)[0]
    assert b"new file mode 100644\n" in section
    return b"".join(line[1:] for line in section.splitlines(keepends=True)
                    if line.startswith(b"+") and not line.startswith(b"+++"))


def test_historical_patch_is_unchanged_and_incomplete():
    patch = PATCH.read_bytes()
    assert hashlib.sha256(patch).hexdigest() == (
        "e966b42b4f39a3c1e87fc8500b0228701b20f6bd5144c245fe2a03915f8127d4")
    assert patch.count(b"diff --git ") == 21
    prereg = _new_file(patch, PREFIX + "preregistration.json")
    assert hashlib.sha256(prereg).hexdigest() == (
        "ecaccfe468b7ca926ff5fe5171d07f3a6ffb87348961b796dc67482f97701b2f")
    assert json.loads(prereg)["condition"]["plan"]["requested"] is False
    results = json.loads(_new_file(patch, PREFIX + "results.json"))
    assert results["verdicts"]["samples_present"] == 0
    assert results["verdicts"]["B1_design_first_attempt"]["verdict"] == "not_run"
    relay = json.loads(_new_file(patch, PREFIX + "relay/sample-1/index.json"))
    assert [request["tag"] for request in relay["pending"]] == ["CF27"]
