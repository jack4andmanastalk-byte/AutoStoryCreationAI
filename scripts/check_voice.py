#!/usr/bin/env python3
"""Check a manuscript against its voice specification (seed-09 voice-style).

    python3 scripts/check_voice.py --voice harness/cases/voice-demo/voice.yaml \\
        --text harness/cases/voice-demo/text

Pattern hits are capped at medium (they say *look here*, never *this is
wrong*); drift against the fixed sample is low (informational). Exit status:
0 = no finding at or above ``--fail-on``, 1 = finding found,
2 = the voice file or the text could not be loaded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.style import VoiceError, check_voice, load_voice, render_markdown  # noqa: E402

SEVERITY_RANK = {"none": 99, "low": 2, "medium": 1, "high": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--voice", required=True, help="voice.yaml/json file or directory")
    parser.add_argument("--text", required=True, help="chapter directory (*.md / *.txt)")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write a Markdown summary here")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"],
                        default="medium",
                        help="exit 1 when a finding this severe is found (default: medium)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = check_voice(load_voice(args.voice), args.text)
    except (VoiceError, OSError) as exc:
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
             "evidence": f["evidence"], "message_ja": f["message_ja"]}
            for f in report["findings"]]},
            ensure_ascii=False, indent=2))

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    worst = min((SEVERITY_RANK.get(f["severity"], 99) for f in report["findings"]),
                default=99)
    return 1 if worst <= threshold else 0


if __name__ == "__main__":
    raise SystemExit(main())
