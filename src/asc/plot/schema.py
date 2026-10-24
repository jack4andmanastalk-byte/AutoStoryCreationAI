"""The plot-document schema: acts, turns, plots, ending, unresolved.

A plot file (``plot.yaml`` or ``plot.json``) designs the load-bearing walls of
a work. Chapters, foreshadowing ids and characters are anchored to the canon;
the checker reports anything dangling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PlotDocError(ValueError):
    """Raised when the plot file is missing or malformed."""


@dataclass(frozen=True)
class Act:
    id: str
    chapters: tuple[str, ...]
    question: str = ""


@dataclass(frozen=True)
class Turn:
    id: str
    chapter: str
    choice_ja: str
    point_of_no_return: str = ""


@dataclass(frozen=True)
class Subplot:
    id: str
    beats: tuple[str, ...]
    converges: str = ""


@dataclass(frozen=True)
class Ending:
    kind: str  # resolved | bittersweet | open
    summary: str
    aftertaste_ja: str = ""


@dataclass(frozen=True)
class Unresolved:
    item: str
    foreshadowing: str = ""
    intentional: bool = False


@dataclass(frozen=True)
class PlotDoc:
    path: Path
    logline: str
    acts: tuple[Act, ...]
    turns: tuple[Turn, ...]
    subplots: tuple[Subplot, ...]
    ending: Ending
    unresolved: tuple[Unresolved, ...]
    notes: str = ""


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise PlotDocError(
                f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise PlotDocError(f"{path.name}: the top level must be a mapping")
    return data


def _str(value: Any) -> str:
    return str(value or "").strip()


def _strs(value: Any) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (value or []) if str(v).strip())


def load_plot(path: str | Path) -> PlotDoc:
    path = Path(path)
    if path.is_dir():
        for name in ("plot.yaml", "plot.yml", "plot.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise PlotDocError(f"no plot file in {path}")
    if not path.is_file():
        raise PlotDocError(f"plot file not found: {path}")
    data = _read_mapping(path)

    acts = tuple(
        Act(id=_str(r.get("id")), chapters=_strs(r.get("chapters")),
            question=_str(r.get("question")))
        for r in (data.get("acts") or []) if isinstance(r, dict))
    turns = tuple(
        Turn(id=_str(r.get("id")), chapter=_str(r.get("chapter")),
             choice_ja=_str(r.get("choice_ja")),
             point_of_no_return=_str(r.get("point_of_no_return")))
        for r in (data.get("turns") or []) if isinstance(r, dict))
    subplots = tuple(
        Subplot(id=_str(r.get("id")), beats=_strs(r.get("beats")),
                converges=_str(r.get("converges")))
        for r in (data.get("subplots") or []) if isinstance(r, dict))
    ending_raw = data.get("ending") or {}
    if not isinstance(ending_raw, dict):
        raise PlotDocError(f"{path.name}: 'ending' must be a mapping")
    ending = Ending(kind=_str(ending_raw.get("kind")),
                    summary=_str(ending_raw.get("summary")),
                    aftertaste_ja=_str(ending_raw.get("aftertaste_ja")))
    unresolved = tuple(
        Unresolved(item=_str(r.get("item")),
                   foreshadowing=_str(r.get("foreshadowing")),
                   intentional=bool(r.get("intentional")))
        for r in (data.get("unresolved") or []) if isinstance(r, dict))
    return PlotDoc(path=path, logline=_str(data.get("logline")), acts=acts,
                   turns=turns, subplots=subplots, ending=ending,
                   unresolved=unresolved, notes=_str(data.get("notes")))
