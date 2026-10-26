#!/usr/bin/env python3
"""Observation mode does not move the contract — check that, and show it works.

``check_rewrite(..., observe_surface=True)`` (and ``run_twostage.py
--observe-surface``) attaches the candidate place check's results as
*observations*. The point of the mode is to collect examples of the heuristic's
false positives during real runs, without letting the heuristic decide anything.

This probe compares two runs of the same scripted bundle — one with the flag, one
without — and then injects an off-log trip into a chapter and compares again:

* every contract field (status, findings, checks, chars) must be identical;
* ``observations`` must exist only when the flag was given;
* the injection must produce an observation and must **not** change the status.

    python3 scripts/probe_surface_observe.py \\
        --baseline experiments/2026-10-surface-observe-t01/observe-off/run \\
        --observe experiments/2026-10-surface-observe-t01/observe-on/run \\
        --game-log experiments/2026-10-trpg-slice-t01/inputs/canon/../game_log.json \\
        --canon experiments/2026-10-trpg-slice-t01/inputs/canon \\
        --out experiments/2026-10-surface-observe-t01/results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog import check_rewrite, load_game_log  # noqa: E402
from asc.gamelog.world import derive_timeline  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402

#: An error the log never declares, of the kind the detection probe injects.
INJECTION = "アリアは船で対岸の島へ渡り、知らない港町を歩いた。"

#: Fields the contract is allowed to be judged on. Everything here must match
#: between the two runs, whatever the observation flag says.
CONTRACT_FIELDS = ("status", "findings", "checks", "chars", "by_severity",
                   "blocking_findings", "warning_findings")


def chapter_files(run_dir: Path) -> dict[str, Path]:
    return {path.stem: path
            for path in sorted((run_dir / "text").glob("ch*.md"))}


def contract_view(report: dict) -> dict:
    summary = report["summary"]
    return {
        "chapter": report["chapter"],
        "summary": {key: summary.get(key) for key in CONTRACT_FIELDS},
        "findings": report["findings"],
        "checks": [{key: check.get(key) for key in
                    ("id", "status", "evaluated", "findings")}
                   for check in report["checks"]],
        "has_observations_key": "observations" in report,
        "observations": report.get("observations", []),
    }


def compare_runs(baseline: dict, observe: dict) -> dict:
    chapters: dict[str, dict] = {}
    for chapter in sorted(set(baseline) | set(observe)):
        left = contract_view(baseline[chapter])
        right = contract_view(observe[chapter])
        same = (left["summary"] == right["summary"]
                and left["findings"] == right["findings"]
                and left["checks"] == right["checks"])
        chapters[chapter] = {
            "contract_identical": same,
            "status": right["summary"]["status"],
            "findings": len(right["findings"]),
            "observations_baseline": ("absent" if not left["has_observations_key"]
                                      else len(left["observations"])),
            "observations_observe": ("absent" if not right["has_observations_key"]
                                     else len(right["observations"])),
        }
    return chapters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", required=True, help="run dir without the flag")
    parser.add_argument("--observe", required=True, help="run dir with the flag")
    parser.add_argument("--game-log", required=True)
    parser.add_argument("--canon", required=True)
    parser.add_argument("--design-dir", default=None)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--scenes", default=None)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    reports: dict[str, dict[str, dict]] = {}
    for arm, run_dir in (("baseline", Path(args.baseline)),
                         ("observe", Path(args.observe))):
        reports[arm] = json.loads(
            (run_dir / "rewrite.report.json").read_text(encoding="utf-8"))["chapters"]

    chapters = compare_runs(reports["baseline"], reports["observe"])

    canon = load_canon(args.canon)
    log = load_game_log(args.game_log)
    timeline = derive_timeline(log, canon)
    scenes = load_scenes(args.scenes) if args.scenes else None
    voice = load_voice(args.voice) if args.voice else None

    injected: dict[str, dict] = {}
    for chapter, path in chapter_files(Path(args.observe)).items():
        if chapter != "ch01":
            continue
        text = path.read_text(encoding="utf-8").rstrip() + "\n\n" + INJECTION + "\n"
        for arm, observe_surface in (("baseline", False), ("observe", True)):
            report = check_rewrite(text, chapter, log, canon, voice, scenes,
                                   timeline=timeline,
                                   observe_surface=observe_surface)
            view = contract_view(report)
            injected[arm] = {
                "status": view["summary"]["status"],
                "findings": len(view["findings"]),
                "blocking_findings": view["summary"]["blocking_findings"],
                "observations_baseline": ("absent"
                                          if not view["has_observations_key"]
                                          else len(view["observations"])),
                "observation_destinations": [item["evidence"]["destination"]
                                             for item in view["observations"]],
            }

    report = {
        "schema": "surface-observe-v1",
        "scope": ("the candidate place check attached as observations. It is not "
                  "a finding and cannot trigger a repair."),
        "baseline_run": str(args.baseline),
        "observe_run": str(args.observe),
        "chapters": chapters,
        "injection": {"sentence": INJECTION, "results": injected},
        "findings": {
            "contract_identical": all(row["contract_identical"]
                                      for row in chapters.values()),
            "observations_only_with_flag": all(
                row["observations_baseline"] == "absent" for row in chapters.values()),
            "injection_status_unchanged": (
                injected["baseline"]["status"] == injected["observe"]["status"]),
            "injection_observed": bool(injected["observe"]["observation_destinations"]),
        },
        "limits": [
            "The text is the scripted bundle's, not model output: this shows the "
            "wiring and the non-interference, not what real prose will collect.",
            "Observation mode collects examples; it does not measure a rate. A "
            "sample of real runs still has to be read by a human.",
            "The place check remains outside the contract: no severity, no "
            "blocking, no repair prompt.",
        ],
    }

    print("## chapters")
    for chapter, row in chapters.items():
        print(f"  {chapter}: contract_identical={row['contract_identical']} "
              f"status={row['status']} findings={row['findings']} "
              f"observations {row['observations_baseline']} -> "
              f"{row['observations_observe']}")
    print("## injection")
    for arm, row in injected.items():
        print(f"  {arm:9s} status={row['status']} findings={row['findings']} "
              f"observations={row['observations_baseline']} "
              f"destinations={row['observation_destinations'] or '—'}")
    print("## " + json.dumps(report["findings"], ensure_ascii=False))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
