"""Evaluation harness: L1 deterministic checks, L2 model judgement, L3 human labels.

The three layers are reported separately and never collapsed into one score.

* **L1** — counts, pattern matches and the continuity audit. Deterministic, free,
  and the only layer that can *fail* a build on its own.
* **L2** — model-graded rubric scores with evidence. Skipped when no judge is
  configured; a score without evidence is flagged, not silently accepted.
* **L3** — human or expert preference. Only computed when labels are supplied.
  L2 is calibrated against it, never the other way round.

Failure taxonomy: every defect (a continuity violation, a forbidden pattern, a
low rubric dimension) is mapped to an owning skill and a concrete next action,
so that an evaluation ends in a change list rather than a number.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..story.canon import CanonError
from ..story.continuity import audit_texts
from .judge import Judge, JudgeError, compare_pairwise
from .metrics import Document, density, find_forbidden, load_documents, measure
from .rubric import Rubric, load_rubric

#: defect -> (分類, 担当, 次の一手)
TAXONOMY: dict[str, dict] = {
    "dead_character_reappears": {
        "category": "整合性 / 人物状態",
        "owner": "skills/continuity-ledger",
        "action_ja": "死亡章以降の参照を削除するか、suppressions.yaml に理由つきで登録する。",
    },
    "knowledge_violation": {
        "category": "整合性 / 知識状態",
        "owner": "skills/continuity-ledger",
        "action_ja": "学習章を前へ移すか、その人物が知らない前提で台詞を書き直す。",
    },
    "foreshadow_order": {
        "category": "整合性 / 伏線",
        "owner": "skills/continuity-ledger",
        "action_ja": "設置を回収より前の章へ移す。回収だけの伏線は設置を書く。",
    },
    "unresolved_foreshadow": {
        "category": "整合性 / 伏線",
        "owner": "skills/continuity-ledger",
        "action_ja": "回収を書くか、続巻送りとして canon から外す。",
    },
    "travel_time": {
        "category": "整合性 / 時空間",
        "owner": "skills/continuity-ledger",
        "action_ja": "章の日付を動かすか、移動日数表を見直す。",
    },
    "stated_age": {
        "category": "整合性 / 時空間",
        "owner": "skills/continuity-ledger",
        "action_ja": "年齢の明示を修正する。誕生日を canon に追加すると自動検査できる。",
    },
    "forbidden_pattern": {
        "category": "文体 / 表層",
        "owner": "skills/voice-style",
        "action_ja": "該当箇所を言い換える。多用されている場合はテンプレート側を直す。",
    },
    "low_dimension": {
        "category": "質 / ルーブリック",
        "owner": "skills/premise-brief",
        "action_ja": "次元ごとの担当スキルで原因を切り分ける（下の次元別チケットを参照）。",
    },
}

DIMENSION_OWNERS = {
    "coherence": ("skills/continuity-ledger", "因果の欠落。台帳で前章との接続を確認する。"),
    "character_consistency": ("skills/character-core", "欲望・恐れ・知識の整合を人物表で確認する。"),
    "world_rule_consistency": ("skills/world-rules", "規則とコストの記述を世界設定に戻す。"),
    "originality": ("skills/premise-brief", "既存の型の組合せから外れた要素を企画段階で足す。"),
    "reader_orientation": ("skills/scene-information", "初出情報の提示順を場面表で直す。"),
    "prose_control": ("skills/voice-style", "文長・表記・視点の揺れを文体ガイドで揃える。"),
}

def _story_label(directory) -> str:
    """A stable name for a chapter directory (``.../demo/text`` -> ``demo``)."""
    path = Path(directory)
    name = path.name
    if name in {"text", "chapters", "manuscript", "out"} and path.parent.name:
        return path.parent.name
    return name


def _extract_coded(report: dict) -> list[dict]:
    """Turn continuity violations into taxonomy rows."""
    rows = []
    for violation in report.get("violations", []):
        entry = TAXONOMY.get(violation["type"])
        if not entry:
            continue
        rows.append({
            "source": "continuity",
            "code": violation["type"],
            "category": entry["category"],
            "owner": entry["owner"],
            "action_ja": entry["action_ja"],
            "severity": violation["severity"],
            "detail": violation["message_ja"],
            "chapter": violation.get("chapter"),
        })
    return rows


def _gate(results: dict) -> list[dict]:
    gates = []
    summary = results["l1"]["continuity"]["summary"] if results["l1"]["continuity"] else None
    gates.append({
        "id": "no_high_severity_continuity",
        "status": "skipped" if summary is None else
                  ("pass" if summary["by_severity"].get("high", 0) == 0 else "fail"),
        "detail_ja": "high の整合性違反が 0 件であること。",
    })
    verdicts = results["l2"].get("verdicts") or []
    unevidenced = [v for v in verdicts if v["unevidenced"]]
    gates.append({
        "id": "all_verdicts_evidenced",
        "status": "skipped" if not verdicts else ("pass" if not unevidenced else "fail"),
        "detail_ja": "L2 の全判定に根拠（引用または位置）が付いていること。",
    })
    gates.append({
        "id": "no_regression",
        "status": ("skipped" if not results.get("comparison")
                   else ("pass" if not results["comparison"].get("regressions") else "fail")),
        "detail_ja": "ベースラインと比べて悪化した指標がないこと。",
    })
    return gates


def evaluate(
    candidate_dir: str | Path,
    *,
    canon_dir: str | Path | None = None,
    baseline_dir: str | Path | None = None,
    rubric_path: str | Path | None = None,
    patterns_path: str | Path | None = None,
    judge: Judge | None = None,
    human_labels: str | Path | None = None,
    out_dir: str | Path | None = None,
    allow_length_gap: bool = False,
    regression_margin: float = 0.0,
    label: str | None = None,
) -> dict:
    candidate_docs = load_documents(candidate_dir)
    if not candidate_docs:
        raise FileNotFoundError(f"no chapters in {candidate_dir}")
    l1: dict = {"metrics": measure(candidate_docs)}

    patterns = []
    if patterns_path:
        patterns = load_patterns(patterns_path)
    l1["forbidden"] = find_forbidden(candidate_docs, patterns) if patterns else []
    l1["patterns_configured"] = patterns

    continuity = None
    if canon_dir:
        try:
            continuity = audit_texts(canon_dir, candidate_dir)
        except CanonError as exc:
            raise CanonError(f"continuity audit failed: {exc}") from exc
    l1["continuity"] = continuity

    chars = l1["metrics"]["chars"]
    l1["densities"] = {
        "ced_per_10k_chars": continuity["summary"]["ced_per_10k_chars"] if continuity else None,
        "forbidden_per_10k_chars": density(len(l1["forbidden"]), chars),
    }

    tickets: list[dict] = []
    tickets += _extract_coded(continuity) if continuity else []
    for hit in l1["forbidden"]:
        entry = TAXONOMY["forbidden_pattern"]
        tickets.append({
            "source": "pattern", "code": "forbidden_pattern", "category": entry["category"],
            "owner": entry["owner"], "action_ja": entry["action_ja"],
            "severity": hit.get("severity", "low"),
            "detail": f"{hit.get('id')}: {hit.get('message_ja')}",
            "chapter": hit["evidence"]["path"],
        })

    rubric = load_rubric(rubric_path) if rubric_path else None
    story_label = label or _story_label(candidate_dir)
    baseline_docs = load_documents(baseline_dir) if baseline_dir else None
    baseline_label = _story_label(baseline_dir) if baseline_dir else None
    l2: dict = {"status": "skipped", "reason_ja": "judge が設定されていない", "verdicts": []}
    if judge is not None and rubric is not None:
        story = "\n\n".join(d.text for d in candidate_docs)
        try:
            verdicts = judge.score_story(story, rubric, {"story": story_label})
        except JudgeError as exc:
            l2 = {"status": "error", "reason_ja": str(exc), "verdicts": []}
        else:
            l2 = {"status": "ok", "judge": judge.name,
                  "verdicts": [v.as_dict() for v in verdicts]}
            for verdict in l2["verdicts"]:
                if verdict["score"] is None:
                    continue
                threshold = rubric.scale_min + (rubric.scale_max - rubric.scale_min) * 0.4
                if verdict["score"] <= threshold:
                    owner, action = DIMENSION_OWNERS.get(
                        verdict["dimension"], ("skills/premise-brief", "原因を切り分ける。"))
                    tickets.append({
                        "source": "rubric", "code": "low_dimension",
                        "category": f"質 / {verdict['dimension']}", "owner": owner,
                        "action_ja": action, "severity": "medium",
                        "detail": f"{verdict['dimension']}={verdict['score']} "
                                  f"（基準 {threshold:.1f} 以下）",
                        "chapter": None,
                    })
    elif judge is not None and rubric is None:
        l2 = {"status": "skipped", "reason_ja": "rubric が指定されていない", "verdicts": []}

    comparison = None
    if baseline_docs is not None:
        comparison = _compare(candidate_docs, baseline_docs, l1, canon_dir, patterns,
                              judge, rubric, baseline_label, regression_margin, l2)
        if judge is not None and rubric is not None and judge.supports_pairwise:
            story = "\n\n".join(d.text for d in candidate_docs)
            baseline_story = "\n\n".join(d.text for d in baseline_docs)
            ratio = abs(len(story) - len(baseline_story)) / max(len(story), len(baseline_story))
            comparison["length_gap_ratio"] = round(ratio, 3)
            comparison["length_confound"] = ratio > 0.25
            if ratio > 0.25 and not allow_length_gap:
                comparison["pairwise"] = None
                comparison["pairwise_skipped_ja"] = (
                    "文字数の差が 25% を超えるためペア比較を省略した（長さバイアス）。"
                    "比較するには --allow-length-gap を付ける。")
            else:
                try:
                    comparison["pairwise"] = compare_pairwise(
                        judge, story, baseline_story, rubric,
                        {"story": story_label, "baseline": baseline_label})
                except JudgeError as exc:
                    comparison["pairwise"] = None
                    comparison["pairwise_error_ja"] = str(exc)

    l3 = {"status": "skipped", "reason_ja": "人間ラベルが指定されていない"}
    if human_labels:
        l3 = _calibrate(human_labels, comparison)

    results = {
        "schema_version": "1.0",
        "tool": "evaluation-harness",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate": str(candidate_dir),
        "candidate_label": story_label,
        "baseline": str(baseline_dir) if baseline_dir else None,
        "baseline_label": baseline_label,
        "rubric": rubric.as_dict() if rubric else None,
        "l1": l1,
        "l2": l2,
        "l3": l3,
        "comparison": comparison,
        "tickets": tickets,
        "tickets_by_owner": _group(tickets),
    }
    results["gates"] = _gate(results)
    results["status"] = ("fail" if any(g["status"] == "fail" for g in results["gates"])
                         else "pass")
    if out_dir:
        write_outputs(results, out_dir)
    return results


def _group(tickets: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for ticket in tickets:
        grouped.setdefault(ticket["owner"], []).append(ticket)
    return {owner: rows for owner, rows in sorted(grouped.items())}


def _marker_coverage(report: dict) -> float:
    """Share of chapters that carry at least one marker.

    Two texts can only be compared by error density if both were written with
    comparable instrumentation. A draft without markers is audited less
    thoroughly, not cleaner.
    """
    chapters = report.get("chapters") or []
    if not chapters:
        return 0.0
    return round(sum(1 for c in chapters if c.get("markers")) / len(chapters), 3)


def _compare(candidate_docs, baseline_docs, l1, canon_dir, patterns, judge, rubric,
             baseline_label, margin, l2=None) -> dict:
    """Compare two works.

    Only defects are treated as regressions: the continuity error density (when a
    canon is given), the forbidden-pattern density, and — when a judge is
    configured — the rubric dimensions. Length, dialogue ratio and sentence
    variation are reported as **descriptive** deltas: a story is not better for
    having longer paragraphs, and treating those numbers as scores would be a
    category error.
    """
    baseline = measure(baseline_docs)
    current = l1["metrics"]
    descriptive: dict[str, dict] = {}

    def note(name, now, before):
        if now is None or before is None:
            return
        descriptive[name] = {"candidate": now, "baseline": before,
                             "delta": round(now - before, 3)}

    note("chars", current["chars"], baseline["chars"])
    note("dialogue_ratio", current["dialogue_ratio"], baseline["dialogue_ratio"])
    note("mean_paragraph_chars", current["mean_paragraph_chars"],
         baseline["mean_paragraph_chars"])
    note("sentence_length_cv", current["style"]["sentence_length_cv"],
         baseline["style"]["sentence_length_cv"])

    regressions: list[str] = []
    defects: dict[str, dict] = {}
    coverage_warnings: list[str] = []

    baseline_chars = baseline["chars"]
    baseline_forbidden = find_forbidden(baseline_docs, patterns) if patterns else []
    cand_forbidden_density = l1["densities"]["forbidden_per_10k_chars"]
    base_forbidden_density = density(len(baseline_forbidden), baseline_chars)
    if cand_forbidden_density is not None and base_forbidden_density is not None:
        delta = round(cand_forbidden_density - base_forbidden_density, 3)
        defects["forbidden_per_10k_chars"] = {
            "candidate": cand_forbidden_density, "baseline": base_forbidden_density,
            "delta": delta, "direction": "lower_is_better",
        }
        if delta > margin:
            regressions.append("forbidden_per_10k_chars")

    baseline_continuity = None
    if canon_dir:
        try:
            baseline_continuity = audit_texts(canon_dir, str(baseline_docs[0].path.parent))
        except CanonError:
            baseline_continuity = None
    if baseline_continuity and l1.get("continuity"):
        cand_ced = l1["continuity"]["summary"]["ced_per_10k_chars"]
        base_ced = baseline_continuity["summary"]["ced_per_10k_chars"]
        coverage_cand = _marker_coverage(l1["continuity"])
        coverage_base = _marker_coverage(baseline_continuity)
        comparable = abs(coverage_cand - coverage_base) <= 0.3
        if cand_ced is not None and base_ced is not None:
            delta = round(cand_ced - base_ced, 3)
            defects["ced_per_10k_chars"] = {
                "candidate": cand_ced, "baseline": base_ced, "delta": delta,
                "direction": "lower_is_better",
                "comparable": comparable,
                "coverage": {"candidate": coverage_cand, "baseline": coverage_base},
                "note_ja": ("監査カバレッジ（マーカーのある章の割合）が"
                            f"{coverage_cand:.0%} と {coverage_base:.0%} で異なるため、"
                            "この差は欠陥の比較として使えない。")
                if not comparable else "",
            }
            if comparable and delta > margin:
                regressions.append("ced_per_10k_chars")
            elif not comparable:
                coverage_warnings.append(
                    f"CED を比較しなかった: 監査カバレッジ {coverage_cand:.0%} vs {coverage_base:.0%}")

    dimensions: dict[str, dict] = {}
    baseline_verdicts = None
    if judge is not None and rubric is not None:
        baseline_story = "\n\n".join(d.text for d in baseline_docs)
        try:
            baseline_verdicts = judge.score_story(
                baseline_story, rubric, {"story": baseline_label})
        except JudgeError as exc:
            baseline_verdicts = None
            dimensions["_error_ja"] = str(exc)
        if baseline_verdicts:
            scores = {v.dimension: v.score for v in baseline_verdicts}
            for verdict in ((l2 or {}).get("verdicts") or []):
                before = scores.get(verdict["dimension"])
                after = verdict["score"]
                if before is None or after is None:
                    continue
                delta = round(after - before, 2)
                dimensions[verdict["dimension"]] = {
                    "candidate": after, "baseline": before, "delta": delta,
                    "direction": "higher_is_better",
                }
                if delta < -margin:
                    regressions.append(f"dimension:{verdict['dimension']}")

    return {
        "descriptive": descriptive,
        "defects": defects,
        "dimensions": dimensions,
        "regressions": sorted(set(regressions)),
        "warnings_ja": coverage_warnings,
        "baseline_metrics": baseline,
        "baseline_continuity": (baseline_continuity["summary"]
                                if baseline_continuity else None),
        "baseline_verdicts": ([v.as_dict() for v in baseline_verdicts]
                              if baseline_verdicts else None),
    }


def _calibrate(labels_path, comparison) -> dict:
    path = Path(labels_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not items:
        return {"status": "skipped", "reason_ja": "ラベルが空"}
    winners = [str(item.get("winner", "tie")).lower() for item in items]
    counts = {w: winners.count(w) for w in ("a", "b", "tie")}
    result = {"status": "ok", "raters": sorted({item.get("rater", "?") for item in items}),
              "n": len(items), "distribution": counts}
    pairwise = (comparison or {}).get("pairwise")
    if pairwise:
        agree = sum(1 for w in winners if w == pairwise["winner"])
        result["agreement_with_judge"] = round(agree / len(winners), 3)
        result["judge_winner"] = pairwise["winner"]
    else:
        result["agreement_with_judge"] = None
        result["note_ja"] = "ペア比較が実行されていないため一致率は計算できない。"
    # a single-rater set cannot measure agreement between humans
    if len(result["raters"]) < 2:
        result["warning_ja"] = "評定者が 1 名のため、人間間の一致は測れない。"
    return result


def load_patterns(path: str | Path) -> list[dict]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml
        data = yaml.safe_load(text)
    patterns = (data or {}).get("patterns") or []
    for row in patterns:
        if not row.get("pattern"):
            raise ValueError(f"{path.name}: every pattern needs a 'pattern'")
    return patterns


def write_outputs(results: dict, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(render_markdown(results) + "\n", encoding="utf-8")
    if results["l1"].get("continuity"):
        (out / "continuity.json").write_text(
            json.dumps(results["l1"]["continuity"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")


def render_markdown(results: dict) -> str:
    l1, l2, l3 = results["l1"], results["l2"], results["l3"]
    metrics = l1["metrics"]
    lines = [
        "# 評価レポート",
        "",
        f"対象: `{results['candidate']}`"
        + (f" / 基準: `{results['baseline']}`" if results["baseline"] else ""),
        "",
        f"**状態: {results['status'].upper()}**",
        "",
        "| ゲート | 状態 | 条件 |",
        "| --- | --- | --- |",
    ]
    for gate in results["gates"]:
        lines.append(f"| `{gate['id']}` | {gate['status']} | {gate['detail_ja']} |")

    lines += [
        "",
        "## L1 決定論的検査",
        "",
        f"* 文字数 {metrics['chars']:,} / 段落 {metrics['paragraphs']} / "
        f"会話率 {metrics['dialogue_ratio']:.0%}",
        f"* 違反密度（CED 相当）: "
        f"{l1['densities']['ced_per_10k_chars']} / 1万文字、"
        f"禁止パターン {l1['densities']['forbidden_per_10k_chars']} / 1万文字",
    ]
    if l1.get("continuity"):
        summary = l1["continuity"]["summary"]
        lines.append(
            f"* 継続性違反 {summary['violations']} 件"
            f"（high {summary['by_severity'].get('high', 0)} / "
            f"medium {summary['by_severity'].get('medium', 0)} / "
            f"low {summary['by_severity'].get('low', 0)}）")
        skipped = [c["id"] for c in l1["continuity"]["checks"] if c["status"] == "skipped"]
        if skipped:
            lines.append(f"* 実行できなかった検査: {', '.join(skipped)}（canon の不足）")
        covered = sum(1 for c in l1["continuity"]["chapters"] if c["markers"])
        total = len(l1["continuity"]["chapters"])
        lines.append(f"* 監査カバレッジ: {covered}/{total} 章にマーカーあり"
                     "（低い場合、0 件は「矛盾なし」ではなく「未検査」）")

    lines += ["", "## L2 モデル判定", ""]
    if l2["status"] != "ok":
        lines.append(f"スキップ: {l2.get('reason_ja', '')}")
    else:
        lines += [f"判定器: `{l2['judge']}`", "",
                  "| 次元 | 点 | 根拠 | 所見 |", "| --- | ---: | --- | --- |"]
        for verdict in l2["verdicts"]:
            evidence = verdict["evidence"]
            if evidence:
                where = evidence[0].get("path", "")
                if evidence[0].get("line"):
                    where += f":{evidence[0]['line']}"
            else:
                where = "（根拠なし）" if verdict["unevidenced"] else "（根拠は任意）"
            flag = " ⚠" if verdict["unevidenced"] else ""
            lines.append(f"| {verdict['dimension']} | {verdict['score']} | {where}{flag} "
                         f"| {verdict['rationale_ja'][:80]} |")

    lines += ["", "## L3 人間評価", ""]
    if l3["status"] != "ok":
        lines.append(f"スキップ: {l3.get('reason_ja', '')}")
    else:
        lines.append(f"評定 {l3['n']} 件 / 評定者 {len(l3['raters'])} 名。"
                     f"判定器との一致率: {l3['agreement_with_judge']}")
        if l3.get("warning_ja"):
            lines.append(f"注意: {l3['warning_ja']}")

    if results.get("comparison"):
        comparison = results["comparison"]
        lines += ["", "## ベースライン比較", "",
                  "### 欠陥（悪化すると失敗）", "",
                  "| 指標 | 候補 | 基準 | 差 |", "| --- | ---: | ---: | ---: |"]
        for name, row in comparison.get("defects", {}).items():
            suffix = "" if row.get("comparable", True) else "（比較不可）"
            lines.append(f"| {name}{suffix} | {row['candidate']} | {row['baseline']} | "
                         f"{row['delta']:+} |")
        for warning in comparison.get("warnings_ja") or []:
            lines.append("")
            lines.append(f"⚠ {warning}")
        for name, row in comparison.get("dimensions", {}).items():
            if name.startswith("_"):
                continue
            lines.append(f"| dimension:{name} | {row['candidate']} | {row['baseline']} | "
                         f"{row['delta']:+} |")
        lines += ["", "### 記述統計（良し悪しを意味しない）", "",
                  "| 指標 | 候補 | 基準 | 差 |", "| --- | ---: | ---: | ---: |"]
        for name, row in comparison.get("descriptive", {}).items():
            lines.append(f"| {name} | {row['candidate']} | {row['baseline']} | "
                         f"{row['delta']:+} |")
        if comparison["regressions"]:
            lines.append("")
            lines.append(f"**悪化**: {', '.join(comparison['regressions'])}")
        if comparison.get("pairwise"):
            pairwise = comparison["pairwise"]
            lines.append("")
            lines.append(f"ペア比較: 勝者 `{pairwise['winner']}`"
                         + ("（順序バイアスのため引き分け扱い）"
                            if pairwise["position_bias"] else ""))
        elif comparison.get("pairwise_skipped_ja"):
            lines.append("")
            lines.append(comparison["pairwise_skipped_ja"])

    lines += ["", "## 改善チケット", ""]
    if not results["tickets"]:
        lines.append("なし。")
    else:
        lines += ["| 担当 | 分類 | 件数 | 次の一手 |", "| --- | --- | ---: | --- |"]
        for owner, rows in results["tickets_by_owner"].items():
            by_category: dict[str, list[dict]] = {}
            for row in rows:
                by_category.setdefault(row["category"], []).append(row)
            for category, items in sorted(by_category.items()):
                lines.append(f"| `{owner}` | {category} | {len(items)} | "
                             f"{items[0]['action_ja']} |")

    lines += ["", "## この評価で分からないこと", ""]
    lines += [
        "* L1 は整合性の一部（台帳にある項目）しか見ない。意味の破綻は対象外。",
        "* L2 の点数は判定器に依存する。判定器名・版・設定を記録しない比較は無効。",
        "* L3 が無い場合、L2 の妥当性は測れていない。",
        "* 単一の総合点は出さない。次元ごとの差を見る。",
        "",
    ]
    return "\n".join(lines)


def render_json(results: dict) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
