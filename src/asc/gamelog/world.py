"""Deterministic world state: the travel graph and the story timeline.

Two things a language model must not be asked to compute:

* **how many days it takes to get somewhere** — that is a property of the world,
  so it is a graph over ``locations.travel_days`` and is answered with a
  shortest-path search, not by arithmetic in prose;
* **how many days a character has been away from a place** — that is a fold
  over the verified game log, so it is derived here and handed to Stage B as
  settled numbers.

The same derivation is used in two directions:

* the log side uses :class:`World` to decide whether a declared move is
  possible at all (a pair that is not directly listed may still be reachable
  through a third place);
* the prose side compares *explicitly written* day counts against
  :func:`derive_timeline` so "四日ぶり" in a chapter that is really six days
  later is reported instead of silently accepted.

What this does **not** do is judge prose that stays abstract ("しばらく",
"明け方"). That is deliberate: a chapter is allowed to render time without
numbers, and a number that is never written cannot contradict anything. The
contract is "an explicit day count must match the derived timeline", not
"the prose must state the timeline".
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from ..story.canon import Canon
from .schema import GameLog

#: ``schema`` string for the derived ``timeline.json``.
TIMELINE_SCHEMA = "trpg-timeline-v1"


@dataclass(frozen=True)
class World:
    """The travel graph: shortest-path days, or ``None`` when disconnected."""

    edges: dict[str, dict[str, float]] = field(default_factory=dict)

    def neighbours(self, place: str) -> dict[str, float]:
        return self.edges.get(place, {})

    def places(self) -> list[str]:
        return sorted({*self.edges} |
                      {other for row in self.edges.values() for other in row})

    def distances_from(self, place: str) -> dict[str, float]:
        """Shortest-path days from ``place`` to every reachable place."""
        if place not in self.edges and place not in self.places():
            return {}
        best: dict[str, float] = {place: 0.0}
        queue: list[tuple[float, str]] = [(0.0, place)]
        while queue:
            cost, here = heapq.heappop(queue)
            if cost > best.get(here, float("inf")):
                continue
            for there, weight in self.neighbours(here).items():
                candidate = cost + weight
                if candidate < best.get(there, float("inf")):
                    best[there] = candidate
                    heapq.heappush(queue, (candidate, there))
        return best

    def travel_days(self, origin: str | None, destination: str | None) -> float | None:
        """Shortest path in days; ``None`` when the two places are not linked."""
        if not origin or not destination:
            return None
        if origin == destination:
            return 0.0
        return self.distances_from(origin).get(destination)

    def reachable(self, origin: str | None, destination: str | None) -> bool:
        return self.travel_days(origin, destination) is not None


def build_world(canon: Canon) -> World:
    """Undirected travel graph from ``locations[].travel_days``.

    The table is written one way (``灯台: {王都: 3}``), but travel is not
    directed in this canon, so both directions are added. When a pair is
    listed twice with different values the smaller one wins: the graph must
    not make a trip impossible because of a richer alternate route.
    """
    edges: dict[str, dict[str, float]] = {}
    for place_id, location in canon.locations.items():
        edges.setdefault(place_id, {})
        for other, days in (location.travel_days or {}).items():
            value = float(days)
            for a, b in ((place_id, other), (other, place_id)):
                row = edges.setdefault(a, {})
                row[b] = min(value, row.get(b, value))
    return World(edges=edges)


# -- timeline derivation ----------------------------------------------------
def _chapter_rows(log: GameLog, canon: Canon) -> list[dict[str, Any]]:
    """Per-chapter day/location in the order the log declares them."""
    rows: list[dict[str, Any]] = []
    for chapter in log.chapters:
        present: list[str] = []
        for scene in chapter.scenes:
            for name in scene.present_characters:
                if name not in present:
                    present.append(name)
        rows.append({"id": chapter.id, "day": float(chapter.day),
                     "location": chapter.location, "present": present,
                     "scenes": list(chapter.scenes)})
    return rows


def derive_timeline(log: GameLog, canon: Canon,
                    world: World | None = None) -> dict:
    """The settled timeline, derived from canon + the verified log.

    Every value here is a fact about the story, computed by folding the log.
    Nothing in this module reads prose.
    """
    world = world or build_world(canon)
    rows = _chapter_rows(log, canon)
    # ``here`` is where each character is *now*; ``left`` remembers the day a
    # character last departed a place, which is what "N 日ぶり" refers to.
    here: dict[str, str] = {cid: char.location for cid, char in canon.characters.items()
                            if char.location}
    left: dict[tuple[str, str], float] = {}
    arrived: dict[tuple[str, str], float] = {}
    chapters: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else None
        following = rows[index + 1] if index + 1 < len(rows) else None
        entry = {cid: here.get(cid) for cid in row["present"]}
        moves: list[dict[str, Any]] = []
        for scene in row["scenes"]:
            for move in scene.state_delta.location_moves:
                days = move.arrival_day - move.depart_day
                moves.append({
                    "character": move.character,
                    "origin": move.origin,
                    "destination": move.destination,
                    "depart_day": float(move.depart_day),
                    "arrival_day": float(move.arrival_day),
                    "days": days,
                    "required_days": world.travel_days(move.origin, move.destination),
                })
                left[(move.character, move.origin)] = float(move.depart_day)
                arrived[(move.character, move.destination)] = float(move.arrival_day)
                here[move.character] = move.destination
        characters: list[dict[str, Any]] = []
        for cid in row["present"]:
            since_left = None
            if (cid, row["location"]) in left:
                since_left = row["day"] - left[(cid, row["location"])]
            since_arrival = None
            if (cid, row["location"]) in arrived:
                since_arrival = row["day"] - arrived[(cid, row["location"])]
            characters.append({
                "id": cid,
                "location_at_entry": entry.get(cid),
                "location_at_exit": here.get(cid),
                "days_since_leaving_here": since_left,
                "days_since_arriving_here": since_arrival,
            })
        chapters.append({
            "id": row["id"],
            "day": row["day"],
            "location": row["location"],
            "present": row["present"],
            "elapsed_since_previous": (None if previous is None
                                       else row["day"] - previous["day"]),
            "days_until_next": (None if following is None
                                else following["day"] - row["day"]),
            "characters": characters,
            "moves": moves,
        })
    return {
        "schema": TIMELINE_SCHEMA,
        "mode": "deterministic",
        "note": ("この表はゲームログと canon から導出した確定値。本文ではこの数字だけを使い、"
                 "計算し直さない。数字を書かない（抽象化する）のは自由。"),
        "travel_days": {f"{a}->{b}": days
                        for a in world.places()
                        for b, days in world.distances_from(a).items() if a != b},
        "chapters": chapters,
    }


def chapter_timeline(timeline: dict, chapter_id: str) -> dict | None:
    for row in timeline.get("chapters", []):
        if row.get("id") == chapter_id:
            return row
    return None


def _format_days(value: float | None) -> str:
    if value is None:
        return "—"
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def render_chapter_timeline(timeline: dict, chapter_id: str,
                            canon: Canon | None = None) -> str:
    """The compact, settled timeline handed to Stage B for one chapter."""
    row = chapter_timeline(timeline, chapter_id)
    if row is None:
        return "（この章の時系列は未導出）"
    names = {}
    if canon is not None:
        names = {cid: char.name for cid, char in canon.characters.items()}
    lines = [
        f"- この章の日: {_format_days(row['day'])}日目",
        f"- 場所: {row['location']}",
        f"- 前章からの経過: {_format_days(row['elapsed_since_previous'])}日",
        f"- 次章までの残り: {_format_days(row['days_until_next'])}日",
    ]
    for item in row["characters"]:
        label = names.get(item["id"], item["id"])
        lines.append(
            f"- {label}: この場所を離れてから {_format_days(item['days_since_leaving_here'])}日"
            f"／この場所に着いてから {_format_days(item['days_since_arriving_here'])}日")
    for move in row["moves"]:
        label = names.get(move["character"], move["character"])
        required = move["required_days"]
        lines.append(
            f"- 移動 {label}: {move['origin']} → {move['destination']} "
            f"{_format_days(move['depart_day'])}日目発 → {_format_days(move['arrival_day'])}日目着"
            f"（{_format_days(move['days'])}日"
            + ("" if required is None else f"／必要 {_format_days(required)}日") + "）")
    return "\n".join(lines)


__all__ = [
    "TIMELINE_SCHEMA", "World", "build_world", "derive_timeline",
    "chapter_timeline", "render_chapter_timeline",
]
