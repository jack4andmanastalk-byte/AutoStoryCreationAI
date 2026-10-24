"""The character-document schema: cores, views, voice, arcs.

A character file (``characters.yaml`` or ``characters.json``) designs the
people of a work. It is *not* the canon: the canon records state (alive,
location, known facts) while this document records the model behind the
choices (WANT/NEED, fears, principles, voice, arc). The two are cross-checked
by id.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CharacterDocError(ValueError):
    """Raised when the character file is missing or malformed."""


@dataclass(frozen=True)
class Prediction:
    situation: str
    choice: str


@dataclass(frozen=True)
class Speech:
    sample: str
    vocab: tuple[str, ...]
    avoid: tuple[str, ...]


@dataclass(frozen=True)
class Arc:
    endpoint: str
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]


@dataclass(frozen=True)
class Character:
    id: str
    want: str
    need: str
    fear: str
    wound: str
    secret: str
    principle: str
    self_view: str
    others_view: tuple[str, ...]
    predictions: tuple[Prediction, ...]
    speech: Speech
    arc: Arc
    bans: tuple[str, ...]


@dataclass(frozen=True)
class CharacterDoc:
    path: Path
    characters: tuple[Character, ...]
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "characters": [
                {"id": c.id, "want": c.want, "need": c.need,
                 "predictions": len(c.predictions)} for c in self.characters],
        }


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise CharacterDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise CharacterDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(row: dict, key: str) -> str:
    return str(row.get(key, "") or "").strip()


def _strs(row: dict, key: str) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (row.get(key) or []) if str(v).strip())


def load_characters(path: str | Path) -> CharacterDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("characters.yaml", "characters.yml", "characters.json",
                     "character-cores.yaml", "character-cores.yml",
                     "character-cores.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise CharacterDocError(f"no character file in {path}")
    if not path.is_file():
        raise CharacterDocError(f"character file not found: {path}")
    data = _read_mapping(path)

    characters: list[Character] = []
    for row in data.get("characters") or []:
        if not isinstance(row, dict) or not _str(row, "id"):
            raise CharacterDocError(
                f"{path.name}: each 'characters' entry needs an id")
        speech = row.get("speech") or {}
        if not isinstance(speech, dict):
            raise CharacterDocError(
                f"{path.name}: characters:{row['id']} 'speech' must be a mapping")
        arc = row.get("arc") or {}
        if not isinstance(arc, dict):
            raise CharacterDocError(
                f"{path.name}: characters:{row['id']} 'arc' must be a mapping")
        predictions = tuple(
            Prediction(situation=_str(p, "situation"), choice=_str(p, "choice"))
            for p in (row.get("predictions") or []) if isinstance(p, dict))
        characters.append(Character(
            id=_str(row, "id"), want=_str(row, "want"), need=_str(row, "need"),
            fear=_str(row, "fear"), wound=_str(row, "wound"),
            secret=_str(row, "secret"), principle=_str(row, "principle"),
            self_view=_str(row, "self_view"),
            others_view=_strs(row, "others_view"),
            predictions=predictions,
            speech=Speech(sample=_str(speech, "sample"),
                          vocab=_strs(speech, "vocab"),
                          avoid=_strs(speech, "avoid")),
            arc=Arc(endpoint=_str(arc, "endpoint"),
                    changed=_strs(arc, "changed"),
                    unchanged=_strs(arc, "unchanged")),
            bans=_strs(row, "bans"),
        ))
    return CharacterDoc(path=path, characters=tuple(characters),
                        notes=str(data.get("notes", "") or "").strip())
