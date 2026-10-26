#!/usr/bin/env python3
"""Check a Stage A structured game log against canon and design.

    python3 scripts/check_gamelog.py \\
        --game-log experiments/2026-10-trpg-slice-t01/inputs/game_log.json \\
        --canon experiments/2026-10-trpg-slice-t01/inputs/canon \\
        --design-dir experiments/2026-10-trpg-slice-t01/inputs/design

Without --design-dir, the plot/scene alignment check is reported as skipped.
Exit status: 0 = no finding at or above ``--fail-on``, 1 = finding found,
2 = an input file could not be loaded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog import (  # noqa: E402
    GameLogError, check_game_log_files, render_gamelog_markdown,
)
from asc.story.canon import CanonError  # noqa: E402

SEVERITY_RANK = {"none": 99, "low": 2, "medium": 1, "high": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-log", required=True, help="game_log.json path")
    parser.add_argument("--canon", required=True, help="canon directory")
    parser.add_argument("--design-dir", default=None,
                        help="design directory with plot.json and scene.json")
    parser.add_argument("--require-design", action="store_true",
                        help="fail (exit 2) when plot.json / scene.json are missing")
    parser.add_argument("--out", help="write the full JSON report here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"],
                        default="high",
                        help="exit 1 when a finding this severe is found (default: high)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = check_game_log_files(
            args.game_log, args.canon, args.design_dir,
            require_design=args.require_design)
    except (GameLogError, CanonError, OSError, ValueError) as exc:
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
        path.write_text(render_gamelog_markdown(report) + "\n", encoding="utf-8")

    if not args.quiet:
        print(json.dumps({
            "summary": report["summary"],
            "checks": [{"id": c["id"], "status": c["status"],
                        "findings": c["findings"]} for c in report["checks"]],
            "findings": [{"check": f["check"], "severity": f["severity"],
                          "message_ja": f["message_ja"]}
                         for f in report["findings"]],
        }, ensure_ascii=False, indent=2))

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    worst = min((SEVERITY_RANK.get(f["severity"], 99) for f in report["findings"]),
                default=99)
    return 1 if worst <= threshold else 0


if __name__ == "__main__":
    raise SystemExit(main())
