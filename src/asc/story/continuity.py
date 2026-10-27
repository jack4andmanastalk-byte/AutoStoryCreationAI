"""Deterministic continuity checks over a canon and a chapter set.

Every check declares the technique it operationalises, the acceptance condition
it is judged by, and — when the canon lacks the data — why it was skipped.
Nothing here asks a language model: the point of the module is to be the layer
that a model cannot talk its way out of.

The reported severity encodes *how* the violation was found:

* ``high``   — backed by an explicit marker (or a speaking mention) after the
  death / before the knowledge was acquired.
* ``medium`` — backed by an *unclassified* name mention only, or by a
  time/location mismatch. Name mentions with an explicit reference context
  (quoted text, reference/past cues in the same sentence, or a non-subject
  form) are retained as observations rather than counted as violations.
* ``low``    — informational, e.g. a foreshadow whose declared payoff differs
  from the one in the text.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .canon import Canon, CanonError, chapter_key, load_canon
from .ledger import Ledger, build_ledger
from .text import ChapterText, Mention, load_chapters


# --------------------------------------------------------------------------
# check specifications (the acceptance layer the executability audit found
# missing in the source catalogs)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CheckSpec:
    id: str
    title_ja: str
    technique_ids: tuple[str, ...]
    question_ja: str
    acceptance_ja: str
    requires: tuple[str, ...]
    limits_ja: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title_ja": self.title_ja,
            "technique_ids": list(self.technique_ids),
            "question_ja": self.question_ja,
            "acceptance_ja": self.acceptance_ja,
            "requires": list(self.requires),
            "limits_ja": self.limits_ja,
        }


CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec(
        id="dead_character_reappears",
        title_ja="死亡した人物の再登場",
        technique_ids=("production/game_narrative_us:P19", "narrative/us_2026:T116"),
        question_ja="死亡が確定した人物が、その後の章で行為・発話していないか。",
        acceptance_ja=(
            "死亡章より後の章で、その人物の行為マーカー（state/learn/use）または"
            "発話（名前＋直後の「」）が 0 件であること。名前だけの場合は、"
            "引用内・同じ文の参照/過去の手掛かり・非主語形を参照として"
            " observations に残し、分類できない言及だけを medium とする。"
        ),
        requires=("characters", "chapters"),
        limits_ja=("名前の言及は存在の証明ではない。文単位の語彙と助詞だけの"
                   "機械的分類であり、夢・幽霊・代役・省略された主語は誤分類になりうる。"),
    ),
    CheckSpec(
        id="knowledge_violation",
        title_ja="知り得ない情報の使用",
        technique_ids=("narrative/us_2026:T012", "narrative/us_2026:T116"),
        question_ja="人物が、知る前の章で事実を使っていないか。",
        acceptance_ja=(
            "`use` マーカーの事実が、その人物の既知集合（canon の knows ＋ それ以前の "
            "`learn`）に含まれること。含まれない場合は high。事実の語彙（terms）が"
            "学習前の台詞に現れる場合は、話者推定を含むため medium。"
        ),
        requires=("characters", "facts"),
        limits_ja="台詞の話者推定は行単位の近接に依存する。地の文の言及は対象外。",
    ),
    CheckSpec(
        id="foreshadow_order",
        title_ja="伏線の設置と回収の順序",
        technique_ids=("narrative/japan_2026:T033", "narrative/japan_2026:T034",
                       "narrative/japan_2026:T035", "narrative/japan_2026:T036",
                       "narrative/japan_2026:T037"),
        question_ja="回収が設置より前になっていないか。回収だけが存在しないか。",
        acceptance_ja=(
            "各伏線について、回収章 ≥ 設置章であること。回収のみで設置がない場合は"
            "medium、canon の宣言と実際の章が食い違う場合は low。"
        ),
        requires=("foreshadowing",),
        limits_ja="回収の「意味が通るか」は判定しない。順序と有無だけを見る。",
    ),
    CheckSpec(
        id="unresolved_foreshadow",
        title_ja="未回収の伏線",
        technique_ids=("narrative/japan_2026:T033", "narrative/us_2026:T012"),
        question_ja="設置されたが回収されていない伏線が残っていないか。",
        acceptance_ja=(
            "最終章までに `payoff` マーカー（または canon の payoff 章）に到達した"
            "伏線の集合が、設置済みの集合と一致すること。差集合は medium。"
        ),
        requires=("foreshadowing", "chapters"),
        limits_ja="続巻前提の作品では未回収が正常。単巻として監査する場合のみ有効。",
    ),
    CheckSpec(
        id="travel_time",
        title_ja="移動時間の整合",
        technique_ids=("narrative/japan_2026:T112", "production/game_narrative_us:P22"),
        question_ja="章の経過日数が、場所間の移動日数以上か。",
        acceptance_ja=(
            "連続する章の日数差 ≥ canon の移動日数であること。移動日数が未定義の"
            "組は判定せず、skipped として件数を報告する。"
        ),
        requires=("locations", "timeline"),
        limits_ja="移動日数表の網羅性に依存する。同日移動・省略・転移は誤検出になりうる。",
    ),
    CheckSpec(
        id="stated_age",
        title_ja="年齢・時点の整合",
        technique_ids=("narrative/us_2026:T116", "production/game_narrative_us:P19"),
        question_ja="本文中で示された年齢が、経過時間と矛盾しないか。",
        acceptance_ja=(
            "`age` マーカーの値が、開始時年齢＋誕生日の通過回数と一致すること。"
            "誕生日が未設定の場合は、前回の明示年齢より減少していないことのみを見る。"
        ),
        requires=("characters", "timeline"),
        limits_ja="年齢は作中で明示された箇所しか検査できない。",
    ),
)

CHECK_BY_ID = {spec.id: spec for spec in CHECKS}


@dataclass
class Violation:
    type: str
    severity: str
    subject: str | None
    chapter: str | None
    message_ja: str
    canon_ref: str
    evidence_basis: str
    evidence: dict = field(default_factory=dict)
    intentional: bool = False

    def as_dict(self) -> dict:
        spec = CHECK_BY_ID.get(self.type)
        return {
            "type": self.type,
            "title_ja": spec.title_ja if spec else self.type,
            "severity": self.severity,
            "subject": self.subject,
            "chapter": self.chapter,
            "message_ja": self.message_ja,
            "canon_ref": self.canon_ref,
            "evidence_basis": self.evidence_basis,
            "technique_ids": list(spec.technique_ids) if spec else [],
            "evidence": self.evidence,
            "intentional": self.intentional,
        }


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _chapter_ref(path_name: str | None, line: int | None) -> dict:
    ref: dict = {}
    if path_name:
        ref["path"] = path_name
    if line:
        ref["line"] = line
    return ref


_HONORIFIC_FOLLOWING_RE = re.compile(r"^(?:さん|さま|様|君|ちゃん)")

# A name followed by one of these forms is being referred to (possessor,
# comparison, role, or topic of talk) rather than presented as the
# grammatical subject of a present-time action. Object/destination/source
# particles (を/に/へ/から) deliberately stay unclassified: "met/saw the dead
# person" may still be a reappearance. Subject-like forms (は/が/も) also stay
# unclassified unless a reference/past cue is present.
_NON_SUBJECT_FOLLOWING = (
    "のように", "みたい", "と同じ", "に似", "について", "のこと",
    "という", "として", "の",
)


def _dead_mention_context(mention: Mention) -> tuple[str, list[str]]:
    """Classify a non-speaking dead-character name mention.

    Returns ``("reference", reasons)`` only for mechanically explicit
    reference contexts; everything else is ``("unclassified", [])`` and keeps
    the audit's conservative medium signal. This is not semantic parsing:
    an omitted particle or an unusual supernatural construction can still be
    misclassified, which is why reference mentions remain in the report as
    observations instead of disappearing.
    """
    cues = [f"cue:{cue}" for cue in mention.reference_cues]
    if cues:
        return "reference", cues
    if mention.in_quoted_text:
        return "reference", ["quoted_text"]
    following = _HONORIFIC_FOLLOWING_RE.sub("", mention.following.lstrip())
    if following.startswith(_NON_SUBJECT_FOLLOWING):
        return "reference", ["non_subject"]
    return "unclassified", []


class Audit:
    def __init__(self, canon: Canon, chapters: list[ChapterText]):
        self.canon = canon
        self.chapters = sorted(chapters, key=lambda c: c.id)
        self.order = {cid: i for i, cid in enumerate(canon.chapter_order())}
        for index, chapter in enumerate(self.chapters):
            self.order.setdefault(chapter.id, index + 1000)
        self.ledger: Ledger = build_ledger(canon, self.chapters)
        self.violations: list[Violation] = []
        self.suppressed: list[Violation] = []
        self.observations: list[dict] = []
        self.checks: list[dict] = []
        self.by_chapter = {c.id: c for c in self.chapters}

    # -- helpers ---------------------------------------------------------
    def _pos(self, chapter: str | None) -> int:
        return self.order.get(chapter or "", 10**6)

    def _add(self, violation: Violation) -> None:
        for suppression in self.canon.suppressions:
            if suppression.covers(violation.type, violation.subject, violation.chapter):
                violation.intentional = True
                self.suppressed.append(violation)
                return
        self.violations.append(violation)

    def _speaks(self, chapter: str, character_id: str) -> list:
        return [m for m in self.by_chapter[chapter].mentions
                if m.character_id == character_id and m.quoted_line]

    def _run(self, spec: CheckSpec, fn) -> None:
        missing = []
        if "characters" in spec.requires and not self.canon.characters:
            missing.append("characters")
        if "facts" in spec.requires and not self.canon.facts:
            missing.append("facts")
        if "locations" in spec.requires and not self.canon.locations:
            missing.append("locations")
        if "timeline" in spec.requires and not any(
                self.ledger.chapter_time.get(c, {}).get("day") for c in self.order):
            missing.append("timeline(day)")
        if "foreshadowing" in spec.requires and not self.canon.foreshadowing:
            missing.append("foreshadowing")
        if missing:
            self.checks.append({**spec.as_dict(), "status": "skipped",
                                "reason": f"canon lacks: {', '.join(missing)}",
                                "evaluated": 0, "violations": 0, "observations": 0})
            return
        before = len(self.violations)
        before_observations = len(self.observations)
        evaluated = fn()
        self.checks.append({**spec.as_dict(), "status": "pass" if len(self.violations) == before else "fail",
                            "evaluated": evaluated, "violations": len(self.violations) - before,
                            "observations": len(self.observations) - before_observations})

    # -- checks ----------------------------------------------------------
    def check_dead_character_reappears(self) -> int:
        evaluated = 0
        for char in self.canon.characters.values():
            death_chapter = None
            for event in self.ledger.events:
                if event.kind == "death" and event.subject == char.id:
                    death_chapter = event.chapter
                    break
            if death_chapter is None and char.status == "dead":
                death_chapter = char.status_since or self.chapters[0].id if self.chapters else None
            if death_chapter is None:
                continue
            evaluated += 1
            for chapter in self.chapters:
                if self._pos(chapter.id) <= self._pos(death_chapter):
                    continue
                for event in [e for e in self.ledger.events
                              if e.chapter == chapter.id and e.subject == char.id
                              and e.kind in {"state", "learn", "use", "age"}]:
                    self._add(Violation(
                        type="dead_character_reappears", severity="high", subject=char.id,
                        chapter=chapter.id,
                        message_ja=(f"{char.name} は {death_chapter} で死亡しているが、"
                                    f"{chapter.id} で {event.kind} の状態変化がある。"),
                        canon_ref=f"{self.canon.root.name}/characters:{char.id}.status",
                        evidence_basis="marker",
                        evidence=_chapter_ref(chapter.path.name, event.line),
                    ))
                speaking_lines = {m.line for m in chapter.mentions
                                  if m.character_id == char.id and m.quoted_line}
                for mention in [m for m in chapter.mentions if m.character_id == char.id]:
                    if mention.line in speaking_lines and not mention.quoted_line:
                        # the same line is already reported as speech
                        continue
                    if mention.quoted_line:
                        severity, basis = "high", "name_mention"
                        context, reasons = "speech", []
                        message = (f"{char.name} は {death_chapter} で死亡しているが、"
                                   f"{chapter.id} で発話している。")
                    else:
                        context, reasons = _dead_mention_context(mention)
                        if context == "reference":
                            self.observations.append({
                                "type": "dead_character_reference",
                                "title_ja": "死亡した人物への参照",
                                "subject": char.id,
                                "chapter": chapter.id,
                                "message_ja": (
                                    f"{char.name} は {death_chapter} で死亡しているが、"
                                    f"{chapter.id} の言及は参照文脈と分類したため、"
                                    "再登場とは数えない。"),
                                "canon_ref": (
                                    f"{self.canon.root.name}/characters:{char.id}.status"),
                                "evidence_basis": "name_mention",
                                "technique_ids": list(
                                    CHECK_BY_ID["dead_character_reappears"].technique_ids),
                                "evidence": {
                                    **_chapter_ref(chapter.path.name, mention.line),
                                    "quote": mention.text,
                                    "sentence": mention.sentence,
                                    "context": context,
                                    "reasons": reasons,
                                },
                            })
                            continue
                        severity, basis = "medium", "name_mention"
                        message = (f"{char.name} は {death_chapter} で死亡しているが、"
                                   f"{chapter.id} で名前が現れ、参照文脈と分類できない"
                                   "（現在時の再登場・回想・遺体・言及の可能性）。")
                    self._add(Violation(
                        type="dead_character_reappears", severity=severity, subject=char.id,
                        chapter=chapter.id, message_ja=message,
                        canon_ref=f"{self.canon.root.name}/characters:{char.id}.status",
                        evidence_basis=basis,
                        evidence={**_chapter_ref(chapter.path.name, mention.line),
                                  "quote": mention.text,
                                  "sentence": mention.sentence,
                                  "context": context,
                                  "reasons": reasons},
                    ))
        return evaluated

    def check_knowledge_violation(self) -> int:
        known = {cid: set(char.knows) for cid, char in self.canon.characters.items()}
        evaluated = 0
        # first pass: when does each character learn each fact?
        learn_chapter: dict[tuple[str, str], str] = {}
        for chapter in self.chapters:
            for marker in chapter.markers:
                if marker.kind != "learn":
                    continue
                char = self.canon.character(marker.subject)
                fact = marker.options().get("fact")
                if char and fact:
                    learn_chapter.setdefault((char.id, fact), chapter.id)
        for chapter in self.chapters:
            for marker in chapter.markers:
                if marker.kind == "learn":
                    char = self.canon.character(marker.subject)
                    fact = marker.options().get("fact")
                    if char and fact:
                        known[char.id].add(fact)
                continue
            for marker in chapter.markers:
                if marker.kind != "use":
                    continue
                char = self.canon.character(marker.subject)
                fact = marker.options().get("fact")
                if not char or not fact:
                    continue
                evaluated += 1
                if fact not in known[char.id]:
                    learned_at = learn_chapter.get((char.id, fact))
                    self._add(Violation(
                        type="knowledge_violation", severity="high", subject=char.id,
                        chapter=chapter.id,
                        message_ja=(f"{char.name} は {fact} を {chapter.id} で使っているが、"
                                    + (f"学習は {learned_at}。" if learned_at
                                       else "学習の記録がない。")),
                        canon_ref=f"{self.canon.root.name}/facts:{fact}",
                        evidence_basis="marker",
                        evidence=_chapter_ref(chapter.path.name, marker.line),
                    ))
        # lexical cue: a fact's terms in a character's line before they learn it
        for fact in self.canon.facts.values():
            if not fact.terms:
                continue
            for chapter in self.chapters:
                for char in self.canon.characters.values():
                    if fact.id in known[char.id]:
                        continue
                    learned_at = learn_chapter.get((char.id, fact.id))
                    if learned_at and self._pos(learned_at) <= self._pos(chapter.id):
                        continue
                    for mention in chapter.mentions:
                        if mention.character_id != char.id or not mention.quoted_line:
                            continue
                        hit = next((t for t in fact.terms if t in mention.text), None)
                        if hit:
                            evaluated += 1
                            self._add(Violation(
                                type="knowledge_violation", severity="medium",
                                subject=char.id, chapter=chapter.id,
                                message_ja=(f"{char.name} の発話に {fact.id} の語「{hit}」が現れるが、"
                                            + (f"学習は {learned_at}。" if learned_at
                                               else "canon 上まだ知らない。")),
                                canon_ref=f"{self.canon.root.name}/facts:{fact.id}",
                                evidence_basis="name_mention",
                                evidence={**_chapter_ref(chapter.path.name, mention.line),
                                          "quote": mention.text},
                            ))
        return evaluated

    def check_foreshadow_order(self) -> int:
        evaluated = 0
        for state in self.ledger.foreshadowing.values():
            if not state.setup_chapter and not state.payoff_chapter:
                continue
            evaluated += 1
            if state.setup_chapter and state.payoff_chapter \
                    and self._pos(state.payoff_chapter) < self._pos(state.setup_chapter):
                self._add(Violation(
                    type="foreshadow_order", severity="high", subject=state.id,
                    chapter=state.payoff_chapter,
                    message_ja=(f"{state.id} の回収（{state.payoff_chapter}）が"
                                f"設置（{state.setup_chapter}）より前にある。"),
                    canon_ref=f"{self.canon.root.name}/foreshadowing:{state.id}",
                    evidence_basis="marker",
                    evidence={"setup": state.setup_chapter, "payoff": state.payoff_chapter},
                ))
            elif state.payoff_chapter and not state.setup_chapter:
                self._add(Violation(
                    type="foreshadow_order", severity="medium", subject=state.id,
                    chapter=state.payoff_chapter,
                    message_ja=f"{state.id} は回収だけがあり、設置の記録がない。",
                    canon_ref=f"{self.canon.root.name}/foreshadowing:{state.id}",
                    evidence_basis="marker",
                    evidence={"payoff": state.payoff_chapter},
                ))
            declared = self.ledger.foreshadowing[state.id].declared_payoff
            if declared and state.payoff_chapter and declared != state.payoff_chapter:
                self._add(Violation(
                    type="foreshadow_order", severity="low", subject=state.id,
                    chapter=state.payoff_chapter,
                    message_ja=(f"{state.id} の回収章が canon の宣言（{declared}）と"
                                f"実際（{state.payoff_chapter}）で異なる。"),
                    canon_ref=f"{self.canon.root.name}/foreshadowing:{state.id}",
                    evidence_basis="marker",
                    evidence={"declared": declared, "actual": state.payoff_chapter},
                ))
        return evaluated

    def check_unresolved_foreshadow(self) -> int:
        evaluated = 0
        last = self.chapters[-1].id if self.chapters else None
        for state in self.ledger.foreshadowing.values():
            if not state.setup_chapter:
                continue
            evaluated += 1
            if not state.payoff_chapter:
                self._add(Violation(
                    type="unresolved_foreshadow", severity="medium", subject=state.id,
                    chapter=last,
                    message_ja=(f"{state.id} は {state.setup_chapter} で設置されたが、"
                                f"{last} までに回収されていない。"),
                    canon_ref=f"{self.canon.root.name}/foreshadowing:{state.id}",
                    evidence_basis="marker",
                    evidence={"setup": state.setup_chapter, "last_chapter": last},
                ))
        return evaluated

    def check_travel_time(self) -> int:
        evaluated = 0
        previous = None
        for chapter in self.chapters:
            time = self.ledger.chapter_time.get(chapter.id, {})
            if time.get("day") is None or not time.get("location"):
                continue
            if previous is not None:
                prev_day = self.ledger.chapter_time[previous.id].get("day")
                prev_loc = self.ledger.chapter_time[previous.id].get("location")
                elapsed = float(time["day"]) - float(prev_day)
                required = self.canon.travel_days(prev_loc, time["location"])
                if required is not None and elapsed < required:
                    evaluated += 1
                    self._add(Violation(
                        type="travel_time", severity="medium", subject=None,
                        chapter=chapter.id,
                        message_ja=(f"{prev_loc} → {time['location']} は {required:g} 日必要だが、"
                                    f"{previous.id}→{chapter.id} の経過は {elapsed:g} 日。"),
                        canon_ref=f"{self.canon.root.name}/locations:{time['location']}.travel_days",
                        evidence_basis="timeline",
                        evidence={"from": prev_loc, "to": time["location"],
                                  "elapsed_days": elapsed, "required_days": required},
                    ))
            previous = chapter
        return evaluated

    def check_stated_age(self) -> int:
        evaluated = 0
        last_stated: dict[str, int] = {}
        for chapter in self.chapters:
            for marker in chapter.markers:
                if marker.kind != "age" or len(marker.args) < 2:
                    continue
                char = self.canon.character(marker.subject)
                if not char:
                    continue
                try:
                    stated = int(marker.args[1])
                except ValueError:
                    continue
                evaluated += 1
                if char.id in last_stated and stated < last_stated[char.id]:
                    self._add(Violation(
                        type="stated_age", severity="medium", subject=char.id,
                        chapter=chapter.id,
                        message_ja=(f"{char.name} の年齢が {last_stated[char.id]} から "
                                    f"{stated} に減っている。"),
                        canon_ref=f"{self.canon.root.name}/characters:{char.id}.age_at_start",
                        evidence_basis="marker",
                        evidence=_chapter_ref(chapter.path.name, marker.line),
                    ))
                last_stated[char.id] = stated
        return evaluated

    # -- driver ----------------------------------------------------------
    def run(self) -> dict:
        self._run(CHECK_BY_ID["dead_character_reappears"], self.check_dead_character_reappears)
        self._run(CHECK_BY_ID["knowledge_violation"], self.check_knowledge_violation)
        self._run(CHECK_BY_ID["foreshadow_order"], self.check_foreshadow_order)
        self._run(CHECK_BY_ID["unresolved_foreshadow"], self.check_unresolved_foreshadow)
        self._run(CHECK_BY_ID["travel_time"], self.check_travel_time)
        self._run(CHECK_BY_ID["stated_age"], self.check_stated_age)
        return self.report()

    def report(self) -> dict:
        chars = sum(c.chars for c in self.chapters)
        violations = sorted(self.violations, key=lambda v: (
            SEVERITY_ORDER.get(v.severity, 9), self._pos(v.chapter), v.type))
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for violation in violations:
            by_type[violation.type] = by_type.get(violation.type, 0) + 1
            by_severity[violation.severity] = by_severity.get(violation.severity, 0) + 1
        weighted = sum(SEVERITY_WEIGHT.get(v.severity, 0) for v in violations)
        return {
            "schema_version": "1.0",
            "tool": "continuity-ledger",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "canon": str(self.canon.root),
            "chapters": [
                {"id": c.id, "path": c.path.name, "chars": c.chars,
                 "markers": len(c.markers), "mentions": len(c.mentions)}
                for c in self.chapters
            ],
            "checks": self.checks,
            "violations": [v.as_dict() for v in violations],
            "observations": self.observations,
            "suppressed": [{**v.as_dict(), "reason": next(
                (s.reason for s in self.canon.suppressions
                 if s.covers(v.type, v.subject, v.chapter)), "")}
                for v in self.suppressed],
            "ledger": self.ledger.as_dict(self.canon),
            "canon_warnings": list(self.canon.warnings),
            "summary": {
                "chars": chars,
                "violations": len(violations),
                "by_type": by_type,
                "by_severity": by_severity,
                # ConStory-Bench-style density: defects per 10k characters
                "ced_per_10k_chars": round(len(violations) / chars * 10_000, 3) if chars else None,
                "weighted_score": weighted,
                "observations": len(self.observations),
                "suppressed": len(self.suppressed),
                "checks_run": sum(1 for c in self.checks if c["status"] != "skipped"),
                "checks_skipped": sum(1 for c in self.checks if c["status"] == "skipped"),
            },
        }


def audit_texts(canon_dir: str | Path, text_dir: str | Path) -> dict:
    canon = load_canon(canon_dir)
    names: dict[str, str] = {}
    for char in canon.characters.values():
        for name in char.all_names:
            names[name] = char.id
    from .canon import load_chapters as load_chapter_index

    index = load_chapter_index(text_dir)
    chapters = load_chapters([(c.id, c.path) for c in index if c.path], names)
    return Audit(canon, chapters).run()


def write_report(report: dict, path: str | Path, ledger_path: str | Path | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if ledger_path:
        ledger_path = Path(ledger_path)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(
            json.dumps(report["ledger"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# 継続性監査: {Path(report['canon']).name}",
        "",
        f"対象 {len(report['chapters'])} 章 / {summary['chars']:,} 文字。"
        f"違反 {summary['violations']} 件（high {summary['by_severity'].get('high', 0)} / "
        f"medium {summary['by_severity'].get('medium', 0)} / "
        f"low {summary['by_severity'].get('low', 0)}）。",
        "",
        f"誤り密度（CED 相当）: **{summary['ced_per_10k_chars'] or 0} / 1万文字**。"
        "件数ではなく密度で見るのは、長さの違う作品を比較するためである。",
        "",
        "## 検査の実行状況",
        "",
        "| 検査 | 状態 | 対象 | 違反 | 観測 | 合格条件 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            f"| `{check['id']}` | {check['status']} | {check['evaluated']} | "
            f"{check['violations']} | {check.get('observations', 0)} | "
            f"{check['acceptance_ja']} |")
    skipped = [c for c in report["checks"] if c["status"] == "skipped"]
    if skipped:
        lines += ["", "**実行できなかった検査**（canon の不足）:", ""]
        lines += [f"* `{c['id']}` — {c['reason']}" for c in skipped]

    lines += ["", "## 違反", ""]
    if not report["violations"]:
        lines.append("なし。")
    else:
        lines += ["| 重要度 | 種別 | 章 | 対象 | メッセージ | 根拠 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for violation in report["violations"]:
            evidence = violation["evidence"]
            where = f"{evidence.get('path', '')}:{evidence.get('line', '')}".strip(":")
            lines.append(
                f"| {violation['severity']} | `{violation['type']}` | {violation['chapter']} | "
                f"{violation['subject'] or '—'} | {violation['message_ja']} | "
                f"{violation['evidence_basis']} {where} |")

    if report.get("observations"):
        lines += ["", "## 違反に数えなかった参照", "",
                  "| 種別 | 章 | 対象 | 理由 | メッセージ |",
                  "| --- | --- | --- | --- | --- |"]
        for item in report["observations"]:
            reasons = ", ".join((item.get("evidence") or {}).get("reasons") or [])
            lines.append(
                f"| `{item['type']}` | {item['chapter']} | {item['subject']} | "
                f"{reasons} | {item['message_ja']} |")

    if report["suppressed"]:
        lines += ["", "## 意図的な矛盾として除外", "",
                  "| 種別 | 章 | 対象 | 理由 |", "| --- | --- | --- | --- |"]
        for item in report["suppressed"]:
            lines.append(f"| `{item['type']}` | {item['chapter']} | {item['subject']} | "
                         f"{item['reason']} |")

    if report["canon_warnings"]:
        lines += ["", "## canon の警告", ""]
        lines += [f"* {warning}" for warning in report["canon_warnings"]]

    lines += [
        "",
        "## この監査で分からないこと",
        "",
        "* 名前の言及は、引用・参照語彙・助詞だけで分類する。参照として観測に残したものも、意味上の再登場でないことの証明ではない。",
        "* 台詞の話者推定は行内の近接に依存する。",
        "* 意味的な破綻（動機の飛躍、主題の不一致）は対象外。`evaluation-harness` の L2 で扱う。",
        "",
    ]
    return "\n".join(lines)
