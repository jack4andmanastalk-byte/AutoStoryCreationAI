#!/usr/bin/env python3
"""Build blind A/B packets so that L2/L3 judging cannot see who wrote what.

Protocol §4 needs a preference or identification judgement per pair, and the
judge must not know which side came from which system. This script takes two
sets of finished runs and writes:

    <out>/pairs/pair-001.json   {"pair_id": "pair-001", "a": "...", "b": "..."}
    <out>/key.json              which run is on which side (never given to a judge)
    <out>/manifest.json         counts, drops and why
    <out>/judge_prompt.md       what to send the rater

Three things are removed before a text goes into a packet, because each one
would let a rater guess the system instead of judging the prose:

* the ``{{time: ...}}`` / ``{{foreshadow: ...}}`` markers (only S1 has canon),
* the run id, task id, system and seed: packets carry an opaque pair id,
* Markdown headings a model may have added.

Pairs whose texts differ by more than ``--max-length-diff`` are dropped and
counted, because §4 forbids using them for preference comparison. Sides are
balanced by construction (half the pairs start with the candidate, half with the
baseline, then shuffled), so "a" does not mean "S1".

Usage
-----
    python3 scripts/make_blind_pairs.py --runs-root runs \\
        --baseline s0 --candidate s1 --out build/pairs/2026-10-pilot

    # then, with a fresh rater session
    cat <out>/judge_prompt.md | pbcopy   # or hand the directory over

Exit codes: 0 ok, 2 bad input (no usable pairs, unknown system).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = re.compile(r"\{\{[^{}]*\}\}")
HEADING = re.compile(r"^\s*#{1,6}\s+.*$")
BLANK_RUN = re.compile(r"\n{3,}")


class PairError(RuntimeError):
    """Raised when no usable pair can be built; exits 2."""


def strip_markers(text: str) -> str:
    """Remove the evidence markers and any headings, keep the prose."""
    lines = [line for line in MARKER.sub("", text).splitlines()
             if not HEADING.match(line)]
    body = "\n".join(lines)
    return BLANK_RUN.sub("\n\n", body).strip()


def chars(text: str) -> int:
    """Same definition as ``ChapterDraft.chars``: whitespace does not count."""
    return len(re.sub(r"\s", "", text))


def load_runs(root: Path) -> tuple[dict[tuple[str, str, int], dict], list[dict]]:
    """Index finished runs by (task, system, seed); newest run wins a tie."""
    index: dict[tuple[str, str, int], dict] = {}
    duplicates: list[dict] = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if manifest.get("status") != "ok":
            continue
        try:
            key = (str(manifest["task_id"]), str(manifest["system"]), int(manifest["seed"]))
        except (KeyError, TypeError, ValueError):
            continue
        entry = {"run_id": manifest.get("run_id") or manifest_path.parent.name,
                 "run_dir": manifest_path.parent,
                 "started_at": manifest.get("started_at") or ""}
        if key in index:
            previous = index[key]
            duplicates.append({"task": key[0], "system": key[1], "seed": key[2],
                               "kept": entry["run_id"], "replaced": previous["run_id"]})
            if entry["started_at"] < previous["started_at"]:
                continue
        index[key] = entry
    return index, duplicates


def run_text(entry: dict) -> str:
    text_dir = Path(entry["run_dir"]) / "text"
    chapters = sorted(text_dir.glob("*.md"))
    if not chapters:
        raise PairError(f"{entry['run_id']}: no text/*.md")
    return strip_markers("\n\n".join(path.read_text(encoding="utf-8") for path in chapters))


def build_pairs(index: dict, baseline: str, candidate: str, *, seed: int,
                max_length_diff: float, tasks: list[str] | None,
                seeds: list[int] | None) -> tuple[list[dict], list[dict]]:
    keys = sorted({(task, seed_) for (task, system, seed_) in index
                   if system in {baseline, candidate}})
    usable: list[dict] = []
    dropped: list[dict] = []
    for task, seed_ in keys:
        if tasks and task not in tasks:
            continue
        if seeds is not None and seed_ not in seeds:
            continue
        left = index.get((task, baseline, seed_))
        right = index.get((task, candidate, seed_))
        if not left or not right:
            dropped.append({"task": task, "seed": seed_, "reason": "missing_side",
                            "has_baseline": bool(left), "has_candidate": bool(right)})
            continue
        left_text, right_text = run_text(left), run_text(right)
        left_chars, right_chars = chars(left_text), chars(right_text)
        longest = max(left_chars, right_chars) or 1
        gap = abs(left_chars - right_chars) / longest
        if gap > max_length_diff:
            dropped.append({"task": task, "seed": seed_, "reason": "length_gap",
                            "baseline_chars": left_chars, "candidate_chars": right_chars,
                            "gap": round(gap, 3)})
            continue
        usable.append({"task": task, "seed": seed_, "baseline": left, "candidate": right,
                       "baseline_text": left_text, "candidate_text": right_text,
                       "baseline_chars": left_chars, "candidate_chars": right_chars})

    # Balance by construction: half the pairs put the candidate on side "a".
    sides = [i % 2 == 0 for i in range(len(usable))]
    random.Random(seed).shuffle(sides)

    pairs, key_entries = [], {}
    for number, (item, candidate_first) in enumerate(zip(usable, sides), start=1):
        pair_id = f"pair-{number:03d}"
        if candidate_first:
            a, b = item["candidate"], item["baseline"]
            a_text, b_text = item["candidate_text"], item["baseline_text"]
            a_chars, b_chars = item["candidate_chars"], item["baseline_chars"]
        else:
            a, b = item["baseline"], item["candidate"]
            a_text, b_text = item["baseline_text"], item["candidate_text"]
            a_chars, b_chars = item["baseline_chars"], item["candidate_chars"]
        pairs.append({"pair_id": pair_id, "a": a_text, "b": b_text})
        key_entries[pair_id] = {
            "task": item["task"], "seed": item["seed"],
            "a": {"run_id": a["run_id"], "system": baseline if not candidate_first else candidate,
                  "chars": a_chars},
            "b": {"run_id": b["run_id"], "system": candidate if not candidate_first else baseline,
                  "chars": b_chars},
        }
    return pairs, {"pairs": key_entries, "dropped": dropped}


JUDGE_PROMPT = """\
あなたは日本語の短編小説を比較する評定者です。`pairs/` の各ファイルには、同じタスク・
同じ seed から作られた 2 作品（`a` と `b`）が入っています。

