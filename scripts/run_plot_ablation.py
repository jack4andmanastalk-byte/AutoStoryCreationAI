#!/usr/bin/env python3
"""Run a paired L1-only ablation of chapter-local Plot memos.

A canon and clean design directory must already exist and are held fixed for
both arms. The script drafts once with Plot memos omitted and once with them
included, then runs only the deterministic L1 evaluation. It does not assess
creative quality and never invokes L2/L3.

Example (fixed model/version, credentials supplied through the environment):
    python3 scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 \\
        --canon runs/shared-plan/canon --design-dir runs/shared-design/design \\
        --provider command --command "python3 scripts/model_adapter.py --model MODEL --model-version VERSION" \\
        --model MODEL --out experiments/plot-ablation-t01

The shared plan/design preparation is intentionally separate so it is not
regenerated between the paired Draft conditions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline.tasks import TaskError, load_tasks  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
DEFAULT_SCRIPT = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def _sha256_tree(path: Path) -> dict[str, str]:
    return {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(path.rglob("*")) if file.is_file()
    }


def _read_responses(run_dir: Path) -> list[dict]:
    path = run_dir / "responses.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _without_plot_lines(prompt: str) -> str:
    return "\n".join(
        line for line in prompt.split("\n")
        if not line.startswith("- 幕 ") and not line.startswith("- 転換点 "))


def _draft_prompts(run_dir: Path) -> dict[str, str]:
    return {
        str(row["purpose"]): str(row["prompt"])
        for row in _read_responses(run_dir)
        if str(row.get("purpose", "")).startswith("draft:")
    }


def _response_models(run_dir: Path) -> dict[str, dict]:
    return {
        str(row["purpose"]): {
            "model": (row.get("response") or {}).get("model"),
            "model_version": (row.get("response") or {}).get("model_version"),
        }
        for row in _read_responses(run_dir)
        if str(row.get("purpose", "")).startswith("draft:")
    }


def _task_avoid_hits(run_dir: Path, task) -> dict[str, int]:
    bodies = [path.read_text(encoding="utf-8")
              for path in sorted((run_dir / "text").glob("*.md"))]
    joined = "\n".join(bodies)
    return {term: joined.count(term) for term in task.avoid}


def _l1_summary(run_dir: Path, run_summary: dict, evaluation: dict,
                evaluation_path: Path, task) -> dict:
    l1 = evaluation["l1"]
    continuity = l1.get("continuity")
    continuity_summary = continuity.get("summary") if continuity else None
    draft = run_summary.get("draft", {})
    must_include = draft.get("must_include", {})
    return {
        "run_id": run_summary["run_id"],
        "run_dir": run_summary["run_dir"],
        "status": run_summary.get("status"),
        "chars_excluding_markers": run_summary.get("chars"),
        "must_include": must_include,
        "task_avoid_hits": _task_avoid_hits(run_dir, task),
        "forbidden_hits": len(l1.get("forbidden") or []),
        "forbidden_per_10k_chars": l1["densities"]["forbidden_per_10k_chars"],
        "continuity": continuity_summary,
        "audit": run_summary.get("audit"),
        "descriptive_metrics": l1.get("metrics", {}),
        "evaluation_json": str(evaluation_path),
    }


def _delta(a, b):
    if isinstance(a, (int, float)) and not isinstance(a, bool) \
            and isinstance(b, (int, float)) and not isinstance(b, bool):
        return round(b - a, 6)
    return None


def _note(result: dict) -> str:
    rows = []
    for arm, values in result["arms"].items():
        rows.append(
            f"| {arm} | {values['l1']['chars_excluding_markers']} | "
            f"{values['l1']['must_include'].get('rate')} | "
            f"{sum(values['l1']['task_avoid_hits'].values())} | "
            f"{values['l1']['forbidden_hits']} | "
            f"{values['l1']['forbidden_per_10k_chars']} | "
            f"{(values['l1'].get('continuity') or {}).get('ced_per_10k_chars')} |")
    rows_text = "\n".join(rows)
    return f"""# Plot memo ablation: {result['experiment_id']}

- Scope: **exploratory L1-only paired comparison**; tests only the Plot-SKILL-derived memo handoff, not the Plot SKILL's overall efficacy, story quality, or protocol-v1 passage.
- Task/system/seed: {result['conditions']['task']} / S1 / {result['conditions']['seed']}
- Model/version: {result['model']['name']} / {result['model']['version']}
- Draft temperature: {result['conditions']['temperature']}
- Shared canon/design hashes: see `results.json`.
- L2/L3: `frozen_not_measured`; G5/reproducibility: not established by one pair.

| Arm | Chars (markers excluded) | Must-include rate | Task-avoid hits | Forbidden hits | Forbidden / 10k chars | CED / 10k chars |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{rows_text}

## Limits

