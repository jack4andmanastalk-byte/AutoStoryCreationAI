"""Structural checks for character cores, with canon cross-references.

The checks ask whether each character is *modelled* rather than listed:
WANT/NEED separated, views separated, choices predicted under varied
pressure, voice fixed in a sample, arc endpoints decided. Whether the model
holds on the page is checked by voice-style (speech) and L2 (choices).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import CharacterDoc

#: predictions per character: one choice proves nothing; three show a pattern
MIN_PREDICTIONS = 3


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("core_declared", "WANT・NEED・恐れ・行動原理が書かれている。",
          ("narrative/japan_2026:T023", "narrative/japan_2026:T021",
           "narrative/us_2026:T018")),
    Check("views_separated", "自己像と他者からの見え方が分かれている。",
          ("narrative/us_2026:T022", "narrative/japan_2026:T029")),
    Check("choices_predicted", "状況を変えた選択の予測が 3 件以上ある。",
          ("narrative/us_2026:T019", "narrative/us_2026:T017")),
    Check("voice_fixed", "口調サンプルと語彙・回避の規則がある。",
          ("production/game_narrative_us:P07", "narrative/us_2026:T023")),
    Check("arc_decided", "アークの終点と、変わる選択・変わらない選択がある。",
          ("narrative/japan_2026:T024", "narrative/us_2026:T020")),
    Check("canon_grounded", "人物 ID が canon に存在する。",
          ("narrative/japan_2026:T022",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "character_ref": ref}


def check_characters(doc: CharacterDoc, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}

    if not doc.characters:
        findings.append(_finding(
            "core_declared", "medium",
            "人物がいない。1 人以上書く。", "characters"))

    for char in doc.characters:
        ref = f"characters:{char.id}"
        # -- core_declared --------------------------------------------------
        for field, label in (("want", "WANT（失いたくないもの）"),
                             ("need", "NEED（本当に必要なもの）"),
                             ("fear", "恐れ"), ("principle", "行動原理")):
            if not getattr(char, field):
                findings.append(_finding(
                    "core_declared", "medium", f"{label}が空欄。", ref))
        if char.want and char.need and char.want == char.need:
            findings.append(_finding(
                "core_declared", "medium",
                "WANT と NEED が同一文。別々に書く。", ref))
        # -- views_separated --------------------------------------------------
        if not char.self_view:
            findings.append(_finding(
                "views_separated", "medium", "自己像（self_view）が空欄。", ref))
        if not char.others_view:
            findings.append(_finding(
                "views_separated", "medium",
                "他者からの見え方（others_view）が空欄。", ref))
        # -- choices_predicted --------------------------------------------------
        if len(char.predictions) < MIN_PREDICTIONS:
            findings.append(_finding(
                "choices_predicted", "medium",
                f"選択の予測が {len(char.predictions)} 件"
                f"（{MIN_PREDICTIONS} 件必要）。状況を変えて足す。", ref))
        for i, prediction in enumerate(char.predictions, start=1):
            if not prediction.situation or not prediction.choice:
                findings.append(_finding(
                    "choices_predicted", "medium",
                    f"予測 {i} の状況か選択が空欄。", ref))
        # -- voice_fixed ------------------------------------------------------
        if len(re.sub(r"\s", "", char.speech.sample)) < 30:
            findings.append(_finding(
                "voice_fixed", "medium",
                "口調サンプルが短い（30 字以上）。会話を書き写す。", ref))
        if not char.speech.vocab:
            findings.append(_finding(
                "voice_fixed", "medium",
                "語彙の規則（vocab）が空欄。使う語を固定する。", ref))
        # -- arc_decided ------------------------------------------------------
        if not char.arc.endpoint:
            findings.append(_finding(
                "arc_decided", "medium", "アークの終点が空欄。", ref))
        if not char.arc.changed:
            findings.append(_finding(
                "arc_decided", "medium",
                "変わる選択（changed）が空欄。終点で変わるものを書く。", ref))
        if not char.arc.unchanged:
            findings.append(_finding(
                "arc_decided", "medium",
                "変わらない選択（unchanged）が空欄。核として残るものを書く。", ref))

    # -- canon_grounded ------------------------------------------------------
    if canon is None:
        skipped["canon_grounded"] = "canon が無いため照合しない。"
    else:
        known = set(canon.characters)
        for char in doc.characters:
            if char.id not in known:
                findings.append(_finding(
                    "canon_grounded", "medium",
                    f"人物「{char.id}」が canon にいない。ID か canon を直す。",
                    f"characters:{char.id}"))

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
        "characters": str(doc.path),
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
    lines = ["# 人物核の検査結果", "",
             f"対象: `{report['characters']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**人物の魅力は判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['character_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
