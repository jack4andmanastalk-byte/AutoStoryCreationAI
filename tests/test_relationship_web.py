from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.relation import (  # noqa: E402
    RelationDocError, check_relations, load_relations,
)
from asc.story.canon import load_canon  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "relation-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_relations_have_no_findings():
    report = check_relations(load_relations(DEMO / "relations.yaml"),
                             load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_relations_fail_every_check():
    """EXPECTED.md の 6 検査が、すべて fail になること。"""
    report = check_relations(load_relations(DEMO / "relations-bad.yaml"),
                             load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"pair_grounded", "conflict_declared",
                      "knowledge_tabled", "knowledge_matches_canon",
                      "change_staged", "silence_meant"}


def test_bad_relations_name_each_seeded_defect():
    report = check_relations(load_relations(DEMO / "relations-bad.yaml"),
                             load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("表向き" in m for m in by_check["pair_grounded"])
    assert any("両立しない" in m for m in by_check["conflict_declared"])
    assert any("maybe" in m for m in by_check["knowledge_tabled"])
    assert any("F-07" in m for m in by_check["knowledge_matches_canon"])
    assert any("関係表にない" in m for m in by_check["change_staged"])
    assert any("unsaid_ja" in m for m in by_check["silence_meant"])


def test_every_check_reports_its_acceptance_condition():
    report = check_relations(load_relations(DEMO / "relations.yaml"),
                             load_canon(CANON))
    assert len(report["checks"]) == 6
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_design_may_plan_beyond_the_canon(tmp_path):
    """設計は canon の先を描いてよい（knows の計画は許す）。"""
    doc = tmp_path / "relations.yaml"
    doc.write_text("pairs:\n  - {a: aria, b: boris, public: P, stakes: S,"
                   " conflict: C}\n"
                   "knowledge:\n  - {character: aria, fact: F-09,"
                   " state: knows}\n", encoding="utf-8")
    report = check_relations(load_relations(doc), load_canon(CANON))
    assert [f for f in report["findings"]
            if f["check"] == "knowledge_matches_canon"] == []


def test_canon_is_optional():
    report = check_relations(load_relations(DEMO / "relations.yaml"), None)
    skipped = {c["id"] for c in report["checks"] if c["status"] == "skipped"}
    assert skipped == {"knowledge_matches_canon"}


def test_pair_without_people_is_an_input_error(tmp_path):
    bad = tmp_path / "relations.yaml"
    bad.write_text("pairs:\n  - {a: aria}\n", encoding="utf-8")
    with pytest.raises(RelationDocError):
        load_relations(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_relation.py",
         "--relations", str(DEMO / "relations.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_relation.py",
         "--relations", str(DEMO / "relations-bad.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
