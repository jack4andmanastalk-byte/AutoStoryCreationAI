#!/usr/bin/env python3
"""How much of a log-dependent check actually fires when text carries an error.

The two-stage checks are only as useful as their sensitivity: a clean run is
not evidence that the checks would notice a mistake. This script takes two
arms of prose (both written for the same task and canon) and injects the same
small, known errors into each, then reports which checks fire *because of the
injection* rather than at baseline.

The two arms are deliberately different:

* a **log-backed** arm (Stage B output, produced under the game log contract);
* a **direct** arm (S1 draft), which never saw the log.

Running the log checks on the direct arm is a counterfactual — that text was
never asked to satisfy the contract. It is included because it answers the
question the comparison left open: *if we demanded a log, which of these
errors would we have caught, and which would still slip through?*

``marker_sequence`` is excluded from the table: the direct arm was never asked
for the derived marker column, so it fails at baseline for a structural reason
and would drown every content finding. The marker failure is reported once,
separately.

    python3 scripts/probe_detection_power.py \
        --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \
        --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
        --design-dir experiments/2026-10-stageb-v11-t01/inputs/design \
        --arm log-backed=experiments/2026-10-stageb-v11-t01/relay/responses \
        --arm direct=experiments/2026-10-l1-pair-t01/relay/responses \
        --out experiments/2026-10-detect-power-t01/results.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog import check_rewrite, load_game_log  # noqa: E402
from asc.gamelog.world import derive_timeline  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402

CHAPTER_RE = re.compile(r"(ch\d+)")
ATTEMPT_RE = re.compile(r"-a(\d+)$")
IGNORED_CHECKS = {"marker_sequence"}

#: Each mutation is a small, deliberate error of a kind the trial actually saw.
MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("wrong_day_since", "ch03",
     "「六日ぶり」を「四日ぶり」にする（離れてからの日数を誤る）",
     "六日ぶり"),
    ("dead_acts_now", "ch01",
     "死者が現在時に行動する一文を足す",
     "ヨハンが戸口から入ってきて、アリアの肩に手を置いた。"),
    ("withheld_term", "ch02",
     "この章で保留の事実 F-04 の語「三年前」を足す",
     "それは三年前の嵐の夜のことだった。"),
    ("offlog_place", "ch01",
     "ログにない場所と船旅を足す",
     "アリアは船で対岸の島へ渡り、知らない港町を歩いた。"),
    ("unquantified_number", "ch02",
     "ログが宣言しない数量「半日」を足す",
     "写しの日付は、帳面の日付より半日だけずれていた。"),
)


def load_arm(path: Path) -> dict[str, dict]:
    """Latest recorded answer per chapter, from a relay responses directory."""
    latest: dict[str, tuple[int, Path]] = {}
    for file in sorted(path.glob("*.json")):
        chapter = CHAPTER_RE.search(file.stem)
        if not chapter:
            continue
        attempt = ATTEMPT_RE.search(file.stem)
        number = int(attempt.group(1)) if attempt else 1
        key = chapter.group(1)
        if key not in latest or number >= latest[key][0]:
            latest[key] = (number, file)
    if not latest:
        raise SystemExit(f"no chapter responses in {path}")
    return {chapter: json.loads(file.read_text(encoding="utf-8"))
            for chapter, (_attempt, file) in sorted(latest.items())}


def apply_mutation(mutation: str, text: str) -> tuple[str, bool]:
    if mutation == "wrong_day_since":
        if "六日ぶり" not in text:
            return text, False
        return text.replace("六日ぶり", "四日ぶり"), True
    sentence = dict((name, needle) for name, _chapter, _label, needle in MUTATIONS)[mutation]
    return text.rstrip() + "\n\n" + sentence + "\n", True


def findings(report: dict) -> list[dict]:
    return [item for item in report.get("findings", [])
            if item["check"] not in IGNORED_CHECKS]


def evaluate(context: dict, arms: dict[str, dict]) -> dict:
    out: dict[str, dict] = {}
    for arm, chapters in arms.items():
        baseline: dict[str, list[dict]] = {}
        marker_failures: dict[str, bool] = {}
        for chapter, payload in chapters.items():
            report = context["check"](payload["text"], chapter)
            baseline[chapter] = findings(report)
            marker_failures[chapter] = any(
                item["check"] == "marker_sequence" for item in report["findings"])
        rows = {}
        for mutation, chapter, label, _needle in MUTATIONS:
            payload = chapters.get(chapter)
            if payload is None:
                rows[mutation] = {"chapter": chapter, "label": label,
                                  "applied": False, "detected": []}
                continue
            text, applied = apply_mutation(mutation, payload["text"])
            before = {(item["check"], item["message_ja"]) for item in baseline[chapter]}
            after = findings(context["check"](text, chapter))
            detected = [{"check": item["check"], "severity": item["severity"],
                         "message_ja": item["message_ja"]}
                        for item in after
                        if (item["check"], item["message_ja"]) not in before]
            rows[mutation] = {"chapter": chapter, "label": label,
                              "applied": applied,
                              "detected": detected,
                              "detected_by": sorted({item["check"] for item in detected})}
        out[arm] = {
            "chapters": sorted(chapters),
            "baseline": {chapter: [
                {"check": item["check"], "severity": item["severity"]}
                for item in items] for chapter, items in baseline.items()},
            "marker_sequence_fails_at_baseline": marker_failures,
            "mutations": rows,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-log", required=True)
    parser.add_argument("--canon", required=True)
    parser.add_argument("--design-dir", required=True)
    parser.add_argument("--arm", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--voice", help="default: <design-dir>/voice.json")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    canon = load_canon(args.canon)
    log = load_game_log(args.game_log)
    scenes = load_scenes(Path(args.design_dir) / "scene.json")
    voice = load_voice(args.voice or Path(args.design_dir) / "voice.json")
    timeline = derive_timeline(log, canon)

    def check(text: str, chapter: str) -> dict:
        return check_rewrite(text, chapter, log, canon, voice, scenes,
                             timeline=timeline)

    arms = {}
    for entry in args.arm:
        name, _, path = entry.partition("=")
        if not name or not path:
            raise SystemExit(f"--arm needs NAME=PATH, got {entry!r}")
        arms[name] = load_arm(Path(path))

    report = {
        "schema": "detection-power-v1",
        "scope": ("which log-dependent checks fire when a known error is "
                  "injected. Not a measure of story quality, and not a "
                  "protocol-v1 result."),
        "game_log": str(args.game_log),
        "mutations": [{"id": name, "chapter": chapter, "label": label}
                      for name, chapter, label, _needle in MUTATIONS],
        "ignored_checks": sorted(IGNORED_CHECKS),
        "arms": evaluate({"check": check}, arms),
        "limits": [
            "The direct arm never saw the game log; running the log checks on "
            "it is a counterfactual, not a verdict on that text.",
            "One text per arm and one injection per mutation: a miss is a miss "
            "for this text, not a proven blind spot of the check.",
            "marker_sequence is excluded because the direct arm fails it at "
            "baseline for structural reasons.",
        ],
    }

    for arm, data in report["arms"].items():
        print(f"## {arm}: baseline findings "
              f"{ {c: len(v) for c, v in data['baseline'].items()} } "
              f"marker fail {data['marker_sequence_fails_at_baseline']}")
        for mutation, row in data["mutations"].items():
            checks = ", ".join(row.get("detected_by") or []) or "—"
            print(f"  {mutation:22s} {row['chapter']:5s} → {checks}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
