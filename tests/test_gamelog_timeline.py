"""Deterministic time authority: the travel graph, the derived timeline, and
the prose-side consistency check.

The split is the point of these tests:

* the **log side** owns the numbers (``derive_timeline``), strictly;
* the **prose side** may stay abstract. Only a number that is actually written
  is compared, and a mismatch is a warning unless the run asks otherwise.

The prose cases use the committed full-pipeline trial
(``experiments/2026-10-full-t01``): a real Stage A log and a real chapter that
says 「六日ぶり」 for a six-day absence.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog import check_rewrite, load_game_log, parse_game_log  # noqa: E402
from asc.gamelog.rewrite import _day_number, timeline_findings  # noqa: E402
from asc.gamelog.world import (TIMELINE_SCHEMA, World, build_world,  # noqa: E402
                               chapter_timeline, derive_timeline,
                               render_chapter_timeline)
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402

SLICE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
GAME_LOG = SLICE / "inputs" / "game_log.json"

FULL = REPO_ROOT / "experiments" / "2026-10-full-t01"
FULL_INPUTS = FULL / "inputs"
#: The Stage A response body, which is the game log JSON as text.
FULL_LOG_JSON = json.loads(json.loads(
    (FULL / "relay" / "responses" / "two-stage-t01-s0-stage_a-a1.json")
    .read_text(encoding="utf-8"))["text"])
# The r2 run is the one where 「四日ぶり」 was corrected to 「六日ぶり」.
FULL_CH03 = json.loads(
    (FULL / "relay-r2" / "responses" / "two-stage-t01-s3-stage_b-ch03-a1.json")
    .read_text(encoding="utf-8"))["text"]


@pytest.fixture(scope="module")
def canon():
    return load_canon(SLICE / "inputs" / "canon")


@pytest.fixture(scope="module")
def log():
    return load_game_log(GAME_LOG)


@pytest.fixture(scope="module")
def timeline(log, canon):
    return derive_timeline(log, canon)


@pytest.fixture(scope="module")
def full():
    """The real trial: canon, parsed log, design documents, derived timeline."""
    canon = load_canon(FULL_INPUTS / "canon")
    log = parse_game_log(FULL_LOG_JSON, Path("full-t01-stage-a.json"))
    return {
        "canon": canon, "log": log,
        "voice": load_voice(FULL_INPUTS / "design" / "voice.json"),
        "scenes": load_scenes(FULL_INPUTS / "design" / "scene.json"),
        "timeline": derive_timeline(log, canon),
    }


def rewrite(full, text: str, *, strict: bool = False) -> dict:
    return check_rewrite(text, "ch03", full["log"], full["canon"],
                         full["voice"], full["scenes"],
                         timeline=full["timeline"], strict_timeline=strict)


def timeline_only(report: dict) -> list[dict]:
    return [item for item in report["findings"]
            if item["check"] == "timeline_consistency"]


# -- the graph ---------------------------------------------------------------
def test_world_reads_the_adjacency_it_is_given():
    world = World(edges={"灯台": {"王都": 3.0}, "王都": {"港": 2.0}})
    assert world.travel_days("灯台", "王都") == 3.0
    # An edge written one way is one way in a hand-built World ...
    assert world.travel_days("王都", "灯台") is None
    assert world.travel_days("灯台", "灯台") == 0.0
    assert world.places() == sorted(["港", "王都", "灯台"])


def test_build_world_mirrors_the_pair_table_and_keeps_the_smaller_value(canon):
    mirrored = build_world(canon)
    assert mirrored.travel_days("港", "灯台") == mirrored.travel_days("灯台", "港")
    assert mirrored.travel_days("王都", "灯台") == 3.0

    # canon 灯台->王都 3, but a contradictory 王都->灯台 5 must not win.
    locations = dict(canon.locations)
    locations["王都"] = dataclasses.replace(
        locations["王都"], travel_days={"灯台": 5, "港": 2})
    world = build_world(dataclasses.replace(canon, locations=locations))
    assert world.travel_days("灯台", "王都") == 3.0
    assert world.travel_days("王都", "灯台") == 3.0


def test_shortest_path_can_pass_through_a_place_that_was_not_listed():
    world = World(edges={"灯台": {"港": 1.0}, "港": {"灯台": 1.0, "王都": 2.0},
                         "王都": {"港": 2.0}})
    # 灯台 -> 王都 is not a listed pair, but it is three days away.
    assert world.travel_days("灯台", "王都") == 3.0


def test_unreachable_and_unknown_places_have_no_duration():
    world = World(edges={"灯台": {"港": 1.0}, "港": {"灯台": 1.0},
                         "内陸": {"内陸": 0.0}})
    assert world.travel_days("灯台", "内陸") is None
    assert world.travel_days("灯台", "どこか") is None
    assert world.travel_days(None, "港") is None
    assert world.reachable("灯台", "内陸") is False


# -- the timeline ------------------------------------------------------------
def test_derive_timeline_folds_the_real_log(timeline):
    assert timeline["schema"] == TIMELINE_SCHEMA
    assert timeline["mode"] == "deterministic"
    rows = timeline["chapters"]
    assert [(row["id"], row["day"], row["location"]) for row in rows] == [
        ("ch01", 1.0, "灯台"), ("ch02", 4.0, "王都"), ("ch03", 7.0, "灯台")]
    assert [row["elapsed_since_previous"] for row in rows] == [None, 3.0, 3.0]
    assert [row["days_until_next"] for row in rows] == [3.0, 3.0, None]


def test_derive_timeline_counts_days_since_leaving_a_place(timeline):
    aria = chapter_timeline(timeline, "ch03")["characters"][0]
    assert aria["id"] == "aria"
    # Left 灯台 on day 1, came back on day 7.
    assert aria["days_since_leaving_here"] == 6.0
    assert aria["days_since_arriving_here"] == 0.0


def test_derive_timeline_records_each_move_with_its_required_duration(timeline):
    outward = chapter_timeline(timeline, "ch01")["moves"][0]
    assert (outward["origin"], outward["destination"]) == ("灯台", "王都")
    assert (outward["depart_day"], outward["arrival_day"]) == (1.0, 4.0)
    assert outward["days"] == outward["required_days"] == 3.0
    homeward = chapter_timeline(timeline, "ch02")["moves"][0]
    assert (homeward["origin"], homeward["destination"]) == ("王都", "灯台")
    assert homeward["days"] == homeward["required_days"] == 3.0


def test_derive_timeline_is_a_pure_function_of_log_and_canon(log, canon):
    first = derive_timeline(log, canon)
    second = derive_timeline(log, canon)
    assert (json.dumps(first, ensure_ascii=False, sort_keys=True)
            == json.dumps(second, ensure_ascii=False, sort_keys=True))


def test_unknown_topology_stays_unknown_instead_of_guessed(canon):
    payload = json.loads(GAME_LOG.read_text(encoding="utf-8"))
    move = payload["chapters"][0]["scenes"][0]["state_delta"]["location_moves"][0]
    move["destination"] = "霧の岬"
    broken = parse_game_log(payload, GAME_LOG)
    derived = derive_timeline(broken, canon)
    assert chapter_timeline(derived, "ch01")["moves"][0]["required_days"] is None


def test_render_chapter_timeline_hands_over_settled_numbers(timeline, canon):
    rendered = render_chapter_timeline(timeline, "ch03", canon)
    assert "この章の日: 7日目" in rendered
    assert "場所: 灯台" in rendered
    assert "前章からの経過: 3日" in rendered
    assert "この場所を離れてから 6日" in rendered
    # Nothing is derived for a chapter the timeline does not know.
    assert render_chapter_timeline(timeline, "ch99", canon) == "（この章の時系列は未導出）"


@pytest.mark.parametrize("raw, expected", [
    ("六", 6), ("四", 4), ("十二", 12), ("二十", 20), ("三", 3),
    ("7", 7), ("１２", 12),
])
def test_day_number_reads_japanese_and_arabic_numerals(raw, expected):
    assert _day_number(raw) == expected


def test_day_number_returns_none_when_there_is_no_number():
    assert _day_number("しばらく") is None


# -- the prose side ----------------------------------------------------------
def test_rewrite_without_a_timeline_skips_the_check(full):
    report = check_rewrite(FULL_CH03, "ch03", full["log"], full["canon"],
                           full["voice"], full["scenes"])
    check = next(item for item in report["checks"]
                 if item["id"] == "timeline_consistency")
    assert check["status"] == "skipped"
    assert report["summary"]["timeline"]["checked"] == 0


def test_the_real_chapter_passes_against_the_derived_timeline(full):
    report = rewrite(full, FULL_CH03)
    assert "六日ぶり" in FULL_CH03
    assert report["summary"]["timeline"]["checked"] >= 1
    assert timeline_only(report) == []
    assert report["summary"]["status"] == "clean"


def test_injected_wrong_day_count_is_reported_but_does_not_block(full):
    broken = FULL_CH03.replace("六日ぶり", "四日ぶり")
    report = rewrite(full, broken)
    findings = timeline_only(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding["severity"] == "medium"
    assert finding["blocks_repair"] is False
    assert "四日ぶり" in finding["message_ja"]
    assert finding["evidence"]["value"] == 4
    assert finding["evidence"]["allowed"] == [6]
    # A warning is not a repair trigger, so the chapter stays clean.
    assert report["summary"]["blocking_findings"] == 0
    assert report["summary"]["warning_findings"] == 1
    assert report["summary"]["status"] == "clean"


def test_strict_timeline_turns_the_same_mismatch_into_a_repair(full):
    broken = FULL_CH03.replace("六日ぶり", "四日ぶり")
    report = rewrite(full, broken, strict=True)
    assert report["summary"]["timeline"]["strict"] is True
    assert report["summary"]["blocking_findings"] == 1
    assert report["summary"]["status"] == "unresolved"


def test_abstract_time_words_are_counted_as_skipped_not_failed(full):
    vague = FULL_CH03.replace("六日ぶり", "しばらく")
    report = rewrite(full, vague, strict=True)
    assert timeline_only(report) == []
    assert report["summary"]["timeline"]["skipped"] >= 1


def test_prose_without_any_day_wording_is_never_a_failure(full):
    plain = "灯台は静かだった。潮の音だけがしていた。"
    findings, checked, skipped = timeline_findings(
        plain, "ch03", full["timeline"])
    assert findings == [] and checked == 0 and skipped == 0
    # ... and it is not a blocking rewrite either.
    report = rewrite(full, plain, strict=True)
    assert timeline_only(report) == []


def test_a_chapter_missing_from_the_timeline_is_skipped_not_guessed(full):
    findings, checked, skipped = timeline_findings(
        "あれから六日ぶりだ。", "ch99", full["timeline"])
    assert findings == [] and checked == 0 and skipped == 0
