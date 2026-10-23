#!/usr/bin/env python3
"""Compare human labels and judge verdicts over the same blind pairs.

    python3 scripts/calibrate_judge.py --labels build/pairs/latest/judgements \\
        --verdicts build/pairs/latest/verdicts.json --out build/pairs/latest/agreement.json

Labels: ``judgements/<rater_id>/<pair_id>.json`` (or one file with items).
Verdicts: ``{pair_id: {winner, ...}}`` from ``scripts/judge_pairs.py``.
Reports rater-vs-rater kappa and judge-vs-majority agreement.

Exit status: 0 ok, 2 bad input. A low kappa is a finding, not an error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.calibration import (  # noqa: E402
    CalibrationError, judge_agreement, load_judgements, rater_agreement,
    render_markdown,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", required=True,
                        help="judgements directory or a single labels file")
    parser.add_argument("--verdicts", help="verdicts.json from judge_pairs.py (optional)")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        labels = load_judgements(args.labels)
        report: dict = {"raters": rater_agreement(labels)}
        if args.verdicts:
            raw = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
            verdicts = {k: (v.get("winner", "") if isinstance(v, dict) else v)
                        for k, v in raw.items()}
            report["judge"] = judge_agreement(labels, verdicts)
    except (CalibrationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    if args.markdown:
        target = Path(args.markdown)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_markdown(report) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
