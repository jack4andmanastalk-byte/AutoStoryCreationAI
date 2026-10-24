#!/usr/bin/env python3
"""Check a relationship web for structural defects (seed-05 relationship-web).

    python3 scripts/check_relation.py \\
        --relations harness/cases/relation-demo/relations.yaml \\
        --canon harness/cases/demo/canon

Without --canon, the id/fact/chapter cross-references are weakened.
Exit status: 0 = no finding at or above ``--fail-on``, 1 = finding found,
2 = the relation file or the canon could not be loaded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.relation import (  # noqa: E402
    RelationDocError, check_relations, load_relations, render_markdown,
)
from asc.story.canon import CanonError, load_canon  # noqa: E402

SEVERITY_RANK = {"none": 99, "low": 2, "medium": 1, "high": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--relations", required=True,
                        help="relations.yaml/json file or directory")
    parser.add_argument("--canon", help="canon directory for cross-references (optional)")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"],
                        default="medium",
                        help="exit 1 when a finding this severe is found (default: medium)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        doc = load_relations(args.relations)
        canon = load_canon(args.canon) if args.canon else None
        report = check_relations(doc, canon)
    except (RelationDocError, CanonError, OSError) as exc:
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
