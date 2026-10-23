"""Rubric loading and validation.

A rubric is a YAML file with dimensions, a question per dimension and anchors
that describe what the extremes look like. It deliberately has **no total
score**: the evaluation reports a profile, because a single number hides which
dimension regressed.

    id: story-quality-v0
    version: "0.1"
    scale: {min: 1, max: 5}
    dimensions:
      - id: coherence
        question_ja: 出来事の因果と時系列が、本文の情報だけで説明できるか。
        anchors: {5: "...", 3: "...", 1: "..."}
        evidence_required: true
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class RubricError(ValueError):
    pass


@dataclass(frozen=True)
class Dimension:
    id: str
    question_ja: str
    anchors: dict[int, str] = field(default_factory=dict)
    evidence_required: bool = True
    owner_skill: str | None = None


@dataclass
class Rubric:
    id: str
    version: str
    scale_min: int
    scale_max: int
    dimensions: list[Dimension]
    path: Path | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "scale": {"min": self.scale_min, "max": self.scale_max},
            "dimensions": [
                {"id": d.id, "question_ja": d.question_ja, "anchors": d.anchors,
                 "evidence_required": d.evidence_required, "owner_skill": d.owner_skill}
                for d in self.dimensions
            ],
        }

    @property
    def dimension_ids(self) -> list[str]:
        return [d.id for d in self.dimensions]


def load_rubric(path: str | Path) -> Rubric:
    path = Path(path)
    if not path.is_file():
        raise RubricError(f"rubric not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RubricError("loading a YAML rubric requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise RubricError(f"{path.name}: the top level must be a mapping")

    scale = data.get("scale") or {}
    low, high = int(scale.get("min", 1)), int(scale.get("max", 5))
    if low >= high:
        raise RubricError(f"{path.name}: scale.min must be < scale.max")

    dimensions: list[Dimension] = []
    for row in data.get("dimensions") or []:
        if not isinstance(row, dict) or not row.get("id"):
            raise RubricError(f"{path.name}: every dimension needs an 'id'")
        anchors = {int(k): str(v) for k, v in (row.get("anchors") or {}).items()}
        for score in anchors:
            if not low <= score <= high:
                raise RubricError(f"{path.name}: anchor {score} outside the scale")
        dimensions.append(Dimension(
            id=str(row["id"]),
            question_ja=str(row.get("question_ja") or row.get("question") or ""),
            anchors=anchors,
            evidence_required=bool(row.get("evidence_required", True)),
            owner_skill=row.get("owner_skill"),
        ))
    if not dimensions:
        raise RubricError(f"{path.name}: no dimensions")
    ids = [d.id for d in dimensions]
    if len(ids) != len(set(ids)):
        raise RubricError(f"{path.name}: duplicate dimension ids")
    return Rubric(id=str(data.get("id") or path.stem), version=str(data.get("version") or "0"),
                  scale_min=low, scale_max=high, dimensions=dimensions, path=path)
