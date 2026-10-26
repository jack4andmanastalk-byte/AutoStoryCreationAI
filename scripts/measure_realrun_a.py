#!/usr/bin/env python3
"""Measure batch A against the rules that were fixed before it ran.

The registration lives in ``experiments/2026-10-realrun-a-t01/preregistration.json``
and is hashed into the result, so the thresholds in this script are the ones
that were recorded, not ones chosen after seeing the text.

What it reads: one ``rewrite.report.json`` per sample (written by
``run_twostage.py --stage b --observe-surface``). What it writes: per-chapter
numbers, per-sample aggregates, and a verdict for each pre-registered rule.

    python3 scripts/measure_realrun_a.py
    python3 scripts/measure_realrun_a.py --bundle experiments/2026-10-realrun-a-t01

A sample's directory must be ``<bundle>/sample-N/run``; ``--sample NAME=PATH``
overrides discovery, which is also how the script is tested (against the
scripted runs, where it is a check of the arithmetic, not evidence about prose).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.story.canon import load_canon  # noqa: E402

DEFAULT_BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-a-t01"


def discover_samples(bundle: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for path in sorted(bundle.glob("sample-*/run")):
        if (path / "rewrite.report.json").is_file():
            found.append((path.parent.name, path))
    return found


def classify(destination: str, canon) -> str:
    """``undeclared`` if the place exists in canon, ``off_log`` if it does not."""
    return "undeclared" if destination in canon.locations else "off_log"


def summarise_chapter(report: dict, canon, length_band: tuple[int, int]) -> dict:
    summary = report["summary"]
    observations = report.get("observations")
    items = [{"destination": item["evidence"]["destination"],
              "branch": classify(item["evidence"]["destination"], canon),
              "expression": item["evidence"]["expression"]}
             for item in (observations or [])]
    chars = summary["chars"]
    expected = summary["expected_markers"]
    found = summary["found_markers"]
    return {
        "chars": chars,
        "in_length_band": length_band[0] <= chars <= length_band[1],
        "status": summary["status"],
        "attempts": report.get("attempts"),
        "repairs": report.get("repairs"),
        "blocking_findings": summary["blocking_findings"],
        "warning_findings": summary["warning_findings"],
        "findings": [{"check": item["check"], "severity": item["severity"],
                      "blocks_repair": item.get("blocks_repair", True)}
                     for item in report["findings"]],
        "expected_markers": expected,
        "found_markers": found,
        "markers_missing": max(0, expected - found),
        "observations_present": observations is not None,
        "observations": items,
    }


def summarise_sample(name: str, run_dir: Path, canon,
                     length_band: tuple[int, int]) -> dict:
    report = json.loads((run_dir / "rewrite.report.json").read_text(encoding="utf-8"))
    chapters = {chapter: summarise_chapter(row, canon, length_band)
                for chapter, row in report["chapters"].items()}
    in_band = sum(1 for row in chapters.values() if row["in_length_band"])
    branches = {"off_log": 0, "undeclared": 0}
    for row in chapters.values():
        for item in row["observations"]:
            branches[item["branch"]] += 1
    checks: dict[str, int] = {}
    for row in chapters.values():
        for item in row["findings"]:
            checks[item["check"]] = checks.get(item["check"], 0) + 1
    return {
        "run_dir": str(run_dir),
        "status": report.get("status"),
        "chapters": chapters,
        "chapters_in_length_band": in_band,
        "chapters_total": len(chapters),
        "chars_total": sum(row["chars"] for row in chapters.values()),
        "observations_present": all(row["observations_present"]
                                    for row in chapters.values()),
        "observation_branches": branches,
        "findings_by_check": checks,
        "repairs_total": sum(row["repairs"] or 0 for row in chapters.values()),
    }


def verdicts(samples: dict[str, dict], prereg: dict) -> dict:
    rules = prereg["rules"]
    planned = prereg["samples_planned"]
    enough = len(samples) >= planned
    missing_flag = [name for name, row in samples.items()
                    if not row["observations_present"]]

    off_log = sum(row["observation_branches"]["off_log"] for row in samples.values())
    undeclared = sum(row["observation_branches"]["undeclared"]
                     for row in samples.values())
    if not samples:
        branch = "not_run"
    elif not enough:
        branch = "not_enough_data"
    elif missing_flag:
        branch = "observations_absent"
    elif off_log == 0 and undeclared == 0:
        branch = "no_examples"
    elif off_log == 0:
        branch = "drop_undeclared_branch"
    elif undeclared == 0:
        branch = "narrow_branch_only"
    else:
        branch = "inspect_both"

    need = rules["R2_length"]["min_chapters_in_band"]
    in_band = {name: row["chapters_in_length_band"] for name, row in samples.items()}
    if not samples or not enough:
        length = "not_enough_data"
    elif all(count >= need for count in in_band.values()):
        length = "length_ok"
    elif all(count < need for count in in_band.values()):
        length = "fix_prompt_target"
    else:
        length = "mixed"

    hits: dict[str, list[str]] = {}
    for name, row in samples.items():
        for check in row["findings_by_check"]:
            hits.setdefault(check, []).append(name)
    threshold = rules["R3_recurring_failure"]["min_samples"]
    recurring = sorted(check for check, names in hits.items()
                       if len(set(names)) >= threshold)
    recurrence = "not_enough_data" if not enough else (
        "recurring" if recurring else "no_recurring_failure")

    return {
        "samples_present": len(samples),
        "samples_planned": planned,
        "enough_samples": enough,
        "R1_place_branch": {
            "verdict": branch,
            "off_log": off_log,
            "undeclared": undeclared,
            "samples_missing_observations": missing_flag,
            "adoption": rules["R1_place_branch"]["adoption"],
        },
        "R2_length": {"verdict": length,
                      "chapters_in_band": in_band,
                      "needed_per_sample": need},
        "R3_recurring_failure": {"verdict": recurrence,
                                 "recurring_checks": recurring,
                                 "by_check": {check: sorted(set(names))
                                              for check, names in hits.items()}},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--preregistration", default=None,
                        help="default: <bundle>/preregistration.json")
    parser.add_argument("--canon", default=None, help="default: <bundle>/inputs/canon")
    parser.add_argument("--sample", action="append", default=None,
                        metavar="NAME=RUN_DIR",
                        help="override discovery (repeatable)")
    parser.add_argument("--out", default=None, help="default: <bundle>/results.json")
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    prereg_path = Path(args.preregistration or bundle / "preregistration.json")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    prereg_bytes = prereg_path.read_bytes()
    canon = load_canon(args.canon or bundle / "inputs" / "canon")
    band = tuple(prereg["length_band"])

    if args.sample:
        pairs: list[tuple[str, Path]] = []
        for entry in args.sample:
            name, _, path = entry.partition("=")
            if not name or not path:
                raise SystemExit(f"--sample needs NAME=PATH, got {entry!r}")
            pairs.append((name, Path(path)))
    else:
        pairs = discover_samples(bundle)

    samples = {name: summarise_sample(name, path, canon, band)
               for name, path in pairs}
    result = {
        "schema": "realrun-a-v1",
        "experiment": prereg["experiment"],
        "preregistration": {
            "path": str(prereg_path.relative_to(REPO_ROOT))
            if prereg_path.is_absolute() and REPO_ROOT in prereg_path.parents
            else str(prereg_path),
            "sha256": hashlib.sha256(prereg_bytes).hexdigest(),
        },
        "samples": samples,
        "verdicts": verdicts(samples, prereg),
        "not_claimed": prereg["not_claimed"],
        "limits": [
            "Observations are examples, not a rate: no false-positive rate is "
            "claimed from this batch.",
            "The operator cannot be seeded, so the text is not reproducible (G5 "
            "stays unmet); provenance is recorded per response, not assumed fresh.",
            "Length and marker counts are L1 quantities; they say nothing about "
            "whether the chapters are any good.",
        ],
    }

    if not samples:
        print("no samples yet: nothing measured "
              f"(expected {prereg['samples_planned']} under {bundle})")
    for name, row in samples.items():
        print(f"## {name}: status={row['status']} chars={row['chars_total']} "
              f"in_band={row['chapters_in_length_band']}/{row['chapters_total']} "
              f"branches={row['observation_branches']} "
              f"repairs={row['repairs_total']}")
        for chapter, chapter_row in row["chapters"].items():
            destinations = [f"{item['destination']}({item['branch']})"
                            for item in chapter_row["observations"]]
            print(f"   {chapter}: {chapter_row['chars']:5d}字 "
                  f"{chapter_row['status']:10s} "
                  f"markers {chapter_row['found_markers']}/"
                  f"{chapter_row['expected_markers']} "
                  f"findings={[f['check'] for f in chapter_row['findings']] or '—'} "
                  f"observed={destinations or '—'}")
    print("## verdicts")
    for key, value in result["verdicts"].items():
        if isinstance(value, dict) and "verdict" in value:
            print(f"  {key}: {value['verdict']}")

    out = Path(args.out or bundle / "results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
