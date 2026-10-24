from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.adapt import (  # noqa: E402
    AdaptationDocError, check_adaptation, load_adaptation,
)

DEMO = REPO_ROOT / "harness" / "cases" / "adaptation-demo"


def test_good_adaptation_has_no_findings():
    report = check_adaptation(load_adaptation(DEMO / "adaptation.yaml"))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_adaptation_fails_every_check():
    """EXPECTED.md の 4 検査が、すべて fail になること。"""
    report = check_adaptation(load_adaptation(DEMO / "adaptation-bad.yaml"))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"functions_listed", "mappings_assigned",
                      "deletions_recorded", "rights_logged"}


def test_bad_adaptation_names_each_seeded_defect():
    report = check_adaptation(load_adaptation(DEMO / "adaptation-bad.yaml"))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("mystery" in m for m in by_check["functions_listed"])
    assert any("fn-ghost" in m for m in by_check["mappings_assigned"])
    assert any("fn-b" in m for m in by_check["mappings_assigned"])
    assert any("両方" in m for m in by_check["deletions_recorded"])
    assert any("unknown" in m for m in by_check["rights_logged"])


def test_every_check_reports_its_acceptance_condition():
    report = check_adaptation(load_adaptation(DEMO / "adaptation.yaml"))
    assert len(report["checks"]) == 4
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_pending_rights_are_low_not_medium(tmp_path):
    doc = tmp_path / "adaptation.yaml"
    doc.write_text(
        "functions:\n  - {id: f1, kind: info, description: D}\n"
        "mappings:\n"
        "  - {function: f1, means: M, newcomer: N, existing: E}\n"
        "rights: {source: S, scope: C, status: pending}\n", encoding="utf-8")
    report = check_adaptation(load_adaptation(doc))
    assert [(f["check"], f["severity"]) for f in report["findings"]] == [
        ("rights_logged", "low")]


def test_rights_must_be_a_mapping(tmp_path):
    bad = tmp_path / "adaptation.yaml"
    bad.write_text("rights: なんか許諾\n", encoding="utf-8")
    with pytest.raises(AdaptationDocError):
        load_adaptation(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_adaptation.py",
         "--adaptation", str(DEMO / "adaptation.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_adaptation.py",
         "--adaptation", str(DEMO / "adaptation-bad.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
