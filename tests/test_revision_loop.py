from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.revision import (  # noqa: E402
    apply_patches, compare_reports, detect_repeats, plan_round,
)
from asc.story.continuity import audit_texts  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "revision-demo"


def test_plan_turns_findings_into_critiques():
    """EXPECTED.md の 2 件が CR-001/CR-002 になること。"""
    critique = plan_round(audit_texts(DEMO / "canon", DEMO / "text"))
    assert [c["id"] for c in critique["critiques"]] == ["CR-001", "CR-002"]
    assert critique["critiques"][0]["severity"] == "high"
    assert critique["critiques"][1]["severity"] == "medium"
    for item in critique["critiques"]:
        assert item["problem_ja"] and item["fix_ja"] and item["status"] == "open"


def test_full_loop_removes_both_findings(tmp_path):
    patch = json.loads((DEMO / "patch.json").read_text(encoding="utf-8"))
    revised = tmp_path / "revised"
    applied = apply_patches(DEMO / "text", patch, revised)
    assert applied["summary"] == {"patches": 2, "applied": 2, "failed": 0}
    before = audit_texts(DEMO / "canon", DEMO / "text")
    after = audit_texts(DEMO / "canon", revised)
    assert after["violations"] == []
    comparison = compare_reports(before, after)
    assert comparison["summary"]["fixed"] == 2
    assert comparison["summary"]["persisting"] == 0
    assert comparison["summary"]["new"] == 0


def test_ambiguous_anchor_fails_instead_of_guessing(tmp_path):
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("鍵があった。\n鍵があった。\n", encoding="utf-8")
    result = apply_patches(text, {"patches": [
        {"chapter": "ch01.md", "anchor": "鍵があった。",
         "replacement": "鍵がなかった。", "reason": "試し"}]},
        tmp_path / "out")
    assert result["summary"]["failed"] == 1
    assert "2 箇所" in result["results"][0]["reason"]


def test_missing_anchor_fails_with_reason(tmp_path):
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("鍵があった。\n", encoding="utf-8")
    result = apply_patches(text, {"patches": [
        {"chapter": "ch01.md", "line": 1, "anchor": "剣があった。",
         "replacement": "鍵があった。", "reason": "試し"}]},
        tmp_path / "out")
    assert result["summary"]["failed"] == 1
    assert "anchor" in result["results"][0]["reason"]


def test_compare_detects_new_findings_introduced_by_revision():
    before = {"violations": [], "findings": []}
    after = {"violations": [{"type": "travel_time", "severity": "medium",
                             "subject": None, "chapter": "ch02",
                             "message_ja": "移動が速い。"}], "findings": []}
    comparison = compare_reports(before, after)
    assert comparison["summary"]["new"] == 1
    assert comparison["summary"]["persisting_medium_plus"] == 0


def test_repeats_flag_a_defect_present_in_every_round():
    report = {"violations": [{"type": "travel_time", "severity": "medium",
                              "subject": None, "chapter": "ch02",
                              "message_ja": "移動が速い。"}], "findings": []}
    repeats = detect_repeats([report, report])
    assert len(repeats) == 1
    assert repeats[0]["repeat"] is True
    assert "根本原因" in repeats[0]["note_ja"]
    assert detect_repeats([report]) == []
