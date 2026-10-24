"""Structural checks for relationship webs, with canon cross-references.

The checks ask whether the web *pressures* the scenes: every pair has a
public face and real stakes, at least one conflict is incompatible, knowledge
claims match the canon's facts and known-sets, changes point at real chapters
through action, and silences mean something. Unpresented relations are
reported as wishes, never trusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import RelationDoc

KNOWLEDGE_STATES = {"knows", "unknown", "suspects"}


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("pair_grounded", "関係ごとの表向きと利害があり、人物が実在する。",
          ("production/game_narrative_us:P07", "narrative/china_2026:C05")),
    Check("conflict_declared", "両立しない目的の組合せが 1 件以上ある。",
          ("narrative/japan_2026:T025", "narrative/us_2026:T018")),
    Check("knowledge_tabled", "知識状態が表になり、事実・人物が実在する。",
          ("production/game_narrative_us:P19",)),
    Check("knowledge_matches_canon", "知識表が canon の既知集合と矛盾しない。",
          ("production/game_narrative_us:P19", "narrative/japan_2026:T027")),
    Check("change_staged", "関係の変化が章・契機・変化後の形で設計される。",
          ("narrative/japan_2026:T031", "narrative/us_2026:T023")),
    Check("silence_meant", "沈黙・言い淀みに意味（言わないこと）がある。",
          ("narrative/us_2026:T024",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "relation_ref": ref}


def _chapter_key(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return f"ch{int(match.group(1)):02d}"
    return text


def check_relations(doc: RelationDoc, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}
    characters = set(canon.characters) if canon is not None else set()
    facts = set(canon.facts) if canon is not None else set()
    chapters = set(canon.chapters) if canon is not None else set()
    declared_pairs = {tuple(sorted((p.a, p.b))) for p in doc.pairs}

    if not doc.pairs:
        findings.append(_finding(
            "pair_grounded", "medium",
            "関係がない。1 件以上書く。", "pairs"))

    # -- pair_grounded / conflict_declared -----------------------------------
    for pair in doc.pairs:
        ref = f"pairs:{pair.a}-{pair.b}"
        if not pair.public:
            findings.append(_finding(
                "pair_grounded", "medium", "表向きの関係が空欄。", ref))
        if not pair.stakes:
            findings.append(_finding(
                "pair_grounded", "medium", "実際の利害が空欄。", ref))
        if canon is not None:
            for person in (pair.a, pair.b):
                if person not in characters:
                    findings.append(_finding(
                        "pair_grounded", "medium",
                        f"人物「{person}」が canon にいない。", ref))
    if doc.pairs and not any(p.conflict for p in doc.pairs):
        findings.append(_finding(
            "conflict_declared", "medium",
            "両立しない目的の組合せがない。衝突を 1 件以上書く。", "pairs"))

    # -- knowledge_tabled -----------------------------------------------------
    if not doc.knowledge:
        findings.append(_finding(
            "knowledge_tabled", "low",
            "知識状態の表がない。誰が何を知るかを書く。", "knowledge"))
    for entry in doc.knowledge:
        ref = f"knowledge:{entry.character}-{entry.fact}"
        if entry.state not in KNOWLEDGE_STATES:
            findings.append(_finding(
                "knowledge_tabled", "medium",
                f"状態 '{entry.state}' は knows / unknown / suspects のいずれかにする。",
                ref))
        if canon is not None:
            if entry.character not in characters:
                findings.append(_finding(
                    "knowledge_tabled", "medium",
                    f"人物「{entry.character}」が canon にいない。", ref))
            if entry.fact not in facts:
                findings.append(_finding(
                    "knowledge_tabled", "medium",
                    f"事実「{entry.fact}」が canon にない。", ref))

    # -- knowledge_matches_canon ------------------------------------------------
    if canon is None:
        skipped["knowledge_matches_canon"] = "canon が無いため照合しない。"
    else:
        for entry in doc.knowledge:
            char = canon.characters.get(entry.character)
            if char is None or entry.fact not in facts:
                continue  # reported by knowledge_tabled
            if entry.state == "unknown" and entry.fact in (char.knows or []):
                findings.append(_finding(
                    "knowledge_matches_canon", "medium",
                    f"{entry.character} は canon で {entry.fact} を既知。"
                    "知識表か canon を直す。",
                    f"knowledge:{entry.character}-{entry.fact}"))

    # -- change_staged ------------------------------------------------------------
    for change in doc.changes:
        ref = f"changes:{change.pair[0]}-{change.pair[1]}@{change.chapter}"
        if tuple(sorted(change.pair)) not in declared_pairs:
            findings.append(_finding(
                "change_staged", "medium",
                "変化の相手が関係表にない。関係を先に書く。", ref))
        if not change.trigger:
            findings.append(_finding(
                "change_staged", "medium",
                "変化の契機が空欄。選択と行動で書く。", ref))
        if not change.after:
            findings.append(_finding(
                "change_staged", "medium", "変化後の関係が空欄。", ref))
        if chapters:
            if _chapter_key(change.chapter) not in chapters:
                findings.append(_finding(
                    "change_staged", "medium",
                    f"変化の章「{change.chapter}」が canon の年表にない。", ref))

    # -- silence_meant ----------------------------------------------------------------
    for i, silence in enumerate(doc.silences, start=1):
        ref = f"silences[{i}]"
        if not silence.unsaid_ja:
            findings.append(_finding(
                "silence_meant", "medium",
                "言わないこと（unsaid_ja）が空欄。沈黙の意味を書く。", ref))
        if canon is not None and silence.who and silence.who not in characters:
            findings.append(_finding(
                "silence_meant", "medium",
                f"人物「{silence.who}」が canon にいない。", ref))
        if chapters and silence.chapter and \
                _chapter_key(silence.chapter) not in chapters:
            findings.append(_finding(
                "silence_meant", "medium",
                f"沈黙の章「{silence.chapter}」が canon の年表にない。", ref))

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
        "relations": str(doc.path),
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
    lines = ["# 関係網の検査結果", "",
             f"対象: `{report['relations']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**関係の面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['relation_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
