"""Structural checks for history: order, causality, traces, canon split.

The checks ask whether the past *explains* the present: years run forward,
causes precede effects, every event leaves a trace, invention and citation
are separated, and the knowledge map matches the canon's characters. They
never ask whether the history is moving or plausible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import SOURCE_ORIGINS, History


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("chronology_ordered", "年表が年代順に並び、紀年の逆行がない。",
          ("production/game_narrative_us:P11",
           "history_myth/comparative_mythology:CM-HIST-01")),
    Check("causality_linked", "原因の参照が実在の出来事を指し、年代が前後しない。",
          ("production/game_narrative_us:P12",
           "history_myth/comparative_mythology:CM-HIST-02")),
    Check("trace_exists", "すべての出来事に残された痕跡がある。",
          ("production/game_narrative_us:P13",
           "history_myth/comparative_mythology:CM-HIST-03")),
    Check("canon_separated", "正史と異説が分かれ、実在史料と創作が混ざらない。",
          ("production/game_narrative_us:P24",
           "history_myth/comparative_mythology:CM-HIST-04",
           "history_myth/comparative_mythology:CM-HIST-05")),
    Check("knowledge_consistent", "知識地図の人物・出来事が canon・年表に存在する。",
          ("production/game_narrative_us:P39", "narrative/us_2026:T053")),
)


def _finding(check: str, severity: str, message_ja: str, ref: str = "history") -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "history_ref": ref}


def check_history(history: History, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}
    by_id = {event.id: event for event in history.events}

    # -- chronology_ordered ------------------------------------------------------
    if not history.events:
        findings.append(_finding(
            "chronology_ordered", "medium",
            "出来事がない。年表を 1 件以上書く。"))
    years = [event.year for event in history.events]
    if years != sorted(years):
        findings.append(_finding(
            "chronology_ordered", "medium",
            "年表が年代順に並んでいない。年の昇順に並べ替える。"))
    for era in history.eras:
        if era.begins is not None and era.ends is not None and era.ends < era.begins:
            findings.append(_finding(
                "chronology_ordered", "medium",
                f"時代 {era.id} の終わりが始まりより前。", f"eras:{era.id}"))

    # -- causality_linked ----------------------------------------------------------
    for event in history.events:
        ref = f"events:{event.id}"
        if not event.title:
            findings.append(_finding(
                "causality_linked", "medium", "出来事の題が空欄。", ref))
        if event.cause:
            cause = by_id.get(event.cause)
            if cause is None:
                findings.append(_finding(
                    "causality_linked", "medium",
                    f"原因の参照「{event.cause}」が年表にない。", ref))
            elif cause.year > event.year:
                findings.append(_finding(
                    "causality_linked", "medium",
                    f"原因 {event.cause}（{cause.year} 年）が結果より後。", ref))

    # -- trace_exists ----------------------------------------------------------------
    for event in history.events:
        if len(re.sub(r"\s", "", event.trace)) < 5:
            findings.append(_finding(
                "trace_exists", "medium",
                "痕跡が無いか短い（5 字以上）。出来事の残した物を書く。",
                f"events:{event.id}"))

    # -- canon_separated -----------------------------------------------------------------
    # ``apocrypha`` stores sayings, not event IDs. Match each saying against
    # the event's human-readable fields after removing punctuation/spacing;
    # accept an event ID as well for older data that used that convention.
    def normalise_claim(value: str) -> str:
        return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)

    for apocryphal in history.apocrypha:
        claim = normalise_claim(apocryphal)
        represented = apocryphal in by_id or any(
            claim and claim in normalise_claim(" ".join(
                (event.title, event.effect, event.trace)))
            for event in history.events)
        if not represented:
            findings.append(_finding(
                "canon_separated", "medium",
                f"異説「{apocryphal}」が年表にない。",
                f"apocrypha:{apocryphal}"))
    for source in history.sources:
        ref = f"sources:{source.id}"
        origin_kind = source.origin.split(":", 1)[0].strip()
        if origin_kind not in SOURCE_ORIGINS:
            findings.append(_finding(
                "canon_separated", "medium",
                f"由来 '{source.origin}' は invented / adapted / cited のいずれかにする。",
                ref))
        if origin_kind == "cited" and not source.citation.strip():
            findings.append(_finding(
                "canon_separated", "medium",
                "実在史料の引用には citation（書誌情報）が要る。創作なら adapted にする。",
                ref))
        if not source.holder.strip():
            findings.append(_finding(
                "canon_separated", "low",
                "史料の保持者（holder）が空欄。誰が持ち、誰が消したかを書く。", ref))

    # -- knowledge_consistent ----------------------------------------------------------------
    if canon is None:
        # without a canon, only the event references can be checked
        for character, entry in history.knowledge.items():
            for event_id in (*entry["knows"], *entry["unknown"]):
                if event_id not in by_id:
                    findings.append(_finding(
                        "knowledge_consistent", "medium",
                        f"知識地図の出来事「{event_id}」が年表にない。",
                        f"knowledge:{character}"))
    else:
        characters = set(canon.characters)
        for character, entry in history.knowledge.items():
            ref = f"knowledge:{character}"
            if character not in characters:
                findings.append(_finding(
                    "knowledge_consistent", "medium",
                    f"知識地図の人物「{character}」が canon にいない。", ref))
            for event_id in (*entry["knows"], *entry["unknown"]):
                if event_id not in by_id:
                    findings.append(_finding(
                        "knowledge_consistent", "medium",
                        f"知識地図の出来事「{event_id}」が年表にない。", ref))
            overlap = set(entry["knows"]) & set(entry["unknown"])
            if overlap:
                findings.append(_finding(
                    "knowledge_consistent", "medium",
                    f"「{sorted(overlap)[0]}」が既知と未知の両方にある。", ref))

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
        "history": str(history.path),
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
    lines = ["# 年表の検査結果", "",
             f"対象: `{report['history']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**歴史の説得力は判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['message_ja']} |")
    return "\n".join(lines)
