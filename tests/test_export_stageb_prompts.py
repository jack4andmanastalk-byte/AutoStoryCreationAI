"""The exported prompts must be the ones the pipeline would actually ask.

If this drifts, an operator answers a question the run never asked, and the
answer is refused as stale — or worse, a re-rendered prompt passes for the real
one. The test therefore compares against the committed exports and pins the
hash that the v1.1 run recorded.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import export_stageb_prompts  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-a-t01"
PROMPTS = BUNDLE / "prompts"


def test_the_committed_prompts_match_a_fresh_render(tmp_path):
    assert export_stageb_prompts.main([
        "--bundle", str(BUNDLE), "--out", str(tmp_path)]) == 0
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    for chapter, row in index["prompts"].items():
        fresh = (tmp_path / row["file"]).read_text(encoding="utf-8")
        committed = (PROMPTS / row["file"]).read_text(encoding="utf-8")
        assert fresh == committed, chapter
        assert hashlib.sha256(fresh.encode("utf-8")).hexdigest()[:16] == \
            row["prompt_hash"]


def test_ch01_keeps_the_hash_the_v11_run_recorded():
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    # 2026-10-stageb-v11-t01 asked with this prompt; the template must not drift.
    assert index["prompts"]["ch01"]["prompt_hash"] == "ab8be3c448d7e96d"


def test_every_exported_prompt_asks_for_one_chapter():
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    for chapter, row in index["prompts"].items():
        text = (PROMPTS / row["file"]).read_text(encoding="utf-8")
        assert chapter in text
        assert "1,000〜1,400" in text
        assert row["purpose"] == f"stage_b:{chapter}"


def test_the_bundle_holds_all_three_chapters():
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    assert sorted(index["prompts"]) == ["ch01", "ch02", "ch03"]
    # ALL.md is the single-file handoff for a chat; it must contain each prompt.
    combined = (PROMPTS / "ALL.md").read_text(encoding="utf-8")
    for row in index["prompts"].values():
        assert row["prompt_hash"] in combined


def test_no_answers_are_committed_yet():
    # The bundle must not carry invented model text: no run, no responses.
    assert not list(PROMPTS.parent.glob("sample-*"))
    assert not list((PROMPTS.parent / "relay").glob("*/responses/*.json"))
    results = json.loads((BUNDLE / "results.json").read_text(encoding="utf-8"))
    assert results["samples"] == {}
    assert results["verdicts"]["R1_place_branch"]["verdict"] == "not_run"
