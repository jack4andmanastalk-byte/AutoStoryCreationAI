"""Detection power: injecting a known error must move the log-dependent checks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import probe_detection_power  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-stageb-v11-t01"
ARGS = [
    "--game-log", str(BUNDLE / "inputs" / "game_log.json"),
    "--canon", str(BUNDLE / "inputs" / "canon"),
    "--design-dir", str(BUNDLE / "inputs" / "design"),
]


def run(tmp_path, *arms: str):
    out = tmp_path / "detection.json"
    completed = probe_detection_power.main(
        [*ARGS, *[part for arm in arms for part in ("--arm", arm)],
         "--out", str(out)])
    assert completed == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_a_known_error_is_detected_and_a_gap_is_recorded(tmp_path):
    arm = f"log-backed={BUNDLE / 'relay' / 'responses'}"
    report = run(tmp_path, arm, arm.replace("log-backed", "second"))
    assert report["schema"] == "detection-power-v1"
    assert report["ignored_checks"] == ["marker_sequence"]
    data = report["arms"]["log-backed"]
    # The v1.1 output is clean against its own log.
    assert {chapter: len(items) for chapter, items in data["baseline"].items()} == {
        "ch01": 0, "ch02": 0, "ch03": 0}
    mutations = data["mutations"]
    assert mutations["wrong_day_since"]["detected_by"] == ["timeline_consistency"]
    assert mutations["dead_acts_now"]["detected_by"] == ["character_boundary"]
    assert mutations["dead_acts_now"]["detected"][0]["severity"] == "high"
    assert mutations["withheld_term"]["detected_by"] == ["fact_boundary"]
    # These two are the documented gap: no check looks at place names or
    # numbers that the log never declared.
    assert mutations["offlog_place"]["detected_by"] == []
    assert mutations["unquantified_number"]["detected_by"] == []


def test_an_arm_without_responses_is_refused(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        run(tmp_path, f"a={empty}", f"b={BUNDLE / 'relay' / 'responses'}")
