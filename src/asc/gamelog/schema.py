"""The Stage A structured game log (``game_log.json``).

A game log is the *facts* of a story, decided before any prose exists. It is a
small, chapter/scene ordered record of the Japanese TRPG "situation -> action
-> outcome" loop (B5 in ``research/curated/narrative/japan_trpg/report.md``),
plus the state delta that each scene produces. The continuity-critical facts
(time, place, who learns what, which foreshadow is set up or paid off) live in
``state_delta`` so that a deterministic checker — not a language model — can
fix the marker sequence before Stage B rewrites the log into prose.

Two event types deliberately separate the dead-character cases that the
string-based continuity audit cannot tell apart:

* ``action`` / ``dialogue`` — a *present-time* act by an actor who must be
  alive and present. A dead actor here is a hard violation.
* ``record_reference`` / ``memory_mention`` — a living actor reads a record,
  handles a relic, or recalls someone. The dead person is the ``subject``, and
  a ``medium`` (the handout, relic, ledger, or recollection) must be declared.
  These are allowed and are reported as ``allowed_dead_references``.

This module is a strict loader: malformed structure raises :class:`GameLogError`
so a repair round sees a precise error. Semantic consistency (canon, plot,
scenes) is checked separately in :mod:`asc.gamelog.check`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

#: Keys the schema reads at each level. Anything else is reported, not dropped
#: silently (see :func:`_note_unknown`).
KEYS_ROOT = frozenset({"schema_version", "task", "notes", "chapters"})
KEYS_CHAPTER = frozenset({"id", "day", "location", "emitted_markers", "scenes"})
KEYS_SCENE = frozenset({
    "id", "scene_ref", "act_ref", "turn_ref", "situation", "purpose", "conflict",
    "change", "tension", "choice", "outcome", "present_characters", "actions",
    "state_delta", "day", "location", "emitted_markers"})
KEYS_ACTION = frozenset({"id", "type", "actor", "summary", "target", "subject",
                         "medium", "text"})
KEYS_STATE_DELTA = frozenset({"learned_facts", "used_facts", "foreshadow_events",
                              "location_moves"})
KEYS_FACT_USE = frozenset({"character", "fact"})
KEYS_FORESHADOW = frozenset({"id", "event"})
KEYS_MOVE = frozenset({"character", "origin", "destination", "depart_day",
                       "arrival_day"})

#: Present-time events: the actor must be alive and on stage.
PRESENT_TENSE_TYPES = frozenset({"action", "dialogue"})
#: References to someone/something absent: the dead person is the subject.
REFERENCE_TYPES = frozenset({"record_reference", "memory_mention"})
ACTION_TYPES = frozenset(PRESENT_TENSE_TYPES | REFERENCE_TYPES)
FORESHADOW_EVENTS = frozenset({"setup", "payoff"})
TENSION_DEVICES = frozenset({"suspense", "curiosity", "surprise", "irony",
                             "deadline", "quiet"})


class GameLogError(ValueError):
    """Raised when a game log is not the declared shape."""


# -- small parsing helpers --------------------------------------------------
def _mapping(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise GameLogError(f"{where}: must be an object")
    return value


def _rows(value: Any, where: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise GameLogError(f"{where}: must be a list")
    return [_mapping(row, f"{where}[{i}]") for i, row in enumerate(value)]


def _text(row: dict, key: str, where: str, *, required: bool = True) -> str:
    value = row.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise GameLogError(f"{where}.{key}: must be a string")
    return value.strip()


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise GameLogError(f"{where}: must be a list of strings")
    return tuple(v.strip() for v in value if v.strip())


def _note_unknown(row: dict, allowed: set[str], where: str,
                  unknown: list[dict] | None) -> None:
    """Record keys the schema does not read (A-03).

    Unknown keys are still accepted — a repair round should not fail on a
    cosmetic typo — but they are reported so a misspelt ``learned_facts`` does
    not silently weaken the checks.
    """
    if unknown is None:
        return
    for key in row:
        if key not in allowed:
            unknown.append({"where": where, "key": key})


def _number(row: dict, key: str, where: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GameLogError(f"{where}.{key}: must be a number")
    return float(value)


# -- records ----------------------------------------------------------------
@dataclass(frozen=True)
class Action:
    """One event in a scene's situation -> action -> outcome loop."""

    id: str
    type: str
    actor: str
    summary: str
    target: str = ""
    subject: str = ""   # referenced person for record_reference / memory_mention
    medium: str = ""    # handout / relic / record / recollection
    text: str = ""      # optional verbatim dialogue or record excerpt

    def as_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "actor": self.actor,
                "summary": self.summary, "target": self.target,
                "subject": self.subject, "medium": self.medium, "text": self.text}


