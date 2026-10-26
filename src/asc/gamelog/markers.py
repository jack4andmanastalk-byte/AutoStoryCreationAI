"""Deterministic marker derivation for a Stage A game log.

Markers are *not* something a model has to remember while writing prose. They
are a pure function of the log's state: the chapter's day/location, each
``learn``/``use`` in ``state_delta``, and each foreshadow ``setup``/``payoff``.
Stage A declares the derived sequence in ``emitted_markers``; Stage B must
reproduce exactly that sequence. Both sides are checked mechanically.

The emitted strings use the existing continuity-ledger marker grammar
(:mod:`asc.story.text`), so a rewritten chapter can be audited by the same L1
tooling as a directly generated chapter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..story.text import MARKER_RE, MARKER_KINDS, parse_markers
from .schema import GameLog

#: Kinds this slice derives. ``death``/``state``/``age`` are not derived here;
#: a Stage B text that introduces them is a deviation from the log.
DERIVED_KINDS = frozenset({"time", "location", "learn", "use", "foreshadow"})

#: Markers that imply a present-time state change in the legacy audit. A dead
#: subject here would mean "the dead person acted now", which the log forbids.
DEAD_ACTOR_MARKER_KINDS = frozenset({"state", "learn", "use", "age", "death"})


@dataclass(frozen=True)
class DerivedMarker:
    chapter: str
    owner: str        # "chapter" | "scene"
    owner_id: str
    kind: str
    text: str

    def as_dict(self) -> dict:
        return {"chapter": self.chapter, "owner": self.owner,
                "owner_id": self.owner_id, "kind": self.kind, "text": self.text}


def format_day(day: float) -> str:
    return str(int(day)) if float(day).is_integer() else str(day)


def normalise_marker(raw: str) -> str:
    """Compare markers without punishing harmless whitespace differences."""
    return re.sub(r"\s+", " ", raw.strip())


def marker_kind(raw: str) -> str | None:
    match = MARKER_RE.fullmatch(normalise_marker(raw))
    return match.group(1) if match else None


def derive_markers(log: GameLog) -> tuple[DerivedMarker, ...]:
    """The one canonical, ordered marker sequence for the whole log."""
    markers: list[DerivedMarker] = []
    for chapter in log.chapters:
        markers.append(DerivedMarker(
            chapter=chapter.id, owner="chapter", owner_id=chapter.id,
            kind="time", text="{{time: day=%s}}" % format_day(chapter.day)))
        markers.append(DerivedMarker(
            chapter=chapter.id, owner="chapter", owner_id=chapter.id,
            kind="location", text="{{location: %s}}" % chapter.location))
        for scene in chapter.scenes:
            for item in scene.state_delta.learned_facts:
                markers.append(DerivedMarker(
                    chapter=chapter.id, owner="scene", owner_id=scene.id,
                    kind="learn",
                    text="{{learn: %s fact=%s}}" % (item.character, item.fact)))
            for item in scene.state_delta.used_facts:
                markers.append(DerivedMarker(
                    chapter=chapter.id, owner="scene", owner_id=scene.id,
                    kind="use",
                    text="{{use: %s fact=%s}}" % (item.character, item.fact)))
            for event in scene.state_delta.foreshadow_events:
                markers.append(DerivedMarker(
                    chapter=chapter.id, owner="scene", owner_id=scene.id,
                    kind="foreshadow",
                    text="{{foreshadow: %s %s}}" % (event.id, event.event)))
    return tuple(markers)


def chapter_markers(log: GameLog, chapter_id: str) -> tuple[DerivedMarker, ...]:
    """Markers a Stage B chapter must contain, in this exact order."""
    return tuple(marker for marker in derive_markers(log)
                 if marker.chapter == chapter_id)


def owner_markers(log: GameLog, owner: str, owner_id: str,
                  chapter_id: str) -> tuple[str, ...]:
    """Derived marker strings declared by one chapter or one scene."""
    return tuple(marker.text for marker in derive_markers(log)
                 if (marker.chapter == chapter_id and marker.owner == owner
                     and marker.owner_id == owner_id))


def prose_markers(text: str, chapter_id: str) -> list[dict]:
    """Parse a rewritten chapter into ordered ``{kind, raw}`` records."""
    records = []
    for marker in parse_markers(text, chapter_id):
        records.append({
            "kind": marker.kind,
            "raw": normalise_marker(marker.raw),
            "subject": marker.subject,
            "line": marker.line,
            "supported": marker.kind in MARKER_KINDS,
        })
    return records


def expected_marker_texts(log: GameLog, chapter_id: str) -> tuple[str, ...]:
    return tuple(normalise_marker(marker.text)
                 for marker in chapter_markers(log, chapter_id))


__all__ = [
    "DERIVED_KINDS", "DEAD_ACTOR_MARKER_KINDS", "DerivedMarker", "format_day",
    "normalise_marker", "marker_kind", "derive_markers", "chapter_markers",
    "owner_markers", "prose_markers", "expected_marker_texts",
]
