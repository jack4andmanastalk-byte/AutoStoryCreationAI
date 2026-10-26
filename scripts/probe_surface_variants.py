#!/usr/bin/env python3
"""Does the place check survive other wordings? A paraphrase and lookalike set.

The first surface measurement (`scripts/probe_surface_checks.py`) checked the
candidate place check on one wording, over six clean chapters. That is enough to
see it work, not enough to trust it: a pattern that fires on 「対岸の島へ渡った」
may miss 「北の港に着いた」 and may fire on 「話は振り出しに戻った」. This script
therefore does two things, and keeps them apart.

* **clean corpus** — every chapter we have that was written for this canon
  (Stage B v1.1, the direct S1 draft, and the older Stage B v1.0). More clean
  text means the false-positive count stops being a single observation.
* **fixed case set** — hand-written sentences, each with an expected verdict:
  paraphrases of an off-log trip (these must fire) and lookalikes that merely
  *look* like travel (these must not). The sentences are written by the agent,
  not sampled from model output, so they measure how the pattern behaves on
  wording, not the rate of false positives in real prose.

    python3 scripts/probe_surface_variants.py \\
        --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \\
        --canon experiments/2026-10-stageb-v11-t01/inputs/canon \\
        --arm log-backed=experiments/2026-10-stageb-v11-t01/relay/responses \\
        --arm direct=experiments/2026-10-l1-pair-t01/relay/responses \\
        --arm log-backed-v10=experiments/2026-10-full-t01/relay/responses \\
        --out experiments/2026-10-surface-checks-t02/results.json
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
from asc.gamelog.surface import movement_claims, place_findings  # noqa: E402
from asc.gamelog.world import chapter_timeline, derive_timeline  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from probe_detection_power import load_arm  # noqa: E402

#: ``(case, chapter, sentence, expected)``. ``expected`` is what the check
#: should say: ``fires`` for a trip the log does not declare, ``silent`` for a
#: sentence that only resembles one. ``why`` is printed in the note.
CASES: tuple[tuple[str, str, str, str, str], ...] = (
    # Paraphrases of the same error: an off-log destination, said differently.
    ("place_original", "ch01",
     "アリアは船で対岸の島へ渡り、知らない港町を歩いた。", "fires",
     "the injection used in t01"),
    ("place_ni_mukatta", "ch01",
     "その夜、アリアは対岸の島に向かった。", "fires",
     "へ replaced by に, different verb"),
    ("place_ni_tsuita", "ch01",
     "明け方には、北の港に着いた。", "fires",
     "a new place-shaped name, not in canon"),
    ("place_he_modotta", "ch01",
     "アリアは隣町へ戻った。", "fires",
     "へ + 戻った"),
    ("place_wo_koete", "ch01",
     "一行は山を越えて村に着いた。", "fires",
     "a clause before the destination"),
    ("place_undeclared_canon", "ch03",
     "アリアは港へ向かった。", "fires",
     "a canon place, but this chapter declares no move"),
    # Lookalikes: に + a movement verb, but not a trip to a place.
    ("look_hanashi", "ch01", "父は灯りの話に戻った。", "silent",
     "「話」 is not place-shaped"),
    ("look_memory", "ch01", "記憶の底へ沈んだ。", "silent",
     "沈んだ is not a movement verb"),
    ("look_daidokoro", "ch01", "アリアは台所へ行った。", "silent",
     "an indoor room, not a place name"),
    ("look_mieta", "ch01", "島が見えた。", "silent",
     "seeing a place is not going to it"),
    ("look_kaze", "ch01", "風が沖へ向かった。", "silent",
     "沖 has no place suffix"),
    ("look_furidashi", "ch01", "話は振り出しに戻った。", "silent",
     "に戻った about a story, not a person"),
    ("look_mune", "ch01", "マーサは手紙を胸に戻した。", "silent",
     "戻した (transitive) is not travel"),
    ("look_allowed", "ch01", "アリアは灯台に着いた。", "silent",
     "the chapter's own location is allowed"),
    ("look_declared_move", "ch01", "アリアは王都へ発った。", "silent",
     "ch01 declares the move 灯台→王都, so 王都 is allowed"),
    ("look_duration", "ch01", "三日かけて王都へ着いた。", "silent",
     "a duration clause before the place — this used to be read as "
     "「三日かけて王都」 on the v1.0 chapter"),
    # Known misses, kept in the table so the limit is visible rather than absent.
    ("miss_walked", "ch01", "アリアは王都の市場を目指して歩いた。", "silent",
     "歩いた is not in the verb list — a known miss"),
    ("miss_described", "ch01", "対岸の島が霞んで見えた。", "silent",
     "description, not travel — a known miss"),
)


def evaluate_case(sentence: str, expected: str, canon, row) -> dict:
    findings = place_findings(sentence, row, canon)
    fired = bool(findings)
    return {
        "expected": expected,
        "fired": fired,
        "destinations": [item["evidence"]["destination"] for item in findings],
        "claims": [claim.destination for claim in movement_claims(sentence)],
        "verdict": ("ok" if (expected == "fires") == fired
                    else ("miss" if expected == "fires" else "false_positive")),
    }


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

    clean: dict[str, dict] = {}
    chapters_seen = 0
    for entry in args.arm:
        name, _, path = entry.partition("=")
        if not name or not path:
            raise SystemExit(f"--arm needs NAME=PATH, got {entry!r}")
        per_chapter: dict[str, dict] = {}
        for chapter, payload in load_arm(Path(path)).items():
            row = chapter_timeline(timeline, chapter)
            findings = place_findings(payload["text"], row, canon)
            chars = len(payload["text"].replace("\n", ""))
            per_chapter[chapter] = {
                "chars": chars,
                "place_findings": findings,
                "claims": [claim.destination
                           for claim in movement_claims(payload["text"])],
            }
            chapters_seen += 1
        clean[name] = {"source": path, "chapters": per_chapter}

    cases: dict[str, dict] = {}
    for case, chapter, sentence, expected, why in CASES:
        row = chapter_timeline(timeline, chapter)
        result = evaluate_case(sentence, expected, canon, row)
        result.update({"chapter": chapter, "sentence": sentence, "why": why})
        cases[case] = result

    fires = [key for key, row in cases.items() if row["expected"] == "fires"]
    silent = [key for key, row in cases.items() if row["expected"] == "silent"]
    report = {
        "schema": "surface-variants-v1",
        "scope": ("the place check from asc.gamelog.surface, measured on more "
                  "clean prose and on a hand-written paraphrase set. Not wired "
                  "into check_rewrite; nothing here is a contract."),
        "game_log": str(args.game_log),
        "canon": str(args.canon),
        "clean": clean,
        "cases": cases,
        "summary": {
            "clean_chapters": chapters_seen,
            "clean_chapters_with_findings": sum(
                1 for arm in clean.values() for row in arm["chapters"].values()
                if row["place_findings"]),
            "recall": {
                "fired": sum(1 for key in fires if cases[key]["fired"]),
                "of": len(fires),
                "missed": [key for key in fires if not cases[key]["fired"]],
            },
            "precision": {
                "silent": sum(1 for key in silent if not cases[key]["fired"]),
                "of": len(silent),
                "false_positives": [key for key in silent if cases[key]["fired"]],
            },
        },
        "limits": [
            "The case set is hand-written by the agent, not sampled from model "
            "output: it measures behaviour on wording, not a false-positive rate.",
            "One log and one canon are used for every arm, including the direct "
            "arm that never saw them; chapter rows are shared on purpose so the "
            "comparison is about prose, not about a different timeline.",
            "The clean corpus is nine chapters from three runs of the same canon; "
            "they are not independent samples of a distribution.",
            "Only asserted travel is visible: 歩いた and 見えた are known misses, "
            "and are kept in the table rather than dropped from it.",
        ],
    }

    print(f"## clean ({chapters_seen} chapters)")
    for name, arm in clean.items():
        for chapter, row in arm["chapters"].items():
            places = [item["evidence"]["destination"]
                      for item in row["place_findings"]]
            print(f"  {name:16s} {chapter}: chars {row['chars']:5d} "
                  f"claims {row['claims'] or '—'} findings {places or '—'}")
    print("## cases")
    for key, row in cases.items():
        mark = {"ok": "ok ", "miss": "MISS", "false_positive": "FP "}[row["verdict"]]
        print(f"  {mark} {key:18s} expected {row['expected']:6s} "
              f"destinations {row['destinations'] or '—'}")
    summary = report["summary"]
    print(f"## recall {summary['recall']['fired']}/{summary['recall']['of']} "
          f"precision {summary['precision']['silent']}/"
          f"{summary['precision']['of']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
