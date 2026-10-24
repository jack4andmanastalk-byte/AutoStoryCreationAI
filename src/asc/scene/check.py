"""Structural checks for scene information, with canon cross-references.

The checks ask whether each scene *works*: it has a job (purpose, conflict,
change), a declared tension device, a tracked knowledge flow, a disclosure
plan that accounts for what characters learn, and foreshadowing that is paid
after it is planted. Every canon chapter must have at least one scene.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import SceneDoc

TENSION_DEVICES = {"suspense", "curiosity", "surprise", "irony",
                   "deadline", "quiet"}


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("scene_purposed", "場面に目的・対立・変化がある。",
          ("narrative/us_2026:T035", "narrative/us_2026:T005")),
    Check("tension_designed", "場面に緊張の型がある。",
          ("narrative/us_2026:T009", "narrative/us_2026:T010",
           "narrative/us_2026:T013", "narrative/us_2026:T015",
           "narrative/us_2026:T011")),
    Check("knowledge_tracked", "入場時と獲得の知識が追跡され、開示と一致する。",
          ("narrative/us_2026:T014", "narrative/us_2026:T016")),
    Check("disclosure_planned", "開示と保留が分かれ、保留に理由がある。",
          ("narrative/us_2026:T016", "narrative/japan_2026:T039")),
    Check("foreshadow_tagged", "回収は実在の布石を指し、仕掛けは回収より前にある。",
          ("narrative/us_2026:T012", "narrative/japan_2026:T034",
           "narrative/japan_2026:T037")),
    Check("scenes_cover", "全章に場面があり、場面の章が実在する。",
          ("narrative/us_2026:T005",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "scene_ref": ref}


def _chapter_key(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return f"ch{int(match.group(1)):02d}"
    return text


def check_scenes(doc: SceneDoc, canon=None) -> dict:
    findings: list[dict] = []
    skipped: dict[str, str] = {}
    characters = set(canon.characters) if canon is not None else set()
    facts = set(canon.facts) if canon is not None else set()
    chapters = set(canon.chapters) if canon is not None else set()
    days = {cid: ch.day for cid, ch in (canon.chapters.items()
                                        if canon is not None else [])}
    foreshadows = set(canon.foreshadowing) if canon is not None else set()

    if not doc.scenes:
        findings.append(_finding(
            "scene_purposed", "medium", "場面がない。1 件以上書く。", "scenes"))

    for scene in doc.scenes:
        ref = f"scenes:{scene.id}"
        # -- scene_purposed --------------------------------------------------
        for field, label in (("purpose", "目的"), ("conflict", "対立"),
                             ("change", "変化")):
            if not getattr(scene, field):
                findings.append(_finding(
                    "scene_purposed", "medium",
                    f"{label}が空欄。1 文で書く。", ref))
        # -- tension_designed -------------------------------------------------
        if scene.tension not in TENSION_DEVICES:
            findings.append(_finding(
                "tension_designed", "medium",
                f"緊張の型「{scene.tension}」は"
                f" {sorted(TENSION_DEVICES)} のいずれかにする。", ref))
        # -- knowledge_tracked ---------------------------------------------------
        for flow in scene.knowledge:
            if characters and flow.character not in characters:
                findings.append(_finding(
                    "knowledge_tracked", "medium",
                    f"人物「{flow.character}」が canon にいない。", ref))
            for fact in flow.entry + flow.gained:
                if facts and fact not in facts:
                    findings.append(_finding(
                        "knowledge_tracked", "medium",
                        f"事実「{fact}」が canon にない。", ref))
            withheld_facts = {item.fact for item in scene.withheld}
            for fact in flow.gained:
                if fact not in scene.disclosed and fact not in withheld_facts:
                    findings.append(_finding(
                        "knowledge_tracked", "medium",
                        f"{flow.character} が得る {fact} が開示計画にない。"
                        "開示か保留のどちらかに書く。", ref))
        # -- disclosure_planned -------------------------------------------------------
        disclosed = set(scene.disclosed)
        if facts:
            for fact in scene.disclosed:
                if fact not in facts:
                    findings.append(_finding(
                        "disclosure_planned", "medium",
                        f"開示する事実「{fact}」が canon にない。", ref))
        for item in scene.withheld:
            if not item.fact:
                findings.append(_finding(
                    "disclosure_planned", "medium",
                    "保留する事実が空欄。", ref))
            elif item.fact in disclosed:
                findings.append(_finding(
                    "disclosure_planned", "medium",
                    f"{item.fact} は開示と保留の両方にある。どちらかにする。",
                    ref))
            if facts and item.fact and item.fact not in facts:
                findings.append(_finding(
                    "disclosure_planned", "medium",
                    f"保留する事実「{item.fact}」が canon にない。", ref))
            if not item.reason:
                findings.append(_finding(
                    "disclosure_planned", "medium",
                    f"{item.fact or '保留'}に理由がない。なぜ伏せるか書く。",
                    ref))
        # -- foreshadow_tagged ---------------------------------------------------------
        for paid in scene.paid:
            if foreshadows and paid not in foreshadows:
                findings.append(_finding(
                    "foreshadow_tagged", "medium",
                    f"回収する布石「{paid}」が canon の伏線表にない。", ref))
        for plant in scene.planted:
            if not plant.id:
                findings.append(_finding(
                    "foreshadow_tagged", "medium",
                    "仕掛ける布石の ID が空欄。", ref))
            elif foreshadows and plant.id in foreshadows:
                findings.append(_finding(
                    "foreshadow_tagged", "medium",
                    f"布石「{plant.id}」は canon に既にある。新規 ID にする。",
                    ref))
            if plant.payoff:
                key = _chapter_key(plant.payoff)
                if chapters and key not in chapters:
                    findings.append(_finding(
                        "foreshadow_tagged", "medium",
                        f"回収予定の章「{plant.payoff}」が canon の年表にない。",
                        ref))
                elif chapters:
                    day_here = days.get(_chapter_key(scene.chapter))
                    day_pay = days.get(key)
                    if (day_here is not None and day_pay is not None
                            and day_pay < day_here):
                        findings.append(_finding(
                            "foreshadow_tagged", "medium",
                            f"布石 {plant.id} の回収（{plant.payoff}）が"
                            f"仕掛け（{scene.chapter}）より前にある。", ref))

    # -- scenes_cover ------------------------------------------------------
    if canon is None:
        skipped["scenes_cover"] = "canon が無いため被覆を検査しない。"
    else:
        covered = set()
        for scene in doc.scenes:
            key = _chapter_key(scene.chapter)
            if key not in chapters:
                findings.append(_finding(
                    "scenes_cover", "medium",
                    f"場面 {scene.id} の章「{scene.chapter}」が canon の年表にない。",
                    f"scenes:{scene.id}"))
            else:
                covered.add(key)
        missing = sorted(chapters - covered)
        if missing:
            findings.append(_finding(
                "scenes_cover", "medium",
                f"場面のない章: {', '.join(missing)}。", "scenes"))

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
        "scenes": str(doc.path),
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
    lines = ["# 場面情報の検査結果", "",
             f"対象: `{report['scenes']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**場面の面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['scene_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
