"""Deterministic Stage A checks: game log vs canon, plot and scenes.

The checker never asks a model. It answers seven mechanical questions:

1. ``schema_shape`` — does each chapter/scene actually describe a TRPG loop
   (situation, purpose, conflict, change, choice, outcome, actions)?
2. ``canon_refs`` — do characters, facts, places, foreshadows and chapters
   exist in the canon?
3. ``design_alignment`` — do the declared ``scene_ref`` / ``act_ref`` /
   ``turn_ref`` match ``scene.json`` / ``plot.json``, and does the disclosure
   plan (learned facts vs withheld facts) hold?
4. ``timeline_travel`` — do chapter days/locations match the canon timeline,
   and is every move paid for by ``travel_days``?
5. ``presence_death`` — is a dead character ever *present* or acting now?
   (Forbidden.) Is a dead person only the ``subject`` of a declared
   record/relic/recollection reference? (Allowed, and listed explicitly.)
6. ``knowledge_boundary`` — is a fact used only after it is known, learned
   once, never before its canon ``setup`` chapter, and by someone on stage?
7. ``foreshadow_order`` — is every setup before its payoff, at the declared
   chapter, and is every declared payoff actually paid?
8. ``emitted_markers`` — does the log declare exactly the marker sequence
   derived from its own state?

A finding at ``high`` or ``medium`` sends the log back for a repair round;
``low`` is informational. The report carries the derived markers and the
allowed dead references so Stage B can be checked against the same facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..plot.schema import PlotDoc
from ..scene.schema import SceneDoc
from ..story.canon import Canon, chapter_key, load_canon
from .markers import DERIVED_KINDS, derive_markers, marker_kind, normalise_marker, owner_markers
from .schema import (GameLog, GameLogError, PRESENT_TENSE_TYPES, REFERENCE_TYPES,
                     TENSION_DEVICES, load_game_log)

REPAIR_SEVERITIES = frozenset({"high", "medium"})


@dataclass(frozen=True)
class Check:
    id: str
    question_ja: str
    acceptance_ja: str
    limits_ja: str


CHECKS: tuple[Check, ...] = (
    Check("schema_shape", "各場面が状況→行動→結果のループを記述しているか。",
          "目的・対立・変化・選択・結果・状況・緊張が空でなく、行為が 1 件以上あること。",
          "日本語の意味は見ない。空欄と列挙値だけを検査する。"),
    Check("canon_refs", "章・人物・事実・場所・伏線が canon に存在するか。",
          "参照される ID がすべて canon にあり、全章がログに含まれること。",
          "canon 自体の正しさは検査しない。"),
    Check("design_alignment", "設計書の幕・転換点・場面・情報開示と一致するか。",
          "scene_ref / act_ref / turn_ref が設計書の該当章を指し、学習事実が開示・保留の宣言と矛盾しないこと。",
          "設計書が無い場合は検査をスキップする。設計の質は判定しない。"),
    Check("timeline_travel", "章の日付・場所と移動日数が canon と整合するか。",
          "章の day / location が年表と一致し、章間および location_moves の経過日数が travel_days 以上であること。",
          "移動日数が未定義の組は判定せず、件数を報告する。"),
    Check("presence_death", "死者が現在時に行動していないか。記録・遺物・回想の言及は区別されているか。",
          "dead の人物が present_characters または action/dialogue の actor に現れないこと。記録・回想での言及は subject + medium を宣言すること。",
          "死者の名前が散文に現れること自体は違反ではない（Stage B の宣言照合で扱う）。"),
    Check("knowledge_boundary", "知る前の事実を使っていないか。",
          "use は canon の knows かそれ以前の learn の後であること。learn は一度だけ、canon の setup 章より前ではないこと。",
          "語彙の漏洩は Stage B の prose 検査で別途報告する。"),
    Check("foreshadow_order", "伏線の設置→回収の順序と章が守られているか。",
          "回収は設置より後、canon の setup / payoff 章どおりであり、宣言された payoff がすべて回収されていること。",
          "回収の意味が通るかは判定しない。順序と有無だけを見る。"),
    Check("emitted_markers", "確定マーカー列が state_delta から導出した列と一致するか。",
          "各章・各場面の emitted_markers が導出列と順序まで一致し、対応する marker 種別に限られること。",
          "マーカーは state_delta から決まる。Stage B の本文保持は別の検査。"),
)

CHECK_BY_ID = {spec.id: spec for spec in CHECKS}


def _finding(check: str, severity: str, message_ja: str, ref: str,
             **evidence: Any) -> dict:
    return {"check": check, "severity": severity, "message_ja": message_ja,
            "gamelog_ref": ref, "evidence": evidence}


@dataclass
class _Context:
    canon: Canon
    plot: PlotDoc | None
    scenes: SceneDoc | None
    positions: dict[str, int]
    findings: list[dict] = field(default_factory=list)
    allowed_dead_references: list[dict] = field(default_factory=list)
    travel_pairs_skipped: int = 0
    known_at_end: dict[str, list[str]] = field(default_factory=dict)
    foreshadow_state: dict[str, dict] = field(default_factory=dict)

    def pos(self, chapter: str | None) -> int:
        if not chapter:
            return 10 ** 6
        return self.positions.get(chapter_key(chapter), 10 ** 6)

    def add(self, finding: dict) -> None:
        self.findings.append(finding)


def _dead_at(canon: Canon, character_id: str, chapter: str,
             positions: dict[str, int]) -> bool:
    """Canon death status, honouring ``status_since`` when it is declared."""
    char = canon.characters.get(character_id)
    if char is None or char.status != "dead":
        return False
    if not char.status_since:
        return True  # dead before the story starts
    at = positions.get(chapter_key(chapter), 10 ** 6)
    since = positions.get(chapter_key(char.status_since), -1)
    return at >= since


def _dead_in_text(canon: Canon, text: str) -> list[str]:
    """Exact-id/name matches of dead characters inside a free-text field."""
    hits = []
    for char in canon.characters.values():
        if char.status != "dead":
            continue
        if text.strip() in {char.id, char.name, *char.aliases}:
            hits.append(char.id)
    return hits


# -- individual checks ------------------------------------------------------
def _check_schema_shape(log: GameLog, ctx: _Context) -> int:
    evaluated = 0
    seen_scenes: set[str] = set()
    for chapter in log.chapters:
        cref = f"chapters:{chapter.id}"
        if not chapter.location:
            ctx.add(_finding("schema_shape", "medium", "章の場所が空欄。", cref))
        for scene in chapter.scenes:
            evaluated += 1
            sref = f"{cref}.scenes:{scene.id}"
            if scene.id in seen_scenes:
                ctx.add(_finding("schema_shape", "medium",
                                 f"場面 ID {scene.id} が重複している。", sref))
            seen_scenes.add(scene.id)
            for name, label in (("situation", "状況"), ("purpose", "目的"),
                                ("conflict", "対立"), ("change", "変化"),
                                ("choice", "転換点の選択"), ("outcome", "結果")):
                if not getattr(scene, name):
                    ctx.add(_finding(
                        "schema_shape", "medium",
                        f"{label}が空欄。棒読みのログにしないため 1 文で書く。", sref))
            if scene.tension not in TENSION_DEVICES:
                ctx.add(_finding(
                    "schema_shape", "medium",
                    f"緊張の型「{scene.tension}」は {sorted(TENSION_DEVICES)} のいずれか。",
                    sref))
            if not scene.present_characters:
                ctx.add(_finding("schema_shape", "medium",
                                 "現在その場にいる人物が空欄。", sref))
            if not scene.actions:
                ctx.add(_finding("schema_shape", "medium",
                                 "行為（actions）が 1 件もない。", sref))
            action_ids: set[str] = set()
            for action in scene.actions:
                aref = f"{sref}.actions:{action.id}"
                if action.id in action_ids:
                    ctx.add(_finding("schema_shape", "medium",
                                     f"行為 ID {action.id} が重複している。", aref))
                action_ids.add(action.id)
                if not action.summary:
                    ctx.add(_finding("schema_shape", "medium",
                                     "行為の要約が空欄。", aref))
                if not action.actor:
                    ctx.add(_finding("schema_shape", "medium",
                                     "行為者（actor）が空欄。", aref))
    return evaluated


def _check_canon_refs(log: GameLog, ctx: _Context) -> int:
    canon = ctx.canon
    planted_ids = {p.id for scene in (ctx.scenes.scenes if ctx.scenes else ())
                   for p in scene.planted}
    known_foreshadows = set(canon.foreshadowing) | planted_ids
    evaluated = 0
    logged_chapters = set()
    for chapter in log.chapters:
        cref = f"chapters:{chapter.id}"
        cid = chapter_key(chapter.id)
        logged_chapters.add(cid)
        if canon.chapters and cid not in canon.chapters:
            ctx.add(_finding("canon_refs", "high",
                             f"章 {chapter.id} が canon の年表にない。", cref))
        if canon.locations and chapter.location not in canon.locations:
            ctx.add(_finding("canon_refs", "high",
                             f"場所「{chapter.location}」が canon にない。", cref))
        for scene in chapter.scenes:
            evaluated += 1
            sref = f"{cref}.scenes:{scene.id}"
            for name in scene.present_characters:
                if name not in canon.characters:
                    ctx.add(_finding("canon_refs", "high",
                                     f"人物「{name}」が canon にない。", sref))
            for action in scene.actions:
                for field_name in ("actor", "subject"):
                    value = getattr(action, field_name)
                    if value and value not in canon.characters:
                        ctx.add(_finding(
                            "canon_refs", "high",
                            f"行為 {action.id} の {field_name}「{value}」が canon にない。",
                            sref))
            for group in (scene.state_delta.learned_facts, scene.state_delta.used_facts):
                for item in group:
                    if item.character not in canon.characters:
                        ctx.add(_finding(
                            "canon_refs", "high",
                            f"知識更新の人物「{item.character}」が canon にない。", sref))
                    if canon.facts and item.fact not in canon.facts:
                        ctx.add(_finding(
                            "canon_refs", "high",
                            f"事実「{item.fact}」が canon にない。", sref))
            for event in scene.state_delta.foreshadow_events:
                if event.id not in known_foreshadows:
                    ctx.add(_finding(
                        "canon_refs", "high",
                        f"伏線「{event.id}」が canon にも scene.json の planted にもない。",
                        sref))
            for move in scene.state_delta.location_moves:
                for field_name in ("origin", "destination"):
                    value = getattr(move, field_name)
                    if canon.locations and value not in canon.locations:
                        ctx.add(_finding(
                            "canon_refs", "high",
                            f"移動の {field_name}「{value}」が canon の場所にない。", sref))
    if canon.chapters:
        missing = sorted(set(canon.chapters) - logged_chapters)
        if missing:
            ctx.add(_finding("canon_refs", "high",
                             f"ゲームログにない章: {', '.join(missing)}。", "chapters"))
    return evaluated


def _check_design_alignment(log: GameLog, ctx: _Context) -> int:
    if ctx.plot is None or ctx.scenes is None:
        return 0
    evaluated = 0
    design_scenes = {scene.id: scene for scene in ctx.scenes.scenes}
    acts = {act.id: act for act in ctx.plot.acts}
    turns = {turn.id: turn for turn in ctx.plot.turns}
    logged_scene_refs: set[str] = set()
    logged_acts: set[str] = set()
    logged_turns: set[str] = set()
    for chapter in log.chapters:
        cid = chapter_key(chapter.id)
        for scene in chapter.scenes:
            evaluated += 1
            sref = f"chapters:{chapter.id}.scenes:{scene.id}"
            design = design_scenes.get(scene.scene_ref)
            if design is None:
                ctx.add(_finding(
                    "design_alignment", "high",
                    f"scene_ref「{scene.scene_ref}」が scene.json にない。", sref))
            else:
                logged_scene_refs.add(scene.scene_ref)
                if chapter_key(design.chapter) != cid:
                    ctx.add(_finding(
                        "design_alignment", "high",
                        f"設計場面 {design.id} の章は {design.chapter} だが、"
                        f"ログでは {chapter.id}。", sref))
                if scene.tension and scene.tension != design.tension:
                    ctx.add(_finding(
                        "design_alignment", "medium",
                        f"緊張の型が設計（{design.tension}）とログ（{scene.tension}）で違う。",
                        sref))
                disclosed = set(design.disclosed)
                withheld = {item.fact: item.reason for item in design.withheld}
                gained = {fact for flow in design.knowledge for fact in flow.gained}
                for item in scene.state_delta.learned_facts:
                    if item.fact in withheld:
                        ctx.add(_finding(
                            "design_alignment", "high",
                            f"{item.fact} は {design.id} で保留と宣言されているのに "
                            f"{item.character} が学習している（理由: {withheld[item.fact]}）。",
                            sref, fact=item.fact, character=item.character))
                    elif item.fact not in disclosed and item.fact not in gained:
                        ctx.add(_finding(
                            "design_alignment", "high",
                            f"{item.fact} が {design.id} の開示計画（disclosed / gained）にない。",
                            sref, fact=item.fact))
                for item in scene.state_delta.used_facts:
                    if item.fact in withheld:
                        ctx.add(_finding(
                            "design_alignment", "high",
                            f"{item.fact} は {design.id} で保留なのに {item.character} が使っている。",
                            sref, fact=item.fact))
                for flow in design.knowledge:
                    if flow.gained and flow.character not in scene.present_characters:
                        ctx.add(_finding(
                            "design_alignment", "medium",
                            f"設計で {flow.character} が得る {', '.join(flow.gained)} に対し、"
                            "ログの present_characters に当人がいない。", sref))
                for paid in design.paid:
                    events = {event.id for event in scene.state_delta.foreshadow_events
                              if event.event == "payoff"}
                    if paid not in events:
                        ctx.add(_finding(
                            "design_alignment", "high",
                            f"設計場面 {design.id} が回収する {paid} がログの場面にない。",
                            sref, foreshadow=paid))
            act = acts.get(scene.act_ref)
            if act is None:
                ctx.add(_finding(
                    "design_alignment", "high",
                    f"act_ref「{scene.act_ref}」が plot.json にない。", sref))
            else:
                logged_acts.add(scene.act_ref)
                if cid not in {chapter_key(c) for c in act.chapters}:
                    ctx.add(_finding(
                        "design_alignment", "high",
                        f"幕 {act.id} は {chapter.id} を覆っていない。", sref))
            if not scene.turn_ref:
                ctx.add(_finding(
                    "design_alignment", "medium",
                    "turn_ref が空欄。転換点の選択と結び付ける。", sref))
            else:
                turn = turns.get(scene.turn_ref)
                if turn is None:
                    ctx.add(_finding(
                        "design_alignment", "high",
                        f"turn_ref「{scene.turn_ref}」が plot.json にない。", sref))
                else:
                    logged_turns.add(scene.turn_ref)
                    if chapter_key(turn.chapter) != cid:
                        ctx.add(_finding(
                            "design_alignment", "high",
                            f"転換点 {turn.id} の章は {turn.chapter} だがログは {chapter.id}。",
                            sref))
    for scene_id in sorted(set(design_scenes) - logged_scene_refs):
        ctx.add(_finding(
            "design_alignment", "medium",
            f"設計場面 {scene_id} がゲームログに現れない。", "chapters"))
    for act_id in sorted(set(acts) - logged_acts):
        ctx.add(_finding(
            "design_alignment", "medium",
            f"幕 {act_id} を参照する場面がない。", "chapters"))
    for turn_id in sorted(set(turns) - logged_turns):
        ctx.add(_finding(
            "design_alignment", "medium",
            f"転換点 {turn_id} を参照する場面がない。", "chapters"))
    return evaluated


def _check_timeline_travel(log: GameLog, ctx: _Context) -> int:
    canon = ctx.canon
    evaluated = 0
    ordered = sorted(log.chapters, key=lambda c: ctx.pos(c.id))
    previous = None
    for chapter in ordered:
        cref = f"chapters:{chapter.id}"
        declared = canon.chapters.get(chapter_key(chapter.id))
        if declared is not None:
            evaluated += 1
            if declared.day is not None and float(declared.day) != chapter.day:
                ctx.add(_finding(
                    "timeline_travel", "high",
                    f"章の day が canon（{declared.day:g}）とログ（{chapter.day:g}）で違う。",
                    cref))
            if declared.location and declared.location != chapter.location:
                ctx.add(_finding(
                    "timeline_travel", "high",
                    f"章の場所が canon（{declared.location}）とログ"
                    f"（{chapter.location}）で違う。", cref))
        if previous is not None:
            elapsed = chapter.day - previous.day
            required = canon.travel_days(previous.location, chapter.location)
            if elapsed < 0:
                ctx.add(_finding(
                    "timeline_travel", "high",
                    f"{previous.id}→{chapter.id} の日付が逆行している。", cref))
            elif required is None:
                ctx.travel_pairs_skipped += 1
            elif elapsed + 1e-9 < required:
                ctx.add(_finding(
                    "timeline_travel", "high",
                    f"{previous.location}→{chapter.location} は {required:g} 日必要だが、"
                    f"{previous.id}→{chapter.id} の経過は {elapsed:g} 日。", cref,
                    elapsed_days=elapsed, required_days=required))
        previous = chapter
    for index, chapter in enumerate(ordered):
        next_chapter = ordered[index + 1] if index + 1 < len(ordered) else None
        for scene in chapter.scenes:
            sref = f"chapters:{chapter.id}.scenes:{scene.id}"
            for move in scene.state_delta.location_moves:
                evaluated += 1
                required = canon.travel_days(move.origin, move.destination)
                elapsed = move.arrival_day - move.depart_day
                if required is None:
                    ctx.travel_pairs_skipped += 1
                elif elapsed + 1e-9 < required:
                    ctx.add(_finding(
                        "timeline_travel", "high",
                        f"{move.character} の {move.origin}→{move.destination} は "
                        f"{required:g} 日必要だが {elapsed:g} 日しか経っていない。", sref,
                        elapsed_days=elapsed, required_days=required))
                if move.depart_day + 1e-9 < chapter.day:
                    ctx.add(_finding(
                        "timeline_travel", "medium",
                        f"{move.character} の出発日 {move.depart_day:g} が章 "
                        f"{chapter.id}（{chapter.day:g} 日）より前。", sref))
                if next_chapter and move.arrival_day > next_chapter.day + 1e-9:
                    ctx.add(_finding(
                        "timeline_travel", "medium",
                        f"{move.character} の到着日 {move.arrival_day:g} が次の章 "
                        f"{next_chapter.id}（{next_chapter.day:g} 日）より後。", sref))
    return evaluated


def _check_presence_death(log: GameLog, ctx: _Context) -> int:
    canon = ctx.canon
    evaluated = 0
    for chapter in log.chapters:
        for scene in chapter.scenes:
            evaluated += 1
            sref = f"chapters:{chapter.id}.scenes:{scene.id}"
            present = set(scene.present_characters)
            for name in scene.present_characters:
                if _dead_at(canon, name, chapter.id, ctx.positions):
                    ctx.add(_finding(
                        "presence_death", "high",
                        f"{name} は {chapter.id} の時点で死亡しているのに "
                        "present_characters にいる（現在時の再登場）。", sref,
                        character=name))
            for action in scene.actions:
                aref = f"{sref}.actions:{action.id}"
                actor_dead = _dead_at(canon, action.actor, chapter.id, ctx.positions)
                if action.type in PRESENT_TENSE_TYPES:
                    if actor_dead:
                        ctx.add(_finding(
                            "presence_death", "high",
                            f"死者 {action.actor} が {action.type} の行為者として現在時に動いている。",
                            aref, character=action.actor, event_type=action.type))
                    if action.actor not in present:
                        ctx.add(_finding(
                            "presence_death", "medium",
                            f"行為者 {action.actor} が present_characters にいない。", aref))
                    for dead in _dead_in_text(canon, action.target):
                        ctx.add(_finding(
                            "presence_death", "high",
                            f"行為 {action.id} の対象が死者 {dead} の現在時行動を指している。",
                            aref, character=dead))
                elif action.type in REFERENCE_TYPES:
                    if actor_dead:
                        ctx.add(_finding(
                            "presence_death", "high",
                            f"死者 {action.actor} が記録・回想の主体として現在時に動いている。",
                            aref, character=action.actor))
                    if action.actor not in present:
                        ctx.add(_finding(
                            "presence_death", "medium",
                            f"記録・回想の主体 {action.actor} が present_characters にいない。",
                            aref))
                    if not action.subject:
                        ctx.add(_finding(
                            "presence_death", "high",
                            f"{action.type} に subject（言及される人物）がない。", aref))
                    if not action.medium:
                        ctx.add(_finding(
                            "presence_death", "high",
                            f"{action.type} に medium（記録・遺物・回想の媒体）がない。"
                            "死者の言及を許容する根拠が失われる。", aref))
                    subject_dead = _dead_at(canon, action.subject, chapter.id,
                                            ctx.positions)
                    if action.subject and subject_dead and action.medium:
                        ctx.allowed_dead_references.append({
                            "chapter": chapter.id, "scene": scene.id,
                            "action": action.id, "event_type": action.type,
                            "subject": action.subject, "medium": action.medium,
                            "actor": action.actor,
                        })
    return evaluated


def _check_knowledge_boundary(log: GameLog, ctx: _Context) -> int:
    canon = ctx.canon
    known: dict[str, set[str]] = {
        cid: set(char.knows) for cid, char in canon.characters.items()}
    evaluated = 0
    for chapter in log.chapters:
        for scene in chapter.scenes:
            sref = f"chapters:{chapter.id}.scenes:{scene.id}"
            present = set(scene.present_characters)
            for item in scene.state_delta.used_facts:
                evaluated += 1
                if item.fact not in known.get(item.character, set()):
                    ctx.add(_finding(
                        "knowledge_boundary", "high",
                        f"{item.character} は {item.fact} をまだ知らないのに "
                        f"{chapter.id} で使っている。", sref,
                        character=item.character, fact=item.fact))
                if item.character not in present:
                    ctx.add(_finding(
                        "knowledge_boundary", "medium",
                        f"{item.character} は {chapter.id} の場面にいないのに "
                        f"{item.fact} を使っている。", sref))
            for item in scene.state_delta.learned_facts:
                evaluated += 1
                if item.character not in present:
                    ctx.add(_finding(
                        "knowledge_boundary", "medium",
                        f"{item.character} は {chapter.id} の場面にいないのに "
                        f"{item.fact} を学習している。", sref))
                if _dead_at(canon, item.character, chapter.id, ctx.positions):
                    ctx.add(_finding(
                        "knowledge_boundary", "high",
                        f"死者 {item.character} が {chapter.id} で {item.fact} を学習している。",
                        sref, character=item.character))
                if item.fact in known.get(item.character, set()):
                    ctx.add(_finding(
                        "knowledge_boundary", "medium",
                        f"{item.character} は {item.fact} を既に知っているのに再度 learn している。",
                        sref, fact=item.fact))
                fact = canon.facts.get(item.fact)
                if fact is not None and fact.setup:
                    if ctx.pos(chapter.id) < ctx.pos(fact.setup):
                        ctx.add(_finding(
                            "knowledge_boundary", "high",
                            f"{item.fact} の canon 上の開示章は {fact.setup} だが、"
                            f"{chapter.id} で学習している（開示順序の先行）。", sref,
                            fact=item.fact))
                known.setdefault(item.character, set()).add(item.fact)
    ctx.known_at_end = {cid: sorted(facts) for cid, facts in sorted(known.items())}
    return evaluated


def _check_foreshadow_order(log: GameLog, ctx: _Context) -> int:
    canon = ctx.canon
    planted: dict[str, tuple[str, str]] = {}
    if ctx.scenes:
        for scene in ctx.scenes.scenes:
            for item in scene.planted:
                planted[item.id] = (chapter_key(scene.chapter),
                                    chapter_key(item.payoff))
    events: list[tuple[int, str, str, str, str]] = []
    seq = 0
    for chapter in log.chapters:
        for scene in chapter.scenes:
            for event in scene.state_delta.foreshadow_events:
                events.append((seq, event.id, event.event, chapter.id, scene.id))
                seq += 1
    state: dict[str, dict] = {}
    for index, fs_id, kind, chapter_id, scene_id in events:
        entry = state.setdefault(fs_id, {"setup": None, "payoff": None})
        ref = f"chapters:{chapter_id}.scenes:{scene_id}"
        if entry[kind] is None:
            entry[kind] = (index, chapter_id, scene_id)
        elif entry[kind][1] != chapter_id or entry[kind][2] != scene_id:
            ctx.add(_finding(
                "foreshadow_order", "medium",
                f"{fs_id} の {kind} が複数回宣言されている。", ref, foreshadow=fs_id))
    for fs_id, entry in state.items():
        setup, payoff = entry["setup"], entry["payoff"]
        if payoff and (not setup or setup[0] > payoff[0]):
            ctx.add(_finding(
                "foreshadow_order", "high",
                f"{fs_id} の回収が設置より前か、設置の記録がない。",
                f"chapters:{payoff[1]}.scenes:{payoff[2]}", foreshadow=fs_id))
        declared = canon.foreshadowing.get(fs_id)
        if declared:
            if declared.setup and setup and chapter_key(setup[1]) != declared.setup:
                ctx.add(_finding(
                    "foreshadow_order", "medium",
                    f"{fs_id} の設置章が canon（{declared.setup}）とログ"
                    f"（{setup[1]}）で違う。", f"chapters:{setup[1]}", foreshadow=fs_id))
            if declared.setup and not setup:
                ctx.add(_finding(
                    "foreshadow_order", "medium",
                    f"{fs_id} は canon で {declared.setup} に設置される宣言があるが、"
                    "ログに setup がない。", "chapters", foreshadow=fs_id))
            if declared.payoff and payoff and chapter_key(payoff[1]) != declared.payoff:
                ctx.add(_finding(
                    "foreshadow_order", "medium",
                    f"{fs_id} の回収章が canon（{declared.payoff}）とログ"
                    f"（{payoff[1]}）で違う。", f"chapters:{payoff[1]}",
                    foreshadow=fs_id))
            if declared.payoff and not payoff:
                ctx.add(_finding(
                    "foreshadow_order", "high",
                    f"{fs_id} は {declared.payoff} で回収される宣言があるが、"
                    "ログに payoff がない。", "chapters", foreshadow=fs_id))
        elif fs_id in planted:
            setup_chapter, payoff_chapter = planted[fs_id]
            if not setup or not payoff:
                ctx.add(_finding(
                    "foreshadow_order", "medium",
                    f"設計で植えられた {fs_id} の設置・回収がログに揃っていない。",
                    "chapters", foreshadow=fs_id))
            else:
                if chapter_key(setup[1]) != setup_chapter and setup_chapter:
                    ctx.add(_finding(
                        "foreshadow_order", "medium",
                        f"{fs_id} の設置章が設計（{setup_chapter}）とログ"
                        f"（{setup[1]}）で違う。", f"chapters:{setup[1]}"))
                if payoff_chapter and ctx.pos(payoff[1]) < ctx.pos(payoff_chapter):
                    ctx.add(_finding(
                        "foreshadow_order", "medium",
                        f"{fs_id} の回収（{payoff[1]}）が設計の回収予定"
                        f"（{payoff_chapter}）より前。", f"chapters:{payoff[1]}"))
        if setup and not payoff:
            ctx.add(_finding(
                "foreshadow_order", "medium",
                f"{fs_id} は設置されたが回収されていない。",
                f"chapters:{setup[1]}.scenes:{setup[2]}", foreshadow=fs_id))
        ctx.foreshadow_state[fs_id] = {
            "setup": setup[1] if setup else None,
            "payoff": payoff[1] if payoff else None,
        }
    for fs_id, declared in canon.foreshadowing.items():
        if fs_id in state:
            continue
        if declared.setup or declared.payoff:
            ctx.add(_finding(
                "foreshadow_order", "medium",
                f"canon の伏線 {fs_id} がゲームログに現れない。", "chapters",
                foreshadow=fs_id))
    return len(state)


def _compare_declared(log: GameLog, ctx: _Context, owner: str, owner_id: str,
                      chapter_id: str, declared: tuple[str, ...], ref: str) -> int:
    expected = owner_markers(log, owner, owner_id, chapter_id)
    problems = 0
    for raw in declared:
        kind = marker_kind(raw)
        if kind is None:
            problems += 1
            ctx.add(_finding(
                "emitted_markers", "high",
                f"マーカー「{raw}」を既存のマーカー文法で読めない。", ref,
                marker=raw))
        elif kind not in DERIVED_KINDS:
            problems += 1
            ctx.add(_finding(
                "emitted_markers", "high",
                f"マーカー種別「{kind}」は state_delta から導出できない。", ref,
                marker=raw))
    wanted = [normalise_marker(text) for text in expected]
    given = [normalise_marker(text) for text in declared]
    if wanted != given:
        problems += 1
        missing = [text for text in wanted if text not in given]
        extra = [text for text in given if text not in wanted]
        ctx.add(_finding(
            "emitted_markers", "high",
            f"{owner} {owner_id} の emitted_markers が導出列と一致しない"
            f"（欠落 {len(missing)} / 余分 {len(extra)} / 順序差 "
            f"{int(not missing and not extra)}）。", ref,
            expected=wanted, declared=given, missing=missing, extra=extra))
    return problems


def _check_emitted_markers(log: GameLog, ctx: _Context) -> int:
    evaluated = 0
    for chapter in log.chapters:
        cref = f"chapters:{chapter.id}"
        _compare_declared(log, ctx, "chapter", chapter.id, chapter.id,
                          chapter.emitted_markers, cref)
        evaluated += 1
        for scene in chapter.scenes:
            _compare_declared(log, ctx, "scene", scene.id, chapter.id,
                              scene.emitted_markers,
                              f"{cref}.scenes:{scene.id}")
            evaluated += 1
    return evaluated


# -- driver -----------------------------------------------------------------
def check_game_log(log: GameLog, canon: Canon, plot: PlotDoc | None = None,
                   scenes: SceneDoc | None = None) -> dict:
    """Check a game log against canon and (optionally) the design documents."""
    positions = {cid: index for index, cid in enumerate(canon.chapter_order())}
    for index, chapter in enumerate(log.chapters):
        positions.setdefault(chapter_key(chapter.id), 1000 + index)
    ctx = _Context(canon=canon, plot=plot, scenes=scenes, positions=positions)
    runners: list[tuple[str, Callable[[GameLog, _Context], int]]] = [
        ("schema_shape", _check_schema_shape),
        ("canon_refs", _check_canon_refs),
        ("design_alignment", _check_design_alignment),
        ("timeline_travel", _check_timeline_travel),
        ("presence_death", _check_presence_death),
        ("knowledge_boundary", _check_knowledge_boundary),
        ("foreshadow_order", _check_foreshadow_order),
        ("emitted_markers", _check_emitted_markers),
    ]
    checks: list[dict] = []
    for check_id, runner in runners:
        if check_id == "design_alignment" and (plot is None or scenes is None):
            checks.append({**_spec_dict(check_id), "status": "skipped",
                           "reason": "plot.json / scene.json が与えられていない。",
                           "evaluated": 0, "findings": 0})
            continue
        before = len(ctx.findings)
        evaluated = runner(log, ctx)
        found = len(ctx.findings) - before
        checks.append({**_spec_dict(check_id),
                       "status": "fail" if found else "pass",
                       "evaluated": evaluated, "findings": found})
    by_severity: dict[str, int] = {}
    by_check: dict[str, int] = {}
    for item in ctx.findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
        by_check[item["check"]] = by_check.get(item["check"], 0) + 1
    markers = [marker.as_dict() for marker in derive_markers(log)]
    marker_counts: dict[str, int] = {}
    for marker in markers:
        marker_counts[marker["kind"]] = marker_counts.get(marker["kind"], 0) + 1
    blocking = sum(1 for item in ctx.findings
                   if item["severity"] in REPAIR_SEVERITIES)
    return {
        "schema_version": "1.0",
        "tool": "game-log-check",
        # Names only: the report must be portable inside an experiment bundle
        # and byte-identical when the same inputs are replayed elsewhere.
        "game_log": log.path.name,
        "canon": canon.root.name,
        "design": {
            "plot": Path(plot.path).name if plot else None,
            "scenes": Path(scenes.path).name if scenes else None,
        },
        "findings": ctx.findings,
        "checks": checks,
        "markers": markers,
        "marker_counts": marker_counts,
        "allowed_dead_references": ctx.allowed_dead_references,
        "state": {
            "knows_at_end": ctx.known_at_end,
            "foreshadow_state": ctx.foreshadow_state,
            "travel_pairs_skipped": ctx.travel_pairs_skipped,
        },
        "summary": {
            "status": "clean" if blocking == 0 else "unresolved",
            "chapters": len(log.chapters),
            "scenes": sum(len(chapter.scenes) for chapter in log.chapters),
            "findings": len(ctx.findings),
            "blocking_findings": blocking,
            "by_severity": by_severity,
            "by_check": by_check,
            "checks_run": sum(1 for c in checks if c["status"] != "skipped"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
            "markers": len(markers),
            "allowed_dead_references": len(ctx.allowed_dead_references),
        },
    }


def _spec_dict(check_id: str) -> dict:
    spec = CHECK_BY_ID[check_id]
    return {"id": spec.id, "question_ja": spec.question_ja,
            "acceptance_ja": spec.acceptance_ja, "limits_ja": spec.limits_ja}


def check_game_log_files(game_log_path: str | Path, canon_dir: str | Path,
                         design_dir: str | Path | None = None, *,
                         require_design: bool = False) -> dict:
    """Convenience loader for the CLI: files in, report out."""
    if require_design and design_dir is None:
        raise GameLogError("--require-design needs a design directory")
    log = load_game_log(game_log_path)
    canon = load_canon(canon_dir)
    plot = scenes = None
    if design_dir is not None:
        from ..plot.schema import load_plot
        from ..scene.schema import load_scenes
        root = Path(design_dir)
        plot_path = root / "plot.json" if root.is_dir() else root
        scene_path = root / "scene.json" if root.is_dir() else root
        if plot_path.is_file():
            plot = load_plot(plot_path)
        if scene_path.is_file():
            scenes = load_scenes(scene_path)
        if require_design and (plot is None or scenes is None):
            raise GameLogError(
                f"{root}: plot.json and scene.json are required for a full check")
    return check_game_log(log, canon, plot, scenes)


def needs_repair(findings: list[dict]) -> bool:
    return any(item["severity"] in REPAIR_SEVERITIES for item in findings)


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# 構造化ゲームログの検査結果 (Stage A)",
        "",
        f"対象: `{Path(report['game_log']).name}` / "
        f"{summary['chapters']} 章・{summary['scenes']} 場面・"
        f"確定マーカー {summary['markers']} 件。",
        f"所見: {summary['findings']} 件（{summary['by_severity']}）／"
        f"状態: **{summary['status']}**。",
        "",
        "死者の記録・遺物・回想への言及は `record_reference` / `memory_mention` "
        "として許容し、現在時行動（`present_characters` / `action` / `dialogue`）"
        "のみを禁止している。",
        "",
        "| 検査 | 状態 | 対象 | 所見 | 合格条件 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['id']}` | {check['status']} | "
                     f"{check['evaluated']} | {check['findings']} | "
                     f"{check['acceptance_ja']} |")
    lines += ["", "## 確定マーカー列", ""]
    for marker in report["markers"]:
        lines.append(f"* `{marker['text']}` （{marker['owner']}: "
                     f"{marker['owner_id']}）")
    if report["allowed_dead_references"]:
        lines += ["", "## 許容された死者への言及", ""]
        for item in report["allowed_dead_references"]:
            lines.append(f"* {item['chapter']}/{item['scene']}: "
                         f"{item['subject']} を {item['medium']} 経由で"
                         f"参照（{item['event_type']}）")
    if report["findings"]:
        lines += ["", "## 所見", "", "| 検査 | 重要度 | 位置 | 内容 |",
                  "| --- | --- | --- | --- |"]
        for item in report["findings"]:
            lines.append(f"| `{item['check']}` | {item['severity']} | "
                         f"{item['gamelog_ref']} | {item['message_ja']} |")
    lines += ["", "この検査は構造・衛生の L1 であり、物語の面白さや質は判定しない。", ""]
    return "\n".join(lines)


__all__ = [
    "CHECKS", "CHECK_BY_ID", "REPAIR_SEVERITIES", "check_game_log",
    "check_game_log_files", "needs_repair", "render_markdown",
]
