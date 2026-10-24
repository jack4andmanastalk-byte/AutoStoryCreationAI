"""The branch-document schema: nodes, edges, flags.

A branch file (``branches.yaml`` or ``branches.json``) designs a branching
structure. Nodes are scenes, choices or endings; edges carry the traversal
conditions (``requires``), the flag updates (``sets``) and, for edges leaving
a choice, the option taken (``via``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BranchDocError(ValueError):
    """Raised when the branch file is missing or malformed."""


@dataclass(frozen=True)
class Flag:
    id: str
    meaning: str


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Node:
    id: str
    kind: str  # scene | choice | ending
    summary: str
    options: tuple[Option, ...]
    ending: str
    merge_note: str


@dataclass(frozen=True)
class Edge:
    index: int
    from_id: str
    to_id: str
    via: str
    requires: tuple[str, ...]
    sets: tuple[str, ...]


@dataclass(frozen=True)
class BranchDoc:
    path: Path
    start: str
    initial: tuple[str, ...]
    flags: tuple[Flag, ...]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    notes: str = ""


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise BranchDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise BranchDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(value: Any) -> str:
    return str(value or "").strip()


def _strs(value: Any) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (value or []) if str(v).strip())


def load_branches(path: str | Path) -> BranchDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("branches.yaml", "branches.yml", "branches.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise BranchDocError(f"no branch file in {path}")
    if not path.is_file():
        raise BranchDocError(f"branch file not found: {path}")
    data = _read_mapping(path)

    flags = tuple(
        Flag(id=_str(f.get("id")), meaning=_str(f.get("meaning")))
        for f in (data.get("flags") or []) if isinstance(f, dict))
    nodes: list[Node] = []
    for row in data.get("nodes") or []:
        if not isinstance(row, dict) or not _str(row.get("id")):
            raise BranchDocError(
                f"{path.name}: each 'nodes' entry needs an id")
        options = tuple(
            Option(id=_str(o.get("id")), label=_str(o.get("label")),
                   requires=_strs(o.get("requires")))
            for o in (row.get("options") or []) if isinstance(o, dict))
        nodes.append(Node(
            id=_str(row.get("id")), kind=_str(row.get("kind")) or "scene",
            summary=_str(row.get("summary")), options=options,
            ending=_str(row.get("ending")),
            merge_note=_str(row.get("merge_note"))))
    edges = tuple(
        Edge(index=i, from_id=_str(e.get("from")), to_id=_str(e.get("to")),
             via=_str(e.get("via")), requires=_strs(e.get("requires")),
             sets=_strs(e.get("sets")))
        for i, e in enumerate(data.get("edges") or [], start=1)
        if isinstance(e, dict))
    return BranchDoc(path=path, start=_str(data.get("start")),
                     initial=_strs(data.get("initial")), flags=flags,
                     nodes=tuple(nodes), edges=edges,
                     notes=_str(data.get("notes")))
