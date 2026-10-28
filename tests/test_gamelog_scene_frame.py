"""Schema 1.1 scene frame (phase, outcome_kind, rescue, carry_forward).

The frozen 1.0 bundle is never edited: the 1.1 payload is derived from it here.
These tests check the deterministic contract only, not whether the story is good.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import check_game_log  # noqa: E402
from asc.gamelog.schema import GameLogError, parse_game_log  # noqa: E402
from asc.plot.schema import load_plot  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
import run_twostage  # noqa: E402
from test_twostage_pipeline import (  # noqa: E402
    INPUTS, SCRIPT, base_responses, read_json, run_cli, write_script)

BUNDLE_LOG = INPUTS / "game_log.json"
FRAME = {
    "ch01": {"phase": "opening", "outcome_kind": "success", "rescue": "",
             "carry_forward": ["灯台の鍵の在り処を知った"]},
    "ch02": {"phase": "development", "outcome_kind": "fail_forward",
             "rescue": "同じ情報を記録の写しから得て、次の行き先が決まる",
             "carry_forward": ["王都へ向かう理由が生まれた"]},
    "ch03": {"phase": "ending", "outcome_kind": "partial", "rescue": "",
             "carry_forward": []},
}


def v11_payload() -> dict:
    payload = copy.deepcopy(json.loads(BUNDLE_LOG.read_text(encoding="utf-8")))
    payload["schema_version"] = "1.1"
    for chapter in payload["chapters"]:
        for scene in chapter["scenes"]:
            scene.update(copy.deepcopy(FRAME[chapter["id"]]))
    return payload


@pytest.fixture(scope="module")
def canon():
    return load_canon(INPUTS / "canon")


@pytest.fixture(scope="module")
def designs():
    return load_plot(INPUTS / "design" / "plot.json"), load_scenes(
        INPUTS / "design" / "scene.json")


def check(payload: dict, canon, designs) -> dict:
    log = parse_game_log(payload, "game_log.json")
    plot, scenes = designs
    return check_game_log(log, canon, plot, scenes)


def frame_checks(report: dict) -> dict:
    return next(item for item in report["checks"] if item["id"] == "scene_frame")


def test_v11_log_round_trips_the_frame_and_1_0_output_is_unchanged():
    log = parse_game_log(v11_payload(), "game_log.json")
    assert log.schema_version == "1.1"
    scene = log.chapters[1].scenes[0]
    assert scene.phase == "development" and scene.outcome_kind == "fail_forward"
    assert scene.carry_forward == ("王都へ向かう理由が生まれた",)
    assert log.as_dict()["chapters"][1]["scenes"][0]["rescue"].startswith("同じ情報")

    legacy = parse_game_log(json.loads(BUNDLE_LOG.read_text(encoding="utf-8")), "g.json")
    dumped = legacy.as_dict()["chapters"][0]["scenes"][0]
    assert not {"phase", "outcome_kind", "carry_forward", "rescue"} & set(dumped)


def test_v11_clean_log_passes_the_new_check(canon, designs):
    report = check(v11_payload(), canon, designs)
    assert report["summary"]["status"] == "clean", report["findings"]
    assert frame_checks(report)["status"] == "pass"
    assert report["summary"]["checks_run"] == 9
    assert report["summary"]["checks_skipped"] == 0


def test_v10_log_does_not_list_the_new_check(canon, designs):
    # Frozen 1.0 reports must stay byte-identical, so the check is simply absent.
    report = check(json.loads(BUNDLE_LOG.read_text(encoding="utf-8")), canon, designs)
    assert not [item for item in report["checks"] if item["id"] == "scene_frame"]
    assert report["summary"]["status"] == "clean"
    assert report["summary"]["checks_run"] == 8


def _mutate(mutation):
    payload = v11_payload()
    mutation(payload)
    return payload


CASES = [
    ("invalid phase",
     lambda p: p["chapters"][0]["scenes"][0].update(phase="intro"), "high", "フェイズ"),
    ("empty phase",
     lambda p: p["chapters"][1]["scenes"][0].update(phase=""), "high", "フェイズ"),
    ("phase goes backwards",
     lambda p: (p["chapters"][1]["scenes"][0].update(phase="climax"),
                p["chapters"][2]["scenes"][0].update(phase="development")), "high",
     "戻っている"),
    ("invalid outcome kind",
     lambda p: p["chapters"][0]["scenes"][0].update(outcome_kind="win"), "high", "結果の種別"),
    ("fail_forward without a rescue",
     lambda p: p["chapters"][1]["scenes"][0].update(rescue=""), "high", "rescue"),
    ("too many carry-forward notes",
     lambda p: p["chapters"][0]["scenes"][0].update(carry_forward=["a", "b", "c", "d"]),
     "medium", "上限"),
    ("missing carry-forward before the last scene",
     lambda p: p["chapters"][0]["scenes"][0].update(carry_forward=[]), "medium",
     "carry_forward"),
    ("first scene is not opening",
     lambda p: p["chapters"][0]["scenes"][0].update(phase="development"), "medium",
     "opening"),
    ("last scene is not ending",
     lambda p: p["chapters"][2]["scenes"][0].update(phase="climax"), "medium", "ending"),
]


@pytest.mark.parametrize("label,mutation,severity,message", CASES,
                         ids=[case[0] for case in CASES])
def test_each_frame_defect_is_reported_at_its_severity(label, mutation, severity,
                                                       message, canon, designs):
    report = check(_mutate(mutation), canon, designs)
    found = [item for item in report["findings"] if item["check"] == "scene_frame"]
    assert found, label
    assert any(item["severity"] == severity and message in item["message_ja"]
               for item in found), found
    # high and medium both send the log back for repair (REPAIR_SEVERITIES).
    assert report["summary"]["status"] == "unresolved"


def test_unknown_schema_version_is_still_refused():
    payload = v11_payload()
    payload["schema_version"] = "9.9"
    with pytest.raises(GameLogError, match="expected one of"):
        parse_game_log(payload, "game_log.json")


def test_scripted_stage_a_1_1_run_uses_the_1_1_prompt_and_records_the_version(tmp_path):
    responses = base_responses()
    responses["stage_a:t01"] = json.dumps(v11_payload(), ensure_ascii=False)
    script = write_script(tmp_path, responses)
    out = tmp_path / "bundle"
    completed = run_cli(out, "--gamelog-schema", "1.1", script=script, run_id="v11")
    assert completed.returncode == 0, completed.stderr

    run = out / "v11"
    report = read_json(run / "game_log.report.json")
    assert report["summary"]["status"] == "clean"
    assert report["prompt_hashes"].keys() == {"stage-a-gamelog-v1.1", "stage-a-repair"}
    prompt = (run / "stage_a" / "attempt-1.prompt.txt").read_text(encoding="utf-8")
    assert "場面フレーム" in prompt and '"schema_version": "1.1"' in prompt
    state = read_json(run / "state.json")
    assert state["config"]["gamelog_schema"] == "1.1"
    assert "stage-a-gamelog-v1.1" in state["config"]["prompt_hashes"]


def test_default_run_keeps_the_1_0_prompt_and_config(tmp_path):
    out = tmp_path / "bundle"
    completed = run_cli(out, run_id="v10")
    assert completed.returncode == 0, completed.stderr
    state = read_json(out / "v10" / "state.json")
    assert "gamelog_schema" not in state["config"]
    assert "stage-a-gamelog-v1.1" not in state["config"]["prompt_hashes"]
    prompt = (out / "v10" / "stage_a" / "attempt-1.prompt.txt").read_text(encoding="utf-8")
    assert "場面フレーム" not in prompt


def test_1_0_schema_text_is_byte_identical_to_the_frozen_one():
    assert "schema_version\": \"1.0\"" in run_twostage.GAMELOG_SCHEMA
    assert "phase" not in run_twostage.GAMELOG_SCHEMA
    assert "\"schema_version\": \"1.1\"" in run_twostage.GAMELOG_SCHEMA_V11
    assert '"phase": "opening"' in run_twostage.GAMELOG_SCHEMA_V11
