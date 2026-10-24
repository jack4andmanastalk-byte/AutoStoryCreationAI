"""The scene-document schema: jobs, tension, knowledge, disclosure.

A scene file (``scenes.yaml`` or ``scenes.json``) designs the information
flow of a work, scene by scene. Chapters, facts, characters and foreshadowing
are anchored to the canon; the checker reports anything dangling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SceneDocError(ValueError):
    """Raised when the scene file is missing or malformed."""


@dataclass(frozen=True)
class KnowledgeFlow:
    character: str
    entry: tuple[str, ...]
    gained: tuple[str, ...]


@dataclass(frozen=True)
class Withheld:
    fact: str
    reason: str


@dataclass(frozen=True)
class Planted:
    id: str
    payoff: str


@dataclass(frozen=True)
class Scene:
    id: str
    chapter: str
    purpose: str
    conflict: str
    change: str
    tension: str
    knowledge: tuple[KnowledgeFlow, ...]
    disclosed: tuple[str, ...]
    withheld: tuple[Withheld, ...]
    planted: tuple[Planted, ...]
    paid: tuple[str, ...]


@dataclass(frozen=True)
class SceneDoc:
    path: Path
    scenes: tuple[Scene, ...]
    notes: str = ""


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise SceneDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SceneDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(value: Any) -> str:
    return str(value or "").strip()


def _strs(value: Any) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (value or []) if str(v).strip())


def load_scenes(path: str | Path) -> SceneDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("scenes.yaml", "scenes.yml", "scenes.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise SceneDocError(f"no scene file in {path}")
    if not path.is_file():
        raise SceneDocError(f"scene file not found: {path}")
    data = _read_mapping(path)

    scenes: list[Scene] = []
    for row in data.get("scenes") or []:
        if not isinstance(row, dict) or not _str(row.get("id")):
            raise SceneDocError(
                f"{path.name}: each 'scenes' entry needs an id")
        knowledge = tuple(
            KnowledgeFlow(character=_str(k.get("character")),
                          entry=_strs(k.get("entry")),
                          gained=_strs(k.get("gained")))
            for k in (row.get("knowledge") or []) if isinstance(k, dict))
        disclosure = row.get("disclosure") or {}
        if not isinstance(disclosure, dict):
            raise SceneDocError(
                f"{path.name}: scenes:{row['id']} 'disclosure' must be a mapping")
        withheld = tuple(
            Withheld(fact=_str(w.get("fact")), reason=_str(w.get("reason")))
            for w in (disclosure.get("withheld") or [])
            if isinstance(w, dict))
        foreshadows = row.get("foreshadows") or {}
        if not isinstance(foreshadows, dict):
            raise SceneDocError(
                f"{path.name}: scenes:{row['id']} 'foreshadows' must be a mapping")
        planted = tuple(
            Planted(id=_str(p.get("id")), payoff=_str(p.get("payoff")))
            for p in (foreshadows.get("planted") or [])
            if isinstance(p, dict))
        scenes.append(Scene(
            id=_str(row.get("id")), chapter=_str(row.get("chapter")),
            purpose=_str(row.get("purpose")),
            conflict=_str(_str(row.get("conflict"))),
            change=_str(row.get("change")),
            tension=_str(row.get("tension")) or "quiet",
            knowledge=knowledge,
            disclosed=_strs(disclosure.get("disclosed")),
            withheld=withheld, planted=planted,
            paid=_strs(foreshadows.get("paid"))))
    return SceneDoc(path=path, scenes=tuple(scenes),
                    notes=_str(data.get("notes")))
