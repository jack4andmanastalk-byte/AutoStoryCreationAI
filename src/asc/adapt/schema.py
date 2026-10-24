"""The adaptation-document schema: functions, mappings, deletions.

An adaptation file (``adaptation.yaml`` or ``adaptation.json``) designs how a
source work's functions are translated to another medium. Everything is
anchored to the function ids declared in the same file; the checker reports
anything dangling, unassigned or rights-unlogged.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AdaptationDocError(ValueError):
    """Raised when the adaptation file is missing or malformed."""


@dataclass(frozen=True)
class Function:
    id: str
    kind: str  # info | emotion | relation | tempo
    description: str


@dataclass(frozen=True)
class Mapping:
    function: str
    means: str
    newcomer: str
    existing: str


@dataclass(frozen=True)
class Deletion:
    function: str
    reason: str
    substitute: str


@dataclass(frozen=True)
class Rights:
    source: str
    scope: str
    status: str  # cleared | pending | na


@dataclass(frozen=True)
class AdaptationDoc:
    path: Path
    source_title: str
    target_medium: str
    functions: tuple[Function, ...]
    mappings: tuple[Mapping, ...]
    deletions: tuple[Deletion, ...]
    rights: Rights
    notes: str = ""


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise AdaptationDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise AdaptationDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(value: Any) -> str:
    return str(value or "").strip()


def load_adaptation(path: str | Path) -> AdaptationDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("adaptation.yaml", "adaptation.yml", "adaptation.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise AdaptationDocError(f"no adaptation file in {path}")
    if not path.is_file():
        raise AdaptationDocError(f"adaptation file not found: {path}")
    data = _read_mapping(path)

    functions = tuple(
        Function(id=_str(f.get("id")), kind=_str(f.get("kind")),
                 description=_str(f.get("description")))
        for f in (data.get("functions") or []) if isinstance(f, dict))
    mappings = tuple(
        Mapping(function=_str(m.get("function")), means=_str(m.get("means")),
                newcomer=_str(m.get("newcomer")),
                existing=_str(m.get("existing")))
        for m in (data.get("mappings") or []) if isinstance(m, dict))
    deletions = tuple(
        Deletion(function=_str(d.get("function")),
                 reason=_str(d.get("reason")),
                 substitute=_str(d.get("substitute")))
        for d in (data.get("deletions") or []) if isinstance(d, dict))
    rights_raw = data.get("rights") or {}
    if not isinstance(rights_raw, dict):
        raise AdaptationDocError(f"{path.name}: 'rights' must be a mapping")
    rights = Rights(source=_str(rights_raw.get("source")),
                    scope=_str(rights_raw.get("scope")),
                    status=_str(rights_raw.get("status")) or "pending")
    return AdaptationDoc(path=path,
                         source_title=_str(data.get("source_title")),
                         target_medium=_str(data.get("target_medium")),
                         functions=functions, mappings=mappings,
                         deletions=deletions, rights=rights,
                         notes=_str(data.get("notes")))
