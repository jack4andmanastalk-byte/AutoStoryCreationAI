#!/usr/bin/env python3
"""Run the evaluation harness over a story and write a report.

The three layers are independent: L1 always runs, L2 runs only when a judge is
configured, L3 only when human labels are supplied. Nothing is collapsed into a
single score.

Examples
--------
    # L1 only (deterministic, offline)
    python3 scripts/run_evaluation.py \
        --candidate harness/cases/demo/text \
        --canon harness/cases/demo/canon \
        --rubric harness/rubrics/story-quality-v0.yaml \
        --patterns harness/patterns.yaml \
        --out build/eval/demo

    # replay recorded judgements (offline, no tokens)
    ... --judge-fixture harness/fixtures/judgements-demo.json

    # a real model through any CLI that speaks the JSON protocol
    ... --judge-command "python3 my_judge.py"

Exit status: 0 = all gates pass, 1 = a gate failed, 2 = input error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.harness import evaluate  # noqa: E402
from asc.evaluation.judge import CommandJudge, FixtureJudge, JudgeError  # noqa: E402
from asc.evaluation.rubric import RubricError  # noqa: E402
from asc.story.canon import CanonError  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate", required=True, help="chapter directory to evaluate")
    parser.add_argument("--baseline", help="chapter directory to compare against")
    parser.add_argument("--canon", help="canon directory (enables the L1 continuity audit)")
    parser.add_argument("--rubric", default=str(REPO_ROOT / "harness" / "rubrics"
                                               / "story-quality-v0.yaml"))
    parser.add_argument("--patterns", default=str(REPO_ROOT / "harness" / "patterns.yaml"))
    parser.add_argument("--judge-command", help="external command implementing the JSON protocol")
    parser.add_argument("--judge-fixture", help="replay recorded judgements from this JSON file")
    parser.add_argument("--human-labels", help="human pairwise labels (JSON)")
    parser.add_argument("--out", help="output directory (evaluation.json, report.md)")
    parser.add_argument("--allow-length-gap", action="store_true",
                        help="run the pairwise comparison even when lengths differ by >25%")
    parser.add_argument("--regression-margin", type=float, default=0.0,
                        help="tolerance before a metric change counts as a regression")
    parser.add_argument("--report-only", action="store_true",
                        help="always exit 0 and print the gate status (for demos and docs)")
    args = parser.parse_args(argv)

    judge = None
    if args.judge_command:
        judge = CommandJudge(args.judge_command)
    elif args.judge_fixture:
        judge = FixtureJudge(args.judge_fixture)

    try:
        results = evaluate(
            args.candidate,
            canon_dir=args.canon,
            baseline_dir=args.baseline,
            rubric_path=args.rubric if judge else None,
            patterns_path=args.patterns,
            judge=judge,
            human_labels=args.human_labels,
            out_dir=args.out,
            allow_length_gap=args.allow_length_gap,
            regression_margin=args.regression_margin,
        )
    except (CanonError, RubricError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except JudgeError as exc:
        print(f"judge error: {exc}", file=sys.stderr)
        return 2

    summary = {
        "status": results["status"],
        "gates": {g["id"]: g["status"] for g in results["gates"]},
        "l1": {
            "chars": results["l1"]["metrics"]["chars"],
            "dialogue_ratio": results["l1"]["metrics"]["dialogue_ratio"],
            "ced_per_10k_chars": results["l1"]["densities"]["ced_per_10k_chars"],
            "forbidden": len(results["l1"]["forbidden"]),
        },
        "l2": results["l2"]["status"],
        "tickets": len(results["tickets"]),
    }
    import json
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report_only:
        return 0
    return 0 if results["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
