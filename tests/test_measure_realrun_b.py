"""Batch B's measurement: registration hash, empty state, and first-attempt counting.

The end-to-end fixture is a scripted S1 run. It checks that the script reads a
real run directory and applies the registered arithmetic; it is not evidence
about prose or about a real model.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import measure_realrun_b  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-b-t01"
SCRIPTED_SCRIPT = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


@pytest.fixture(scope="module")
def scripted_run(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("realrun-b-scripted")
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", "t01",
            "--system", "s1",
            "--stage", "all",
            "--design",
            "--provider", "scripted",
            "--script", str(SCRIPTED_SCRIPT),
            "--seed", "0",
            "--temperature", "0.8",
            "--out", str(out),
            "--run-id", "run",
            "--report-only",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    run_dir = out / "run"
    assert (run_dir / "run-summary.json").is_file(), (
        f"returncode={completed.returncode}\nstdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return run_dir


def measure(tmp_path: Path, *extra: str, bundle: Path = BUNDLE) -> dict:
    out = tmp_path / "measured.json"
    completed = measure_realrun_b.main([
        "--bundle", str(bundle), "--out", str(out), *extra])
    assert completed == 0
    return json.loads(out.read_text(encoding="utf-8"))


def load_prereg() -> dict:
    return json.loads((BUNDLE / "preregistration.json").read_text(encoding="utf-8"))


def prereg_with_live_history_pin(tmp_path: Path) -> Path:
    """Copy of batch B's registration carrying the live design-history pin.

    Batch B's frozen pins predate the B2 prompt change (design-history 1.1),
    while the scripted fixture run is generated with live templates. Measuring
    that fresh scripted run against the frozen pin must, correctly, report a
    condition violation -- so the scripted arithmetic tests measure against
    this copy instead. The bundle's own registration is never rewritten.
    """
    from asc.pipeline.prompts import load_prompt

    data = load_prereg()
    prompt = load_prompt("design-history")
    data["condition"]["prompt_set"]["pins"]["design-history"] = {
        "version": str(prompt.version), "digest": prompt.digest}
    path = tmp_path / "preregistration-live.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def test_the_registration_is_fixed_and_hashed(tmp_path):
    result = measure(tmp_path)
    prereg = BUNDLE / "preregistration.json"
    registered = load_prereg()

    assert result["preregistration"]["sha256"] == \
        hashlib.sha256(prereg.read_bytes()).hexdigest()
    assert registered["samples_planned"] == 1
    assert registered["registered_before_any_sample"] is True
    assert set(registered["rules"]) == {
        "B0_condition", "B1_completion", "B2_first_attempt",
        "B3_length", "B4_audit",
    }
    assert registered["rules"]["B2_first_attempt"]["counting_rule"]["primary"] == \
        "count_first_attempt_findings_even_if_repaired_away"
    assert registered["condition"]["canon_policy"]["mode"] == \
        "plan_generated_once_within_the_single_run"
    assert result["registration_checks"]["tasks_file"]["matches"] is True


def test_an_empty_batch_says_not_run(tmp_path):
    """A bundle with the registration but no samples must never invent a verdict."""
    empty = tmp_path / "empty-bundle"
    empty.mkdir()
    (empty / "preregistration.json").write_text(
        (BUNDLE / "preregistration.json").read_text(encoding="utf-8"),
        encoding="utf-8")

    result = measure(tmp_path, bundle=empty)

    assert result["schema"] == "realrun-b-v1"
    assert result["samples"] == {}
    assert result["verdicts"]["B0_condition"]["verdict"] == "not_run"
    assert result["verdicts"]["B1_completion"]["verdict"] == "not_run"
    assert result["verdicts"]["B2_first_attempt"]["verdict"] == "not_enough_data"
    assert result["verdicts"]["B3_length"]["verdict"] == "not_enough_data"
    assert result["verdicts"]["B4_audit"]["verdict"] == "not_enough_data"


def test_scripted_s1_run_is_counted_and_rules_applied(tmp_path, scripted_run):
    result = measure(tmp_path, "--preregistration", str(prereg_with_live_history_pin(tmp_path)), "--sample", f"sample-1={scripted_run}")
    sample = result["samples"]["sample-1"]
    verdicts = result["verdicts"]

    assert sample["complete"] is True
    assert sample["eligible"] is True
    assert sample["condition_violations"] == []
    assert sample["plan"] == {
        "attempts": 1,
        "first_attempt_failed": False,
        "first_attempt_error_file_present": False,
        "prompt": {
            "name": "plan-canon",
            "version": "1.0",
            "digest": "d5efcf43e513e63c",
        },
    }
    assert list(sample["canon"]["files_sha256"]) == [
        "characters.json", "facts.json", "locations.json", "timeline.json",
        "foreshadowing.json", "suppressions.json",
    ]
    assert all(len(value) == 64 for value in sample["canon"]["files_sha256"].values())
    assert sample["canon"]["missing_files"] == []

    design = sample["design"]
    assert list(design["docs"]) == [
        "brief", "world", "history", "character", "relation", "plot", "scene", "voice",
    ]
    assert design["reports_present"] == 8
    assert design["first_attempt_findings"] == 0
    assert design["final_findings"] == 0
    assert design["repairs"] == 0
    assert design["unresolved"] == []
    assert design["missing"] == []

    chapters = sample["draft"]["chapters"]
    assert [chapters[name]["chars"] for name in ("ch01", "ch02", "ch03")] == [277, 245, 224]
    assert sample["draft"]["chars_total"] == 746
    assert sample["draft"]["chapters_in_length_band"] == 0
    assert sample["draft"]["first_failed_chapters"] == []
    assert sample["audit"]["violations"] == 0
    assert sample["audit"]["high"] == 0
    assert sample["audit"]["checks_skipped"] == 0
    assert sample["responses"]["ledger_entries"] == 12
    assert sample["responses"]["provenance_counts"] == {"scripted": 12}

    # The short scripted chapters must fail the registered length band.
    assert verdicts["B0_condition"]["verdict"] == "condition_ok"
    assert verdicts["B1_completion"]["verdict"] == "complete_but_gate_fail"
    assert verdicts["B2_first_attempt"]["verdict"] == "first_attempt_clean"
    assert verdicts["B3_length"]["verdict"] == "length_outside"
    assert verdicts["B4_audit"]["verdict"] == "audit_no_high_all_checks_ran"


def test_a_design_finding_repaired_away_still_counts(tmp_path, scripted_run):
    run_copy = tmp_path / "run"
    shutil.copytree(scripted_run, run_copy)
    report_path = run_copy / "design" / "brief.report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    finding = {
        "id": "test_finding",
        "check": "test_finding",
        "severity": "high",
        "message_ja": "計測テスト用の所見",
    }
    report["status"] = "clean"
    report["attempts"] = 2
    report["repairs"] = 1
    report["first_attempt"] = {"findings": [finding], "checks_failed": 1}
    report["findings"] = []
    report["checks_failed"] = 0
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")

    result = measure(tmp_path, "--preregistration", str(prereg_with_live_history_pin(tmp_path)), "--sample", f"sample-1={run_copy}")
    design = result["samples"]["sample-1"]["design"]

    assert design["first_attempt_findings"] == 1
    assert design["final_findings"] == 0
    assert design["disappeared_exact"] == 1
    assert design["docs_with_first_findings"] == ["brief"]
    assert result["verdicts"]["B2_first_attempt"]["verdict"] == \
        "first_attempt_findings_repaired"


def test_a_run_without_plan_generated_canon_is_a_condition_violation(
        tmp_path, scripted_run):
    run_copy = tmp_path / "run"
    shutil.copytree(scripted_run, run_copy)
    summary_path = run_copy / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["plan"] = None
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    result = measure(tmp_path, "--preregistration", str(prereg_with_live_history_pin(tmp_path)), "--sample", f"sample-1={run_copy}")
    codes = [item["code"] for item in result["samples"]["sample-1"]["condition_violations"]]

    assert "canon_not_plan_generated" in codes
    assert result["verdicts"]["B0_condition"]["verdict"] == "condition_violation"
    assert result["verdicts"]["B1_completion"]["verdict"] == "condition_violation"
    assert result["verdicts"]["B2_first_attempt"]["verdict"] == "condition_violation"


def fake_sample(**overrides) -> dict:
    sample = {
        "complete": True,
        "status": "pass",
        "condition_violations": [],
        "plan": {"first_attempt_failed": False},
        "design": {
            "first_attempt_findings": 0,
            "final_findings": 0,
            "first_repair_findings": 0,
            "final_repair_findings": 0,
            "disappeared_exact": 0,
            "docs_with_first_findings": [],
            "docs_with_multiple_attempts": [],
            "first_by_check": {},
            "unresolved": [],
            "missing": [],
        },
        "draft": {
            "first_failed_chapters": [],
            "chapters_in_length_band": 3,
            "chars_total": 3600,
            "total_in_length_band": True,
        },
        "audit": {
            "present": True,
            "violations": 0,
            "high": 0,
            "checks_skipped": 0,
            "ced_per_10k_chars": 0.0,
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(sample.get(key), dict):
            sample[key].update(value)
        else:
            sample[key] = value
    return sample


def test_nonblocking_first_findings_are_not_called_repaired():
    prereg = load_prereg()
    sample = fake_sample(design={
        "first_attempt_findings": 1,
        "final_findings": 1,
        "first_repair_findings": 0,
        "final_repair_findings": 0,
        "docs_with_first_findings": ["brief"],
    })

    verdicts = measure_realrun_b.verdicts({"sample-1": sample}, prereg)

    assert verdicts["B2_first_attempt"]["verdict"] == \
        "first_attempt_findings_remain_nonblocking"


def test_incomplete_and_skipped_audit_verdicts():
    prereg = load_prereg()

    incomplete = measure_realrun_b.verdicts(
        {"sample-1": fake_sample(complete=False, status="incomplete")}, prereg)
    assert incomplete["B1_completion"]["verdict"] == "incomplete"
    assert incomplete["B2_first_attempt"]["verdict"] == "incomplete"
    assert incomplete["B3_length"]["verdict"] == "not_enough_data"
    assert incomplete["B4_audit"]["verdict"] == "not_measured"

    skipped = measure_realrun_b.verdicts(
        {"sample-1": fake_sample(audit={"checks_skipped": 2})}, prereg)
    assert skipped["B4_audit"]["verdict"] == "audit_incomplete_coverage"


def test_condition_violation_wins_over_other_verdicts():
    prereg = load_prereg()
    sample = fake_sample(condition_violations=[{"code": "task_mismatch:manifest"}])

    verdicts = measure_realrun_b.verdicts({"sample-1": sample}, prereg)

    assert verdicts["B0_condition"]["verdict"] == "condition_violation"
    assert verdicts["B1_completion"]["verdict"] == "condition_violation"
    assert verdicts["B2_first_attempt"]["verdict"] == "condition_violation"
    assert verdicts["B3_length"]["verdict"] == "condition_violation"
    assert verdicts["B4_audit"]["verdict"] == "condition_violation"


def test_optional_target_rule_verdict():
    prereg = load_prereg()
    prereg["rules"]["H_history_first_attempt"] = {
        "doc": "history", "checks": ["canon_separated"]}

    absent = fake_sample(design={
        "docs": {"history": {"first_attempt": {"count": 0, "by_check": {}}}}})
    verdict = measure_realrun_b.verdicts(
        {"sample-1": absent}, prereg)["H_history_first_attempt"]
    assert verdict["verdict"] == "target_findings_absent"
    assert verdict["by_sample"] == {"sample-1": 0}

    present = fake_sample(design={"docs": {"history": {
        "first_attempt": {"count": 2, "by_check": {"canon_separated": 2}}}}})
    verdict = measure_realrun_b.verdicts(
        {"sample-1": present}, prereg)["H_history_first_attempt"]
    assert verdict["verdict"] == "target_findings_present"
    assert verdict["details"]["sample-1"]["doc_first_findings"] == 2

    empty = measure_realrun_b.verdicts({}, prereg)
    assert empty["H_history_first_attempt"]["verdict"] == "not_run"

    # Registrations without an H rule (batch B) gain no extra verdict.
    plain = measure_realrun_b.verdicts({"sample-1": fake_sample()}, load_prereg())
    assert "H_history_first_attempt" not in plain
