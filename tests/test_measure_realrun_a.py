"""Batch A's measurement: arithmetic, pre-registration hash, and empty state.

The fixtures are the scripted runs from the observation experiment. They are
used to check that the script reads a run correctly and applies the registered
rules — not as evidence about prose, which they are not.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import measure_realrun_a  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-a-t01"
OBSERVE = REPO_ROOT / "experiments" / "2026-10-surface-observe-t01"
SLICE_CANON = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01" / "inputs" / "canon"


def run(tmp_path: Path, *extra: str) -> dict:
    out = tmp_path / "measured.json"
    completed = measure_realrun_a.main([
        "--bundle", str(BUNDLE), "--canon", str(SLICE_CANON),
        "--out", str(out), *extra])
    assert completed == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_registration_is_fixed_and_hashed(tmp_path):
    result = run(tmp_path)
    prereg = BUNDLE / "preregistration.json"
    assert result["preregistration"]["sha256"] == \
        hashlib.sha256(prereg.read_bytes()).hexdigest()
    registered = json.loads(prereg.read_text(encoding="utf-8"))
    assert registered["samples_planned"] == 3
    assert registered["registered_before_any_sample"] is True
    assert set(registered["rules"]) == {"R1_place_branch", "R2_length",
                                       "R3_recurring_failure"}


def test_an_empty_batch_says_not_run(tmp_path):
    """A bundle with the registration but no samples must never invent a verdict."""
    empty = tmp_path / "empty-bundle"
    empty.mkdir()
    (empty / "preregistration.json").write_text(
        (BUNDLE / "preregistration.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    out = tmp_path / "empty.json"
    assert measure_realrun_a.main([
        "--bundle", str(empty), "--canon", str(SLICE_CANON),
        "--out", str(out)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["schema"] == "realrun-a-v1"
    assert result["samples"] == {}
    assert result["verdicts"]["R1_place_branch"]["verdict"] == "not_run"
    assert result["verdicts"]["R2_length"]["verdict"] == "not_enough_data"
    assert result["verdicts"]["R3_recurring_failure"]["verdict"] == "not_enough_data"


def test_samples_are_counted_and_rules_applied(tmp_path):
    result = run(tmp_path,
                 "--sample", f"sample-1={OBSERVE / 'observe-on' / 'run'}",
                 "--sample", f"sample-2={OBSERVE / 'observe-on' / 'run'}",
                 "--sample", f"sample-3={OBSERVE / 'observe-on' / 'run'}")
    sample = result["samples"]["sample-1"]
    assert sample["chapters_total"] == 3
    assert sample["observations_present"] is True
    # The scripted chapters are well under the registered 1,000-1,400 band.
    assert sample["chapters_in_length_band"] == 0
    assert result["verdicts"]["R2_length"]["verdict"] == "fix_prompt_target"
    # No observations, no findings: the registered rules must say so.
    assert result["verdicts"]["R1_place_branch"]["verdict"] == "no_examples"
    assert result["verdicts"]["R3_recurring_failure"]["verdict"] == \
        "no_recurring_failure"


def test_a_sample_without_the_observation_flag_is_flagged(tmp_path):
    result = run(tmp_path,
                 "--sample", f"sample-1={OBSERVE / 'observe-off' / 'run'}",
                 "--sample", f"sample-2={OBSERVE / 'observe-on' / 'run'}",
                 "--sample", f"sample-3={OBSERVE / 'observe-on' / 'run'}")
    rule = result["verdicts"]["R1_place_branch"]
    assert rule["verdict"] == "observations_absent"
    assert rule["samples_missing_observations"] == ["sample-1"]


def test_a_single_sample_is_not_enough(tmp_path):
    result = run(tmp_path, "--sample", f"sample-1={OBSERVE / 'observe-on' / 'run'}")
    verdicts = result["verdicts"]
    assert verdicts["samples_present"] == 1
    assert verdicts["enough_samples"] is False
    assert verdicts["R2_length"]["verdict"] == "not_enough_data"
    assert verdicts["R1_place_branch"]["verdict"] == "not_enough_data"


@pytest.mark.parametrize("branch,expected", [
    ({"off_log": 0, "undeclared": 0}, "no_examples"),
    ({"off_log": 0, "undeclared": 2}, "drop_undeclared_branch"),
    ({"off_log": 1, "undeclared": 0}, "narrow_branch_only"),
    ({"off_log": 1, "undeclared": 1}, "inspect_both"),
])
def test_branch_rule_table(branch, expected):
    prereg = json.loads((BUNDLE / "preregistration.json").read_text(encoding="utf-8"))
    samples = {
        f"sample-{index}": {
            "observation_branches": branch, "observations_present": True,
            "chapters_in_length_band": 3, "findings_by_check": {},
        }
        for index in (1, 2, 3)
    }
    assert measure_realrun_a.verdicts(samples, prereg)["R1_place_branch"]["verdict"] \
        == expected


def test_recurring_failures_need_two_samples():
    prereg = json.loads((BUNDLE / "preregistration.json").read_text(encoding="utf-8"))

    def samples(checks: list[dict]) -> dict:
        return {f"sample-{index}": {
            "observation_branches": {"off_log": 0, "undeclared": 0},
            "observations_present": True, "chapters_in_length_band": 2,
            "findings_by_check": check} for index, check in enumerate(checks, start=1)}

    assert measure_realrun_a.verdicts(
        samples([{"fact_boundary": 1}, {"fact_boundary": 1}, {}]),
        prereg)["R3_recurring_failure"]["recurring_checks"] == ["fact_boundary"]
    assert measure_realrun_a.verdicts(
        samples([{"fact_boundary": 1}, {"character_boundary": 1}, {}]),
        prereg)["R3_recurring_failure"]["verdict"] == "no_recurring_failure"


def test_branch_classification_uses_canon_locations():
    from asc.story.canon import load_canon
    canon = load_canon(SLICE_CANON)
    assert measure_realrun_a.classify("王都", canon) == "undeclared"
    assert measure_realrun_a.classify("対岸の島", canon) == "off_log"
