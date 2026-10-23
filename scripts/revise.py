#!/usr/bin/env python3
"""Drive the revision loop in three explicit steps (seed-10 revision-loop).

    # 1. findings -> critique note with fix directions
    python3 scripts/revise.py --mode plan --audit build/audit.json \\
        --out build/critique.json

    # 2. apply an explicit patch (human or model wrote the replacements)
    python3 scripts/revise.py --mode apply --text manuscript/ \\
        --patch build/patch.json --out revised/ --report build/apply.json

    # 3. compare before/after and detect repeats
    python3 scripts/revise.py --mode compare --before audit-before.json \\
        --after audit-after.json --out build/comparison.json

Exit status: 0 ok (compare: no persisting medium+ finding), 1 compare found a
persisting medium+ finding, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.revision import (  # noqa: E402
    apply_patches, compare_reports, load_json, render_markdown,
)
from asc.story.canon import CanonError  # noqa: E402


def _write(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True, choices=["plan", "apply", "compare"])
    parser.add_argument("--audit", help="plan: continuity report (JSON)")
    parser.add_argument("--voice", help="plan: voice report (JSON, optional)")
    parser.add_argument("--text", help="apply: chapter directory")
    parser.add_argument("--patch", help="apply: patch file (JSON)")
    parser.add_argument("--report", help="apply: write the apply report here")
    parser.add_argument("--before", help="compare: report before the revision")
    parser.add_argument("--after", help="compare: report after the revision")
    parser.add_argument("--out", help="write the JSON result here (all modes)")
    parser.add_argument("--markdown", help="compare: write a Markdown summary here")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    # Import here so --help works without the dependency chain.
    from asc.revision import plan_round  # noqa: E402

    try:
        if args.mode == "plan":
            if not args.audit:
                print("error: --mode plan requires --audit", file=sys.stderr)
                return 2
            voice = load_json(args.voice) if args.voice else None
            result = plan_round(load_json(args.audit), voice)
            _write(args.out, result)
            summary = result["summary"]
        elif args.mode == "apply":
            if not args.text or not args.patch or not args.out:
                print("error: --mode apply requires --text, --patch and --out",
                      file=sys.stderr)
                return 2
            result = apply_patches(args.text, load_json(args.patch), args.out)
            _write(args.report, result)
            summary = result["summary"]
        else:
            if not args.before or not args.after:
                print("error: --mode compare requires --before and --after",
                      file=sys.stderr)
                return 2
            result = compare_reports(load_json(args.before), load_json(args.after))
            _write(args.out, result)
            if args.markdown:
                target = Path(args.markdown)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(render_markdown(result) + "\n", encoding="utf-8")
            summary = result["summary"]
    except (OSError, ValueError, CanonError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.mode == "compare":
        return 1 if summary["persisting_medium_plus"] else 0
    if args.mode == "apply":
        return 1 if summary["failed"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
