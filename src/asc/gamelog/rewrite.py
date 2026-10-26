"""Deterministic Stage B checks: rewritten prose vs the verified game log.

The rewritten chapter is a rendering of the log, not a new story. Four
mechanical questions are asked of it:

* ``marker_sequence`` — does the prose contain exactly the derived marker
  sequence (``time`` / ``location`` / ``learn`` / ``fore shadow``), in order?
* ``character_boundary`` — does the prose mention only characters the log put
  on stage, or a dead person *through* a declared medium (or a reference cue) in
the same sentence?
  A chapter-level declaration is not enough: naming the dead in a sentence
  without its record/relic/recollection wording could be a present-time act.
* ``fact_boundary`` — does the prose leak a fact before its canon ``setup``
  chapter or a fact the design withheld for this chapter? Does it introduce a
  marker that gives a dead person a present-time state change?
* ``voice_contract`` — do the voice document's banned patterns appear, and is
  the chapter at least minimally non-empty?

All findings are heuristic *look-here* signals except the marker and
dead-actor-marker ones, which are exact. ``medium``/``high`` findings cause a
repair round; nothing here assesses literary quality (L2/L3 stay frozen).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..evaluation.metrics import Document, find_forbidden
from ..scene.schema import SceneDoc
from ..story.canon import Canon
from ..style.schema import Voice
from .markers import (DEAD_ACTOR_MARKER_KINDS, DERIVED_KINDS,
                      expected_marker_texts, prose_markers)
from .schema import GameLog, REFERENCE_TYPES

MARKER_RE = re.compile(r"\{\{[^{}]*\}\}")
REPAIR_SEVERITIES = frozenset({"high", "medium"})


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    limits_ja: str


CHECKS: tuple[Check, ...] = (
    Check("marker_sequence", "本文のマーカー列がゲームログの導出列と完全一致する。",
          "マーカーの文字列と順序だけを見る。散文の内容は見ない。"),
    Check("character_boundary",
          "本文に出る人物がログの登場人物か、媒体を伴う死者への言及だけである。",
          "名前・別名の 2 文字以上の文字列一致。死者は、名前を含む文に宣言済みの"
          "媒体語か参照の語彙（筆跡・手形・思い出 など）がある場合だけ許容する。"
          "比喩・一般名詞・回想の言い回しとの混同は起こりうる。"),
    Check("fact_boundary", "未開示の事実の語彙や、死者の現在時状態マーカーが現れない。",
          "語彙一致は手掛かりであり断定ではない（medium）。死者マーカーは厳密。"),
    Check("voice_contract", "voice.json の禁止表現が出ず、章本文が空でない。",
          "正規表現の一致のみ。文体の質は判定しない。"),
)


def _finding(check: str, severity: str, message_ja: str,
             line: int = 0, **evidence: Any) -> dict:
    return {"check": check, "severity": severity, "message_ja": message_ja,
            "evidence": {"line": line, **evidence}}


def _dead_at(canon: Canon, character_id: str) -> bool:
    char = canon.characters.get(character_id)
    return bool(char and char.status == "dead")


#: Words that mark a *reference* to someone rather than a present-time act.
#: ``memory_mention`` / ``record_reference`` are allowed when the sentence that
#: names the dead person carries the declared medium or one of these cues.
#: The list is deliberately small and documented as a heuristic: it cannot tell
#: "said with affection" from "stood in the doorway".
REFERENCE_CUES = (
    # records and relics
    "筆跡", "手形", "文字", "記録", "帳面", "頁", "札", "書き", "印",
    "遺した", "残した", "預けた", "手紙", "日記", "写真", "墓", "遺体",
    # recollection and past narration
    "思い出", "思い返", "記憶", "覚えて", "覚えてい", "回想", "面影",
    "昔", "あの頃", "なつかし", "かつて", "生前", "三年前", "あの夜",
    "あの嵐", "あの日", "その夜", "横顔", "名を", "声を聞",
)


def _medium_terms(medium: str) -> set[str]:
    """Words that count as "the declared medium" inside one sentence.

    The declared medium is often a compound ("石膏手形") while the prose splits
    it ("石膏の右手 … 手形"). Matching the full string alone would flag the
    committed ch02 text, so two-character shingles are accepted as well.
    """
    text = medium.strip()
    if len(text) <= 2:
        return {text} if text else set()
    terms = {text}
    terms.update(text[i:i + 2] for i in range(len(text) - 1))
    return terms


def _sentences(text: str) -> list[tuple[int, str]]:
    """``(line_number, sentence)`` pairs; markers are removed first."""
    pairs: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        plain = re.sub(r"\{\{[^{}]*\}\}", "", line).strip()
        if not plain:
            continue
        for sentence in re.split(r"(?<=[。！？])", plain):
            sentence = sentence.strip()
            if sentence:
                pairs.append((number, sentence))
    return pairs


def _mentions_without_medium(text: str, names: tuple[str, ...],
                             references: list[dict]) -> list[dict]:
    """Sentences that name a dead person without saying how they appear.

    A chapter-level ``record_reference`` only licenses a mention *through* its
    medium. The check is per sentence, so "ヨハンの筆跡が…" passes while
    "ヨハンが戸口から入ってきて…" fails even in the same chapter.
    """
    terms: set[str] = set(REFERENCE_CUES)
    for reference in references:
        terms |= _medium_terms(reference["medium"])
    media = "／".join(sorted({reference["medium"] for reference in references}))
    bare: list[dict] = []
    for line, sentence in _sentences(text):
        match = next((name for name in names if len(name) >= 2 and name in sentence), None)
        if match is None:
            continue
        if any(term and term in sentence for term in terms):
            continue
        bare.append({"line": line, "match": match, "media": media,
                     "sentence": sentence[:80]})
    return bare


def check_rewrite(text: str, chapter_id: str, log: GameLog, canon: Canon,
                  voice: Voice | None = None, scenes: SceneDoc | None = None, *,
                  avoid: tuple[str, ...] = (), min_chars: int = 120) -> dict:
    """Check one rewritten chapter against the verified log and voice spec."""
    chapter = log.chapter(chapter_id)
    findings: list[dict] = []
    checks: list[dict] = []
    if chapter is None:
        return {
            "chapter": chapter_id, "status": "unresolved",
            "findings": [_finding("marker_sequence", "high",
                                  f"ゲームログに章 {chapter_id} がない。")],
            "checks": [], "summary": {"status": "unresolved", "findings": 1,
                                      "blocking_findings": 1, "chars": 0,
                                      "by_severity": {"high": 1}},
            "expected_markers": [], "found_markers": [],
            "allowed_dead_references": [],
        }

    expected = list(expected_marker_texts(log, chapter_id))
    found_records = prose_markers(text, chapter_id)
    found = [record["raw"] for record in found_records]
    body = MARKER_RE.sub("", text)
    chars = len(re.sub(r"\s", "", body))

    # -- marker_sequence -----------------------------------------------------
    before = len(findings)
    for record in found_records:
        if not record["supported"]:
            findings.append(_finding(
                "marker_sequence", "high",
                f"未対応のマーカー種別「{record['kind']}」が本文にある。",
                record["line"], marker=record["raw"]))
        elif record["kind"] not in DERIVED_KINDS:
            findings.append(_finding(
                "marker_sequence", "high",
                f"ゲームログにないマーカー「{record['raw']}」が本文にある。",
                record["line"], marker=record["raw"]))
    if found != expected:
        missing = [marker for marker in expected if marker not in found]
        extra = [marker for marker in found if marker not in expected]
        order_changed = not missing and not extra
        findings.append(_finding(
            "marker_sequence", "high",
            f"確定マーカー列が一致しない（欠落 {len(missing)} / 余分 {len(extra)} / "
            f"順序のみの差 {int(order_changed)}）。",
            expected=expected, found=found, missing=missing, extra=extra))
    checks.append(_result("marker_sequence", len(expected) + len(found),
                          len(findings) - before))

    # -- character_boundary --------------------------------------------------
    before = len(findings)
    present: set[str] = set()
    allowed_subjects: dict[str, list[dict]] = {}
    for scene in chapter.scenes:
        present.update(scene.present_characters)
        for action in scene.actions:
            if action.type in REFERENCE_TYPES and action.subject and action.medium:
                allowed_subjects.setdefault(action.subject, []).append({
                    "scene": scene.id, "action": action.id,
                    "event_type": action.type, "medium": action.medium,
                })
    allowed_dead_references = [
        {**item, "chapter": chapter_id, "subject": subject}
        for subject, items in sorted(allowed_subjects.items())
        if _dead_at(canon, subject) for item in items]
    for char in canon.characters.values():
        hits = [name for name in char.all_names if len(name) >= 2 and name in body]
        if not hits:
            continue
        if char.id in present:
            continue
        if _dead_at(canon, char.id):
            references = allowed_subjects.get(char.id)
            if references:
                # A declared reference covers the mention, not the whole chapter:
                # a paragraph that names the dead person must also carry the
                # medium it was declared through (record, relic, recollection).
                bare = _mentions_without_medium(body, char.all_names, references)
                if not bare:
                    continue
                findings.append(_finding(
                    "character_boundary", "high",
                    f"死者 {char.name}（{bare[0]['match']}）の言及に、宣言された媒体"
                    f"（{bare[0]['media']}）も参照の語彙も同じ文にない。現在時の行動として"
                    "読めるため不合格。記録・遺物・回想として書くか、"
                    "ゲームログに宣言を足す。",
                    character=char.id, line=bare[0]["line"],
                    match=bare[0]["match"], sentences=len(bare)))
                continue
            findings.append(_finding(
                "character_boundary", "high",
                f"死者 {char.name}（{hits[0]}）が本文に出るが、ゲームログに"
                "record_reference / memory_mention の宣言がない。",
                match=hits[0], character=char.id))
        elif char.id in allowed_subjects:
            continue
        else:
            findings.append(_finding(
                "character_boundary", "medium",
                f"{char.name}（{hits[0]}）はこの章の present_characters にも"
                "許容された言及にもない。", match=hits[0], character=char.id))
    checks.append(_result("character_boundary", len(canon.characters),
                          len(findings) - before))

    # -- fact_boundary -------------------------------------------------------
    before = len(findings)
    for record in found_records:
        record_kind = record["kind"]
        subject = record.get("subject")
        if (record_kind in DEAD_ACTOR_MARKER_KINDS and subject
                and _dead_at(canon, subject)):
            findings.append(_finding(
                "fact_boundary", "high",
                f"死者 {subject} に現在時の状態変化マーカー"
                f"「{record['raw']}」が付いている。", record["line"],
                marker=record["raw"], character=subject))
    withheld: dict[str, str] = {}
    if scenes:
        refs = {scene.scene_ref for scene in chapter.scenes}
        for design in scenes.scenes:
            if design.id in refs:
                for item in design.withheld:
                    withheld[item.fact] = item.reason
    position = _chapter_position(canon, chapter_id)
    for fact in canon.facts.values():
        premature = bool(fact.setup and _chapter_position(canon, fact.setup) > position)
        held = fact.id in withheld
        if not premature and not held:
            continue
        for term in fact.terms:
            if len(term) < 2 or term not in body:
                continue
            reason = (f"{fact.id} はこの章で保留と宣言（{withheld[fact.id]}）。"
                      if held else
                      f"{fact.id} の開示章は {fact.setup} でこの章より後。")
            findings.append(_finding(
                "fact_boundary", "medium",
                f"未開示の事実 {fact.id} の語「{term}」が本文にある。{reason}",
                term=term, fact=fact.id))
    checks.append(_result("fact_boundary", len(canon.facts), len(findings) - before))

    # -- voice_contract ------------------------------------------------------
    before = len(findings)
    if chars < min_chars:
        findings.append(_finding(
            "voice_contract", "medium",
            f"本文が {chars} 字しかない（最低 {min_chars} 字）。", chars=chars))
    for term in avoid:
        if term and term in body:
            findings.append(_finding(
                "voice_contract", "medium",
                f"タスクの禁止語「{term}」が本文にある。", term=term))
    if voice is None or not voice.banned:
        checks.append({**_spec("voice_contract"), "status": "skipped",
                       "reason": "voice.json の banned がない。",
                       "evaluated": 0, "findings": len(findings) - before})
    else:
        patterns = [{"id": item.id, "pattern": item.pattern,
                     "message_ja": item.message_ja, "severity": "medium"}
                    for item in voice.banned]
        for hit in find_forbidden(
                [Document(path=Path(f"{chapter_id}.md"), text=text)], patterns):
            if "error" in hit:
                findings.append(_finding(
                    "voice_contract", "low",
                    f"禁止表現 {hit['id']} の正規表現が不正: {hit['error']}。",
                    pattern_id=hit["id"]))
            else:
                findings.append(_finding(
                    "voice_contract", "medium",
                    hit["message_ja"] or f"禁止表現 {hit['id']} に一致。",
                    hit["evidence"]["line"], pattern_id=hit["id"],
                    match=hit.get("match", "")))
        checks.append(_result("voice_contract", len(patterns),
                              len(findings) - before))

    by_severity: dict[str, int] = {}
    for item in findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
    blocking = sum(1 for item in findings
                   if item["severity"] in REPAIR_SEVERITIES)
    return {
        "schema_version": "1.0",
        "tool": "game-log-rewrite-check",
        "chapter": chapter_id,
        "findings": findings,
        "checks": checks,
        "expected_markers": expected,
        "found_markers": found,
        "allowed_dead_references": allowed_dead_references,
        "summary": {
            "status": "clean" if blocking == 0 else "unresolved",
            "chars": chars,
            "findings": len(findings),
            "blocking_findings": blocking,
            "by_severity": by_severity,
            "expected_markers": len(expected),
            "found_markers": len(found),
            "allowed_dead_references": len(allowed_dead_references),
            "checks_run": sum(1 for c in checks if c["status"] != "skipped"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        },
    }


def _chapter_position(canon: Canon, chapter_id: str) -> int:
    order = canon.chapter_order()
    from ..story.canon import chapter_key
    key = chapter_key(chapter_id)
    return order.index(key) if key in order else 10 ** 6


def _spec(check_id: str) -> dict:
    for check in CHECKS:
        if check.id == check_id:
            return {"id": check.id, "acceptance_ja": check.acceptance_ja,
                    "limits_ja": check.limits_ja}
    raise KeyError(check_id)


def _result(check_id: str, evaluated: int, findings: int) -> dict:
    return {**_spec(check_id), "status": "fail" if findings else "pass",
            "evaluated": evaluated, "findings": findings}


def needs_repair(findings: list[dict]) -> bool:
    return any(item["severity"] in REPAIR_SEVERITIES for item in findings)


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# 小説化リライトの検査結果 (Stage B): {report['chapter']}",
        "",
        f"本文 {summary['chars']} 字／確定マーカー {summary['expected_markers']} 件／"
        f"所見 {summary['findings']} 件（{summary['by_severity']}）／"
        f"状態: **{summary['status']}**。",
        "",
        "| 検査 | 状態 | 対象 | 所見 | 合格条件 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['id']}` | {check['status']} | "
                     f"{check['evaluated']} | {check['findings']} | "
                     f"{check['acceptance_ja']} |")
    if report["allowed_dead_references"]:
        lines += ["", "許容された死者への言及:", ""]
        for item in report["allowed_dead_references"]:
            lines.append(f"* {item['subject']} — {item['medium']}（{item['event_type']}）")
    if report["findings"]:
        lines += ["", "## 所見", ""]
        for item in report["findings"]:
            lines.append(f"* [{item['severity']}] `{item['check']}` "
                         f"{item['message_ja']}")
    lines += ["", "構造・衛生の L1 検査であり、文章の質や面白さは判定しない。", ""]
    return "\n".join(lines)


__all__ = ["CHECKS", "REPAIR_SEVERITIES", "check_rewrite", "needs_repair",
           "render_markdown"]
