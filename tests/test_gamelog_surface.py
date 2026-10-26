"""Candidate surface checks: places measured, numbers only reported."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import load_game_log  # noqa: E402
from asc.gamelog.surface import (movement_claims, numbers_in_text,  # noqa: E402
                                 place_findings, sentences,
                                 unmatched_numbers)
from asc.gamelog.world import chapter_timeline, derive_timeline  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
import probe_surface_checks  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-stageb-v11-t01"
INPUTS = BUNDLE / "inputs"
ARMS = {
    "log-backed": BUNDLE / "relay" / "responses",
    "direct": REPO_ROOT / "experiments" / "2026-10-l1-pair-t01" / "relay" / "responses",
}


@pytest.fixture(scope="module")
def context():
    canon = load_canon(INPUTS / "canon")
    log = load_game_log(INPUTS / "game_log.json")
    return {"canon": canon, "log": log, "timeline": derive_timeline(log, canon)}


def chapter_text(arm: str, chapter: str) -> str:
    for path in sorted(ARMS[arm].glob(f"*{chapter}-a*.json")):
        text = json.loads(path.read_text(encoding="utf-8"))["text"]
    return text


def test_sentences_drop_markers_and_split_lines():
    text = "{{time: day=1}}{{location: 灯台}}\n一つ目。二つ目！\n\n三つ目。"
    assert sentences(text) == [(2, "一つ目。"), (2, "二つ目！"), (4, "三つ目。")]


def test_movement_claims_need_a_place_shaped_destination():
    claims = movement_claims(
        "アリアは対岸の島へ渡った。父は灯りの話に戻った。灯台に着いた。")
    assert [claim.destination for claim in claims] == ["対岸の島", "灯台"]


def test_a_capture_with_a_leading_clause_is_trimmed_to_the_place(context):
    findings = place_findings(
        "アリアは船で対岸の島へ渡り、知らない港町を歩いた。",
        chapter_timeline(context["timeline"], "ch01"), context["canon"])
    assert len(findings) == 1
    assert findings[0]["evidence"]["destination"] == "対岸の島"
    assert findings[0]["advisory"] is True
    assert findings[0]["severity"] == "medium"
    assert "canon にもログにもない地名" in findings[0]["message_ja"]


def test_a_canon_place_without_a_declared_move_is_reported_differently(context):
    row = chapter_timeline(context["timeline"], "ch03")  # no moves in this chapter
    findings = place_findings("アリアは港へ向かった。", row, context["canon"])
    assert len(findings) == 1
    assert "宣言されていない" in findings[0]["message_ja"]
    # ... but the chapter's own location is allowed.
    assert place_findings("アリアは灯台に着いた。", row, context["canon"]) == []


def test_the_clean_chapters_produce_no_place_findings(context):
    for arm in ARMS:
        for chapter in ("ch01", "ch02", "ch03"):
            row = chapter_timeline(context["timeline"], chapter)
            findings = place_findings(chapter_text(arm, chapter), row,
                                      context["canon"])
            assert findings == [], (arm, chapter, findings)


def test_numbers_are_reported_but_never_a_verdict(context):
    text = chapter_text("log-backed", "ch03")
    tokens = numbers_in_text(text)
    assert tokens and all("token" in item for item in tokens)
    refs = probe_surface_checks.references(INPUTS / "canon", context["log"])
    unmatched = unmatched_numbers(text, refs)
    # 「一本」 has no counterpart in the log, and is still ordinary language:
    # the report lists it, and nothing acts on it.
    assert "一本" in {item["token"] for item in unmatched}
    assert all("severity" not in item for item in unmatched)


def test_the_probe_records_precision_evidence_and_recall(tmp_path):
    out = tmp_path / "surface.json"
    completed = probe_surface_checks.main([
        "--game-log", str(INPUTS / "game_log.json"),
        "--canon", str(INPUTS / "canon"),
        "--arm", f"log-backed={ARMS['log-backed']}",
        "--arm", f"direct={ARMS['direct']}",
        "--out", str(out)])
    assert completed == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "surface-checks-v1"
    for arm in ("log-backed", "direct"):
        for chapter, row in report["arms"][arm]["chapters"].items():
            assert row["place_findings"] == [], (arm, chapter)
    injected = report["injections"]["offlog_place"]
    assert injected["log-backed"]["new_places"] == ["対岸の島"]
    assert injected["direct"]["new_places"] == ["対岸の島"]
    numbers = report["injections"]["unquantified_number"]
    assert numbers["log-backed"]["new_numbers"] == ["半日"]
    # The report exists, but it is a list a human reads; no findings are made.
    assert report["limits"]
