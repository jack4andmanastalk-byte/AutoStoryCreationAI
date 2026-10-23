#!/usr/bin/env python3
"""Check a premise brief for structural defects (seed-01 premise-brief).

    python3 scripts/check_brief.py --brief harness/cases/brief-demo/brief.yaml

The checker only verifies form: one-sentence logline, declared elements,
contrast-shaped theme, grounded similar works, testable prohibitions and
question-shaped failure hypotheses. It never judges whether the premise is
good. Exit status: 0 = no finding at or above ``--fail-on``, 1 = finding
found, 2 = the brief could not be loaded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.brief import BriefError, check_brief, load_brief, render_markdown  # noqa: E402

SEVERITY_RANK = {"none": 99, "low": 2, "medium": 1, "high": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brief", required=True, help="brief.yaml/json file or directory")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"],
                        default="medium",
                        help="exit 1 when a finding this severe is found (default: medium)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = check_brief(load_brief(args.brief))
    except (BriefError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report) + "\n", encoding="utf-8")

    if not args.quiet:
        print(json.dumps({"summary": report["summary"], "findings": [
            {"check": f["check"], "severity": f["severity"],
             "message_ja": f["message_ja"]} for f in report["findings"]]},
            ensure_ascii=False, indent=2))

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    worst = min((SEVERITY_RANK.get(f["severity"], 99) for f in report["findings"]),
                default=99)
    return 1 if worst <= threshold else 0


if __name__ == "__main__":
    raise SystemExit(main())