@dataclass(frozen=True)
class FactUse:
    character: str
    fact: str

    def as_dict(self) -> dict:
        return {"character": self.character, "fact": self.fact}


@dataclass(frozen=True)
class ForeshadowEvent:
    id: str
    event: str  # setup | payoff

    def as_dict(self) -> dict:
        return {"id": self.id, "event": self.event}


@dataclass(frozen=True)
class LocationMove:
    character: str
    origin: str
    destination: str
    depart_day: float
    arrival_day: float

    def as_dict(self) -> dict:
        return {"character": self.character, "origin": self.origin,
                "destination": self.destination, "depart_day": self.depart_day,
                "arrival_day": self.arrival_day}


@dataclass(frozen=True)
class StateDelta:
    """Everything that changes in a scene. Markers are derived from here."""

    learned_facts: tuple[FactUse, ...] = ()
    used_facts: tuple[FactUse, ...] = ()
    foreshadow_events: tuple[ForeshadowEvent, ...] = ()
    location_moves: tuple[LocationMove, ...] = ()

    def as_dict(self) -> dict:
        return {
            "learned_facts": [item.as_dict() for item in self.learned_facts],
            "used_facts": [item.as_dict() for item in self.used_facts],
            "foreshadow_events": [item.as_dict() for item in self.foreshadow_events],
            "location_moves": [item.as_dict() for item in self.location_moves],
        }


@dataclass(frozen=True)
class Scene:
    id: str
    chapter: str
    scene_ref: str      # scene.json id
    act_ref: str        # plot.json act id
    turn_ref: str       # plot.json turn id
    situation: str
    purpose: str
    conflict: str
    change: str
    tension: str
    choice: str         # the turn's choice, as enacted in this scene
    outcome: str
    present_characters: tuple[str, ...]
    actions: tuple[Action, ...]
    state_delta: StateDelta = field(default_factory=StateDelta)
    day: float | None = None
    location: str = ""
    emitted_markers: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        payload = {
            "id": self.id, "scene_ref": self.scene_ref, "act_ref": self.act_ref,
            "turn_ref": self.turn_ref, "situation": self.situation,
            "purpose": self.purpose, "conflict": self.conflict,
            "change": self.change, "tension": self.tension, "choice": self.choice,
            "outcome": self.outcome,
            "present_characters": list(self.present_characters),
            "actions": [action.as_dict() for action in self.actions],
            "state_delta": self.state_delta.as_dict(),
            "emitted_markers": list(self.emitted_markers),
        }
        if self.day is not None:
            payload["day"] = self.day
        if self.location:
            payload["location"] = self.location
        return payload


@dataclass(frozen=True)
class Chapter:
    id: str
    day: float
    location: str
    scenes: tuple[Scene, ...]
    emitted_markers: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"id": self.id, "day": self.day, "location": self.location,
                "emitted_markers": list(self.emitted_markers),
                "scenes": [scene.as_dict() for scene in self.scenes]}


