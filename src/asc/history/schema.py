"""The history schema: eras, events, sources, canon split, knowledge.

A history file (``history.yaml`` or ``history.json``) explains the present
state of the world. Real-world research notes and invented events must live
in different entries: ``origin: cited`` entries need a citation, and invented
events must never borrow the authority of a real source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_ORIGINS = {"invented", "adapted", "cited"}


class HistoryError(ValueError):
    """Raised when the history file is missing or malformed."""


@dataclass(frozen=True)
class Era:
    id: str
    name: str
    begins: int | None = None
    ends: int | None = None


@dataclass(frozen=True)
class Event:
    id: str
    year: int
    title: str
    cause: str = ""
    effect: str = ""
    trace: str = ""
    era: str = ""


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    holder: str
    origin: str
    citation: str = ""


@dataclass(frozen=True)
class History:
    path: Path
    eras: tuple[Era, ...]
    events: tuple[Event, ...]
    sources: tuple[Source, ...]
    apocrypha: tuple[str, ...]
    knowledge: dict[str, dict[str, tuple[str, ...]]]
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "eras": [e.__dict__ for e in self.eras],
            "events": [e.__dict__ for e in self.events],
            "sources": [s.__dict__ for s in self.sources],
            "apocrypha": list(self.apocrypha),
            "knowledge": {k: {kk: list(vv) for kk, vv in v.items()}
                          for k, v in self.knowledge.items()},
        }


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise HistoryError(f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise HistoryError(f"{path.name}: the top level must be a mapping")
    return data


def _as_int(value: Any, what: str, path: Path) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoryError(f"{path.name}: {what} must be an integer year")
    return value


def load_history(path: str | Path) -> History:
    path = Path(path)
    if path.is_dir():
        for name in ("history.yaml", "history.yml", "history.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise HistoryError(f"no history file in {path}")
    if not path.is_file():
        raise HistoryError(f"history file not found: {path}")
    data = _read_mapping(path)

    eras: list[Era] = []
    for row in data.get("eras") or []:
        if not isinstance(row, dict) or not str(row.get("id", "")).strip():
            raise HistoryError(f"{path.name}: each 'eras' entry needs an id")
        eras.append(Era(
            id=str(row["id"]).strip(), name=str(row.get("name", "") or "").strip(),
            begins=_as_int(row.get("begins"), f"era {row['id']} begins", path),
            ends=_as_int(row.get("ends"), f"era {row['id']} ends", path)))

    events: list[Event] = []
    for row in data.get("events") or []:
        if not isinstance(row, dict) or not str(row.get("id", "")).strip():
            raise HistoryError(f"{path.name}: each 'events' entry needs an id")
        year = _as_int(row.get("year"), f"event {row['id']} year", path)
        if year is None:
            raise HistoryError(f"{path.name}: event {row['id']} needs a year")
        events.append(Event(
            id=str(row["id"]).strip(), year=year,
            title=str(row.get("title", "") or "").strip(),
            cause=str(row.get("cause", "") or "").strip(),
            effect=str(row.get("effect", "") or "").strip(),
            trace=str(row.get("trace", "") or "").strip(),
            era=str(row.get("era", "") or "").strip()))

    sources: list[Source] = []
    for row in data.get("sources") or []:
        if not isinstance(row, dict) or not str(row.get("id", "")).strip():
            raise HistoryError(f"{path.name}: each 'sources' entry needs an id")
        sources.append(Source(
            id=str(row["id"]).strip(),
            kind=str(row.get("kind", "") or "").strip(),
            holder=str(row.get("holder", "") or "").strip(),
            origin=str(row.get("origin", "") or "").strip(),
            citation=str(row.get("citation", "") or "").strip()))

    apocrypha = tuple(str(a).strip() for a in (data.get("apocrypha") or [])
                      if str(a).strip())
    knowledge: dict[str, dict[str, tuple[str, ...]]] = {}
    raw_knowledge = data.get("knowledge") or {}
    if not isinstance(raw_knowledge, dict):
        raise HistoryError(f"{path.name}: 'knowledge' must be a mapping")
    for character, entry in raw_knowledge.items():
        if not isinstance(entry, dict):
            raise HistoryError(f"{path.name}: knowledge[{character}] must be a mapping")
        knowledge[str(character)] = {
            "knows": tuple(str(e).strip() for e in (entry.get("knows") or [])),
            "unknown": tuple(str(e).strip() for e in (entry.get("unknown") or [])),
        }
    return History(path=path, eras=tuple(eras), events=tuple(events),
                   sources=tuple(sources), apocrypha=apocrypha,
                   knowledge=knowledge,
                   notes=str(data.get("notes", "") or "").strip())
