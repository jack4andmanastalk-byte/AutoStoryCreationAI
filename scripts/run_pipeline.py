#!/usr/bin/env python3
"""Run the Plan step of the generation pipeline for one frozen task.

    python3 scripts/run_pipeline.py --task t01 \
        --provider scripted --script benchmarks/protocol-v1/fixtures/plan-demo.json \
        --out runs

The run directory holds the manifest (model, prompt hashes, git commit), the
prompt/response pairs, the brief and the canon. ``runs/`` is git-ignored: what
gets committed is an experiment note that points at this manifest.

Exit codes: 0 ok, 1 the plan was produced but the canon could not satisfy the
audit, 2 bad input or provider failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    CommandProvider, PlanError, ProviderError, RunLedger, ScriptedProvider,
    TaskError, build_plan, canon_coverage, load_scripted_responses, load_tasks,
)
from asc.story.canon import CanonError, load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, help="task id, e.g. t01")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--system", default="s1", choices=["s0", "s1", "s2", "s3"])
    parser.add_argument("--provider", default="scripted", choices=["scripted", "command"])
    parser.add_argument("--script", default=str(
        REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"),
        help="scripted responses (used with --provider scripted)")
    parser.add_argument("--command", help="external judge/provider command (with --provider command)")
    parser.add_argument("--model", default=None, help="model name recorded in the manifest")
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(REPO_ROOT / "runs"), help="run root directory")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--text", default=None,
                        help="optional chapter directory to audit against the new canon")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        tasks = load_tasks(args.tasks_file)
        task = tasks.get(args.task)
    except (TaskError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.provider == "command":
        if not args.command:
            print("error: --provider command requires --command", file=sys.stderr)
            return 2
        provider = CommandProvider(args.command, model=args.model or "external")
    else:
        try:
            responses = load_scripted_responses(args.script)
        except (ProviderError, OSError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        provider = ScriptedProvider(responses)

    try:
        ledger = RunLedger.create(
            args.out, task_id=task.id, system=args.system, seed=args.seed,
            protocol_version=tasks.protocol, run_id=args.run_id,
            model=args.model or provider.model, provider=provider.name,
            temperature=args.temperature,
        )
    except FileExistsError:
        print(f"error: run already exists: {args.out}", file=sys.stderr)
        return 2

    try:
        plan = build_plan(
            task, provider, ledger, chapters=tasks.chapters,
            target_chars=tasks.target_chars, temperature=args.temperature,
            seed=args.seed,
        )
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"run: {ledger.path}", file=sys.stderr)
        return 2

    canon = load_canon(ledger.path / "canon")
    coverage = canon_coverage(canon)
    summary: dict = {
        "run_id": ledger.run_id,
        "run_dir": str(ledger.path),
        "task": task.as_dict(),
        "attempts": plan.attempts,
        "canon": {
            "characters": len(canon.characters),
            "facts": len(canon.facts),
            "locations": len(canon.locations),
            "chapters": len(canon.chapters),
            "foreshadowing": len(canon.foreshadowing),
        },
        "checks_covered": f"{len(coverage['met'])}/{coverage['total']}",
        "checks_missing": coverage["missing"],
        "status": "ok" if not coverage["missing"] else "incomplete",
    }

    if args.text:
        try:
            report = audit_texts(ledger.path / "canon", args.text)
        except (CanonError, OSError) as exc:
            print(f"error: audit failed: {exc}", file=sys.stderr)
            return 2
        ledger.write_json("audit.json", report)
        summary["audit"] = {
            "violations": report["summary"]["violations"],
            "checks_skipped": report["summary"]["checks_skipped"],
            "ced_per_10k_chars": report["summary"]["ced_per_10k_chars"],
        }

    ledger.write_json("plan-summary.json", summary)
    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