## 手順

1. `pairs/` のファイルを 1 つずつ、**他のペアを見ない状態で**読んでください。
2. どちらが良いかを選んでください。差が小さい場合は `tie` を選びます。
3. 判定ごとに、`judgements/<pair_id>.json` を次の形で書いてください。

```json
{"rater_id": "<あなたの識別子>", "pair_id": "pair-001",
 "winner": "a" | "b" | "tie", "rationale_ja": "<理由。1〜2 文>"}
```

## 規則

- **文字数・行数・段落数を理由にしない。** 長いほうが良いとは限りません。
- **作者や生成方法を推測しない。** 見えているのは本文だけです。
  来歴を推測した記述は判定に含めないでください。
- 迷ったら `tie` にしてください。無理に決めないでください。
- 各ペアは独立です。同じ理由を使い回さず、その作品のどこが効いたかを書いてください。

## してはいけないこと

- `key.json` を開かないこと（どちらがどちらの系かが書かれています）。
- 他の評定者の判定を見ないこと（一致率 κ を測るためです）。
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-root", default="runs",
                        help="directory of finished runs (default: runs)")
    parser.add_argument("--baseline", default="s0")
    parser.add_argument("--candidate", default="s1")
    parser.add_argument("--tasks", nargs="+", default=None)
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=20261023,
                        help="shuffle seed for the a/b assignment")
    parser.add_argument("--max-length-diff", type=float, default=0.25,
                        help="protocol §4: drop pairs whose length gap exceeds this")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.baseline == args.candidate:
        print("error: --baseline and --candidate must differ", file=sys.stderr)
        return 2
    root = Path(args.runs_root)
    if not root.is_dir():
        print(f"error: no such runs directory: {root}", file=sys.stderr)
        return 2

    index, duplicates = load_runs(root)
    try:
        pairs, key = build_pairs(index, args.baseline, args.candidate, seed=args.seed,
                                 max_length_diff=args.max_length_diff,
                                 tasks=args.tasks, seeds=args.seeds)
    except PairError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not pairs:
        print("error: no usable pair (need both sides, within the length limit)",
              file=sys.stderr)
        return 2

    out = Path(args.out)
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    for pair in pairs:
        (out / "pairs" / f"{pair['pair_id']}.json").write_text(
            json.dumps(pair, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    key_payload = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs_root": str(root),
        "baseline": args.baseline,
        "candidate": args.candidate,
        "seed": args.seed,
        "max_length_diff": args.max_length_diff,
        **key,
    }
    (out / "key.json").write_text(
        json.dumps(key_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "pairs": len(pairs),
        "dropped": len(key["dropped"]),
        "duplicate_runs": duplicates,
        "baseline": args.baseline,
        "candidate": args.candidate,
        "seed": args.seed,
        "chars": {
            "min": min(min(entry["a"]["chars"], entry["b"]["chars"])
                       for entry in key["pairs"].values()),
            "max": max(max(entry["a"]["chars"], entry["b"]["chars"])
                       for entry in key["pairs"].values()),
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "judge_prompt.md").write_text(JUDGE_PROMPT, encoding="utf-8")

    print(json.dumps({"pairs": len(pairs), "dropped": len(key["dropped"]),
                      "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
