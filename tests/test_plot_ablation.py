from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def test_plot_ablation_runner_pairs_shared_inputs_and_reports_l1_only(tmp_path):
    shared_root = tmp_path / "shared"
    prep = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", "t01", "--system", "s1", "--provider", "scripted",
            "--script", str(FIXTURE), "--out", str(shared_root),
            "--run-id", "shared-design", "--report-only", "--quiet",
        ],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    del prep
    shared_run = shared_root / "shared-design"
    experiment_out = tmp_path / "experiment"
    runs_root = tmp_path / "runs"
    completed = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts" / "run_plot_ablation.py"),
            "--id", "fixture-pair", "--task", "t01",
            "--canon", str(shared_run / "canon"),
            "--design-dir", str(shared_run / "design"),
            "--provider", "scripted", "--script", str(FIXTURE),
            "--out", str(experiment_out), "--runs-root", str(runs_root),
        ],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )

    result = json.loads((experiment_out / "results.json").read_text(encoding="utf-8"))
    assert result["scope"] == "exploratory paired L1 only; not creative quality evidence"
    assert result["target"] == "Plot-SKILL-derived memo handoff only; not overall SKILL efficacy"
    assert result["evaluation_scope"] == {
        "l2": "frozen_not_measured", "l3": "frozen_not_measured"}
    assert result["g5"] == "not_established_by_single_pair"
    assert result["prompt_control"]["ch01_diff_only_plot_memo_lines"] is True
    assert result["model"]["name"] == "scripted-fixture"
    assert result["model"]["version"] == "v1"
    assert result["model"]["version_pinned"] is True
    assert len(result["model"]["by_request"]) == 3
    assert result["conditions"]["canon_files_sha256"]
    assert result["conditions"]["design_files_sha256"]
    assert set(result["arms"]) == {"no_plot", "with_plot"}
    assert all("forbidden_per_10k_chars" in arm["l1"]
               for arm in result["arms"].values())
    assert all(set(arm["l1"]["task_avoid_hits"]) == {"選ばれし者", "古代の予言"}
               for arm in result["arms"].values())
    assert all("continuity" in arm["l1"] for arm in result["arms"].values())
    assert result["paired_l1_deltas"]["chars_excluding_markers"][
        "delta_with_minus_without"] == 0
    assert "cannot establish a general effect" in (
        experiment_out / "note.md").read_text(encoding="utf-8")
    assert "completed" in completed.stdout
