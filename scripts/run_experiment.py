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
    CommandProvider, DraftError, PlanError, ProviderError, RevisionError, RunLedger,
    ScriptedProvider, TaskError, VoicePassError, build_design, build_plan,
    build_revision, build_story, build_voice_pass, git_commit,
    load_scripted_responses, load_tasks,
)
from asc.evaluation.scope import (  # noqa: E402
    EvaluationScopeError, load_evaluation_scope,
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


def _measure_final_text(text_dir, task) -> tuple[int, float]:
    import re

    bodies = [p.read_text(encoding="utf-8") for p in sorted(text_dir.iterdir())
              if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    joined = "\n\n".join(bodies)
    chars = len(re.sub(r"\s", "", re.sub(r"\{\{[^{}]*\}\}", "", joined)))
    hits = [term in joined for term in task.must_include]
    rate = round(sum(hits) / len(hits), 3) if hits else 1.0
    return chars, rate


def _response_metrics(ledger: RunLedger) -> tuple[int, dict]:
    """Count answers and preserve their declared origin without guessing.

    Older operator responses have no provenance field. They are reported as
    ``unspecified`` rather than being silently promoted to fresh generation.
    """
    path = ledger.path / "responses.jsonl"
    if not path.is_file():
        return 0, {"counts": {}, "reused_source_run_ids": []}
    counts: dict[str, int] = {}
    reused_sources: set[str] = set()
    requests = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        requests += 1
        provenance = (entry.get("response") or {}).get("provenance") or {}
        if not isinstance(provenance, dict):
            provenance = {}
        origin = str(provenance.get("origin") or "unspecified")
        counts[origin] = counts.get(origin, 0) + 1
        source = provenance.get("source_run_id")
        if origin == "reused" and source:
            reused_sources.add(str(source))
    return requests, {
        "counts": dict(sorted(counts.items())),
        "reused_source_run_ids": sorted(reused_sources),
    }


def run_cell(task, system, seed, provider, tasks, runs_root, temperature,
             max_rounds: int = 1, design: bool = True) -> dict:
    ledger = RunLedger.create(
        runs_root, task_id=task.id, system=system, seed=seed,
        protocol_version=tasks.protocol, model=provider.model,
        provider=provider.name, temperature=temperature,
    )
    summary: dict = {"run_id": ledger.run_id, "run_dir": str(ledger.path),
                     "task": task.id, "system": system, "seed": seed,
                     "revision_rounds": None, "voice_applied": False,
                     "design": "on" if design and system != "s0" else "off"}
    canon = None
    design_dir = None
    try:
        if system != "s0":
            build_plan(task, provider, ledger, chapters=tasks.chapters,
                       target_chars=tasks.target_chars, temperature=temperature, seed=seed)
            canon = load_canon(ledger.path / "canon")
            if design:
                result = build_design(task, provider, ledger, canon,
                                      temperature=temperature, seed=seed)
                design_dir = ledger.path / "design"
                design_summary = result.as_dict()
                summary["design_findings"] = design_summary["findings"]
                summary["design_unresolved"] = len(design_summary["unresolved"])
                summary["design_missing"] = len(design_summary["missing"])
                summary["design_attempts"] = design_summary["attempts"]
                summary["design_repairs"] = design_summary["repairs"]
                summary["design_first_attempt_findings"] = \
                    design_summary["first_attempt_findings"]
            else:
                summary["design_findings"] = None
                summary["design_unresolved"] = None
                summary["design_missing"] = None
                summary["design_attempts"] = None
                summary["design_repairs"] = None
                summary["design_first_attempt_findings"] = None
        draft = build_story(task, provider, ledger, canon=canon, chapters=tasks.chapters,
                            temperature=temperature, seed=seed, design_dir=design_dir)
        summary["warnings"] = len(draft.warnings)
        summary["injected_markers"] = sum(len(c.injected) for c in draft.chapters)
        if system in {"s2", "s3"}:
            revision = build_revision(
                task, provider, ledger, canon, temperature=temperature,
                seed=seed, max_rounds=max_rounds)
            summary["revision_rounds"] = revision.rounds
            summary["revision_converged"] = revision.converged
        if system == "s3":
            voice_path = None
            if design_dir is not None:
                candidate = design_dir / "voice.json"
                if candidate.is_file():
                    voice_path = str(candidate)
            voice = build_voice_pass(
                task, provider, ledger, canon, voice_path=voice_path,
                temperature=temperature, seed=seed)
            summary["voice_applied"] = True
            summary["voice_warnings"] = len(voice.warnings)
        # S2/S3 rewrite the draft: measure the final text, not the first one.
        chars, rate = _measure_final_text(ledger.path / "text", task)
        summary["chars"] = chars
        summary["must_include_rate"] = rate
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
        summary["provider_requests"], summary["response_provenance"] = \
            _response_metrics(ledger)
        ledger.write_json("cell-summary.json", summary)
        ledger.finish("ok")
        summary["status"] = "ok"
    except (PlanError, DraftError, RevisionError, VoicePassError,
            ProviderError) as exc:
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
                       "injected_markers", "revision_rounds", "design_findings",
                       "design_unresolved", "provider_requests", "design_attempts",
                       "design_repairs", "design_first_attempt_findings"):
            values = [row[metric] for row in ok if row.get(metric) is not None]
            if not values:
                continue
            entry[metric] = {
                "mean": round(statistics.fmean(values), 3),
                "min": min(values), "max": max(values),
                "ci95": bootstrap_ci([float(v) for v in values]),
                "n": len(values),
            }
        origin_counts: dict[str, int] = {}
        reused_sources: set[str] = set()
        for row in ok:
            provenance = row.get("response_provenance") or {}
            for origin, count in (provenance.get("counts") or {}).items():
                origin_counts[origin] = origin_counts.get(origin, 0) + count
            reused_sources.update(provenance.get("reused_source_run_ids") or [])
        entry["response_provenance"] = {
            "counts": dict(sorted(origin_counts.items())),
            "reused_source_run_ids": sorted(reused_sources),
        }
        by_system_summary[system] = entry

    result: dict = {"by_system": by_system_summary}
    if "s0" in by_system:
        base = {(c["task"], c["seed"]): c for c in by_system["s0"] if c["status"] == "ok"}
        for candidate in ("s1", "s2", "s3"):
            if candidate not in by_system:
                continue
            pairs = []
            for cell in by_system[candidate]:
                key = (cell["task"], cell["seed"])
                if cell["status"] == "ok" and key in base:
                    pairs.append((base[key], cell))
            paired: dict = {"n_pairs": len(pairs), "candidate": candidate}
            for metric in ("chars", "must_include_rate", "violations", "high",
                           "ced_per_10k_chars", "warnings"):
                diffs = [float(b[metric]) - float(a[metric])
                         for a, b in pairs
                         if a.get(metric) is not None and b.get(metric) is not None]
                if diffs:
                    paired[metric] = {
                        f"mean_{candidate}_minus_s0": round(statistics.fmean(diffs), 3),
                        "ci95": bootstrap_ci(diffs),
                        "n": len(diffs),
                        "direction": "lower_is_better" if metric in {
                            "violations", "high", "ced_per_10k_chars", "warnings"
                        } else "descriptive",
                    }
            # "paired_vs_s0" stays the s1 comparison (existing notes rely on it).
            key = "paired_vs_s0" if candidate == "s1" else f"paired_vs_s0_{candidate}"
            result[key] = paired
    return result


def render_note(experiment: dict, results: dict, scripted: bool,
                evaluation_scope: dict | None = None) -> str:
    lines = [
        f"# 実験 {experiment['id']}",
        "",
        f"- 実施: {experiment['created_at']}",
        f"- プロトコル: `{experiment['protocol']}`",
        f"- タスク: {', '.join(experiment['tasks'])}",
        f"- 系: {', '.join(experiment['systems'])}",
        f"- seed: {', '.join(str(s) for s in experiment['seeds'])}",
        f"- 設計ステージ: {'on' if experiment.get('design', True) else 'off'}",
        f"- プロバイダ: `{experiment['provider']}`",
        f"- コード: `{experiment['git_commit'] or 'unknown'}`",
        "",
        "## 仮説",
        "",
        "（記入）S1（canon＋設計書を使う系）は S0（単発プロンプト）より、継続性の欠陥が少ない。",
        "",
        "## 結果",
        "",
        "| 系 | N | 失敗 | 文字数 | 必須語 | 違反 | high | CED | 警告 | 設計所見 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for system, entry in results["by_system"].items():
        def cell(metric: str) -> str:
            value = entry.get(metric)
            return f"{value['mean']}" if value else "—"
        lines.append(
            f"| {system} | {entry['n']} | {entry['failed']} | {cell('chars')} | "
            f"{cell('must_include_rate')} | {cell('violations')} | {cell('high')} | "
            f"{cell('ced_per_10k_chars')} | {cell('warnings')} | "
            f"{cell('design_findings')} |")

    for key in ("paired_vs_s0", "paired_vs_s0_s2", "paired_vs_s0_s3"):
        paired = results.get(key)
        if not paired or not paired.get("n_pairs"):
            continue
        candidate = paired.get("candidate", "s1").upper()
        lines += ["", f"S0 との対応差（{candidate}、N={paired['n_pairs']}、"
                      "95% 区間はブートストラップ）", ""]
        lines += [f"| 指標 | 平均差 ({candidate}−S0) | 95% CI | 向き |",
                  "| --- | ---: | --- | --- |"]
        mean_key = f"mean_{paired.get('candidate', 's1')}_minus_s0"
        for metric, entry in paired.items():
            if not isinstance(entry, dict):
                continue
            lines.append(f"| {metric} | {entry[mean_key]:+} | "
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
    if not experiment.get("design", True):
        lines.append(
            "- **設計ステージが off のため、S1 は設計書なしの条件である。**"
            "本実験の条件と混ぜて集計しない。")
    l1_only = bool(evaluation_scope and evaluation_scope.get("mode") == "l1-only")
    if "s0" in results["by_system"]:
        if l1_only:
            lines.append(
                "- S0 は canon を持たないため、継続性（違反・CED）を S1–S3 と"
                "直接比較しません。L1-only では必須語・禁止パターンなど、"
                "両系を同じ方法で測れる指標だけを比較します。")
        else:
            lines.append(
                "- S0 は canon を持たないため、継続性（違反・CED）を測れません。"
                "S0 と S1 の比較は、文体・指示追従・人間選好で行う必要があります。")
    if l1_only:
        lines.append(
            "- **評価範囲は L1-only**。L2/L3 は 2026-10-24 に運用凍結されたため、"
            "G3/G4 は未測定であり、意味的な作品品質や人間の選好は評価していません"
            "（`docs/evaluation_scope.md`）。")
    version = str(experiment.get("model_version") or "")
    if "unversioned" in version:
        lines.append(
            "- **G5 を主張しません**。Arena のモデル版を固定できないため、"
            "この実験の L1 の値も protocol-v1 の合格証拠ではなく探索的な参考値です。")
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
    parser.add_argument("--systems", nargs="+", default=["s0", "s1"],
                        choices=["s0", "s1", "s2", "s3"])
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
    parser.add_argument("--max-rounds", type=int, default=1,
                        help="revision rounds for s2/s3 (default: 1)")
    parser.add_argument("--design", dest="design", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="run the design stage for s1/s2/s3 (default: on; "
                             "--no-design is for debugging and ablation only)")
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    parser.add_argument("--out", default=None, help="default: experiments/<id>")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        tasks = load_tasks(args.tasks_file)
        selected = [tasks.get(task_id) for task_id in args.tasks]
        evaluation_scope = load_evaluation_scope()
    except (TaskError, EvaluationScopeError, OSError) as exc:
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
                                      runs_root, args.temperature,
                                      max_rounds=args.max_rounds, design=args.design))

    experiment = {
        "id": args.id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": tasks.protocol,
        "tasks": [task.id for task in selected],
        "systems": args.systems,
        "seeds": args.seeds,
        "design": args.design,
        "provider": provider.name,
        "model": provider.model,
        "model_version": provider.model_version,
        "temperature": args.temperature,
        "git_commit": git_commit(),
        "cells": cells,
    }
    results = {"experiment": {k: v for k, v in experiment.items() if k != "cells"},
               "evaluation_scope": evaluation_scope,
               **aggregate(cells)}
    (out / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "note.md").write_text(
        render_note(experiment, results, scripted=provider.name == "scripted",
                    evaluation_scope=evaluation_scope),
        encoding="utf-8")

    if not args.quiet:
        print(json.dumps({"experiment": args.id, "cells": len(cells),
                          "failures": sum(1 for c in cells if c["status"] != "ok"),
                          "out": str(out)}, ensure_ascii=False, indent=2))
    failures = [c for c in cells if c["status"] != "ok"]
    return 1 if failures and not any(c["status"] == "ok" for c in cells) else 0


if __name__ == "__main__":
    raise SystemExit(main())
