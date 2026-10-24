from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.scene import SceneDocError, check_scenes, load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "scene-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_scenes_have_no_findings():
    report = check_scenes(load_scenes(DEMO / "scenes.yaml"),
                          load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_scenes_fail_every_check():
    """EXPECTED.md の 6 検査が、すべて fail になること。"""
    report = check_scenes(load_scenes(DEMO / "scenes-bad.yaml"),
                          load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"scene_purposed", "tension_designed",
                      "knowledge_tracked", "disclosure_planned",
                      "foreshadow_tagged", "scenes_cover"}


def test_bad_scenes_name_each_seeded_defect():
    report = check_scenes(load_scenes(DEMO / "scenes-bad.yaml"),
                          load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("目的" in m for m in by_check["scene_purposed"])
    assert any("exciting" in m for m in by_check["tension_designed"])
    assert any("zorro" in m for m in by_check["knowledge_tracked"])
    assert any("両方" in m for m in by_check["disclosure_planned"])
    assert any("fs-999" in m for m in by_check["foreshadow_tagged"])
    assert any("ch99" in m for m in by_check["scenes_cover"])


def test_every_check_reports_its_acceptance_condition():
    report = check_scenes(load_scenes(DEMO / "scenes.yaml"),
                          load_canon(CANON))
    assert len(report["checks"]) == 6
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_gained_facts_must_appear_in_the_disclosure_plan(tmp_path):
    doc = tmp_path / "scenes.yaml"
    doc.write_text(
        "scenes:\n  - id: s1\n    chapter: ch01\n    purpose: P\n"
        "    conflict: C\n    change: X\n    tension: quiet\n"
        "    knowledge:\n      - {character: aria, entry: [],"
        " gained: [F-07]}\n"
        "    disclosure: {disclosed: [], withheld: []}\n", encoding="utf-8")
    report = check_scenes(load_scenes(doc), load_canon(CANON))
    assert any("開示計画" in f["message_ja"] for f in report["findings"])


def test_payoff_before_planting_is_reported(tmp_path):
    doc = tmp_path / "scenes.yaml"
    doc.write_text(
        "scenes:\n  - id: s1\n    chapter: ch03\n    purpose: P\n"
        "    conflict: C\n    change: X\n    tension: quiet\n"
        "    foreshadows:\n      planted:\n"
        "        - {id: fs-new, payoff: ch01}\n", encoding="utf-8")
    report = check_scenes(load_scenes(doc), load_canon(CANON))
    assert any("より前" in f["message_ja"] for f in report["findings"])


def test_canon_is_optional():
    report = check_scenes(load_scenes(DEMO / "scenes.yaml"), None)
    skipped = {c["id"] for c in report["checks"] if c["status"] == "skipped"}
    assert skipped == {"scenes_cover"}


def test_scene_without_id_is_an_input_error(tmp_path):
    bad = tmp_path / "scenes.yaml"
    bad.write_text("scenes:\n  - {chapter: ch01}\n", encoding="utf-8")
    with pytest.raises(SceneDocError):
        load_scenes(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_scene.py",
         "--scenes", str(DEMO / "scenes.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_scene.py",
         "--scenes", str(DEMO / "scenes-bad.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
