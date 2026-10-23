#!/usr/bin/env python3
"""Audit a story against its canon and write a continuity report.

Examples
--------
    python3 scripts/audit_continuity.py \
        --canon harness/cases/demo/canon \
        --text harness/cases/demo/text \
        --out build/audit/demo.json \
        --ledger build/audit/demo-ledger.json \
        --markdown build/audit/demo.md

Exit status: 0 = no violation at or above ``--fail-on``, 1 = violation found,
2 = the canon or the text could not be loaded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.story.canon import CanonError  # noqa: E402
from asc.story.continuity import audit_texts, render_markdown, write_report  # noqa: E402

SEVERITY_RANK = {"none": 99, "low": 2, "medium": 1, "high": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canon", required=True, help="canon directory")
    parser.add_argument("--text", required=True, help="chapter directory (*.md / *.txt)")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--ledger", help="write the state ledger here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="high",
                        help="exit 1 when a violation this severe is found (default: high)")
    parser.add_argument("--quiet", action="store_true", help="do not print the report")
    args = parser.parse_args(argv)

    try:
        report = audit_texts(args.canon, args.text)
    except CanonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        write_report(report, args.out, args.ledger)
    elif args.ledger:
        path = Path(args.ledger)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report["ledger"], ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report) + "\n", encoding="utf-8")

    if not args.quiet:
        print(json.dumps({"summary": report["summary"],
                          "violations": [{"type": v["type"], "severity": v["severity"],
                                          "chapter": v["chapter"], "subject": v["subject"]}
                                         for v in report["violations"]]},
                         ensure_ascii=False, indent=2))

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    worst = min((SEVERITY_RANK.get(v["severity"], 99) for v in report["violations"]), default=99)
    return 1 if worst <= threshold else 0


if __name__ == "__main__":
    raise SystemExit(main())
