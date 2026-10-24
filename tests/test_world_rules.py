from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.story.canon import load_canon  # noqa: E402
from asc.world import WorldError, check_world, load_world  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "world-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_world_has_no_findings():
    report = check_world(load_world(DEMO / "world.yaml"), load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_world_fails_every_check():
    """EXPECTED.md の 5 検査が、すべて fail になること。"""
    report = check_world(load_world(DEMO / "world-bad.yaml"), load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"axiom_declared", "rule_has_cost", "exception_bounded",
                      "geography_grounded", "disclosure_ordered"}


def test_bad_world_names_each_seeded_defect():
    report = check_world(load_world(DEMO / "world-bad.yaml"), load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("公理" in m for m in by_check["axiom_declared"])
    assert any("コスト" in m for m in by_check["rule_has_cost"])
    assert any("条件" in m for m in by_check["exception_bounded"])
    assert any("雲の都" in m for m in by_check["geography_grounded"])
    assert any("ch09" in m for m in by_check["disclosure_ordered"])


def test_every_check_reports_its_acceptance_condition():
    report = check_world(load_world(DEMO / "world.yaml"), load_canon(CANON))
    assert len(report["checks"]) == 5
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_canon_is_optional():
    report = check_world(load_world(DEMO / "world.yaml"), None)
    skipped = {c["id"] for c in report["checks"] if c["status"] == "skipped"}
    assert skipped == {"geography_grounded"}


def test_rule_without_id_is_an_input_error(tmp_path):
    bad = tmp_path / "world.yaml"
    bad.write_text("rules:\n  - {statement: X, cost: Y}\n", encoding="utf-8")
    with pytest.raises(WorldError):
        load_world(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_world.py",
         "--world", str(DEMO / "world.yaml"), "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_world.py",
         "--world", str(DEMO / "world-bad.yaml"), "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
