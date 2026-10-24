"""Structural checks for plot architecture, with canon cross-references.

The checks ask whether the plot is *engineered*: acts cover the chapters,
turns are tied to protagonist choices, every subplot has beats and a
convergence, the ending is designed (not merely arrived at), and every
unresolved item is either tied to foreshadowing or declared intentional.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import PlotDoc

MIN_TURNS, MAX_TURNS = 3, 5
ENDING_KINDS = {"resolved", "bittersweet", "open"}


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("acts_cover", "幕が章を過不足なく覆い、各幕に問いがある。",
          ("narrative/japan_2026:T009", "narrative/us_2026:T004",
           "narrative/japan_2026:T010")),
    Check("turns_placed", "転換点が 3～5 件あり、主人公の選択に結び付く。",
          ("narrative/us_2026:T002", "narrative/japan_2026:T011")),
    Check("subplots_allocated", "副筋に節目と本筋への合流がある。",
          ("narrative/us_2026:T007", "narrative/japan_2026:T018")),
    Check("ending_designed", "結末の型・要約・余韻がある。",
          ("narrative/us_2026:T008", "narrative/japan_2026:T013")),
    Check("debts_listed", "未回収が棚卸しされ、伏線か意図に結び付く。",
          ("narrative/japan_2026:T015",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "plot_ref": ref}


def _chapter_key(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return f"ch{int(match.group(1)):02d}"
    return text


def check_plot(doc: PlotDoc, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}
    chapters = set(canon.chapters) if canon is not None else set()
    foreshadows = set(canon.foreshadowing) if canon is not None else set()

    # -- acts_cover -------------------------------------------------------------
    if not doc.acts:
        findings.append(_finding(
            "acts_cover", "medium", "幕がない。2 幕以上に割る。", "acts"))
    covered: list[str] = []
    for act in doc.acts:
        ref = f"acts:{act.id or '?'}"
        if not act.chapters:
            findings.append(_finding(
                "acts_cover", "medium", "幕の章割りがない。", ref))
        if not act.question:
            findings.append(_finding(
                "acts_cover", "medium",
                "幕の問い（question）が空欄。この幕が問うものを書く。", ref))
        covered.extend(_chapter_key(c) for c in act.chapters)
    if chapters:
        missing = sorted(chapters - set(covered))
        if missing:
            findings.append(_finding(
                "acts_cover", "medium",
                f"幕割にない章: {', '.join(missing)}。", "acts"))
        extra = sorted(set(covered) - chapters)
        if extra:
            findings.append(_finding(
                "acts_cover", "medium",
                f"canon にない章: {', '.join(extra)}。", "acts"))
    seen: set[str] = set()
    doubled = sorted({c for c in covered if c in seen or seen.add(c)})
    if doubled:
        findings.append(_finding(
            "acts_cover", "medium",
            f"複数幕に属する章: {', '.join(doubled)}。", "acts"))

    # -- turns_placed ---------------------------------------------------------------
    if not MIN_TURNS <= len(doc.turns) <= MAX_TURNS:
        findings.append(_finding(
            "turns_placed", "medium",
            f"転換点が {len(doc.turns)} 件"
            f"（{MIN_TURNS}～{MAX_TURNS} 件必要）。", "turns"))
    for turn in doc.turns:
        ref = f"turns:{turn.id or '?'}"
        if not turn.choice_ja:
            findings.append(_finding(
                "turns_placed", "medium",
                "主人公の選択（choice_ja）が空欄。出来事ではなく選択で書く。", ref))
        if chapters and turn.chapter and \
                _chapter_key(turn.chapter) not in chapters:
            findings.append(_finding(
                "turns_placed", "medium",
                f"転換点の章「{turn.chapter}」が canon の年表にない。", ref))

    # -- subplots_allocated -----------------------------------------------------------
    for subplot in doc.subplots:
        ref = f"subplots:{subplot.id or '?'}"
        if not subplot.beats:
            findings.append(_finding(
                "subplots_allocated", "medium",
                "副筋の節目（beats）が空欄。起動・干渉・決着を書く。", ref))
        if not subplot.converges:
            findings.append(_finding(
                "subplots_allocated", "medium",
                "本筋への合流（converges）が空欄。どこで交わるか書く。", ref))

    # -- ending_designed -------------------------------------------------------------
    if doc.ending.kind not in ENDING_KINDS:
        findings.append(_finding(
            "ending_designed", "medium",
            f"結末の型「{doc.ending.kind}」は"
            f" {sorted(ENDING_KINDS)} のいずれかにする。", "ending"))
    if not doc.ending.summary:
        findings.append(_finding(
            "ending_designed", "medium",
            "結末の要約が空欄。結末から逆算して書く。", "ending"))
    if not doc.ending.aftertaste_ja:
        findings.append(_finding(
            "ending_designed", "medium",
            "余韻（aftertaste_ja）が空欄。読後に残るものを書く。", "ending"))

    # -- debts_listed --------------------------------------------------------------
    for i, item in enumerate(doc.unresolved, start=1):
        ref = f"unresolved[{i}]"
        if not item.item:
            findings.append(_finding(
                "debts_listed", "medium", "未回収の内容が空欄。", ref))
        if item.intentional:
            continue
        if not item.foreshadowing:
            findings.append(_finding(
                "debts_listed", "medium",
                "布石の指定がない。布石 ID を書くか、意図的未回収と宣言する。",
                ref))
        elif foreshadows and item.foreshadowing not in foreshadows:
            findings.append(_finding(
                "debts_listed", "medium",
                f"布石「{item.foreshadowing}」が canon の伏線表にない。", ref))

    checks = []
    for spec in CHECKS:
        if spec.id in skipped:
            checks.append({"id": spec.id, "acceptance_ja": spec.acceptance_ja,
                           "technique_ids": list(spec.technique_ids),
                           "status": "skipped", "reason": skipped[spec.id],
                           "findings": 0})
        else:
            count = sum(1 for f in findings if f["check"] == spec.id)
            checks.append({"id": spec.id, "acceptance_ja": spec.acceptance_ja,
                           "technique_ids": list(spec.technique_ids),
                           "status": "fail" if count else "pass", "findings": count})
    by_severity: dict[str, int] = {}
    for item in findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
    return {
        "plot": str(doc.path),
        "findings": findings,
        "checks": checks,
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
            "checks_failed": sum(1 for c in checks if c["status"] == "fail"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        },
    }


def render_markdown(report: dict) -> str:
    lines = ["# 筋立ての検査結果", "",
             f"対象: `{report['plot']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**筋の面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['plot_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
