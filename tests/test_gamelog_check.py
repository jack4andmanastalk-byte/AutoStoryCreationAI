"""Phase 1: deterministic game-log checks against canon / plot / scenes."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog import check_game_log, load_game_log, parse_game_log  # noqa: E402
from asc.plot.schema import load_plot  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
INPUTS = BUNDLE / "inputs"
GAME_LOG = INPUTS / "game_log.json"


@pytest.fixture(scope="module")
def context():
    return {
        "canon": load_canon(INPUTS / "canon"),
        "plot": load_plot(INPUTS / "design" / "plot.json"),
        "scenes": load_scenes(INPUTS / "design" / "scene.json"),
        "voice": load_voice(INPUTS / "design" / "voice.json"),
        "raw": json.loads(GAME_LOG.read_text(encoding="utf-8")),
    }


def check(context, mutate=None):
    payload = copy.deepcopy(context["raw"])
    if mutate:
        mutate(payload)
    log = parse_game_log(payload, GAME_LOG)
    return check_game_log(log, context["canon"], context["plot"], context["scenes"])


def find_ids(report, check_id, severity=None):
    return [item for item in report["findings"]
            if item["check"] == check_id
            and (severity is None or item["severity"] == severity)]


def test_fixture_log_is_clean_and_lists_allowed_dead_references(context):
    report = check(context)
    assert report["summary"]["status"] == "clean"
    assert report["summary"]["findings"] == 0
    assert report["summary"]["checks_run"] == 8
    assert report["summary"]["checks_skipped"] == 0
    assert all(item["status"] == "pass" for item in report["checks"])
    assert report["summary"]["markers"] == 19
    assert report["marker_counts"] == {"time": 3, "location": 3, "learn": 4,
                                       "use": 3, "foreshadow": 6}
    refs = report["allowed_dead_references"]
    assert len(refs) == 4
    assert {item["medium"] for item in refs} == {"潮札", "石膏手形", "回想"}
    assert all(item["subject"] == "johan" for item in refs)
    assert all(item["actor"] == "aria" for item in refs)
    assert report["state"]["knows_at_end"]["aria"] == [
        "F-01", "F-02", "F-03", "F-04", "F-05"]
    assert report["state"]["foreshadow_state"]["fs-001"] == {
        "setup": "ch01", "payoff": "ch03"}


def test_archived_design_reports_match_the_current_checkers(context):
    from asc.plot.check import check_plot
    from asc.scene.check import check_scenes

    design = INPUTS / "design"
    for name, report in (("plot", check_plot(context["plot"], context["canon"])),
                         ("scene", check_scenes(context["scenes"], context["canon"]))):
        archived = json.loads((design / f"{name}.report.json").read_text(
            encoding="utf-8"))
        assert archived["status"] == "clean"
        assert archived["checks_failed"] == 0
        assert archived["findings"] == report["findings"]
        assert [item["id"] for item in archived["checks"]] == \
            [item["id"] for item in report["checks"]]


def test_absent_design_documents_skip_only_the_alignment_check(context):
    log = parse_game_log(context["raw"], GAME_LOG)
    report = check_game_log(log, context["canon"])
    skipped = [item["id"] for item in report["checks"] if item["status"] == "skipped"]
    assert skipped == ["design_alignment"]
    assert report["summary"]["status"] == "clean"


@pytest.mark.parametrize("mutate,expected", [
    (lambda d: d["chapters"][0]["scenes"][0]["present_characters"].append("johan"),
     "presence_death"),
    (lambda d: d["chapters"][0]["scenes"][0]["actions"][0].update(
        {"actor": "johan"}), "presence_death"),
    (lambda d: d["chapters"][0]["scenes"][0]["actions"][0].update(
        {"target": "johan"}), "presence_death"),
    (lambda d: d["chapters"][0]["scenes"][0]["actions"][1].pop("medium"),
     "presence_death"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"]["learned_facts"].append(
        {"character": "aria", "fact": "F-03"}), "design_alignment"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"]["learned_facts"].append(
        {"character": "aria", "fact": "F-04"}), "knowledge_boundary"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"]["used_facts"].append(
        {"character": "aria", "fact": "F-04"}), "knowledge_boundary"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"][
        "foreshadow_events"][0].update({"event": "payoff"}), "foreshadow_order"),
    (lambda d: d["chapters"][1].update({"day": 2}), "timeline_travel"),
    (lambda d: d["chapters"][1]["scenes"][0]["emitted_markers"].pop(0),
     "emitted_markers"),
    (lambda d: d["chapters"][0]["scenes"][0].update({"scene_ref": "s999"}),
     "design_alignment"),
    (lambda d: d["chapters"][0]["scenes"][0]["actions"][0].update(
        {"actor": "ghost"}), "canon_refs"),
    (lambda d: d["chapters"][0]["scenes"][0].update({"tension": "exciting"}),
     "schema_shape"),
])
def test_each_violation_is_a_high_or_medium_finding(context, mutate, expected):
    report = check(context, mutate)
    hits = find_ids(report, expected)
    assert hits, f"expected {expected}: {report['summary']['by_check']}"
    assert any(item["severity"] in {"high", "medium"} for item in hits)
    assert report["summary"]["status"] == "unresolved"


def test_dead_present_is_forbidden_but_declared_reference_is_allowed(context):
    def add_reference(d):
        scene = d["chapters"][0]["scenes"][0]
        scene["actions"].append({
            "id": "a4", "type": "memory_mention", "actor": "aria",
            "subject": "johan", "medium": "回想", "summary": "兄を思い出す。"})
    report = check(context, add_reference)
    assert not find_ids(report, "presence_death")
    assert len(report["allowed_dead_references"]) == 5

    def dead_on_stage(d):
        add_reference(d)
        d["chapters"][0]["scenes"][0]["present_characters"].append("johan")
    blocked = check(context, dead_on_stage)
    assert any("present_characters" in item["message_ja"]
               for item in find_ids(blocked, "presence_death", "high"))


def test_travel_days_are_checked_for_moves_and_between_chapters(context):
    def short_move(d):
        d["chapters"][0]["scenes"][0]["state_delta"]["location_moves"][0].update(
            {"arrival_day": 2})
    hits = find_ids(check(context, short_move), "timeline_travel", "high")
    assert any("3 日必要" in item["message_ja"] for item in hits)


def test_emitted_markers_cannot_be_invented_or_reordered(context):
    def swapped(d):
        markers = d["chapters"][0]["scenes"][0]["emitted_markers"]
        markers[0], markers[1] = markers[1], markers[0]
    report = check(context, swapped)
    hits = find_ids(report, "emitted_markers", "high")
    assert hits and hits[0]["evidence"]["missing"] == []
    assert "順序" in hits[0]["message_ja"]


def test_check_cli_accepts_the_fixture_and_rejects_a_broken_copy(context, tmp_path):
    script = REPO_ROOT / "scripts" / "check_gamelog.py"
    base = ["--game-log", str(GAME_LOG), "--canon", str(INPUTS / "canon"),
            "--design-dir", str(INPUTS / "design"), "--require-design",
            "--fail-on", "high", "--quiet"]
    good = subprocess.run([sys.executable, str(script), *base],
                          cwd=REPO_ROOT, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    broken = copy.deepcopy(context["raw"])
    broken["chapters"][0]["scenes"][0]["present_characters"].append("johan")
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    bad = subprocess.run([sys.executable, str(script),
                          *["--game-log", str(path), "--canon", str(INPUTS / "canon"),
                            "--design-dir", str(INPUTS / "design"),
                            "--fail-on", "high", "--quiet"]],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
