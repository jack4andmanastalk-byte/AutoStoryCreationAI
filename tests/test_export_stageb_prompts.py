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


def test_the_committed_prompts_are_what_batch_a_answered(tmp_path):
    """The bundle's prompts are an archive: batch A answered them verbatim.

    They were rendered from template v1.1. The template has since moved on, so a
    fresh render must *not* match — the archive stays frozen and says so.
    """
    assert export_stageb_prompts.main([
        "--bundle", str(BUNDLE), "--out", str(tmp_path)]) == 0
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    assert index["archived"] is True
    assert index["template_version"] == "1.1"
    fresh_index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    for chapter, row in index["prompts"].items():
        committed = (PROMPTS / row["file"]).read_text(encoding="utf-8")
        assert hashlib.sha256(committed.encode("utf-8")).hexdigest()[:16] == \
            row["prompt_hash"]
        assert fresh_index["prompts"][chapter]["prompt_hash"] != row["prompt_hash"], \
            f"{chapter}: the archive should lag the current template"


def test_ch01_keeps_the_hash_the_v11_run_recorded():
    index = json.loads((PROMPTS / "index.json").read_text(encoding="utf-8"))
    # 2026-10-stageb-v11-t01 and batch A asked with this prompt.
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


def test_every_committed_answer_declares_where_it_came_from():
    """No invented model text: each answer carries provenance, and the count is
    the one the registration planned."""
    responses = sorted((BUNDLE / "relay").glob("*/responses/*.json"))
    assert responses, "the run recorded no answers"
    for path in responses:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["text"].strip(), path
        assert payload["provenance"]["origin"] in {"fresh", "reused"}, path
        assert payload["model"], path
    registered = json.loads(
        (BUNDLE / "preregistration.json").read_text(encoding="utf-8"))
    samples = {path.parent.name for path in (BUNDLE / "relay").glob("*/responses")}
    assert len(samples) == registered["samples_planned"]
    for name in samples:
        keys = [path.stem for path in (BUNDLE / "relay" / name / "responses").glob("*.json")]
        for chapter in ("ch01", "ch02", "ch03"):
            assert any(chapter in key for key in keys), (name, chapter)
