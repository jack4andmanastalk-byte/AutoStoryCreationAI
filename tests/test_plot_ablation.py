from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def _prepare_shared_design(tmp_path):
    shared_root = tmp_path / "shared"
    subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", "t01", "--system", "s1", "--provider", "scripted",
            "--script", str(FIXTURE), "--out", str(shared_root),
            "--run-id", "shared-design", "--report-only", "--quiet",
        ],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    return shared_root / "shared-design"


def _run_ablation(tmp_path, shared_run, experiment_id, provider):
    args = [
        sys.executable, str(REPO_ROOT / "scripts" / "run_plot_ablation.py"),
        "--id", experiment_id, "--task", "t01",
        "--canon", str(shared_run / "canon"),
        "--design-dir", str(shared_run / "design"),
        "--provider", provider,
        "--out", str(tmp_path / "experiment"),
        "--runs-root", str(tmp_path / "runs"),
        "--operator-root", str(tmp_path / "operator"),
    ]
    if provider == "scripted":
        args.extend(["--script", str(FIXTURE)])
    return subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)


def _ingest_all_pending(operator_root: Path, arms: tuple[str, ...]):
    body = "灯台と鍵の行方を思う嵐の夜だった。" * 30
    for arm in arms:
        operator_dir = operator_root / arm
        index = json.loads((operator_dir / "relay" / "index.json").read_text(encoding="utf-8"))
        assert index["pending"], f"{arm} has no relay request"
        blocks = []
        for item in index["pending"]:
            blocks.append(
                f"<<<ANSWER {item['tag']}>>>\n{body}\n<<<END {item['tag']}>>>")
        answer_file = operator_dir / "answers.txt"
        answer_file.write_text("\n\n".join(blocks), encoding="utf-8")
        subprocess.run(
            [
                sys.executable, str(REPO_ROOT / "scripts" / "relay_prompts.py"),
                "ingest", "--dir", str(operator_dir), "--file", str(answer_file),
                "--model", "arena-agent-mode", "--model-version", "unversioned",
            ],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )


def test_scripted_fixture_runner_is_l1_plumbing_not_a_model_experiment(tmp_path):
    shared_run = _prepare_shared_design(tmp_path)
    completed = _run_ablation(tmp_path, shared_run, "fixture-pair", "scripted")
    assert completed.returncode == 0, completed.stderr

    result = json.loads((tmp_path / "experiment" / "results.json").read_text(encoding="utf-8"))
    assert result["scope"] == "scripted fixture wiring check only; not a model experiment"
    assert result["target"] == "Plot-SKILL-derived memo handoff only; not overall SKILL efficacy"
    assert result["evaluation_scope"] == {
        "provider_constraint": "arena-only",
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
        tmp_path / "experiment" / "note.md").read_text(encoding="utf-8")


def test_arena_relay_resumes_both_arms_with_separate_namespaces(tmp_path):
    shared_run = _prepare_shared_design(tmp_path)
    operator_root = tmp_path / "operator" / "arena-pair"
    first = _run_ablation(tmp_path, shared_run, "arena-pair", "arena")
    assert first.returncode == 3, first.stderr
    first_progress = json.loads(
        (tmp_path / "experiment" / "progress.json").read_text(encoding="utf-8"))
    assert first_progress["status"] == "waiting_for_arena_responses"
    assert set(first_progress["relay"]) == {"no_plot", "with_plot"}
    resume_note = (tmp_path / "experiment" / "note.md").read_text(encoding="utf-8")
    assert f"--operator-root {tmp_path / 'operator'}" in resume_note

    # Each arm has a separate request namespace/tag set; the same response is
    # not accidentally attached to both prompts.
    no_plot_index = json.loads(
        (operator_root / "no_plot" / "relay" / "index.json").read_text(encoding="utf-8"))
    with_plot_index = json.loads(
        (operator_root / "with_plot" / "relay" / "index.json").read_text(encoding="utf-8"))
    assert no_plot_index["pending"][0]["tag"] != with_plot_index["pending"][0]["tag"]

    for attempt in range(3):
        _ingest_all_pending(operator_root, ("no_plot", "with_plot"))
        resumed = subprocess.run(
            [
                sys.executable, str(REPO_ROOT / "scripts" / "run_plot_ablation.py"),
                "--id", "arena-pair", "--task", "t01",
                "--canon", str(shared_run / "canon"),
                "--design-dir", str(shared_run / "design"),
                "--provider", "arena", "--out", str(tmp_path / "experiment"),
                "--runs-root", str(tmp_path / "runs"),
                "--operator-root", str(tmp_path / "operator"), "--resume",
            ],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if attempt < 2:
            assert resumed.returncode == 3, resumed.stderr
        else:
            assert resumed.returncode == 0, resumed.stderr

    result = json.loads((tmp_path / "experiment" / "results.json").read_text(encoding="utf-8"))
    assert result["scope"] == "Arena × L1 exploratory reference only"
    assert result["model"]["name"] == "arena-agent-mode"
    assert result["model"]["version"] == "unversioned"
    assert result["model"]["version_pinned"] is False
    assert result["evaluation_scope"]["provider_constraint"] == "arena-only"
    assert result["g5"] == "not_established_by_single_pair"


def test_arena_run_archives_inputs_and_resumes_without_source_or_runs_cache(tmp_path):
    shared_run = _prepare_shared_design(tmp_path)
    out = tmp_path / "persistent-experiment"
    first = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts" / "run_plot_ablation.py"),
            "--id", "persistent-pair", "--task", "t01",
            "--canon", str(shared_run / "canon"),
            "--design-dir", str(shared_run / "design"),
            "--provider", "arena", "--out", str(out),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert first.returncode == 3, first.stderr
    assert (out / "inputs" / "canon" / "characters.json").is_file()
    assert (out / "inputs" / "design" / "plot.json").is_file()
    assert (out / "state.json").is_file()
    assert (out / "attempts" / "persistent-pair" / "no_plot" /
            "persistent-pair-no_plot-try01").is_dir()
    relay_root = out / "relay" / "persistent-pair"
    assert (relay_root / "no_plot" / "requests").is_dir()
    assert (relay_root / "with_plot" / "requests").is_dir()

    # Simulate an environment reset that removes ignored source/run directories.
    # The experiment-local inputs, run outputs and relay cache must be sufficient.
    shutil.rmtree(shared_run)
    _ingest_all_pending(relay_root, ("no_plot", "with_plot"))
    resumed = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts" / "run_plot_ablation.py"),
            "--id", "persistent-pair", "--task", "t01",
            "--provider", "arena", "--out", str(out), "--resume",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert resumed.returncode == 3, resumed.stderr
    progress = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "waiting_for_arena_responses"
    for arm in ("no_plot", "with_plot"):
        index = json.loads((relay_root / arm / "relay" / "index.json").read_text(
            encoding="utf-8"))
        assert index["pending"][0]["purpose"] == "draft:ch02"
