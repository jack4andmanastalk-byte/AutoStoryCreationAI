"""Structural checks for a premise brief.

Every check here is mechanical: sentence counts, required fields, declared
elements appearing in the logline, contrast markers in the theme. None of them
ask whether the premise is good, original or moving — those judgements belong
to L2/L3. A brief with zero findings is *checkable*, not *good*.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import ELEMENT_KEYS, SIMILAR_AXES, Brief

SENTENCE_END = re.compile(r"[。．！？!?]")
CONTRAST = re.compile(r"対|vs\.?|ｖｓ|⇔|〈〉|↔", re.IGNORECASE)
QUESTION_END = re.compile(r"[?？]\s*$|か\s*[。．]?\s*$")

#: A logline is one sentence a producer can repeat. These bounds only catch
#: fragments and paragraphs; anything inside still needs a human reader.
LOGLINE_MIN_CHARS = 20
LOGLINE_MAX_CHARS = 300


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("logline_form", "ログラインは一文で、20〜300 字に収まる。",
          ("narrative/us_2026:T001", "narrative/japan_2026:T003")),
    Check("logline_elements", "宣言した四要素（誰・どこ・望み・妨げ）がログラインに現れる。",
          ("narrative/us_2026:T001", "narrative/us_2026:T002")),
    Check("theme_contrast", "主題は対立命題の形（A対B）をしている。",
          ("narrative/us_2026:T006", "narrative/japan_2026:T008")),
    Check("similar_grounded", "類似作が 3 件以上あり、差分の軸と内容が書かれている。",
          ("narrative/japan_2026:T006",)),
    Check("prohibition_testable", "禁止条件に、後工程が判定できる確認方法がある。",
          ("narrative/us_2026:T006", "narrative/us_2025:T14")),
    Check("question_form", "失敗の問いが、検証可能な問いの形をしている。",
          ("narrative/japan_2026:T006", "narrative/us_2025:T14")),
)


def _finding(check: str, severity: str, message_ja: str, ref: str = "brief") -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "brief_ref": ref}


def check_brief(brief: Brief) -> dict:
    """Run every structural check. Never raises on content; findings carry it."""
    findings: list[dict] = []

    # -- logline_form ------------------------------------------------------
    sentences = [s for s in SENTENCE_END.split(brief.logline) if s.strip()]
    chars = len(re.sub(r"\s", "", brief.logline))
    if len(sentences) != 1:
        findings.append(_finding(
            "logline_form", "medium",
            f"ログラインが {len(sentences)} 文ある。一文に圧縮する。"))
    if not LOGLINE_MIN_CHARS <= chars <= LOGLINE_MAX_CHARS:
        findings.append(_finding(
            "logline_form", "medium",
            f"ログラインが {chars} 字（目安 {LOGLINE_MIN_CHARS}〜{LOGLINE_MAX_CHARS} 字）。"))

    # -- logline_elements ---------------------------------------------------
    for key in ELEMENT_KEYS:
        element = brief.elements.get(key, "")
        if not element:
            findings.append(_finding(
                "logline_elements", "medium",
                f"四要素の '{key}' が空欄。分からない場合は「未定」と書く。"))
        elif element != "未定" and element not in brief.logline:
            findings.append(_finding(
                "logline_elements", "medium",
                f"四要素 '{key}'（{element}）がログラインに現れない。"))

    # -- theme_contrast ------------------------------------------------------
    match = CONTRAST.search(brief.theme)
    if not match:
        findings.append(_finding(
            "theme_contrast", "medium",
            "主題に対立の印（対・vs・⇔など）がない。『A対B』の形にする。"))
    else:
        left, right = brief.theme[:match.start()], brief.theme[match.end():]
        if len(left.strip()) < 2 or len(right.strip()) < 2:
            findings.append(_finding(
                "theme_contrast", "medium",
                "対立命題の片側が短すぎる。両項を名詞句以上で書く。"))

    # -- similar grounded ----------------------------------------------------
    if len(brief.similar) < 3:
        findings.append(_finding(
            "similar_grounded", "medium",
            f"類似作が {len(brief.similar)} 件（3 件必要）。思いつく範囲で足す。"))
    for i, work in enumerate(brief.similar, start=1):
        ref = f"similar[{i}]"
        if not work.title:
            findings.append(_finding(
                "similar_grounded", "medium", "類似作の題名が空欄。", ref))
        if work.axis not in SIMILAR_AXES:
            findings.append(_finding(
                "similar_grounded", "medium",
                f"差分の軸 '{work.axis}' は structure / character / world のいずれかにする。", ref))
        if len(re.sub(r"\s", "", work.difference)) < 10:
            findings.append(_finding(
                "similar_grounded", "medium",
                "差分の説明が短い（10 字以上）。何がどう違うかを書く。", ref))

    # -- prohibition_testable --------------------------------------------------
    if not brief.prohibitions:
        findings.append(_finding(
            "prohibition_testable", "low",
            "禁止条件がない。「やらないこと」を 1 件以上書く。"))
    for i, ban in enumerate(brief.prohibitions, start=1):
        ref = f"prohibitions[{i}]"
        if not ban.rule:
            findings.append(_finding(
                "prohibition_testable", "medium", "禁止条件の本文が空欄。", ref))
        if len(re.sub(r"\s", "", ban.check_ja)) < 10:
            findings.append(_finding(
                "prohibition_testable", "medium",
                "確認方法（check_ja）が短い（10 字以上）。後工程が判定できる書き方にする。", ref))

    # -- question_form ---------------------------------------------------------
    if not brief.failure_questions:
        findings.append(_finding(
            "question_form", "low",
            "失敗の問いがない。失敗仮説を 1 件以上、問いの形で書く。"))
    for i, question in enumerate(brief.failure_questions, start=1):
        if not QUESTION_END.search(question):
            findings.append(_finding(
                "question_form", "medium",
                f"問いの形になっていない（？・か で終わる）: {question[:30]}…",
                f"failure_questions[{i}]"))

    by_check: dict[str, str] = {}
    for spec in CHECKS:
        relevant = [f for f in findings if f["check"] == spec.id]
        by_check[spec.id] = "fail" if relevant else "pass"

    checks = [{"id": spec.id, "acceptance_ja": spec.acceptance_ja,
               "technique_ids": list(spec.technique_ids),
               "status": by_check[spec.id],
               "findings": sum(1 for f in findings if f["check"] == spec.id)}
              for spec in CHECKS]
    by_severity: dict[str, int] = {}
    for item in findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
    return {
        "brief": str(brief.path),
        "findings": findings,
        "checks": checks,
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
            "checks_failed": sum(1 for c in checks if c["status"] == "fail"),
        },
    }


def render_markdown(report: dict) -> str:
    lines = ["# 企画核の検査結果", "",
             f"対象: `{report['brief']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['message_ja']} |")
    return "\n".join(lines)
