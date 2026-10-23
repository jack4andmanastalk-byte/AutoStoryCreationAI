"""The brief schema: what a plan must declare before drafting.

A brief is a single file (``brief.yaml`` or ``brief.json``). Every field is
human-written; the checker (:mod:`asc.brief.check`) only verifies that the
fields are present, well-formed and mutually consistent. It never judges
whether the premise is interesting.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SIMILAR_AXES = {"structure", "character", "world"}
ELEMENT_KEYS = ("who", "where", "wants", "obstacle")


class BriefError(ValueError):
    """Raised when the brief file is missing, malformed or incomplete."""


@dataclass(frozen=True)
class SimilarWork:
    title: str
    axis: str
    difference: str


@dataclass(frozen=True)
class Prohibition:
    rule: str
    check_ja: str


@dataclass(frozen=True)
class Brief:
    path: Path
    logline: str
    elements: dict[str, str]
    premise: str
    theme: str
    similar: tuple[SimilarWork, ...] = ()
    prohibitions: tuple[Prohibition, ...] = ()
    failure_questions: tuple[str, ...] = ()
    genre: str = ""
    audience: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "logline": self.logline,
            "elements": dict(self.elements),
            "premise": self.premise,
            "theme": self.theme,
            "similar": [s.__dict__ for s in self.similar],
            "prohibitions": [p.__dict__ for p in self.prohibitions],
            "failure_questions": list(self.failure_questions),
            "genre": self.genre,
            "audience": self.audience,
        }


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise BriefError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise BriefError(f"{path.name}: the top level must be a mapping")
    return data


def _need_str(data: dict, key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BriefError(f"{path.name}: '{key}' must be a non-empty string")
    return value.strip()


def load_brief(path: str | Path) -> Brief:
    """Load and validate a brief file. Structural errors raise BriefError."""
    path = Path(path)
    if path.is_dir():
        for name in ("brief.yaml", "brief.yml", "brief.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise BriefError(f"no brief file in {path}")
    if not path.is_file():
        raise BriefError(f"brief file not found: {path}")
    data = _read_mapping(path)

    logline = _need_str(data, "logline", path)
    premise = _need_str(data, "premise", path)
    theme = _need_str(data, "theme", path)

    raw_elements = data.get("elements") or {}
    if not isinstance(raw_elements, dict):
        raise BriefError(f"{path.name}: 'elements' must be a mapping")
    elements = {k: str(raw_elements.get(k, "") or "").strip() for k in ELEMENT_KEYS}

    similar: list[SimilarWork] = []
    for row in data.get("similar") or []:
        if not isinstance(row, dict):
            raise BriefError(f"{path.name}: entries of 'similar' must be mappings")
        similar.append(SimilarWork(
            title=str(row.get("title", "") or "").strip(),
            axis=str(row.get("axis", "") or "").strip(),
            difference=str(row.get("difference", "") or "").strip(),
        ))

    prohibitions: list[Prohibition] = []
    for row in data.get("prohibitions") or []:
        if not isinstance(row, dict):
            raise BriefError(f"{path.name}: entries of 'prohibitions' must be mappings")
        prohibitions.append(Prohibition(
            rule=str(row.get("rule", "") or "").strip(),
            check_ja=str(row.get("check_ja", "") or "").strip(),
        ))

    questions = data.get("failure_questions") or []
    if not isinstance(questions, list) or any(not isinstance(q, str) for q in questions):
        raise BriefError(f"{path.name}: 'failure_questions' must be a list of strings")

    return Brief(
        path=path, logline=logline, elements=elements, premise=premise, theme=theme,
        similar=tuple(similar), prohibitions=tuple(prohibitions),
        failure_questions=tuple(q.strip() for q in questions),
        genre=str(data.get("genre", "") or "").strip(),
        audience=str(data.get("audience", "") or "").strip(),
        notes=str(data.get("notes", "") or "").strip(),
    )
