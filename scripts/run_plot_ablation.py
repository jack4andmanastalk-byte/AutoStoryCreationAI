#!/usr/bin/env python3
"""Run a paired L1-only ablation of chapter-local Plot memos.

A canon and clean design directory must either already exist or be prepared
inside the experiment bundle with ``--prepare-shared``, and are held fixed for
both arms. At the first invocation, immutable copies are archived under the
experiment output directory; by default, run logs and Arena relay requests and
responses also live there. This makes a pending experiment resumable after an
ignored ``runs/`` cache is cleared. The script drafts once with Plot memos
omitted and once with them included, then runs only the deterministic L1
evaluation. It does not assess creative quality and never invokes L2/L3.

Example (active repository scope: Arena relay only):
    python3 scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 \\
        --canon experiments/plot-ablation-prep/canon \\
        --design-dir experiments/plot-ablation-prep/design \\
        --provider arena --out experiments/plot-ablation-t01/paired

    # Or manage shared plan/design preparation in the same persistent bundle:
    python3 scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 \\
        --prepare-shared --provider arena \\
        --out experiments/2026-10-plot-ablation-t01/paired

If Arena responses are pending, the script exports tagged prompts (both per-arm
and combined in ``<out>/PROMPTS.md``) and exits 3. Ingest those answers with
``--ingest answers.txt --resume`` (or ``relay_prompts.py``) and rerun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.evaluation.scope import EvaluationScopeError, load_evaluation_scope  # noqa: E402
from asc.pipeline.tasks import TaskError, load_tasks  # noqa: E402
from asc.story.canon import CanonError, load_canon  # noqa: E402
import relay_prompts  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
DEFAULT_SCRIPT = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
REQUIRED_DESIGN_FILES = ("plot.json", "plot.report.json", "scene.json", "voice.json")
ALL_DESIGN_DOCS = ("brief", "world", "history", "character", "relation", "plot", "scene", "voice")


def _sha256_tree(path: Path) -> dict[str, str]:
    if not path.is_dir():
        return {}
    return {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(path.rglob("*")) if file.is_file()
    }


def _is_under_build(path: Path) -> bool:
    build_root = (REPO_ROOT / "build").resolve()
    resolved = path.resolve()
    return resolved == build_root or build_root in resolved.parents


def _is_canon_ready(canon_dir: Path) -> bool:
    if not canon_dir.is_dir() or not any(canon_dir.glob("*.json")):
        return False
    try:
        canon = load_canon(canon_dir)
    except CanonError:
        return False
    return bool(canon.chapters)


def _is_shared_design_ready(canon_dir: Path, design_dir: Path) -> bool:
    if not _is_canon_ready(canon_dir) or not design_dir.is_dir():
        return False
    if any(not (design_dir / name).is_file() for name in REQUIRED_DESIGN_FILES):
        return False
    try:
        report = json.loads((design_dir / "plot.report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(report, dict) and report.get("status") == "clean"


def _copy_tree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir()):
        if item.name.startswith("."):
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        elif item.is_file():
            shutil.copy2(item, target)


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
            "origin": ((row.get("response") or {}).get("provenance") or {}).get("origin")
            or "unspecified",
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

- Scope: **{result['scope']}**.
- Target: {result['target']}.
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


def _run_shared_prep(args, canon_dir: Path, design_dir: Path,
                     run_root: Path, operator_root: Path, attempt: int) -> dict:
    operator_dir = operator_root / "shared_prep"
    prep_run_root = run_root / "shared_prep"
    if not _is_canon_ready(canon_dir):
        plan_run_id = f"{args.id}-shared-plan-try{attempt:02d}"
        command = [
            sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", args.task, "--tasks-file", args.tasks_file,
            "--system", "s1", "--stage", "plan",
            "--seed", str(args.seed), "--temperature", str(args.temperature),
            "--out", str(prep_run_root), "--run-id", plan_run_id,
            "--report-only", "--quiet",
        ]
        if args.provider == "scripted":
            command.extend(["--provider", "scripted", "--script", args.script])
        else:
            operator_command = shlex.join([
                sys.executable, str(REPO_ROOT / "scripts" / "chat_operator.py"),
                "--dir", str(operator_dir), "--model", "arena-agent-mode",
                "--model-version", "unversioned",
            ])
            command.extend([
                "--provider", "command", "--command", operator_command,
                "--model", "arena-agent-mode",
            ])
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        plan_dir = prep_run_root / plan_run_id
        for prev in sorted(prep_run_root.glob(f"{args.id}-shared-plan-try*")):
            if prev != plan_dir and prev.is_dir():
                shutil.rmtree(prev)
        detail = completed.stderr.strip() or completed.stdout.strip()
        if completed.returncode == 2 and "NEED RESPONSE" in detail:
            return {"status": "pending", "stage": "plan",
                    "run_dir": str(plan_dir), "detail": detail}
        if completed.returncode != 0:
            raise RuntimeError(f"shared_prep Plan run failed ({completed.returncode}): {detail}")
        _copy_tree_contents(plan_dir / "canon", canon_dir)

    if not _is_shared_design_ready(canon_dir, design_dir):
        design_run_id = f"{args.id}-shared-design-try{attempt:02d}"
        command = [
            sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", args.task, "--tasks-file", args.tasks_file,
            "--system", "s1", "--stage", "design",
            "--canon", str(canon_dir.resolve()),
            "--seed", str(args.seed), "--temperature", str(args.temperature),
            "--out", str(prep_run_root), "--run-id", design_run_id,
            "--report-only", "--quiet",
        ]
        if args.provider == "scripted":
            command.extend(["--provider", "scripted", "--script", args.script])
        else:
            operator_command = shlex.join([
                sys.executable, str(REPO_ROOT / "scripts" / "chat_operator.py"),
                "--dir", str(operator_dir), "--model", "arena-agent-mode",
                "--model-version", "unversioned",
            ])
            command.extend([
                "--provider", "command", "--command", operator_command,
                "--model", "arena-agent-mode",
            ])
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        design_run_dir = prep_run_root / design_run_id
        for prev in sorted(prep_run_root.glob(f"{args.id}-shared-design-try*")):
            if prev != design_run_dir and prev.is_dir():
                shutil.rmtree(prev)
        if (design_run_dir / "design").is_dir():
            _copy_tree_contents(design_run_dir / "design", design_dir)
        if (design_run_dir / "design.json").is_file():
            shutil.copy2(design_run_dir / "design.json", design_dir / "design.json")
        detail = completed.stderr.strip() or completed.stdout.strip()
        if completed.returncode == 2 and "NEED RESPONSE" in detail:
            return {"status": "pending", "stage": "design",
                    "run_dir": str(design_run_dir), "detail": detail}
        if completed.returncode != 0:
            raise RuntimeError(
                f"shared_prep Design run failed ({completed.returncode}): {detail}")
        if not _is_shared_design_ready(canon_dir, design_dir):
            raise RuntimeError(
                "shared_prep Design completed without clean plot, scene, and voice artifacts")
        return {"status": "complete", "stage": "design", "run_dir": str(design_run_dir)}

    return {"status": "complete", "stage": "design", "run_dir": str(design_dir)}


def _run_pipeline(args, arm: str, include_plot: bool, run_root: Path,
                  operator_root: Path, attempt: int) -> dict:
    run_id = f"{args.id}-{arm}-try{attempt:02d}"
    command = [
        sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
        "--task", args.task, "--tasks-file", args.tasks_file,
        "--system", "s1", "--stage", "draft",
        "--canon", str(Path(args.canon).resolve()),
        "--design-dir", str(Path(args.design_dir).resolve()),
        "--seed", str(args.seed), "--temperature", str(args.temperature),
        "--out", str(run_root), "--run-id", run_id,
        "--report-only", "--quiet",
    ]
    if args.provider == "scripted":
        command.extend(["--provider", "scripted", "--script", args.script])
    else:
        operator_dir = operator_root / arm
        operator_command = shlex.join([
            sys.executable, str(REPO_ROOT / "scripts" / "chat_operator.py"),
            "--dir", str(operator_dir), "--model", "arena-agent-mode",
            "--model-version", "unversioned",
        ])
        command.extend([
            "--provider", "command", "--command", operator_command,
            "--model", "arena-agent-mode", "--request-namespace", f"plot-{arm}",
        ])
    if not include_plot:
        command.append("--no-plot-memos")
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    run_dir = run_root / run_id
    detail = completed.stderr.strip() or completed.stdout.strip()
    if completed.returncode == 2 and "NEED RESPONSE" in detail:
        return {"status": "pending", "run_dir": str(run_dir), "detail": detail}
    if completed.returncode != 0:
        raise RuntimeError(f"{arm} Draft run failed ({completed.returncode}): {detail}")
    return {"status": "complete", "run_dir": str(run_dir)}


def _export_pending(operator_dir: Path) -> dict:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "relay_prompts.py"),
               "export", "--dir", str(operator_dir)]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"relay export failed for {operator_dir}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def _write_combined_prompts(out_dir: Path, operator_root: Path,
                            pending_keys: list[str]) -> Path:
    items: list[dict] = []
    done = 0
    for arm in pending_keys:
        op_dir = operator_root / arm
        if (op_dir / "requests").is_dir():
            items.extend(relay_prompts.pending(op_dir))
        if (op_dir / "responses").is_dir():
            done += len(list((op_dir / "responses").glob("*.json")))
    combined_path = out_dir / "PROMPTS.md"
    combined_path.write_text(
        relay_prompts.render_prompt_markdown(items, len(items), done),
        encoding="utf-8")
    return combined_path


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _pending_note(args, out_dir: Path, operator_root: Path,
                  pending: dict[str, dict]) -> str:
    blocks = []
    for arm, item in pending.items():
        operator_dir = operator_root / arm
        blocks.append(
            f"### {arm} arm\n\n"
            f"Pending requests: {item['pending']}. Copy `{operator_dir / 'relay' / 'PROMPTS.md'}` "
            "to the Arena chat. Save its tagged answers and ingest them with:\n\n"
            f"`{shlex.quote(sys.executable)} scripts/relay_prompts.py ingest "
            f"--dir {shlex.quote(str(operator_dir))} "
            "--file answers.txt --model arena-agent-mode --model-version unversioned`\n")
    resume_parts = [
        f"{shlex.quote(sys.executable)} scripts/run_plot_ablation.py",
        f"--id {shlex.quote(args.id)} --task {shlex.quote(args.task)}",
        f"--canon {shlex.quote(str(Path(args.canon).resolve()))}",
        f"--design-dir {shlex.quote(str(Path(args.design_dir).resolve()))}",
    ]
    if getattr(args, "prepare_shared", False):
        resume_parts.append("--prepare-shared")
    resume_parts.extend([
        f"--provider arena --seed {args.seed} --temperature {args.temperature}",
        f"--out {shlex.quote(str(Path(args.out).resolve()))}",
        f"--runs-root {shlex.quote(str(Path(args.runs_root).resolve()))}",
        f"--operator-root {shlex.quote(str(Path(args.operator_root).resolve()))} --resume",
    ])
    resume = " ".join(resume_parts)
    one_step_ingest = resume + " --ingest answers.txt"
    return (
        f"# Plot memo ablation: {args.id} — Arena responses pending\n\n"
        "No experiment result has been produced yet. Each arm has its own operator directory; "
        "keep its tagged answers with the matching arm.\n"
        f"Combined pending prompt bundle: `{out_dir / 'PROMPTS.md'}`.\n\n"
        + "\n".join(blocks)
        + "\nAfter ingesting the answers, rerun the same command to continue "
        "(or pass `--ingest answers.txt --resume` to ingest across arms/stages and advance in one command):\n\n"
        + "```sh\n" + resume + "\n# or in one step:\n" + one_step_ingest + "\n```\n"
    )


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


def _parse_ingest_payload(path: Path, map_entries: list[str]) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    tag_map: dict[str, str] = {}
    for entry in map_entries:
        if "=" not in entry:
            raise ValueError(f"--map expects FROM=TO, got {entry!r}")
        source, target = entry.split("=", 1)
        tag_map[source.strip()] = target.strip()

    errors = [
        {"tag": match.group(1), "reason": match.group(2).strip()}
        for match in relay_prompts.ERROR.finditer(text)
    ]
    if errors:
        raise ValueError(f"ingest file contains <<<ERROR>>> blocks: {errors}")

    answers: dict[str, str] = {}
    for match in relay_prompts.ANSWER.finditer(text):
        raw, body = match.group(1), match.group(2).strip()
        tag = tag_map.get(raw, raw)
        if tag in answers:
            raise ValueError(f"duplicate tag in ingest file: {tag}")
        if not body:
            raise ValueError(f"empty answer for tag: {tag}")
        answers[tag] = body

    if not answers:
        raise ValueError(f"no <<<ANSWER TAG>>> blocks found in {path}")
    return answers


def _ingest_matching_for_operators(operator_root: Path, answers: dict[str, str],
                                   consumed: set[str], *,
                                   only_pending: bool = False) -> int:
    newly_written = 0
    for name in ("shared_prep", "no_plot", "with_plot"):
        op_dir = operator_root / name
        if not (op_dir / "requests").is_dir():
            continue
        candidates = (relay_prompts.pending(op_dir) if only_pending
                      else relay_prompts.all_requests(op_dir))
        blocks = []
        matched_tags = []
        for item in candidates:
            tag = item["tag"]
            if tag in answers:
                if only_pending and tag in consumed:
                    continue
                blocks.append(f"<<<ANSWER {tag}>>>\n{answers[tag]}\n<<<END {tag}>>>")
                matched_tags.append(tag)
        if not blocks:
            continue
        summary = relay_prompts.ingest(
            op_dir, "\n\n".join(blocks),
            model="arena-agent-mode", model_version="unversioned")
        if summary["rejected"] or summary["errors"]:
            raise ValueError(f"relay ingest rejected in {op_dir}: {summary}")
        for tag in matched_tags:
            consumed.add(tag)
        newly_written += len(summary["written"])
    return newly_written


def _configs_compatible(saved: dict, current: dict, out_dir: Path) -> bool:
    for key in ("id", "task", "provider", "seed", "temperature"):
        if saved.get(key) != current.get(key):
            return False
    # If canon or design were already finalized when saved, their file trees must match.
    if saved.get("canon_files_sha256") and saved.get("canon_files_sha256") != current.get("canon_files_sha256"):
        return False
    if (not saved.get("prepare_shared") or saved.get("shared_prep_complete")) and saved.get("design_files_sha256"):
        if saved.get("design_files_sha256") != current.get("design_files_sha256"):
            return False
    # Check custom roots if they were not the bundle-local defaults.
    default_runs = str((out_dir / "attempts").resolve())
    default_op = str((out_dir / "relay" / current["id"]).resolve())
    if current["runs_root"] != default_runs and saved.get("runs_root") != current["runs_root"]:
        return False
    if current["operator_root"] != default_op and saved.get("operator_root") != current["operator_root"]:
        return False
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", required=True, help="safe experiment id used in run ids")
    parser.add_argument("--task", default="t01")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--canon", help="shared canon directory (required unless --prepare-shared or --resume)")
    parser.add_argument("--design-dir",
                        help="shared design directory with clean plot, scene and voice "
                             "(required unless --prepare-shared or --resume)")
    parser.add_argument("--prepare-shared", action="store_true",
                        help="prepare shared canon and design inside <out>/inputs before paired Draft")
    parser.add_argument("--provider", required=True, choices=["arena", "scripted"])
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT),
                        help="fixture path for scripted wiring tests only")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--out", required=True, help="new experiment output directory")
    parser.add_argument("--runs-root", default=None,
                        help="attempt-output root (default: <out>/attempts; persistent)")
    parser.add_argument("--operator-root", default=None,
                        help="Arena relay root (default: <out>/relay; persistent)")
    parser.add_argument("--resume", action="store_true",
                        help="resume a pending Arena relay using its existing operator responses")
    parser.add_argument("--ingest", default=None,
                        help="path to a file with <<<ANSWER TAG>>> blocks to ingest before running")
    parser.add_argument("--map", action="append", default=[], metavar="FROM=TO",
                        help="explicit tag remapping for --ingest (repeatable)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.id):
        parser.error("--id may contain only ASCII letters, digits, '.', '_' and '-'")
    if args.resume and args.provider != "arena":
        parser.error("--resume is only supported for the Arena relay")
    if args.ingest and args.provider != "arena":
        parser.error("--ingest is only supported for the Arena relay")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        task = load_tasks(args.tasks_file).get(args.task)
        scope = load_evaluation_scope()
    except (TaskError, EvaluationScopeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.provider == "arena" and scope.get("provider_constraint") != "arena-only":
        print("error: evaluation scope no longer permits the Arena-only runner", file=sys.stderr)
        return 2

    out_dir = Path(args.out).resolve()
    if _is_under_build(out_dir):
        print("error: --out must not be under build/ (scratch is not persisted)", file=sys.stderr)
        return 2
    if args.runs_root and _is_under_build(Path(args.runs_root)):
        print("error: --runs-root must not be under build/", file=sys.stderr)
        return 2
    if args.operator_root and _is_under_build(Path(args.operator_root)):
        print("error: --operator-root must not be under build/", file=sys.stderr)
        return 2

    ingest_answers: dict[str, str] | None = None
    if args.ingest:
        ingest_path = Path(args.ingest)
        if not ingest_path.is_file():
            print(f"error: no such ingest file: {ingest_path}", file=sys.stderr)
            return 2
        try:
            ingest_answers = _parse_ingest_payload(ingest_path, args.map)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    state_path = out_dir / "state.json"
    archived_inputs = out_dir / "inputs"
    archived_canon = archived_inputs / "canon"
    archived_design = archived_inputs / "design"

    if args.resume:
        if not state_path.is_file():
            print("error: --resume requires a saved pending experiment state", file=sys.stderr)
            return 2
        try:
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read resume state: {exc}", file=sys.stderr)
            return 2
        if saved_state.get("config", {}).get("prepare_shared"):
            args.prepare_shared = True
        # New runs are self-contained. For a legacy run without an archived
        # input bundle, require the original source paths and retain its old
        # behavior rather than silently rebuilding or substituting any input.
        if archived_canon.is_dir() and archived_design.is_dir():
            for supplied, archived, label in (
                    (args.canon, archived_canon, "canon"),
                    (args.design_dir, archived_design, "design")):
                if supplied:
                    supplied_path = Path(supplied).resolve()
                    if (supplied_path.is_dir() and _sha256_tree(archived)
                            and _sha256_tree(supplied_path) != _sha256_tree(archived)):
                        print(f"error: supplied {label} differs from the archived experiment input",
                              file=sys.stderr)
                        return 2
            canon_dir, design_dir = archived_canon, archived_design
        else:
            if not args.canon or not args.design_dir:
                print("error: this legacy run has no archived inputs; restore its original "
                      "--canon and --design-dir directories", file=sys.stderr)
                return 2
            canon_dir = Path(args.canon).resolve()
            design_dir = Path(args.design_dir).resolve()
    else:
        if out_dir.exists():
            print("error: output exists; choose a new experiment output directory", file=sys.stderr)
            return 2
        prospective_runs_root = (Path(args.runs_root).resolve() if args.runs_root
                                 else out_dir / "attempts")
        prospective_operator_base = (Path(args.operator_root).resolve()
                                     if args.operator_root else out_dir / "relay")
        if (prospective_runs_root / args.id).exists():
            print(f"error: runs directory already exists: {prospective_runs_root / args.id}",
                  file=sys.stderr)
            return 2
        if args.provider == "arena" and (prospective_operator_base / args.id).exists():
            print("error: Arena operator directory already exists: "
                  f"{prospective_operator_base / args.id}", file=sys.stderr)
            return 2
        if args.prepare_shared:
            canon_source = Path(args.canon).resolve() if args.canon else None
            design_source = Path(args.design_dir).resolve() if args.design_dir else None
            if canon_source is not None and not canon_source.is_dir():
                print(f"error: canon directory does not exist: {canon_source}", file=sys.stderr)
                return 2
            if design_source is not None and not design_source.is_dir():
                print(f"error: design directory does not exist: {design_source}", file=sys.stderr)
                return 2
            out_dir.mkdir(parents=True)
            archived_canon.mkdir(parents=True)
            archived_design.mkdir(parents=True)
            if canon_source is not None:
                _copy_tree_contents(canon_source, archived_canon)
            if design_source is not None:
                _copy_tree_contents(design_source, archived_design)
            canon_dir, design_dir = archived_canon, archived_design
        else:
            if not args.canon or not args.design_dir:
                print("error: --canon and --design-dir are required for a new experiment "
                      "(or pass --prepare-shared)", file=sys.stderr)
                return 2
            canon_source = Path(args.canon).resolve()
            design_source = Path(args.design_dir).resolve()
            for directory, label in ((canon_source, "canon"), (design_source, "design")):
                if not directory.is_dir():
                    print(f"error: {label} directory does not exist: {directory}", file=sys.stderr)
                    return 2
            out_dir.mkdir(parents=True)
            archived_inputs.mkdir(parents=True)
            shutil.copytree(canon_source, archived_canon)
            shutil.copytree(design_source, archived_design)
            canon_dir, design_dir = archived_canon, archived_design

    for directory, label in ((canon_dir, "canon"), (design_dir, "design")):
        if not directory.is_dir():
            print(f"error: {label} directory does not exist: {directory}", file=sys.stderr)
            return 2

    # Defaults place every artifact needed for a resume inside the experiment
    # bundle. Explicit roots remain available for tests and advanced workflows.
    runs_root = (Path(args.runs_root).resolve() if args.runs_root
                 else out_dir / "attempts")
    operator_base = (Path(args.operator_root).resolve() if args.operator_root
                     else out_dir / "relay")
    operator_root = operator_base / args.id
    run_root = runs_root / args.id
    args.canon = str(canon_dir)
    args.design_dir = str(design_dir)
    args.runs_root = str(runs_root)
    args.operator_root = str(operator_base)

    shared_ready = _is_shared_design_ready(canon_dir, design_dir)
    config = {
        "id": args.id, "task": args.task, "provider": args.provider,
        "seed": args.seed, "temperature": args.temperature,
        "canon_source": str(canon_dir), "design_source": str(design_dir),
        "canon_files_sha256": _sha256_tree(canon_dir),
        "design_files_sha256": _sha256_tree(design_dir),
        "runs_root": str(runs_root), "operator_root": str(operator_root),
    }
    if args.prepare_shared:
        config["prepare_shared"] = True
        config["shared_prep_complete"] = shared_ready

    if args.resume:
        state = saved_state
        if not _configs_compatible(state.get("config", {}), config, out_dir):
            print("error: resume settings or archived canon/design inputs changed",
                  file=sys.stderr)
            return 2
        if state.get("completed") or (out_dir / "results.json").exists():
            print("error: this ablation is already complete", file=sys.stderr)
            return 2
    else:
        if run_root.exists():
            print(f"error: runs directory already exists: {run_root}", file=sys.stderr)
            return 2
        if args.provider == "arena" and operator_root.exists():
            print(f"error: Arena operator directory already exists: {operator_root}",
                  file=sys.stderr)
            return 2
        state = {"config": config, "attempts": 0, "attempt_history": [], "completed": False}
        _save_json(state_path, state)

    consumed_tags: set[str] = set()
    if ingest_answers is not None:
        try:
            _ingest_matching_for_operators(
                operator_root, ingest_answers, consumed_tags, only_pending=False)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        while True:
            attempt = int(state.get("attempts", 0)) + 1
            state["attempts"] = attempt
            _save_json(state_path, state)

            shared_ready = _is_shared_design_ready(canon_dir, design_dir)
            if not shared_ready:
                if not args.prepare_shared:
                    raise RuntimeError(
                        "shared canon/design is incomplete and --prepare-shared was not enabled")
                prep_outcome = _run_shared_prep(
                    args, canon_dir, design_dir, run_root, operator_root, attempt)
                state["config"]["canon_files_sha256"] = _sha256_tree(canon_dir)
                state["config"]["design_files_sha256"] = _sha256_tree(design_dir)
                if prep_outcome["status"] == "pending":
                    state["attempt_history"].append(
                        {"attempt": attempt, "shared_prep": prep_outcome, "arms": {}})
                    _save_json(state_path, state)
                    if ingest_answers is not None:
                        newly = _ingest_matching_for_operators(
                            operator_root, ingest_answers, consumed_tags, only_pending=True)
                        if newly > 0:
                            continue
                        unmatched = sorted(set(ingest_answers) - consumed_tags)
                        if unmatched:
                            print(f"error: unknown tag(s) in ingest file: {', '.join(unmatched)}",
                                  file=sys.stderr)
                            return 1
                    exported = _export_pending(operator_root / "shared_prep")
                    combined_md = _write_combined_prompts(
                        out_dir, operator_root, ["shared_prep"])
                    progress = {
                        "status": "waiting_for_arena_responses",
                        "stage": f"shared_prep:{prep_outcome['stage']}",
                        "experiment_id": args.id,
                        "attempt": attempt,
                        "shared_prep": prep_outcome,
                        "arms": {},
                        "prompts_markdown": str(combined_md),
                        "relay": {
                            "shared_prep": {
                                "pending": exported["pending"],
                                "prompts": str(operator_root / "shared_prep" / "relay" / "PROMPTS.md"),
                                "operator_dir": str(operator_root / "shared_prep"),
                            }
                        },
                    }
                    _save_json(out_dir / "progress.json", progress)
                    (out_dir / "note.md").write_text(
                        _pending_note(args, out_dir, operator_root,
                                      {"shared_prep": exported}),
                        encoding="utf-8")
                    print(json.dumps({
                        "status": progress["status"],
                        "stage": progress["stage"],
                        "progress": str(out_dir / "progress.json"),
                        "note": str(out_dir / "note.md"),
                        "prompts": str(combined_md),
                        "relay": progress["relay"],
                    }, ensure_ascii=False, indent=2))
                    return 3

                state["config"]["shared_prep_complete"] = True
                _save_json(state_path, state)

            arms_runs: dict[str, Path] = {}
            arm_status: dict[str, dict] = {}
            for arm, include_plot in (("no_plot", False), ("with_plot", True)):
                outcome = _run_pipeline(
                    args, arm, include_plot, run_root / arm,
                    operator_root, attempt)
                arm_status[arm] = outcome
                arms_runs[arm] = Path(outcome["run_dir"])
            attempt_entry = {"attempt": attempt, "arms": arm_status}
            state["attempt_history"].append(attempt_entry)
            _save_json(state_path, state)

            pending_exports = {}
            if args.provider == "arena":
                for arm, outcome in arm_status.items():
                    if outcome["status"] == "pending":
                        pending_exports[arm] = _export_pending(operator_root / arm)
            if pending_exports:
                if ingest_answers is not None:
                    newly = _ingest_matching_for_operators(
                        operator_root, ingest_answers, consumed_tags, only_pending=True)
                    if newly > 0:
                        continue
                    unmatched = sorted(set(ingest_answers) - consumed_tags)
                    if unmatched:
                        print(f"error: unknown tag(s) in ingest file: {', '.join(unmatched)}",
                              file=sys.stderr)
                        return 1
                combined_md = _write_combined_prompts(
                    out_dir, operator_root, list(pending_exports.keys()))
                progress = {
                    "status": "waiting_for_arena_responses",
                    "experiment_id": args.id,
                    "attempt": attempt,
                    "arms": arm_status,
                    "prompts_markdown": str(combined_md),
                    "relay": {
                        arm: {"pending": value["pending"],
                              "prompts": str(operator_root / arm / "relay" / "PROMPTS.md"),
                              "operator_dir": str(operator_root / arm)}
                        for arm, value in pending_exports.items()
                    },
                }
                _save_json(out_dir / "progress.json", progress)
                (out_dir / "note.md").write_text(
                    _pending_note(args, out_dir, operator_root, pending_exports),
                    encoding="utf-8")
                print(json.dumps({"status": progress["status"],
                                  "progress": str(out_dir / "progress.json"),
                                  "note": str(out_dir / "note.md"),
                                  "prompts": str(combined_md),
                                  "relay": progress["relay"]}, ensure_ascii=False, indent=2))
                return 3

            if ingest_answers is not None:
                unmatched = sorted(set(ingest_answers) - consumed_tags)
                if unmatched:
                    print(f"error: unknown tag(s) in ingest file: {', '.join(unmatched)}",
                          file=sys.stderr)
                    return 1
            break

        runs = arms_runs
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

        eval_root = out_dir / "l1" / f"attempt-{attempt:02d}"
        evals = {}
        for arm, path in runs.items():
            evals[arm] = _evaluate_l1(path, eval_root / arm)
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
                    eval_root / arm / "evaluation.json", task),
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
        is_fixture = args.provider == "scripted"
        results = {
            "schema": "plot-memo-ablation-l1-v1",
            "experiment_id": args.id,
            "scope": ("scripted fixture wiring check only; not a model experiment"
                      if is_fixture else "Arena × L1 exploratory reference only"),
            "target": "Plot-SKILL-derived memo handoff only; not overall SKILL efficacy",
            "evaluation_scope": {"provider_constraint": "arena-only",
                                  "l2": "frozen_not_measured", "l3": "frozen_not_measured"},
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
                      and all(row.get("model_version") and
                              not str(row["model_version"]).startswith("unversioned")
                              for row in response_models["with_plot"].values()),
                      "by_request": response_models["with_plot"]},
            "prompt_control": {
                "ch01_diff_only_plot_memo_lines": True,
                "later_chapter_prompts": "may differ through prior-chapter text; downstream mediation",
            },
            "arms": arms,
            "paired_l1_deltas": {
                name: {"without_plot": a, "with_plot": b,
                       "delta_with_minus_without": _delta(a, b)}
                for name, (a, b) in metric_pairs.items()
            },
            "l1_evaluation_dirs": {arm: str(eval_root / arm) for arm in evals},
        }
        _save_json(out_dir / "results.json", results)
        (out_dir / "note.md").write_text(_note(results), encoding="utf-8")
        state["completed"] = True
        state["completed_attempt"] = attempt
        _save_json(state_path, state)
        _save_json(out_dir / "progress.json", {
            "status": "completed", "experiment_id": args.id,
            "attempt": attempt,
            "arms": {arm: {"status": "complete", "run_dir": str(path)}
                     for arm, path in runs.items()},
        })
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"status": "completed", "results": str(out_dir / "results.json"),
                      "note": str(out_dir / "note.md"), "model": results["model"],
                      "g5": results["g5"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
