from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.branch import (  # noqa: E402
    BranchDocError, check_branches, load_branches,
)

DEMO = REPO_ROOT / "harness" / "cases" / "branch-demo"


def test_good_branches_have_no_findings():
    report = check_branches(load_branches(DEMO / "branches.yaml"))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_branches_fail_every_check():
    """EXPECTED.md の 7 検査が、すべて fail になること。"""
    report = check_branches(load_branches(DEMO / "branches-bad.yaml"))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"graph_grounded", "paths_reachable",
                      "endings_terminated", "flags_declared",
                      "conditions_sound", "options_meaningful",
                      "merges_noted"}


def test_bad_branches_name_each_seeded_defect():
    report = check_branches(load_branches(DEMO / "branches-bad.yaml"))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("missing_option" in m for m in by_check["graph_grounded"])
    assert any("n_orphan" in m for m in by_check["paths_reachable"])
    assert any("n_trap" in m for m in by_check["paths_reachable"])
    assert any("n_dead" in m for m in by_check["endings_terminated"])
    assert any("ghost_flag" in m for m in by_check["flags_declared"])
    assert any("never_set" in m for m in by_check["conditions_sound"])
    assert any("1 件" in m for m in by_check["options_meaningful"])
    assert any("n_merge" in m for m in by_check["merges_noted"])


def test_every_check_reports_its_acceptance_condition():
    report = check_branches(load_branches(DEMO / "branches.yaml"))
    assert len(report["checks"]) == 7
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_cycles_are_allowed_but_traps_are_not(tmp_path):
    """循環は許す。結末に届かない循環（罠）だけ落とす。"""
    doc = tmp_path / "branches.yaml"
    doc.write_text(
        "start: a\nnodes:\n"
        "  - {id: a, kind: scene, summary: A}\n"
        "  - {id: b, kind: scene, summary: B}\n"
        "  - {id: e, kind: ending, summary: E, ending: 終}\n"
        "edges:\n"
        "  - {from: a, to: b}\n"
        "  - {from: b, to: a}\n"
        "  - {from: b, to: e}\n", encoding="utf-8")
    report = check_branches(load_branches(doc))
    assert [f for f in report["findings"]
            if f["check"] == "paths_reachable"] == []


def test_conditional_edges_are_traversed_in_some_state(tmp_path):
    """条件付きの辺は、成立する状態があれば通す。"""
    doc = tmp_path / "branches.yaml"
    doc.write_text(
        "start: a\nflags:\n  - {id: k, meaning: 鍵}\n"
        "nodes:\n"
        "  - {id: a, kind: scene, summary: A}\n"
        "  - {id: b, kind: scene, summary: B}\n"
        "  - {id: e, kind: ending, summary: E, ending: 終}\n"
        "edges:\n"
        "  - {from: a, to: b, sets: [k]}\n"
        "  - {from: b, to: e, requires: [k]}\n", encoding="utf-8")
    report = check_branches(load_branches(doc))
    assert report["findings"] == []


def test_node_without_id_is_an_input_error(tmp_path):
    bad = tmp_path / "branches.yaml"
    bad.write_text("nodes:\n  - {kind: scene}\n", encoding="utf-8")
    with pytest.raises(BranchDocError):
        load_branches(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_branch.py",
         "--branches", str(DEMO / "branches.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_branch.py",
         "--branches", str(DEMO / "branches-bad.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
