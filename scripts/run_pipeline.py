#!/usr/bin/env python3
"""Run the generation pipeline for one frozen task.

    # S1: premise -> canon -> three chapters, then audit
    python3 scripts/run_pipeline.py --task t01 --system s1 \
        --provider scripted --script benchmarks/protocol-v1/fixtures/plan-demo.json \
        --out runs

    # S0: the same premise with a single prompt and no canon (the baseline)
    python3 scripts/run_pipeline.py --task t01 --system s0 --provider scripted \
        --script benchmarks/protocol-v1/fixtures/draft-baseline-demo.json --out runs

Every run writes ``runs/<run_id>/`` with the manifest (model, prompt hashes, git
commit, protocol version), the prompt/response pairs, and the artifacts. ``runs/``
is git-ignored; what gets committed is an experiment note that points at it.

Exit codes: 0 ok, 1 artifacts produced but the protocol gates are not met,
2 bad input or provider failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    CommandProvider, DraftError, PlanError, ProviderError, RevisionError, RunLedger,
    ScriptedProvider, TaskError, VoicePassError, build_plan, build_revision,
    build_story, build_voice_pass, canon_coverage, load_scripted_responses,
    load_tasks,
)
from asc.story.canon import CanonError, load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
DEFAULT_SCRIPT = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, help="task id, e.g. t01")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--system", default="s1", choices=["s0", "s1", "s2", "s3"],
                        help="s0 = single prompt, s1 = canon + chapters")
    parser.add_argument("--stage", default="all", choices=["plan", "draft", "all"])
    parser.add_argument("--provider", default="scripted", choices=["scripted", "command"])
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT))
    parser.add_argument("--command", help="external provider command (with --provider command)")
    parser.add_argument("--canon", help="reuse an existing canon instead of planning")
    parser.add_argument("--max-rounds", type=int, default=1,
                        help="revision rounds for s2/s3 (default: 1)")
    parser.add_argument("--voice", default=None,
                        help="voice.yaml for the s3 voice pass "
                             "(default: a generic guide)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--temperature", type=float, default=None,
                        help="default: 0.6 for planning, 0.8 for drafting")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(REPO_ROOT / "runs"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                        help="always exit 0 and report the gates (for demos and docs)")
    return parser.parse_args(argv)


def _measure_text_dir(text_dir: Path, task) -> dict:
    """Chars and must_include hits of the final text (after revise/voice)."""
    import re

    bodies = []
    for path in sorted(text_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            bodies.append(path.read_text(encoding="utf-8"))
    joined = "\n\n".join(bodies)
    chars = len(re.sub(r"\s", "", re.sub(r"\{\{[^{}]*\}\}", "", joined)))
    hits = {term: term in joined for term in task.must_include}
    return {"chars": chars,
            "must_include": {"hits": hits, "rate": round(
                sum(hits.values()) / len(hits), 3) if hits else 1.0}}


def make_provider(args: argparse.Namespace):
    if args.provider == "command":
        if not args.command:
            raise ProviderError("--provider command requires --command")
        return CommandProvider(args.command, model=args.model or "external")
    return ScriptedProvider(load_scripted_responses(args.script))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        tasks = load_tasks(args.tasks_file)
        task = tasks.get(args.task)
    except (TaskError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.system == "s0" and args.stage == "plan":
        print("error: s0 has no plan stage (the baseline gets no canon)", file=sys.stderr)
        return 2

    try:
        provider = make_provider(args)
    except (ProviderError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    temperature = args.temperature if args.temperature is not None else (
        0.6 if args.stage == "plan" else 0.8)

    try:
        ledger = RunLedger.create(
            args.out, task_id=task.id, system=args.system, seed=args.seed,
            protocol_version=tasks.protocol, run_id=args.run_id,
            model=args.model or provider.model, provider=provider.name,
            temperature=temperature,
        )
    except FileExistsError:
        print(f"error: run already exists: {args.out}", file=sys.stderr)
        return 2

    summary: dict = {
        "run_id": ledger.run_id,
        "run_dir": str(ledger.path),
        "task": task.id,
        "system": args.system,
        "stage": args.stage,
    }
    canon = None

    # -- plan -------------------------------------------------------------
    if args.system != "s0" and args.stage in {"plan", "all"}:
        if args.canon:
            try:
                canon = load_canon(args.canon)
            except CanonError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        else:
            try:
                plan = build_plan(
                    task, provider, ledger, chapters=tasks.chapters,
                    target_chars=tasks.target_chars, temperature=temperature,
                    seed=args.seed,
                )
            except PlanError as exc:
                print(f"error: {exc}", file=sys.stderr)
                print(f"run: {ledger.path}", file=sys.stderr)
                return 2
            summary["plan"] = {"attempts": plan.attempts}
            canon = load_canon(ledger.path / "canon")

        coverage = canon_coverage(canon)
        summary["canon"] = {
            "characters": len(canon.characters),
            "facts": len(canon.facts),
            "locations": len(canon.locations),
            "chapters": len(canon.chapters),
            "foreshadowing": len(canon.foreshadowing),
            "checks_covered": f"{len(coverage['met'])}/{coverage['total']}",
            "checks_missing": coverage["missing"],
        }

    # -- draft ------------------------------------------------------------
    if args.stage in {"draft", "all"}:
        if args.system != "s0" and canon is None:
            print("error: drafting without a canon requires --system s0 "
                  "or a canon from the plan stage", file=sys.stderr)
            return 2
        try:
            draft = build_story(
                task, provider, ledger, canon=canon, chapters=tasks.chapters,
                temperature=temperature, seed=args.seed,
            )
        except DraftError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(f"run: {ledger.path}", file=sys.stderr)
            return 2
        summary["draft"] = draft.as_dict()
        summary["chars"] = draft.chars

    # -- revise (s2/s3) -----------------------------------------------------
    if args.system in {"s2", "s3"} and args.stage in {"draft", "all"}:
        if canon is None:
            print("error: revision requires a canon (plan first, or --canon)",
                  file=sys.stderr)
            return 2
        try:
            revision = build_revision(
                task, provider, ledger, canon, temperature=temperature,
                seed=args.seed, max_rounds=args.max_rounds,
            )
        except RevisionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(f"run: {ledger.path}", file=sys.stderr)
            return 2
        summary["revision"] = revision.as_dict()

    # -- voice (s3) ---------------------------------------------------------
    if args.system == "s3" and args.stage in {"draft", "all"}:
        try:
            voice = build_voice_pass(
                task, provider, ledger, canon, voice_path=args.voice,
                temperature=temperature, seed=args.seed,
            )
        except (VoicePassError, ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(f"run: {ledger.path}", file=sys.stderr)
            return 2
        summary["voice"] = voice.as_dict()

    # -- final text stats (s2/s3 rewrite the draft, so re-measure) --------
    if "draft" in summary and args.system in {"s2", "s3"}:
        summary["final"] = _measure_text_dir(ledger.path / "text", task)

    # -- audit (always against the final text) ------------------------------
    if canon is not None and args.stage in {"draft", "all"}:
        report = audit_texts(ledger.path / "canon", ledger.path / "text")
        ledger.write_json("audit.json", report)
        summary["audit"] = {
            "violations": report["summary"]["violations"],
            "by_severity": report["summary"]["by_severity"],
            "checks_skipped": report["summary"]["checks_skipped"],
            "ced_per_10k_chars": report["summary"]["ced_per_10k_chars"],
        }

    # -- gates ------------------------------------------------------------
    gates: dict[str, bool] = {}
    text_stats = summary.get("final", summary.get("draft"))
    if text_stats is not None:
        gates["must_include"] = text_stats["must_include"]["rate"] >= 1.0
        gates["length"] = text_stats["chars"] >= tasks.target_chars[0]
    if "audit" in summary:
        gates["no_high_severity"] = summary["audit"]["by_severity"].get("high", 0) == 0
        gates["all_checks_ran"] = summary["audit"]["checks_skipped"] == 0
    summary["gates"] = gates
    summary["status"] = "pass" if all(gates.values()) or not gates else "fail"

    ledger.write_json("run-summary.json", summary)
    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.report_only:
        return 0
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