@dataclass(frozen=True)
class GameLog:
    path: Path
    schema_version: str
    task: str
    chapters: tuple[Chapter, ...]
    notes: str = ""
    #: ``{"where": ..., "key": ...}`` for keys the schema ignored (A-03).
    unknown_keys: tuple[dict, ...] = ()

    def as_dict(self) -> dict:
        """Canonical form, used for the persisted log and Stage B prompts."""
        return {
            "schema_version": self.schema_version,
            "task": self.task,
            "notes": self.notes,
            "chapters": [chapter.as_dict() for chapter in self.chapters],
        }

    def chapter(self, chapter_id: str) -> Chapter | None:
        for chapter in self.chapters:
            if chapter.id == chapter_id:
                return chapter
        return None


# -- parsing ----------------------------------------------------------------
def _parse_action(row: dict, where: str, unknown: list[dict] | None = None) -> Action:
    _note_unknown(row, KEYS_ACTION, where, unknown)
    action_type = _text(row, "type", where)
    if action_type not in ACTION_TYPES:
        raise GameLogError(
            f"{where}.type: {action_type!r} is not one of {sorted(ACTION_TYPES)}")
    return Action(
        id=_text(row, "id", where), type=action_type,
        actor=_text(row, "actor", where), summary=_text(row, "summary", where),
        target=_text(row, "target", where, required=False),
        subject=_text(row, "subject", where, required=False),
        medium=_text(row, "medium", where, required=False),
        text=_text(row, "text", where, required=False))


def _parse_fact_use(row: dict, where: str,
                    unknown: list[dict] | None = None) -> FactUse:
    _note_unknown(row, KEYS_FACT_USE, where, unknown)
    return FactUse(character=_text(row, "character", where),
                   fact=_text(row, "fact", where))


def _parse_state_delta(row: dict, where: str,
                       unknown: list[dict] | None = None) -> StateDelta:
    raw = _mapping(row.get("state_delta") or {}, f"{where}.state_delta")
    _note_unknown(raw, KEYS_STATE_DELTA, f"{where}.state_delta", unknown)
    events = []
    for index, item in enumerate(_rows(raw.get("foreshadow_events"),
                                       f"{where}.state_delta.foreshadow_events")):
        at = f"{where}.state_delta.foreshadow_events[{index}]"
        _note_unknown(item, KEYS_FORESHADOW, at, unknown)
        event = _text(item, "event", at)
        if event not in FORESHADOW_EVENTS:
            raise GameLogError(
                f"{at}.event: {event!r} is not one of {sorted(FORESHADOW_EVENTS)}")
        events.append(ForeshadowEvent(id=_text(item, "id", at), event=event))
    moves = []
    for index, item in enumerate(_rows(raw.get("location_moves"),
                                       f"{where}.state_delta.location_moves")):
        at = f"{where}.state_delta.location_moves[{index}]"
        _note_unknown(item, KEYS_MOVE, at, unknown)
        moves.append(LocationMove(
            character=_text(item, "character", at),
            origin=_text(item, "origin", at),
            destination=_text(item, "destination", at),
            depart_day=_number(item, "depart_day", at),
            arrival_day=_number(item, "arrival_day", at)))
    return StateDelta(
        learned_facts=tuple(_parse_fact_use(item, f"{where}.state_delta.learned_facts[{i}]",
                                            unknown)
                            for i, item in enumerate(_rows(
                                raw.get("learned_facts"),
                                f"{where}.state_delta.learned_facts"))),
        used_facts=tuple(_parse_fact_use(item, f"{where}.state_delta.used_facts[{i}]",
                                         unknown)
                         for i, item in enumerate(_rows(
                             raw.get("used_facts"),
                             f"{where}.state_delta.used_facts"))),
        foreshadow_events=tuple(events), location_moves=tuple(moves))


