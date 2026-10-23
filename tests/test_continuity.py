from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.story.canon import CanonError, load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402
from asc.story.ledger import build_ledger  # noqa: E402
from asc.story.text import find_mentions, parse_markers  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "demo"
CANON = DEMO / "canon"
TEXT = DEMO / "text"


@pytest.fixture(scope="module")
def report():
    return audit_texts(CANON, TEXT)


def by_type(report, type_name):
    return [v for v in report["violations"] if v["type"] == type_name]


def test_demo_detects_every_seeded_defect(report):
    """EXPECTED.md に書いた 7 件が、その重要度で検出されること。"""
    detected = {(v["type"], v["severity"]) for v in report["violations"]}
    assert ("dead_character_reappears", "high") in detected
    assert ("knowledge_violation", "high") in detected
    assert ("knowledge_violation", "medium") in detected
    assert ("foreshadow_order", "high") in detected
    assert ("unresolved_foreshadow", "medium") in detected
    assert ("travel_time", "medium") in detected
    assert ("stated_age", "medium") in detected


def test_no_duplicate_violations_for_one_line(report):
    seen = [(v["type"], v["subject"], v["chapter"], v["evidence"].get("line"))
            for v in report["violations"]]
    assert len(seen) == len(set(seen))


def test_intentional_contradiction_is_suppressed_not_dropped(report):
    assert len(report["suppressed"]) == 1
    suppressed = report["suppressed"][0]
    assert suppressed["type"] == "dead_character_reappears"
    assert suppressed["subject"] == "boris"
    assert suppressed["chapter"] == "ch05"
    assert suppressed["reason"]
    assert not [v for v in report["violations"]
                if v["chapter"] == "ch05" and v["type"] == "dead_character_reappears"]


def test_every_check_reports_its_acceptance_condition(report):
    assert len(report["checks"]) == 6
    for check in report["checks"]:
        assert check["acceptance_ja"]
        assert check["technique_ids"]
        assert check["status"] in {"pass", "fail", "skipped"}


def test_violations_carry_evidence_and_techniques(report):
    for violation in report["violations"]:
        assert violation["message_ja"]
        assert violation["canon_ref"]
        assert violation["evidence_basis"] in {"marker", "name_mention", "timeline"}
        assert violation["technique_ids"]
    for violation in by_type(report, "dead_character_reappears"):
        assert violation["evidence"]["path"].startswith("ch")


def test_summary_is_length_normalised(report):
    summary = report["summary"]
    assert summary["chars"] > 0
    assert summary["violations"] == len(report["violations"])
    expected = round(summary["violations"] / summary["chars"] * 10_000, 3)
    assert summary["ced_per_10k_chars"] == expected


def test_missing_canon_is_skipped_not_failed(tmp_path):
    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "characters.yaml").write_text(
        "characters:\n  - id: aria\n    name: アリア\n", encoding="utf-8")
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("アリアは歩いた。\n", encoding="utf-8")
    result = audit_texts(canon, text)
    skipped = {c["id"] for c in result["checks"] if c["status"] == "skipped"}
    assert {"foreshadow_order", "travel_time", "unresolved_foreshadow"} <= skipped
    for check in result["checks"]:
        if check["status"] == "skipped":
            assert check["reason"].startswith("canon lacks")


def test_empty_canon_is_an_error(tmp_path):
    with pytest.raises(CanonError):
        load_canon(tmp_path / "does-not-exist")


def test_invalid_character_status_is_rejected(tmp_path):
    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "characters.yaml").write_text(
        "characters:\n  - id: aria\n    name: アリア\n    status: sleeping\n", encoding="utf-8")
    with pytest.raises(CanonError, match="unknown status"):
        load_canon(canon)


def test_markers_are_parsed_with_options():
    markers = parse_markers("本文。{{death: boris | 崩落}}\n{{state: aria location=王都}}", "ch01")
    assert [m.kind for m in markers] == ["death", "state"]
    assert markers[0].subject == "boris"
    assert markers[1].options() == {"location": "王都"}


def test_speaker_attribution_needs_the_same_clause():
    names = {"アリア": "aria", "ボリス": "boris"}
    line = "ボリスは扉の陰から現れ、「鍵を返せ」と言った。"
    mentions = find_mentions(line, "ch04", names)
    speaking = [m for m in mentions if m.quoted_line]
    assert [m.name for m in speaking] == ["ボリス"]

    # a full stop between the name and the quote means the speaker is ambiguous
    ambiguous = "夢の中で、ボリスはまだ笑っていた。「灯りを絶やすなよ」"
    mentions = find_mentions(ambiguous, "ch05", names)
    assert not [m for m in mentions if m.quoted_line]


def test_ledger_records_state_and_foreshadowing():
    canon = load_canon(CANON)
    from asc.story.text import load_chapters

    names = {n: c.id for c in canon.characters.values() for n in c.all_names}
    from asc.story.canon import load_chapters as index

    chapters = load_chapters([(c.id, c.path) for c in index(TEXT)], names)
    ledger = build_ledger(canon, chapters).as_dict(canon)
    boris = next(c for c in ledger["characters"] if c["id"] == "boris")
    assert boris["status"] == "dead"
    fs = {f["id"]: f for f in ledger["foreshadowing"]}
    assert fs["fs-001"]["setup_chapter"] == "ch01"
    assert fs["fs-001"]["payoff_chapter"] == "ch04"
    assert fs["fs-003"]["resolved"] is False


def test_cli_exit_codes(tmp_path):
    script = str(REPO_ROOT / "scripts" / "audit_continuity.py")
    high = subprocess.run([sys.executable, script, "--canon", str(CANON), "--text", str(TEXT),
                           "--out", str(tmp_path / "r.json"), "--quiet",
                           "--fail-on", "high"], capture_output=True, text=True)
    assert high.returncode == 1

    none = subprocess.run([sys.executable, script, "--canon", str(CANON), "--text", str(TEXT),
                           "--quiet", "--fail-on", "none"], capture_output=True, text=True)
    assert none.returncode == 0

    bad = subprocess.run([sys.executable, script, "--canon", str(tmp_path / "nope"),
                          "--text", str(TEXT), "--quiet"], capture_output=True, text=True)
    assert bad.returncode == 2

    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["summary"]["violations"] >= 7


def test_markdown_report_states_limits(report):
    from asc.story.continuity import render_markdown

    markdown = render_markdown(report)
    assert "# 継続性監査" in markdown
    assert "この監査で分からないこと" in markdown
    assert "誤り密度" in markdown
