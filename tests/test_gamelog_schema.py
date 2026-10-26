"""Phase 1: the Stage A game-log schema and marker derivation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import (  # noqa: E402
    GameLogError, derive_markers, load_game_log, owner_markers, parse_game_log,
)
from asc.gamelog.markers import marker_kind, normalise_marker  # noqa: E402
from asc.story.text import MARKER_RE, parse_markers  # noqa: E402
import run_twostage  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
GAME_LOG = BUNDLE / "inputs" / "game_log.json"


@pytest.fixture()
def payload() -> dict:
    return json.loads(GAME_LOG.read_text(encoding="utf-8"))


def test_fixture_round_trips_through_the_canonical_form(payload):
    log = parse_game_log(payload, GAME_LOG)
    again = parse_game_log(log.as_dict(), GAME_LOG)
    assert again.as_dict() == log.as_dict()
    assert [chapter.id for chapter in log.chapters] == ["ch01", "ch02", "ch03"]
    assert log.chapter("ch02").day == 4
    assert log.chapter("nope") is None


def test_action_types_separate_dead_actors_from_dead_references():
    log = load_game_log(GAME_LOG)
    kinds = {(action.type, action.actor, action.subject, bool(action.medium))
             for chapter in log.chapters for scene in chapter.scenes
             for action in scene.actions}
    assert any(kind == "record_reference" and subject == "johan" and medium
               for kind, _, subject, medium in kinds)
    assert all(actor != "johan" for _, actor, _, _ in kinds)


def test_derive_markers_is_a_pure_function_of_state_delta(payload):
    log = parse_game_log(payload, GAME_LOG)
    markers = derive_markers(log)
    assert [marker.kind for marker in markers[:6]] == [
        "time", "location", "learn", "use", "foreshadow", "foreshadow"]
    assert markers[0].text == "{{time: day=1}}"
    assert markers[1].text == "{{location: 灯台}}"
    assert sum(marker.kind == "foreshadow" for marker in markers) == 6
    assert sum(marker.kind == "learn" for marker in markers) == 4
    assert len(markers) == 19
    # Changing a fact must change the derived sequence (no hidden state).
    payload["chapters"][0]["scenes"][0]["state_delta"]["learned_facts"] = []
    changed = derive_markers(parse_game_log(payload, GAME_LOG))
    assert len(changed) == len(markers) - 1
    assert changed[2].kind == "use"


@pytest.mark.parametrize("marker", [
    "{{time: day=1}}", "{{location: 灯台}}", "{{learn: aria fact=F-05}}",
    "{{use: boris fact=F-02}}", "{{foreshadow: fs-001 setup}}",
])
def test_derived_markers_use_the_existing_continuity_grammar(marker):
    assert MARKER_RE.fullmatch(marker)
    parsed = parse_markers(marker, "ch01")
    assert len(parsed) == 1
    assert parsed[0].raw == marker
    assert marker_kind(marker) == parsed[0].kind


def test_normalise_marker_tolerates_whitespace_only():
    assert normalise_marker("  {{learn:  aria   fact=F-05}} ") == \
        "{{learn: aria fact=F-05}}"
    assert marker_kind("not a marker") is None


def test_declared_emitted_markers_equal_the_derived_sequence():
    log = load_game_log(GAME_LOG)
    for chapter in log.chapters:
        assert chapter.emitted_markers == owner_markers(
            log, "chapter", chapter.id, chapter.id)
        for scene in chapter.scenes:
            assert scene.emitted_markers == owner_markers(
                log, "scene", scene.id, chapter.id)


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d["chapters"][0]["scenes"][0]["actions"][0].update(
        {"type": "narration"}), "is not one of"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"][
        "foreshadow_events"][0].update({"event": "plant"}), "is not one of"),
    (lambda d: d.pop("schema_version"), "must be a string"),
    (lambda d: d.update({"schema_version": "2.0"}), "expected '1.0'"),
    (lambda d: d["chapters"].clear(), "at least one chapter"),
    (lambda d: d["chapters"][0].update({"day": "one"}), "must be a number"),
    (lambda d: d["chapters"][0]["scenes"][0].update(
        {"present_characters": "aria"}), "must be a list"),
    (lambda d: d["chapters"][0]["scenes"][0]["state_delta"][
        "location_moves"][0].update({"arrival_day": None}), "must be a number"),
])
def test_malformed_logs_raise_a_precise_error(payload, mutate, message):
    mutate(payload)
    with pytest.raises(GameLogError, match=message):
        parse_game_log(payload, GAME_LOG)


def test_script_bundle_resolves_file_references_without_duplication(tmp_path):
    responses = run_twostage.load_script_bundle(BUNDLE / "scripted.json")
    assert set(responses) == {
        "stage_a:t01", "stage_b:ch01:t01", "stage_b:ch02:t01", "stage_b:ch03:t01"}
    assert json.loads(responses["stage_a:t01"])["schema_version"] == "1.0"
    assert "{{time: day=1}}" in responses["stage_b:ch01:t01"]
    # Inline strings are accepted too (used by repair-loop tests).
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps({"responses": {
        "stage_a:t01": "{}", "stage_b:ch01:t01": "{{time: day=1}}"}},
        ensure_ascii=False), encoding="utf-8")
    assert run_twostage.load_script_bundle(plain) == {
        "stage_a:t01": "{}", "stage_b:ch01:t01": "{{time: day=1}}"}
