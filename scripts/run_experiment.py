#!/usr/bin/env python3
"""Run a small experiment matrix (task x system x seed) and summarise it.

    python3 scripts/run_experiment.py --id demo --tasks t01 --systems s0 s1 \\
        --seeds 0 1 --provider scripted --script benchmarks/protocol-v1/fixtures/plan-demo.json

Each cell is a normal pipeline run (``runs/<run_id>/``). The experiment writes
``experiments/<id>/results.json`` and ``note.md``. The note is a template with
the numbers filled in: hypothesis, conditions, N, results, limits. It is meant to
be edited by a human before it is committed — an experiment without a written
limit is a press release.

The summary reports a paired difference against the baseline system (S0) with a
bootstrap interval. With N this small the interval is wide by construction; that
is the honest answer, not a reason to drop it.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    CommandProvider, DraftError, PlanError, ProviderError, RunLedger, ScriptedProvider,
    TaskError, build_plan, build_story, git_commit, load_scripted_responses, load_tasks,
)
from asc.story.canon import load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
DEFAULT_SCRIPT = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def bootstrap_ci(values: list[float], samples: int = 1000, seed: int = 0) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [round(values[0], 3), round(values[0], 3)]
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [rng.choice(values) for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[int(0.975 * len(means)) - 1]
    return [round(lo, 3), round(hi, 3)]


def run_cell(task, system, seed, provider, tasks, runs_root, temperature) -> dict:
    ledger = RunLedger.create(
        runs_root, task_id=task.id, system=system, seed=seed,
        protocol_version=tasks.protocol, model=provider.model,
        provider=provider.name, temperature=temperature,
    )
    summary: dict = {"run_id": ledger.run_id, "run_dir": str(ledger.path),
                     "task": task.id, "system": system, "seed": seed}
    canon = None
    try:
        if system != "s0":
            build_plan(task, provider, ledger, chapters=tasks.chapters,
                       target_chars=tasks.target_chars, temperature=temperature, seed=seed)
            canon = load_canon(ledger.path / "canon")
        draft = build_story(task, provider, ledger, canon=canon, chapters=tasks.chapters,
                            temperature=temperature, seed=seed)
        summary["chars"] = draft.chars
        summary["must_include_rate"] = draft.must_include_hits()["rate"]
        summary["warnings"] = len(draft.warnings)
        summary["injected_markers"] = sum(len(c.injected) for c in draft.chapters)
        if canon is not None:
            report = audit_texts(ledger.path / "canon", ledger.path / "text")
            ledger.write_json("audit.json", report)
            summary["violations"] = report["summary"]["violations"]
            summary["high"] = report["summary"]["by_severity"].get("high", 0)
            summary["checks_skipped"] = report["summary"]["checks_skipped"]
            summary["ced_per_10k_chars"] = report["summary"]["ced_per_10k_chars"]
        else:
            summary["violations"] = None
            summary["high"] = None
            summary["checks_skipped"] = None
            summary["ced_per_10k_chars"] = None
        ledger.write_json("cell-summary.json", summary)
        ledger.finish("ok")
        summary["status"] = "ok"
    except (PlanError, DraftError, ProviderError) as exc:
        ledger.fail(str(exc))
        summary["status"] = "failed"
        summary["error"] = str(exc)
    return summary


def aggregate(cells: list[dict]) -> dict:
    by_system: dict[str, list[dict]] = {}
    for cell in cells:
        by_system.setdefault(cell["system"], []).append(cell)

    by_system_summary: dict = {}
    for system, rows in sorted(by_system.items()):
        ok = [row for row in rows if row["status"] == "ok"]
        entry: dict = {"n": len(ok), "failed": len(rows) - len(ok)}
        for metric in ("chars", "must_include_rate", "violations", "high",
                       "checks_skipped", "ced_per_10k_chars", "warnings",
                       "injected_markers"):
            values = [row[metric] for row in ok if row.get(metric) is not None]
            if not values:
                continue
            entry[metric] = {
                "mean": round(statistics.fmean(values), 3),
                "min": min(values), "max": max(values),
                "ci95": bootstrap_ci([float(v) for v in values]),
                "n": len(values),
            }
        by_system_summary[system] = entry

    result: dict = {"by_system": by_system_summary}
    if "s0" in by_system and "s1" in by_system:
        base = {(c["task"], c["seed"]): c for c in by_system["s0"] if c["status"] == "ok"}
        pairs = []
        for cell in by_system["s1"]:
            key = (cell["task"], cell["seed"])
            if cell["status"] == "ok" and key in base:
                pairs.append((base[key], cell))
        paired: dict = {"n_pairs": len(pairs)}
        for metric in ("chars", "must_include_rate", "violations", "high",
                       "ced_per_10k_chars", "warnings"):
            diffs = [float(b[metric]) - float(a[metric])
                     for a, b in pairs if a.get(metric) is not None and b.get(metric) is not None]
            if diffs:
                paired[metric] = {
                    "mean_s1_minus_s0": round(statistics.fmean(diffs), 3),
                    "ci95": bootstrap_ci(diffs),
                    "n": len(diffs),
                    "direction": "lower_is_better" if metric in {
                        "violations", "high", "ced_per_10k_chars", "warnings"} else "descriptive",
                }
        result["paired_vs_s0"] = paired
    return result


def render_note(experiment: dict, results: dict, scripted: bool) -> str:
    lines = [
        f"# 実験 {experiment['id']}",
        "",
        f"- 実施: {experiment['created_at']}",
        f"- プロトコル: `{experiment['protocol']}`",
        f"- タスク: {', '.join(experiment['tasks'])}",
        f"- 系: {', '.join(experiment['systems'])}",
        f"- seed: {', '.join(str(s) for s in experiment['seeds'])}",
        f"- プロバイダ: `{experiment['provider']}`",
        f"- コード: `{experiment['git_commit'] or 'unknown'}`",
        "",
        "## 仮説",
        "",
        "（記入）S1（canon を使う系）は S0（単発プロンプト）より、継続性の欠陥が少ない。",
        "",
        "## 結果",
        "",
        "| 系 | N | 失敗 | 文字数 | 必須語 | 違反 | high | CED | 警告 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for system, entry in results["by_system"].items():
        def cell(metric: str) -> str:
            value = entry.get(metric)
            return f"{value['mean']}" if value else "—"
        lines.append(
            f"| {system} | {entry['n']} | {entry['failed']} | {cell('chars')} | "
            f"{cell('must_include_rate')} | {cell('violations')} | {cell('high')} | "
            f"{cell('ced_per_10k_chars')} | {cell('warnings')} |")

    paired = results.get("paired_vs_s0")
    if paired and paired.get("n_pairs"):
        lines += ["", f"S0 との対応差（N={paired['n_pairs']}、95% 区間はブートストラップ）", ""]
        lines += ["| 指標 | 平均差 (S1−S0) | 95% CI | 向き |", "| --- | ---: | --- | --- |"]
        for metric, entry in paired.items():
            if not isinstance(entry, dict):
                continue
            lines.append(f"| {metric} | {entry['mean_s1_minus_s0']:+} | "
                         f"{entry['ci95']} | {entry['direction']} |")

    lines += [
        "",
        "## 限界",
        "",
    ]
    if scripted:
        lines += [
            "- **この結果は台本（scripted fixture）による配線検証であり、モデルの性能ではありません。**",
            "- 章は 200〜280 字で、プロトコルの 1,000〜1,400 字に届いていません。",
        ]
    if "s0" in results["by_system"]:
        lines.append(
            "- S0 は canon を持たないため、継続性（違反・CED）を測れません。"
            "S0 と S1 の比較は、文体・指示追従・人間選好で行う必要があります。")
    lines += [
        "- N が小さいため、区間は広い。点推定だけを読まない。",
        "- 単一タスク・単一モデルの結果を一般的な傾向として扱わない。",
        "",
        "## 次に試すこと",
        "",
        "（記入）",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", required=True, help="experiment id (directory name)")
    parser.add_argument("--tasks", nargs="+", default=["t01"])
    parser.add_argument("--systems", nargs="+", default=["s0", "s1"], choices=["s0", "s1"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--provider", default="scripted", choices=["scripted", "command"])
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT),
                        help="scripted responses for S1 and later systems")
    parser.add_argument("--script-s0", default=str(
        REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "draft-baseline-demo.json"),
        help="scripted responses for the S0 baseline")
    parser.add_argument("--command", help="external provider command")
    parser.add_argument("--model", default=None,
                        help="model name to record (with --provider command)")
    parser.add_argument("--model-version", default=None,
                        help="model version to record (with --provider command)")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    parser.add_argument("--out", default=None, help="default: experiments/<id>")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        tasks = load_tasks(args.tasks_file)
        selected = [tasks.get(task_id) for task_id in args.tasks]
    except (TaskError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    providers = {}
    if args.provider == "command":
        if not args.command:
            print("error: --provider command requires --command", file=sys.stderr)
            return 2
        provider = CommandProvider(args.command, model=args.model or "external",
                                   model_version=args.model_version)
        providers = {system: provider for system in args.systems}
    else:
        try:
            providers = {
                "s0": ScriptedProvider(load_scripted_responses(args.script_s0)),
                **{system: ScriptedProvider(load_scripted_responses(args.script))
                   for system in args.systems if system != "s0"},
            }
        except (ProviderError, OSError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        provider = providers[args.systems[0]]

    out = Path(args.out) if args.out else REPO_ROOT / "experiments" / args.id
    out.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs)
    runs_root.mkdir(parents=True, exist_ok=True)

    cells = []
    for task in selected:
        for system in args.systems:
            for seed in args.seeds:
                cells.append(run_cell(task, system, seed, providers[system], tasks,
                                      runs_root, args.temperature))

    experiment = {
        "id": args.id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": tasks.protocol,
        "tasks": [task.id for task in selected],
        "systems": args.systems,
        "seeds": args.seeds,
        "provider": provider.name,
        "model": provider.model,
        "model_version": provider.model_version,
        "temperature": args.temperature,
        "git_commit": git_commit(),
        "cells": cells,
    }
    results = {"experiment": {k: v for k, v in experiment.items() if k != "cells"},
               **aggregate(cells)}
    (out / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "note.md").write_text(
        render_note(experiment, results, scripted=provider.name == "scripted"),
        encoding="utf-8")

    if not args.quiet:
        print(json.dumps({"experiment": args.id, "cells": len(cells),
                          "failures": sum(1 for c in cells if c["status"] != "ok"),
                          "out": str(out)}, ensure_ascii=False, indent=2))
    failures = [c for c in cells if c["status"] != "ok"]
    return 1 if failures and not any(c["status"] == "ok" for c in cells) else 0


if __name__ == "__main__":
    raise SystemExit(main())
