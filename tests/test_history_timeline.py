from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.history import HistoryError, check_history, load_history  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "history-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_history_has_no_findings():
    report = check_history(load_history(DEMO / "history.yaml"), load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_apocryphal_claim_matches_event_text_and_detailed_origin(tmp_path):
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps({
        "events": [{
            "id": "E-01", "year": 1,
            "title": "異説・嵐の夜に灯りを消した者は翌朝には帰らぬ者となる",
            "effect": "この語りが港町に広まった。",
            "trace": "子守唄と船頭の口伝に残る。",
        }],
        "sources": [{
            "id": "S-01", "holder": "港町の年寄り",
            "origin": "invented: 港町の口伝",
        }],
        "apocrypha": ["嵐の夜に灯りを消した者は、翌朝には帰らぬ者となる。"],
    }, ensure_ascii=False), encoding="utf-8")

    report = check_history(load_history(history_path))
    assert report["findings"] == []


def test_bad_history_fails_every_check():
    """EXPECTED.md の 5 検査が、すべて fail になること。"""
    report = check_history(load_history(DEMO / "history-bad.yaml"), load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"chronology_ordered", "causality_linked", "trace_exists",
                      "canon_separated", "knowledge_consistent"}


def test_bad_history_names_each_seeded_defect():
    report = check_history(load_history(DEMO / "history-bad.yaml"), load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("年代順" in m for m in by_check["chronology_ordered"])
    assert any("E-09" in m for m in by_check["causality_linked"])
    assert any("痕跡" in m for m in by_check["trace_exists"])
    assert any("E-07" in m for m in by_check["canon_separated"])
    assert any("zorro" in m for m in by_check["knowledge_consistent"])


def test_every_check_reports_its_acceptance_condition():
    report = check_history(load_history(DEMO / "history.yaml"), load_canon(CANON))
    assert len(report["checks"]) == 5
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_canon_is_optional_but_weakens_the_knowledge_check():
    report = check_history(load_history(DEMO / "history.yaml"), None)
    assert report["findings"] == []
    bad = check_history(load_history(DEMO / "history-bad.yaml"), None)
    failed = {c["id"] for c in bad["checks"] if c["status"] == "fail"}
    assert "knowledge_consistent" in failed  # E-05 still dangles


def test_event_without_year_is_an_input_error(tmp_path):
    bad = tmp_path / "history.yaml"
    bad.write_text("events:\n  - {id: E-01, title: X}\n", encoding="utf-8")
    with pytest.raises(HistoryError):
        load_history(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_history.py",
         "--history", str(DEMO / "history.yaml"), "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_history.py",
         "--history", str(DEMO / "history-bad.yaml"), "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
