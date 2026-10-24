from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.plot import PlotDocError, check_plot, load_plot  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "plot-demo"
CANON = REPO_ROOT / "harness" / "cases" / "demo" / "canon"


def test_good_plot_has_no_findings():
    report = check_plot(load_plot(DEMO / "plot.yaml"), load_canon(CANON))
    assert report["findings"] == []
    assert all(c["status"] == "pass" for c in report["checks"])


def test_bad_plot_fails_every_check():
    """EXPECTED.md の 5 検査が、すべて fail になること。"""
    report = check_plot(load_plot(DEMO / "plot-bad.yaml"), load_canon(CANON))
    failed = {c["id"] for c in report["checks"] if c["status"] == "fail"}
    assert failed == {"acts_cover", "turns_placed", "subplots_allocated",
                      "ending_designed", "debts_listed"}


def test_bad_plot_names_each_seeded_defect():
    report = check_plot(load_plot(DEMO / "plot-bad.yaml"), load_canon(CANON))
    by_check = {}
    for item in report["findings"]:
        by_check.setdefault(item["check"], []).append(item["message_ja"])
    assert any("ch99" in m for m in by_check["acts_cover"])
    assert any("1 件" in m for m in by_check["turns_placed"])
    assert any("節目" in m for m in by_check["subplots_allocated"])
    assert any("happy" in m for m in by_check["ending_designed"])
    assert any("fs-999" in m for m in by_check["debts_listed"])


def test_every_check_reports_its_acceptance_condition():
    report = check_plot(load_plot(DEMO / "plot.yaml"), load_canon(CANON))
    assert len(report["checks"]) == 5
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]


def test_intentional_debts_need_no_foreshadowing(tmp_path):
    doc = tmp_path / "plot.yaml"
    doc.write_text(
        "acts:\n  - {id: a, chapters: [ch01], question: Q}\n"
        "turns:\n"
        "  - {id: t1, chapter: ch01, choice_ja: 選ぶ}\n"
        "  - {id: t2, chapter: ch01, choice_ja: 選ぶ}\n"
        "  - {id: t3, chapter: ch01, choice_ja: 選ぶ}\n"
        "ending: {kind: open, summary: S, aftertaste_ja: A}\n"
        "unresolved:\n  - {item: X, intentional: true}\n", encoding="utf-8")
    report = check_plot(load_plot(doc), load_canon(CANON))
    assert [f for f in report["findings"]
            if f["check"] == "debts_listed"] == []


def test_overlapping_acts_are_reported(tmp_path):
    doc = tmp_path / "plot.yaml"
    doc.write_text(
        "acts:\n  - {id: a, chapters: [ch01], question: Q}\n"
        "  - {id: b, chapters: [ch01], question: Q}\n"
        "turns:\n"
        "  - {id: t1, chapter: ch01, choice_ja: 選ぶ}\n"
        "  - {id: t2, chapter: ch01, choice_ja: 選ぶ}\n"
        "  - {id: t3, chapter: ch01, choice_ja: 選ぶ}\n"
        "ending: {kind: open, summary: S, aftertaste_ja: A}\n",
        encoding="utf-8")
    report = check_plot(load_plot(doc), None)
    assert any("複数幕" in f["message_ja"] for f in report["findings"])


def test_ending_must_be_a_mapping(tmp_path):
    bad = tmp_path / "plot.yaml"
    bad.write_text("ending: なんか終わる\n", encoding="utf-8")
    with pytest.raises(PlotDocError):
        load_plot(bad)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_plot.py",
         "--plot", str(DEMO / "plot.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_plot.py",
         "--plot", str(DEMO / "plot-bad.yaml"),
         "--canon", str(CANON), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
