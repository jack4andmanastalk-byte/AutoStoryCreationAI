from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.brief import BriefError, check_brief, load_brief  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "brief-demo"


def test_good_brief_has_no_findings():
    report = check_brief(load_brief(DEMO / "brief.yaml"))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_brief_fails_every_check():
    """EXPECTED.md の 6 検査が、すべて fail になること。"""
    report = check_brief(load_brief(DEMO / "brief-bad.yaml"))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"logline_form", "logline_elements", "theme_contrast",
                      "similar_grounded", "prohibition_testable", "question_form"}


def test_bad_brief_names_each_seeded_defect():
    report = check_brief(load_brief(DEMO / "brief-bad.yaml"))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("4 文" in m for m in by_check["logline_form"])
    assert any("where" in m for m in by_check["logline_elements"])
    assert any("対立" in m for m in by_check["theme_contrast"])
    assert any("1 件" in m for m in by_check["similar_grounded"])
    assert any("check_ja" in m for m in by_check["prohibition_testable"])
    assert any("問い" in m for m in by_check["question_form"])


def test_every_check_reports_its_acceptance_condition():
    report = check_brief(load_brief(DEMO / "brief.yaml"))
    assert len(report["checks"]) == 6
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_missing_required_field_is_an_input_error(tmp_path):
    bad = tmp_path / "brief.yaml"
    bad.write_text("logline: ある話。\n", encoding="utf-8")
    with pytest.raises(BriefError):
        load_brief(bad)


def test_missing_file_is_an_input_error(tmp_path):
    with pytest.raises(BriefError):
        load_brief(tmp_path / "does-not-exist.yaml")


def test_undecided_elements_are_allowed(tmp_path):
    good = tmp_path / "brief.yaml"
    good.write_text(
        "logline: 嵐の夜、灯台守の娘が鍵の行方を追い、灯りを守る務めと向き合う。\n"
        "elements: {who: 灯台守の娘, where: 嵐の夜, wants: 未定, obstacle: 未定}\n"
        "premise: 娘が鍵を追う。\n"
        "theme: 務め対好奇心\n"
        "similar:\n"
        "  - {title: A, axis: structure, difference: 十分に長い差分の説明文。}\n"
        "  - {title: B, axis: character, difference: 十分に長い差分の説明文。}\n"
        "  - {title: C, axis: world, difference: 十分に長い差分の説明文。}\n"
        "prohibitions:\n"
        "  - {rule: Xをしない, check_ja: 本文にXが出たら違反とする。}\n"
        "failure_questions: [鍵は見つかるか？]\n",
        encoding="utf-8")
    report = check_brief(load_brief(good))
    elements = [c for c in report["checks"] if c["id"] == "logline_elements"][0]
    assert elements["status"] == "pass"


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_brief.py",
         "--brief", str(DEMO / "brief.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_brief.py",
         "--brief", str(DEMO / "brief-bad.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
    missing = subprocess.run(
        [sys.executable, "scripts/check_brief.py",
         "--brief", str(DEMO / "nope.yaml"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert missing.returncode == 2
