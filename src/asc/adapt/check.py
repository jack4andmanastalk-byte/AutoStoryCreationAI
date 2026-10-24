"""Structural checks for adaptation designs.

The checks ask whether the adaptation is *translated* rather than traced:
every function has a kind and a mapping (or a recorded deletion with a
substitute), both audiences are addressed, and the rights are logged.
"""
from __future__ import annotations

from dataclasses import dataclass

from .schema import AdaptationDoc

FUNCTION_KINDS = {"info", "emotion", "relation", "tempo"}
RIGHTS_STATUSES = {"cleared", "pending", "na"}


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("functions_listed", "機能が種類付きで列挙される。",
          ("narrative/us_2026:T113", "narrative/japan_2026:T115")),
    Check("mappings_assigned", "機能ごとに翻訳先の手段と両者への対応がある。",
          ("narrative/us_2026:T114", "narrative/japan_2026:T116",
           "narrative/us_2026:T115")),
    Check("deletions_recorded", "削る機能に理由と代替の機能がある。",
          ("narrative/us_2026:T113", "narrative/china_2026:G07")),
    Check("rights_logged", "権利の記録（原作・範囲・状態）がある。",
          ("narrative/japan_2026:T116",)),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "adaptation_ref": ref}


def check_adaptation(doc: AdaptationDoc) -> dict:
    findings: list[dict] = []
    known = {f.id for f in doc.functions}

    # -- functions_listed --------------------------------------------------------
    if not doc.functions:
        findings.append(_finding(
            "functions_listed", "medium",
            "機能がない。1 件以上書く。", "functions"))
    for func in doc.functions:
        ref = f"functions:{func.id or '?'}"
        if not func.id:
            findings.append(_finding(
                "functions_listed", "medium",
                "機能の ID が空欄。", "functions"))
        if func.kind not in FUNCTION_KINDS:
            findings.append(_finding(
                "functions_listed", "medium",
                f"種類「{func.kind}」は"
                f" {sorted(FUNCTION_KINDS)} のいずれかにする。", ref))
        if not func.description:
            findings.append(_finding(
                "functions_listed", "medium",
                "機能の説明が空欄。何の働きか書く。", ref))

    # -- mappings_assigned ---------------------------------------------------------
    mapped = {m.function for m in doc.mappings}
    deleted = {d.function for d in doc.deletions}
    for mapping in doc.mappings:
        ref = f"mappings:{mapping.function or '?'}"
        if mapping.function not in known:
            findings.append(_finding(
                "mappings_assigned", "medium",
                f"機能「{mapping.function}」が機能表にない。", ref))
        if not mapping.means:
            findings.append(_finding(
                "mappings_assigned", "medium",
                "翻訳先の手段（means）が空欄。媒体の固有手段で書く。", ref))
        if not mapping.newcomer:
            findings.append(_finding(
                "mappings_assigned", "medium",
                "初見への対応（newcomer）が空欄。単独で分かる形を書く。",
                ref))
        if not mapping.existing:
            findings.append(_finding(
                "mappings_assigned", "medium",
                "原作読者への対応（existing）が空欄。", ref))
    for func in doc.functions:
        if func.id and func.id not in mapped and func.id not in deleted:
            findings.append(_finding(
                "mappings_assigned", "medium",
                f"機能 {func.id} の行き先がない。翻訳か削除のどちらかに書く。",
                f"functions:{func.id}"))

    # -- deletions_recorded ------------------------------------------------------------
    for deletion in doc.deletions:
        ref = f"deletions:{deletion.function or '?'}"
        if deletion.function not in known:
            findings.append(_finding(
                "deletions_recorded", "medium",
                f"機能「{deletion.function}」が機能表にない。", ref))
        if deletion.function in mapped:
            findings.append(_finding(
                "deletions_recorded", "medium",
                f"機能 {deletion.function} は翻訳と削除の両方にある。"
                "どちらかにする。", ref))
        if not deletion.reason:
            findings.append(_finding(
                "deletions_recorded", "medium",
                "削除の理由が空欄。なぜ削るか書く。", ref))
        if not deletion.substitute:
            findings.append(_finding(
                "deletions_recorded", "medium",
                "代替の機能（substitute）が空欄。"
                "削った働きを何が担うか書く。", ref))

    # -- rights_logged ------------------------------------------------------
    if not doc.rights.source:
        findings.append(_finding(
            "rights_logged", "medium",
            "原作の指定（source）が空欄。", "rights"))
    if not doc.rights.scope:
        findings.append(_finding(
            "rights_logged", "medium",
            "利用範囲（scope）が空欄。", "rights"))
    if doc.rights.status not in RIGHTS_STATUSES:
        findings.append(_finding(
            "rights_logged", "medium",
            f"状態「{doc.rights.status}」は"
            f" {sorted(RIGHTS_STATUSES)} のいずれかにする。", "rights"))
    elif doc.rights.status == "pending":
        findings.append(_finding(
            "rights_logged", "low",
            "権利の状態が pending（確認中）。公開前に cleared にする。",
            "rights"))

    checks = []
    for spec in CHECKS:
        count = sum(1 for f in findings if f["check"] == spec.id)
        checks.append({"id": spec.id, "acceptance_ja": spec.acceptance_ja,
                       "technique_ids": list(spec.technique_ids),
                       "status": "fail" if count else "pass", "findings": count})
    by_severity: dict[str, int] = {}
    for item in findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
    return {
        "adaptation": str(doc.path),
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
    lines = ["# 翻案設計の検査結果", "",
             f"対象: `{report['adaptation']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**翻案の出来は判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['adaptation_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