The intervention is the inclusion of chapter-local Plot memo lines. The first
chapter's prompts are checked for equality after removing those lines. Later
chapters may receive different prior-chapter text because prior outputs are
part of the pipeline; that is a downstream mediated effect, not an independently
controlled chapter-level effect. L1 indicators are reported separately and do
not measure interest, originality, or reader preference. This one paired run
cannot establish a general effect. No L2/L3 judgments were made.
"""


def _run_pipeline(args, arm: str, include_plot: bool, run_root: Path) -> Path:
    run_id = f"{args.id}-{arm}"
    command = [
        sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
        "--task", args.task, "--tasks-file", args.tasks_file,
        "--system", "s1", "--stage", "draft",
        "--provider", args.provider, "--canon", str(Path(args.canon).resolve()),
        "--design-dir", str(Path(args.design_dir).resolve()),
        "--seed", str(args.seed), "--temperature", str(args.temperature),
        "--out", str(run_root), "--run-id", run_id,
        "--report-only", "--quiet",
    ]
    if args.provider == "scripted":
        command.extend(["--script", args.script])
    else:
        command.extend(["--command", args.command])
        if args.model:
            command.extend(["--model", args.model])
    if not include_plot:
        command.append("--no-plot-memos")
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{arm} Draft run failed ({completed.returncode}): {detail}")
    return run_root / run_id


def _evaluate_l1(run_dir: Path, out_dir: Path) -> dict:
    command = [
        sys.executable, str(REPO_ROOT / "scripts" / "run_evaluation.py"),
        "--candidate", str(run_dir / "text"), "--canon", str(run_dir / "canon"),
        "--patterns", str(REPO_ROOT / "harness" / "patterns.yaml"),
        "--out", str(out_dir), "--report-only",
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"L1 evaluation failed for {run_dir.name}: {detail}")
    return json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", required=True, help="safe experiment id used in run ids")
    parser.add_argument("--task", default="t01")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--canon", required=True, help="shared, validated canon directory")
    parser.add_argument("--design-dir", required=True,
                        help="shared design directory with clean plot, scene and voice")
    parser.add_argument("--provider", required=True, choices=["command", "scripted"])
    parser.add_argument("--command", help="external provider command for --provider command")
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT),
                        help="fixture path for scripted wiring tests only")
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--out", required=True, help="new experiment output directory")
    parser.add_argument("--runs-root", default=str(REPO_ROOT / "runs" / "plot-ablation"))
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.id):
        parser.error("--id may contain only ASCII letters, digits, '.', '_' and '-'")
    if args.provider == "command" and not args.command:
        parser.error("--provider command requires --command")
    if args.provider == "scripted" and args.command:
        parser.error("--command is only valid with --provider command")
    if args.provider == "scripted" and args.model:
        parser.error("--model is only valid with --provider command")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        task = load_tasks(args.tasks_file).get(args.task)
    except (TaskError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    canon_dir = Path(args.canon).resolve()
    design_dir = Path(args.design_dir).resolve()
    out_dir = Path(args.out).resolve()
    run_root = Path(args.runs_root).resolve() / args.id
    for directory, label in ((canon_dir, "canon"), (design_dir, "design")):
        if not directory.is_dir():
            print(f"error: {label} directory does not exist: {directory}", file=sys.stderr)
            return 2
    if out_dir.exists():
        print(f"error: output directory already exists: {out_dir}", file=sys.stderr)
        return 2
    if run_root.exists():
        print(f"error: runs directory already exists: {run_root}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True)
    try:
        no_plot_dir = _run_pipeline(args, "no-plot", False, run_root / "no-plot")
        with_plot_dir = _run_pipeline(args, "with-plot", True, run_root / "with-plot")
        runs = {"no_plot": no_plot_dir, "with_plot": with_plot_dir}
        summaries = {
            arm: json.loads((path / "run-summary.json").read_text(encoding="utf-8"))
            for arm, path in runs.items()
        }
        manifests = {
            arm: json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            for arm, path in runs.items()
        }

        no_plot_condition = summaries["no_plot"].get("draft_condition") or {}
        with_plot_condition = summaries["with_plot"].get("draft_condition") or {}
        for key in ("canon_files_sha256", "design_files_sha256"):
            if no_plot_condition.get(key) != with_plot_condition.get(key):
                raise RuntimeError(f"paired runs do not share identical {key}")
        for key in ("task_id", "system", "seed", "temperature", "model", "model_version"):
            if manifests["no_plot"].get(key) != manifests["with_plot"].get(key):
                raise RuntimeError(f"paired runs differ in manifest field {key}")

        prompt_sets = {arm: _draft_prompts(path) for arm, path in runs.items()}
        response_models = {arm: _response_models(path) for arm, path in runs.items()}
        if response_models["no_plot"] != response_models["with_plot"]:
            raise RuntimeError("paired Draft responses differ in model/version metadata")
        first_purpose = "draft:ch01"
        base_prompt = prompt_sets["no_plot"].get(first_purpose)
        plot_prompt = prompt_sets["with_plot"].get(first_purpose)
        if not base_prompt or not plot_prompt:
            raise RuntimeError("paired runs must both contain a ch01 Draft request")
        if _without_plot_lines(plot_prompt) != base_prompt:
            raise RuntimeError("ch01 prompts differ beyond the intended Plot memo lines")
        if _without_plot_lines(plot_prompt) == plot_prompt:
            raise RuntimeError("the shared design has no chapter-local Plot memo in ch01")

        evals = {}
        for arm, path in runs.items():
            evals[arm] = _evaluate_l1(path, out_dir / "l1" / arm)
            if evals[arm].get("l2", {}).get("status") != "skipped" \
                    or evals[arm].get("l3", {}).get("status") != "skipped":
                raise RuntimeError("this runner is L1-only; L2/L3 must remain skipped")

        arms = {}
        for arm, path in runs.items():
            arms[arm] = {
                "manifest": manifests[arm],
                "run_summary": summaries[arm],
                "l1": _l1_summary(
                    path, summaries[arm], evals[arm],
                    out_dir / "l1" / arm / "evaluation.json", task),
                "draft_prompt_hashes": {
                    purpose: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                    for purpose, prompt in prompt_sets[arm].items()
                },
            }
        no_metrics = arms["no_plot"]["l1"]
        yes_metrics = arms["with_plot"]["l1"]
        metric_pairs = {
            "chars_excluding_markers": (no_metrics["chars_excluding_markers"],
                                        yes_metrics["chars_excluding_markers"]),
            "must_include_rate": (no_metrics["must_include"].get("rate"),
                                  yes_metrics["must_include"].get("rate")),
            "forbidden_hits": (no_metrics["forbidden_hits"], yes_metrics["forbidden_hits"]),
            "task_avoid_hits": (sum(no_metrics["task_avoid_hits"].values()),
                                 sum(yes_metrics["task_avoid_hits"].values())),
            "forbidden_per_10k_chars": (no_metrics["forbidden_per_10k_chars"],
                                         yes_metrics["forbidden_per_10k_chars"]),
            "continuity_violations": (
                (no_metrics.get("audit") or {}).get("violations"),
                (yes_metrics.get("audit") or {}).get("violations")),
            "high_continuity_violations": (
                (no_metrics.get("audit") or {}).get("by_severity", {}).get("high"),
                (yes_metrics.get("audit") or {}).get("by_severity", {}).get("high")),
            "checks_skipped": (
                (no_metrics.get("audit") or {}).get("checks_skipped"),
                (yes_metrics.get("audit") or {}).get("checks_skipped")),
            "ced_per_10k_chars": (
                (no_metrics.get("continuity") or {}).get("ced_per_10k_chars"),
                (yes_metrics.get("continuity") or {}).get("ced_per_10k_chars")),
        }
        results = {
            "schema": "plot-memo-ablation-l1-v1",
            "experiment_id": args.id,
            "scope": "exploratory paired L1 only; not creative quality evidence",
            "target": "Plot-SKILL-derived memo handoff only; not overall SKILL efficacy",
            "evaluation_scope": {"l2": "frozen_not_measured", "l3": "frozen_not_measured"},
            "g5": "not_established_by_single_pair",
            "conditions": {
                "task": args.task, "system": "s1", "seed": args.seed,
                "temperature": args.temperature,
                "provider": args.provider,
                "shared_canon_source": str(canon_dir),
                "shared_design_source": str(design_dir),
                "canon_files_sha256": no_plot_condition.get("canon_files_sha256"),
                "design_files_sha256": no_plot_condition.get("design_files_sha256"),
            },
            "model": {"name": manifests["with_plot"].get("model"),
                      "version": manifests["with_plot"].get("model_version"),
                      "version_pinned": bool(response_models["with_plot"])
                      and all(row.get("model_version") for row in
                              response_models["with_plot"].values()),
                      "by_request": response_models["with_plot"]},
            "prompt_control": {
                "ch01_diff_only_plot_memo_lines": True,
                "later_chapter_prompts": "may differ through prior-chapter text; downstream mediation",
            },
            "arms": arms,
            "paired_l1_deltas": {
                name: {"without_plot": a, "with_plot": b, "delta_with_minus_without": _delta(a, b)}
                for name, (a, b) in metric_pairs.items()
            },
            "l1_evaluation_dirs": {arm: str(out_dir / "l1" / arm) for arm in evals},
        }
        (out_dir / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out_dir / "note.md").write_text(_note(results), encoding="utf-8")
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"status": "completed", "results": str(out_dir / "results.json"),
                      "note": str(out_dir / "note.md"), "model": results["model"],
                      "g5": results["g5"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
