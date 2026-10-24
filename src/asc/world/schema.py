"""The world schema: axioms, rules with costs, institutions, geography.

A world file (``world.yaml`` or ``world.json``) is written before drafting
and read by the drafters. Costs are mandatory: a rule without a cost is a
wish, and wishes break stories exactly when they are most needed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorldError(ValueError):
    """Raised when the world file is missing or malformed."""


@dataclass(frozen=True)
class Rule:
    id: str
    statement: str
    cost: str
    constraint: str = ""
    exception: str = ""
    exception_condition: str = ""


@dataclass(frozen=True)
class Institution:
    name: str
    role: str


@dataclass(frozen=True)
class Disclosure:
    info: str
    chapter: str


@dataclass(frozen=True)
class World:
    path: Path
    axioms: tuple[str, ...]
    rules: tuple[Rule, ...]
    institutions: tuple[Institution, ...]
    geography: tuple[str, ...]
    disclosure: tuple[Disclosure, ...]
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "axioms": list(self.axioms),
            "rules": [r.__dict__ for r in self.rules],
            "institutions": [i.__dict__ for i in self.institutions],
            "geography": list(self.geography),
            "disclosure": [d.__dict__ for d in self.disclosure],
        }


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise WorldError(f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise WorldError(f"{path.name}: the top level must be a mapping")
    return data


def load_world(path: str | Path) -> World:
    path = Path(path)
    if path.is_dir():
        for name in ("world.yaml", "world.yml", "world.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise WorldError(f"no world file in {path}")
    if not path.is_file():
        raise WorldError(f"world file not found: {path}")
    data = _read_mapping(path)

    axioms = tuple(str(a).strip() for a in (data.get("axioms") or []) if str(a).strip())
    rules: list[Rule] = []
    for row in data.get("rules") or []:
        if not isinstance(row, dict) or not str(row.get("id", "")).strip():
            raise WorldError(f"{path.name}: each 'rules' entry needs an id")
        rules.append(Rule(
            id=str(row["id"]).strip(),
            statement=str(row.get("statement", "") or "").strip(),
            cost=str(row.get("cost", "") or "").strip(),
            constraint=str(row.get("constraint", "") or "").strip(),
            exception=str(row.get("exception", "") or "").strip(),
            exception_condition=str(row.get("exception_condition", "") or "").strip(),
        ))
    institutions = tuple(
        Institution(name=str(r.get("name", "") or "").strip(),
                    role=str(r.get("role", "") or "").strip())
        for r in (data.get("institutions") or []) if isinstance(r, dict))
    geography = tuple(str(g).strip() for g in (data.get("geography") or [])
                      if str(g).strip())
    disclosure = tuple(
        Disclosure(info=str(r.get("info", "") or "").strip(),
                   chapter=str(r.get("chapter", "") or "").strip())
        for r in (data.get("disclosure") or []) if isinstance(r, dict))
    return World(path=path, axioms=axioms, rules=tuple(rules),
                 institutions=institutions, geography=geography,
                 disclosure=disclosure,
                 notes=str(data.get("notes", "") or "").strip())
