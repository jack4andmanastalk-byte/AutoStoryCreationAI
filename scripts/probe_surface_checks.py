#!/usr/bin/env python3
"""Candidate surface checks, measured before they are trusted.

The detection-power probe found two errors that no existing check sees: a place
and a trip the log never declares, and a quantity the log never says. This
script runs the candidate answer in :mod:`asc.gamelog.surface` over the same two
arms, and — more importantly — reports what it says about text that is already
known to be **clean**, because that is where a heuristic check has to earn its
place.

* places: 0 findings on the clean chapters is the precision evidence;
  the injected off-log trip must produce exactly one.
* numbers: reported as a list, not as findings. The report below is the reason
  the number side is not a check: ordinary numerals (一本・一枚・一度) have no
  counterpart in the log and would drown an invented count.

    python3 scripts/probe_surface_checks.py \
        --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \
        --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
        --arm log-backed=experiments/2026-10-stageb-v11-t01/relay/responses \
        --arm direct=experiments/2026-10-l1-pair-t01/relay/responses \
        --out experiments/2026-10-surface-checks-t01/results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asc.gamelog import load_game_log  # noqa: E402
from asc.gamelog.surface import (numbers_in_text, place_findings,  # noqa: E402
                                unmatched_numbers)
from asc.gamelog.world import chapter_timeline, derive_timeline  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from probe_detection_power import (MUTATIONS, apply_mutation,  # noqa: E402
                                   load_arm)

INJECTIONS = ("offlog_place", "unquantified_number")


def references(canon_dir: Path, log) -> str:
    """Everything the log and canon say, as one searchable string."""
    text = "".join(path.read_text(encoding="utf-8")
                   for path in sorted(canon_dir.glob("*.json")))
    text += json.dumps([{"id": chapter.id, "day": chapter.day,
                         "location": chapter.location,
                         "scenes": [scene.id for scene in chapter.scenes]}
                        for chapter in log.chapters], ensure_ascii=False)
    text += json.dumps(log.as_dict(), ensure_ascii=False)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-log", required=True)
    parser.add_argument("--canon", required=True)
    parser.add_argument("--arm", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    canon = load_canon(args.canon)
    log = load_game_log(args.game_log)
    timeline = derive_timeline(log, canon)
    refs = references(Path(args.canon), log)

    arms: dict[str, dict] = {}
    injections: dict[str, dict] = {}
    for entry in args.arm:
        name, _, path = entry.partition("=")
        if not name or not path:
            raise SystemExit(f"--arm needs NAME=PATH, got {entry!r}")
        chapters = load_arm(Path(path))
        per_chapter: dict[str, dict] = {}
        for chapter, payload in chapters.items():
            row = chapter_timeline(timeline, chapter)
            findings = place_findings(payload["text"], row, canon)
            unmatched = unmatched_numbers(payload["text"], refs)
            per_chapter[chapter] = {
                "place_findings": findings,
                "numbers": {
                    "tokens": len(numbers_in_text(payload["text"])),
                    "unmatched": sorted({item["token"] for item in unmatched}),
                },
            }
        arms[name] = {"source": path, "chapters": per_chapter}

        for injection in INJECTIONS:
            chapter = next(c for m, c, _l, _n in MUTATIONS if m == injection)
            payload = chapters[chapter]
            text, applied = apply_mutation(injection, payload["text"])
            row = chapter_timeline(timeline, chapter)
            before = {item["evidence"]["expression"]
                      for item in place_findings(payload["text"], row, canon)}
            after = place_findings(text, row, canon)
            new_places = [item["evidence"]["destination"] for item in after
                          if item["evidence"]["expression"] not in before]
            before_numbers = {item["token"]
                              for item in unmatched_numbers(payload["text"], refs)}
            new_numbers = sorted({item["token"]
                                  for item in unmatched_numbers(text, refs)}
                                 - before_numbers)
            injections.setdefault(injection, {})[name] = {
                "chapter": chapter, "applied": applied,
                "new_places": new_places,
                "new_numbers": new_numbers,
            }

    report = {
        "schema": "surface-checks-v1",
        "scope": ("candidate checks measured outside the contract. Places are "
                  "reported as findings; numbers are a report, not a verdict."),
        "game_log": str(args.game_log),
        "canon": str(args.canon),
        "arms": arms,
        "injections": injections,
        "limits": [
            "The place check is a pattern match on a travel verb plus a "
            "place-shaped word; it fires only on assertions of travel.",
            "Numbers are not checked. A numeral has no reference of its own, "
            "so the report lists unmatched tokens for a human to read.",
            "One text per arm: 0 findings on clean text is weak precision "
            "evidence, not a false-positive rate.",
            "Nothing here is wired into check_rewrite; a decision to adopt "
            "would need a larger sample of prose.",
        ],
    }

    for name, data in report["arms"].items():
        print(f"## {name}")
        for chapter, row in data["chapters"].items():
            places = [item["evidence"]["destination"]
                      for item in row["place_findings"]]
            print(f"  {chapter}: places {places or '—'} "
                  f"unmatched numerals {row['numbers']['unmatched'] or '—'}")
    print("## injections")
    for injection, per_arm in report["injections"].items():
        for name, row in per_arm.items():
            print(f"  {injection:22s} {name:11s} places={row['new_places'] or '—'} "
                  f"numbers={row['new_numbers'] or '—'}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