def _parse_scene(row: dict, chapter_id: str, where: str,
                 unknown: list[dict] | None = None) -> Scene:
    _note_unknown(row, KEYS_SCENE, where, unknown)
    day = row.get("day")
    if day is not None:
        if isinstance(day, bool) or not isinstance(day, (int, float)):
            raise GameLogError(f"{where}.day: must be a number")
        day = float(day)
    return Scene(
        id=_text(row, "id", where), chapter=chapter_id,
        scene_ref=_text(row, "scene_ref", where),
        act_ref=_text(row, "act_ref", where),
        turn_ref=_text(row, "turn_ref", where, required=False),
        situation=_text(row, "situation", where),
        purpose=_text(row, "purpose", where),
        conflict=_text(row, "conflict", where),
        change=_text(row, "change", where),
        tension=_text(row, "tension", where),
        choice=_text(row, "choice", where),
        outcome=_text(row, "outcome", where),
        present_characters=_strings(row.get("present_characters"),
                                    f"{where}.present_characters"),
        actions=tuple(_parse_action(item, f"{where}.actions[{i}]", unknown)
                      for i, item in enumerate(_rows(row.get("actions"),
                                                     f"{where}.actions"))),
        state_delta=_parse_state_delta(row, where, unknown),
        day=day,
        location=_text(row, "location", where, required=False),
        emitted_markers=_strings(row.get("emitted_markers"),
                                 f"{where}.emitted_markers"))


def parse_game_log(data: Any, path: str | Path = "<memory>") -> GameLog:
    """Parse a mapping into a :class:`GameLog` (no canon/design checks here)."""
    root = _mapping(data, "game_log")
    unknown: list[dict] = []
    _note_unknown(root, KEYS_ROOT, "game_log", unknown)
    version = _text(root, "schema_version", "game_log")
    if version != SCHEMA_VERSION:
        raise GameLogError(
            f"game_log.schema_version: expected {SCHEMA_VERSION!r}, got {version!r}")
    chapter_rows = _rows(root.get("chapters"), "game_log.chapters")
    if not chapter_rows:
        raise GameLogError("game_log.chapters: at least one chapter is required")
    chapters: list[Chapter] = []
    for index, row in enumerate(chapter_rows):
        where = f"game_log.chapters[{index}]"
        _note_unknown(row, KEYS_CHAPTER, where, unknown)
        chapter_id = _text(row, "id", where)
        scene_rows = _rows(row.get("scenes"), f"{where}.scenes")
        if not scene_rows:
            raise GameLogError(f"{where}.scenes: at least one scene is required")
        chapters.append(Chapter(
            id=chapter_id, day=_number(row, "day", where),
            location=_text(row, "location", where),
            emitted_markers=_strings(row.get("emitted_markers"),
                                     f"{where}.emitted_markers"),
            scenes=tuple(_parse_scene(item, chapter_id,
                                      f"{where}.scenes[{i}]", unknown)
                         for i, item in enumerate(scene_rows))))
    return GameLog(path=Path(path), schema_version=version,
                   task=_text(root, "task", "game_log"),
                   chapters=tuple(chapters),
                   notes=_text(root, "notes", "game_log", required=False),
                   unknown_keys=tuple(unknown))


def load_game_log(path: str | Path) -> GameLog:
    """Load a ``game_log.json`` file."""
    path = Path(path)
    if path.is_dir():
        path = path / "game_log.json"
    if not path.is_file():
        raise GameLogError(f"game log not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GameLogError(f"{path.name}: cannot read game log JSON: {exc}") from exc
    return parse_game_log(data, path)


#: Raised for parse errors during Stage A; exported for callers that only want
#: the loader's exception type.
__all__ = [
    "SCHEMA_VERSION", "ACTION_TYPES", "PRESENT_TENSE_TYPES", "REFERENCE_TYPES",
    "FORESHADOW_EVENTS", "TENSION_DEVICES", "GameLogError", "Action", "FactUse",
    "ForeshadowEvent", "LocationMove", "StateDelta", "Scene", "Chapter",
    "GameLog", "parse_game_log", "load_game_log", "KEYS_ROOT", "KEYS_CHAPTER",
    "KEYS_SCENE", "KEYS_ACTION", "KEYS_STATE_DELTA", "KEYS_FACT_USE",
    "KEYS_FORESHADOW", "KEYS_MOVE",
]
