"""Structural checks for world rules, with canon cross-references.

The checks ask whether the world *constrains* the story: axioms exist, every
rule has a cost, exceptions are bounded, geography matches the canon's
locations, and disclosure points at real chapters. They never ask whether the
world is original or immersive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import World

CHAPTER_REF = re.compile(r"^(ch\d+|第\d+章|\d+)$")


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("axiom_declared", "変えてはいけない前提（公理）が 1 件以上ある。",
          ("narrative/us_2026:T049", "narrative/japan_2026:T005")),
    Check("rule_has_cost", "すべての規則にコスト（代償・制約）がある。",
          ("narrative/us_2026:T050", "narrative/us_2026:T051",
           "production/game_narrative_us:P10")),
    Check("exception_bounded", "例外には条件があり、無条件の抜け道がない。",
          ("narrative/us_2026:T052", "production/game_narrative_us:P15")),
    Check("geography_grounded", "地理の地名が canon の場所と対応する。",
          ("narrative/us_2026:T053", "production/game_narrative_us:P02")),
    Check("disclosure_ordered", "開示計画が実在の章を指し、内容が書かれている。",
          ("narrative/japan_2026:T106",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str = "world") -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "world_ref": ref}


def check_world(world: World, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}

    # -- axiom_declared ------------------------------------------------------
    if not world.axioms:
        findings.append(_finding(
            "axiom_declared", "medium",
            "公理がない。世界で変えてはいけない前提を 1 件以上書く。"))

    # -- rule_has_cost ---------------------------------------------------------
    if not world.rules:
        findings.append(_finding(
            "rule_has_cost", "medium",
            "規則がない。人物の選択を拘束する規則を 1 件以上書く。"))
    for rule in world.rules:
        ref = f"rules:{rule.id}"
        if not rule.statement:
            findings.append(_finding(
                "rule_has_cost", "medium", "規則の本文が空欄。", ref))
        if len(re.sub(r"\s", "", rule.cost)) < 5:
            findings.append(_finding(
                "rule_has_cost", "medium",
                "コストが無いか短い（5 字以上）。代償なき力は物語を壊す。", ref))

    # -- exception_bounded -------------------------------------------------------
    for rule in world.rules:
        ref = f"rules:{rule.id}"
        if rule.exception and not rule.exception_condition.strip():
            findings.append(_finding(
                "exception_bounded", "medium",
                "例外に条件がない。いつ・誰に例外が適用されるかを書く。", ref))

    # -- geography_grounded ------------------------------------------------------
    if canon is None:
        skipped["geography_grounded"] = "canon が無いため照合しない。"
    else:
        places = {loc.id for loc in canon.locations.values()}
        places |= {c.location for c in canon.chapters.values() if c.location}
        for place in world.geography:
            if place not in places:
                findings.append(_finding(
                    "geography_grounded", "medium",
                    f"地名「{place}」が canon の場所にない。表記か canon を直す。",
                    f"geography:{place}"))

    # -- disclosure_ordered --------------------------------------------------------
    chapters = set()
    if canon is not None:
        chapters = set(canon.chapters)
    for i, item in enumerate(world.disclosure, start=1):
        ref = f"disclosure[{i}]"
        if len(re.sub(r"\s", "", item.info)) < 5:
            findings.append(_finding(
                "disclosure_ordered", "medium",
                "開示する情報が短い（5 字以上）。何を開示するか書く。", ref))
        if chapters:
            key = _chapter_key(item.chapter)
            if key not in chapters:
                findings.append(_finding(
                    "disclosure_ordered", "medium",
                    f"開示先の章「{item.chapter}」が canon の年表にない。", ref))
        elif not CHAPTER_REF.match(item.chapter.strip()):
            findings.append(_finding(
                "disclosure_ordered", "low",
                f"開示先「{item.chapter}」が章の形（ch01 等）をしていない。", ref))

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
        "world": str(world.path),
        "findings": findings,
        "checks": checks,
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
            "checks_failed": sum(1 for c in checks if c["status"] == "fail"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        },
    }


def _chapter_key(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return f"ch{int(match.group(1)):02d}"
    return text


def render_markdown(report: dict) -> str:
    lines = ["# 世界規則の検査結果", "",
             f"対象: `{report['world']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**世界の面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['message_ja']} |")
    return "\n".join(lines)
