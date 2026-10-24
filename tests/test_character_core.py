from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.character import (  # noqa: E402
    CharacterDocError, check_characters, load_characters,
)
from asc.story.canon import load_canon  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "character-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_characters_have_no_findings():
    report = check_characters(load_characters(DEMO / "characters.yaml"),
                              load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_characters_fail_every_check():
    """EXPECTED.md の 6 検査が、すべて fail になること。"""
    report = check_characters(load_characters(DEMO / "characters-bad.yaml"),
                              load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"core_declared", "views_separated", "choices_predicted",
                      "voice_fixed", "arc_decided", "canon_grounded"}


def test_bad_characters_name_each_seeded_defect():
    report = check_characters(load_characters(DEMO / "characters-bad.yaml"),
                              load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("同一文" in m for m in by_check["core_declared"])
    assert any("自己像" in m for m in by_check["views_separated"])
    assert any("1 件" in m for m in by_check["choices_predicted"])
    assert any("30 字" in m for m in by_check["voice_fixed"])
    assert any("終点" in m for m in by_check["arc_decided"])
    assert any("zorro" in m for m in by_check["canon_grounded"])


def test_every_check_reports_its_acceptance_condition():
    report = check_characters(load_characters(DEMO / "characters.yaml"),
                              load_canon(CANON))
    assert len(report["checks"]) == 6
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_canon_is_optional():
    report = check_characters(load_characters(DEMO / "characters.yaml"), None)
    skipped = {c["id"] for c in report["checks"] if c["status"] == "skipped"}
    assert skipped == {"canon_grounded"}


def test_character_without_id_is_an_input_error(tmp_path):
    bad = tmp_path / "characters.yaml"
    bad.write_text("characters:\n  - {want: X}\n", encoding="utf-8")
    with pytest.raises(CharacterDocError):
        load_characters(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_character.py",
         "--characters", str(DEMO / "characters.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_character.py",
         "--characters", str(DEMO / "characters-bad.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
