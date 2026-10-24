"""Deterministic voice checks: viewpoint slips, pronouns, banned voice, drift.

All pattern checks are heuristics over Japanese prose. A hit means *look
here*, never *this is wrong*: every pattern finding is capped at medium, and
every drift finding is low (informational). Doubt is resolved by a human
reader, not by a stricter regex.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..evaluation.metrics import (
    DIALOGUE, find_forbidden, load_documents, style_uniformity,
)
from .schema import FIRST_PRONOUNS, Voice

#: third-person inner-state assertion in narrative prose:
#: 「彼は悟った」「母は安堵した」. Applied to地の文 only (quotes removed).
INNER_STATE = re.compile(
    r"(彼|彼女|父|母|兄|弟|姉|妹|[^「」\s、。『』]{1,8})(は|が)"
    r"[^「」。]{0,12}(思った|感じた|考えた|決意した|悟った|気づいた|思い出した|"
    r"望んだ|恐れた|安堵した|落胆した|喜んだ|悲しんだ)")
MARKER = re.compile(r"\{\{[^}]*\}\}")

#: drift that earns a low (look-here) finding, never a failure
DRIFT_RATIO = 2.0
DIALOGUE_GAP = 0.30


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("viewpoint_slip", "視点人物以外の内面を地の文で断定していない。",
          ("narrative/us_2026:T025", "narrative/us_2026:T026",
           "narrative/japan_2026:T043")),
    Check("pronoun_drift", "宣言した一人称以外の自称が現れない（一人称のみ）。",
          ("narrative/us_2026:T027", "narrative/japan_2026:T044")),
    Check("banned_voice", "文体固有の禁止表現が出ない。",
          ("narrative/us_2026:T041", "narrative/us_2026:T042",
           "narrative/japan_2026:T050")),
    Check("sample_drift", "章の文長・会話率が固定サンプルから大きく外れない（注意喚起のみ）。",
          ("narrative/us_2026:T065", "narrative/us_2026:T066",
           "narrative/us_2025:T49")),
)


def narrative_text(line: str) -> str:
    """The line without dialogue and markers: what the narrator asserts."""
    return MARKER.sub("", DIALOGUE.sub("", line))


def _finding(check: str, severity: str, message_ja: str,
             path: str = "", line: int = 0, match: str = "") -> dict:
    return {"check": check, "severity": severity, "message_ja": message_ja,
            "evidence": {"path": path, "line": line}, "match": match}


def check_voice(voice: Voice, text_dir) -> dict:
    documents = load_documents(text_dir)
    findings: list[dict] = []
    skipped: dict[str, str] = {}
    viewpoint_names = {voice.character, *voice.aliases}

    # -- viewpoint_slip ------------------------------------------------------
    for document in documents:
        for number, line in enumerate(document.text.splitlines(), start=1):
            prose = narrative_text(line)
            if not prose.strip():
                continue
            # the viewpoint character's own inner state is allowed
            if any(name and name in prose for name in viewpoint_names):
                continue
            for match in INNER_STATE.finditer(prose):
                # first person: the narrator's own 思った/感じた is legitimate
                if voice.person == "first" and match.group(1) in set(voice.pronouns):
                    continue
                findings.append(_finding(
                    "viewpoint_slip", "medium",
                    f"視点外の内面断定の疑い（{voice.character} の視点では知りえない）。",
                    document.path.name, number, match.group(0)[:40]))

    # -- pronoun_drift ---------------------------------------------------------
    if voice.person != "first":
        skipped["pronoun_drift"] = "一人称の作品ではないため検査しない。"
    elif not voice.pronouns:
        skipped["pronoun_drift"] = "自称の宣言（pronouns）がないため検査しない。"
    else:
        declared = set(voice.pronouns)
        others = FIRST_PRONOUNS - declared
        for document in documents:
            for number, line in enumerate(document.text.splitlines(), start=1):
                prose = narrative_text(line)
                for pronoun in sorted(others):
                    if pronoun in prose:
                        findings.append(_finding(
                            "pronoun_drift", "medium",
                            f"宣言外の自称「{pronoun}」（宣言: {','.join(voice.pronouns)}）。",
                            document.path.name, number, pronoun))

    # -- banned_voice ------------------------------------------------------------
    if not voice.banned:
        skipped["banned_voice"] = "禁止表現の宣言（banned）がないため検査しない。"
    else:
        patterns = [{"id": b.id, "pattern": b.pattern,
                     "message_ja": b.message_ja, "severity": "medium"}
                    for b in voice.banned]
        for hit in find_forbidden(documents, patterns):
            if "error" in hit:
                findings.append(_finding(
                    "banned_voice", "low",
                    f"禁止表現 {hit['id']} の正規表現が不正: {hit['error']}。"))
                continue
            findings.append(_finding(
                "banned_voice", "medium",
                hit["message_ja"] or f"禁止表現 {hit['id']} に一致。",
                hit["evidence"]["path"], hit["evidence"]["line"], hit["match"]))

    # -- sample_drift (descriptive; low at most) ---------------------------------
    profile: dict = {"sample": None, "chapters": []}
    if not voice.sample:
        skipped["sample_drift"] = "固定サンプル（sample）がないため比較しない。"
    else:
        sample_style = style_uniformity([voice.sample])
        sample_mean = sample_style["sentence_length_mean"]
        profile["sample"] = {
            "chars": len(re.sub(r"\s", "", voice.sample)),
            "sentence_length_mean": sample_mean,
            "sentence_length_cv": sample_style["sentence_length_cv"],
            "dialogue_ratio": _dialogue_ratio(voice.sample),
        }
        for document in documents:
            style = style_uniformity([document.text])
            mean = style["sentence_length_mean"]
            ratio = _dialogue_ratio(document.text)
            profile["chapters"].append({
                "path": document.path.name,
                "sentence_length_mean": mean,
                "sentence_length_cv": style["sentence_length_cv"],
                "dialogue_ratio": ratio,
            })
            if sample_mean and mean:
                drift = max(mean, sample_mean) / min(mean, sample_mean)
                if drift >= DRIFT_RATIO:
                    findings.append(_finding(
                        "sample_drift", "low",
                        f"平均文長がサンプル（{sample_mean} 字）と {drift:.1f} 倍違う。"
                        "欠陥ではなく注意喚起。",
                        document.path.name, 0, ""))
            gap = abs(ratio - profile["sample"]["dialogue_ratio"])
            if gap >= DIALOGUE_GAP:
                findings.append(_finding(
                    "sample_drift", "low",
                    f"会話率がサンプルと {gap:.2f} 違う。欠陥ではなく注意喚起。",
                    document.path.name, 0, ""))

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
        "voice": str(voice.path),
        "findings": findings,
        "checks": checks,
        "profile": profile,
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
            "checks_failed": sum(1 for c in checks if c["status"] == "fail"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        },
    }


def _dialogue_ratio(text: str) -> float:
    quoted = sum(len(m.group(1)) for m in DIALOGUE.finditer(text))
    stripped = len(re.sub(r"\s", "", DIALOGUE.sub("", text)))
    total = quoted + stripped
    return round(quoted / total, 3) if total else 0.0


def render_markdown(report: dict) -> str:
    lines = ["# 文体の検査結果", "",
             f"対象: `{report['voice']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("機械的な所見はない。**文章の良し悪しは判定していない。**")
    else:
        lines.append("| 検査 | 重要度 | 位置 | 所見 |")
        lines.append("| --- | --- | --- | --- |")
        for item in report["findings"]:
            at = f"{item['evidence']['path']}:{item['evidence']['line']}" \
                if item["evidence"]["line"] else item["evidence"]["path"]
            lines.append(f"| {item['check']} | {item['severity']} | {at} "
                         f"| {item['message_ja']} |")
    lines += ["", "## 章の文体プロファイル（記述のみ）", ""]
    sample = report["profile"]["sample"]
    if sample:
        lines.append(f"サンプル: 平均文長 {sample['sentence_length_mean']} 字・"
                     f"会話率 {sample['dialogue_ratio']}")
    for chapter in report["profile"]["chapters"]:
        lines.append(f"* {chapter['path']}: 平均文長 {chapter['sentence_length_mean']} 字"
                     f"（CV {chapter['sentence_length_cv']}）・"
                     f"会話率 {chapter['dialogue_ratio']}")
    return "\n".join(lines)
