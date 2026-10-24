"""The relation-document schema: pairs, knowledge, changes, silences.

A relation file (``relations.yaml`` or ``relations.json``) designs the forces
between people. Characters are referenced by canon id; facts by canon fact
id; change events by chapter. Anything that cannot be tied to those anchors
is a wish, and wishes are reported.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RelationDocError(ValueError):
    """Raised when the relation file is missing or malformed."""


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    public: str
    stakes: str
    conflict: str = ""


@dataclass(frozen=True)
class KnowledgeEntry:
    character: str
    fact: str
    state: str  # knows | unknown | suspects


@dataclass(frozen=True)
class ChangeEvent:
    pair: tuple[str, str]
    chapter: str
    trigger: str
    after: str


@dataclass(frozen=True)
class Silence:
    chapter: str
    who: str
    unsaid_ja: str


@dataclass(frozen=True)
class RelationDoc:
    path: Path
    pairs: tuple[Pair, ...]
    knowledge: tuple[KnowledgeEntry, ...]
    changes: tuple[ChangeEvent, ...]
    silences: tuple[Silence, ...]
    notes: str = ""


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise RelationDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise RelationDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(value: Any) -> str:
    return str(value or "").strip()


def load_relations(path: str | Path) -> RelationDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("relations.yaml", "relations.yml", "relations.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise RelationDocError(f"no relation file in {path}")
    if not path.is_file():
        raise RelationDocError(f"relation file not found: {path}")
    data = _read_mapping(path)

    pairs: list[Pair] = []
    for row in data.get("pairs") or []:
        if not isinstance(row, dict) or not _str(row.get("a")) or not _str(row.get("b")):
            raise RelationDocError(
                f"{path.name}: each 'pairs' entry needs a and b")
        pairs.append(Pair(a=_str(row.get("a")), b=_str(row.get("b")),
                          public=_str(row.get("public")),
                          stakes=_str(row.get("stakes")),
                          conflict=_str(row.get("conflict"))))

    knowledge: list[KnowledgeEntry] = []
    for row in data.get("knowledge") or []:
        if not isinstance(row, dict):
            raise RelationDocError(
                f"{path.name}: entries of 'knowledge' must be mappings")
        knowledge.append(KnowledgeEntry(
            character=_str(row.get("character")), fact=_str(row.get("fact")),
            state=_str(row.get("state")) or "unknown"))

    changes: list[ChangeEvent] = []
    for row in data.get("changes") or []:
        if not isinstance(row, dict):
            raise RelationDocError(
                f"{path.name}: entries of 'changes' must be mappings")
        pair = row.get("pair") or []
        if not isinstance(pair, list) or len(pair) != 2:
            raise RelationDocError(
                f"{path.name}: each change needs a two-person 'pair'")
        changes.append(ChangeEvent(
            pair=(_str(pair[0]), _str(pair[1])),
            chapter=_str(row.get("chapter")),
            trigger=_str(row.get("trigger")), after=_str(row.get("after"))))

    silences = tuple(
        Silence(chapter=_str(r.get("chapter")), who=_str(r.get("who")),
                unsaid_ja=_str(r.get("unsaid_ja")))
        for r in (data.get("silences") or []) if isinstance(r, dict))

    return RelationDoc(path=path, pairs=tuple(pairs),
                       knowledge=tuple(knowledge), changes=tuple(changes),
                       silences=silences,
                       notes=_str(data.get("notes")))
