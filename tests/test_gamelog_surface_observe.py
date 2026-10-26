"""Observation mode: the candidate place check may look, but not decide."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import check_rewrite, load_game_log  # noqa: E402
from asc.gamelog.rewrite import render_markdown  # noqa: E402
from asc.gamelog.world import derive_timeline  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402
import probe_surface_observe  # noqa: E402
import run_twostage  # noqa: E402

SLICE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
OBSERVE = REPO_ROOT / "experiments" / "2026-10-surface-observe-t01"
RUN = OBSERVE / "observe-on" / "run"
INJECTION = probe_surface_observe.INJECTION


@pytest.fixture(scope="module")
def context():
    inputs = SLICE / "inputs"
    canon = load_canon(inputs / "canon")
    log = load_game_log(inputs / "game_log.json")
    return {
        "canon": canon, "log": log,
        "timeline": derive_timeline(log, canon),
        "voice": load_voice(inputs / "design" / "voice.json"),
        "scenes": load_scenes(inputs / "design" / "scene.json"),
        "design": inputs / "design",
    }


def check(context, text: str, chapter: str = "ch01", observe: bool = False) -> dict:
    return check_rewrite(text, chapter, context["log"], context["canon"],
                         context["voice"], context["scenes"],
                         timeline=context["timeline"], observe_surface=observe)


def test_observations_are_absent_unless_asked(context):
    text = (RUN / "text" / "ch01.md").read_text(encoding="utf-8")
    assert "observations" not in check(context, text)
    assert check(context, text, observe=True)["observations"] == []


def test_an_off_log_trip_is_observed_but_never_a_finding(context):
    text = (RUN / "text" / "ch01.md").read_text(encoding="utf-8") + "\n\n" + INJECTION
    plain = check(context, text)
    observed = check(context, text, observe=True)
    # The contract does not move: same findings, same status, nothing blocking.
    assert observed["findings"] == plain["findings"]
    assert observed["summary"] == plain["summary"]
    assert observed["summary"]["status"] == "clean"
    assert [item["evidence"]["destination"] for item in observed["observations"]] \
        == ["対岸の島"]
    assert observed["observation_summary"]["count"] == 1
    assert all(item["advisory"] for item in observed["observations"])
    # ... and they are not findings, so they cannot trigger a repair.
    assert observed["findings"] == []
    assert not run_twostage.rewrite_needs_repair(observed["observations"])


def test_markdown_keeps_observations_out_of_the_findings_section(context):
    text = (RUN / "text" / "ch01.md").read_text(encoding="utf-8") + "\n\n" + INJECTION
    rendered = render_markdown(check(context, text, observe=True))
    assert "観測（契約外・判定に使わない）" in rendered
    assert "対岸の島" in rendered
    assert "## 所見" not in rendered


def test_the_pipeline_flag_records_observations(tmp_path, context):
    out = tmp_path / "run"
    completed = run_twostage.main([
        "--task", "t01", "--canon", str(SLICE / "inputs" / "canon"),
        "--design-dir", str(SLICE / "inputs" / "design"),
        "--provider", "scripted", "--script", str(SLICE / "scripted.json"),
        "--out", str(out), "--run-id", "run", "--allow-temp-out", "--quiet",
        "--observe-surface"])
    assert completed == 0
    report = json.loads((out / "run" / "rewrite.report.json").read_text(encoding="utf-8"))
    for chapter, row in report["chapters"].items():
        assert "observations" in row, chapter
        assert row["summary"]["status"] == "clean"
    state = json.loads((out / "run" / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["observe_surface"] is True


def test_the_observation_probe_shows_non_interference(tmp_path):
    out = tmp_path / "observe.json"
    completed = probe_surface_observe.main([
        "--baseline", str(OBSERVE / "observe-off" / "run"),
        "--observe", str(RUN),
        "--game-log", str(RUN / "game_log.json"),
        "--canon", str(SLICE / "inputs" / "canon"),
        "--out", str(out)])
    assert completed == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "surface-observe-v1"
    assert all(report["findings"].values())
    assert report["injection"]["results"]["observe"]["status"] == "clean"
    assert report["injection"]["results"]["observe"]["observation_destinations"] \
        == ["対岸の島"]
    assert report["limits"]
