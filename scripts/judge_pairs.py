#!/usr/bin/env python3
"""Run an L2 judge over blind pairs (the L2 half of L3 calibration).

    python3 scripts/judge_pairs.py --pairs build/pairs/latest/pairs \\
        --judge-command "python3 scripts/judge_adapter.py --llm-command '...'" \\
        --out build/pairs/latest/verdicts.json

Each pair is judged twice (A/B and B/A); a judge that picks the same position
twice is treated as a tie (see ``asc.evaluation.judge.compare_pairwise``).
The verdicts feed ``scripts/calibrate_judge.py`` alongside human labels.

Exit status: 0 ok, 2 bad input or judge failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.judge import (  # noqa: E402
    CommandJudge, JudgeError, compare_pairwise,
)
from asc.evaluation.rubric import load_rubric  # noqa: E402

DEFAULT_RUBRIC = REPO_ROOT / "harness" / "rubrics" / "story-quality-v0.yaml"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pairs", required=True, help="pairs directory (pair-*.json)")
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--judge-command", required=True,
                        help="external command implementing the judge JSON protocol")
    parser.add_argument("--out", required=True, help="write verdicts.json here")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    pairs_dir = Path(args.pairs)
    files = sorted(pairs_dir.glob("pair-*.json")) if pairs_dir.is_dir() else []
    if not files:
        print(f"error: no pair files in {args.pairs}", file=sys.stderr)
        return 2
    try:
        rubric = load_rubric(args.rubric)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    judge = CommandJudge(args.judge_command)
    verdicts: dict[str, dict] = {}
    try:
        for path in files:
            pair = json.loads(path.read_text(encoding="utf-8"))
            result = compare_pairwise(
                judge, pair["a"], pair["b"], rubric,
                context={"pair_id": pair.get("pair_id", path.stem)})
            verdicts[pair.get("pair_id", path.stem)] = result
    except (OSError, ValueError, JudgeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    if not args.quiet:
        biased = sum(1 for v in verdicts.values() if v["position_bias"])
        print(json.dumps({"pairs": len(verdicts), "position_bias": biased},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
