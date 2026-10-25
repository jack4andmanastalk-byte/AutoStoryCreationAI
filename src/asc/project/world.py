"""Versioned reference records for a project's persistent world model.

The work containment tree and this world reference graph are deliberately
separate.  Time spans, regions, culture states, canon, and work bindings use
stable IDs; none of them implicitly becomes a parent of a work or culture.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from .model import ArtifactRef
from .schema import (
    SCHEMA_VERSION,
    ProjectValidationError,
    canonical_json,
    validate_id,
)

TIMESPAN_PRECISIONS = {"exact", "approximate", "range", "unknown"}
CULTURE_RELATION_KINDS = {"inheritance", "split", "contact"}
CANON_SCOPE_KINDS = {"global", "timeframe", "region", "culture", "work", "node"}
VERSIONED_RECORDS = {"culture_state", "world_canon_entry", "work_world_binding"}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectValidationError(f"{field} must be a JSON object")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{field} must be a non-empty string")
    return value


def _header(data: Any, record_type: str) -> dict[str, Any]:
    data = _mapping(data, record_type)
    if data.get("record_type") != record_type:
        raise ProjectValidationError(f"record_type must be {record_type!r}")
    if data.get("schema_version") != SCHEMA_VERSION or isinstance(
        data.get("schema_version"), bool
    ):
        raise ProjectValidationError(f"unsupported {record_type} schema_version")
    validate_id(data.get("id"), f"{record_type}.id")
    validate_id(data.get("project_id"), f"{record_type}.project_id")
    return data


def _timestamp(value: Any, field: str = "created_at") -> str:
    value = _nonempty(value, field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        qualifier = "positive " if positive else ""
        raise ProjectValidationError(f"{field} must be a finite {qualifier}number")
    return value


def _optional_id(value: Any, field: str) -> str | None:
    return None if value is None else validate_id(value, field)


def _id_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ProjectValidationError(f"{field} must be a list")
    result = tuple(validate_id(item, field) for item in value)
    if len(result) != len(set(result)):
        raise ProjectValidationError(f"{field} contains a duplicate ID")
    return result


def record_version(data: dict[str, Any]) -> str:
    """Hash immutable world content, excluding bookkeeping time and the hash itself."""
    payload = {
        key: value for key, value in data.items()
        if key not in {"created_at", "content_version"}
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _check_version(data: dict[str, Any]) -> None:
    version = data.get("content_version")
    if not isinstance(version, str) or len(version) != 64:
        raise ProjectValidationError("content_version must be a SHA-256 hash")
    if version != record_version(data):
        raise ProjectValidationError("content_version does not match the world record")


def _base_dict(record_type: str, item: Any) -> dict[str, Any]:
    return {
        "record_type": record_type,
        "schema_version": SCHEMA_VERSION,
        "id": item.id,
        "project_id": item.project_id,
        "created_at": item.created_at,
    }


@dataclass(frozen=True)
class TimeFrame:
    id: str
    project_id: str
    name: str
    calendar: str
    epoch: str
    created_at: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("time_frame", self),
            "name": self.name,
            "calendar": self.calendar,
            "epoch": self.epoch,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeFrame":
        data = _header(data, "time_frame")
        return cls(
            id=data["id"], project_id=data["project_id"],
            name=_nonempty(data.get("name"), "time_frame.name"),
            calendar=_nonempty(data.get("calendar"), "time_frame.calendar"),
            epoch=_nonempty(data.get("epoch"), "time_frame.epoch"),
            description=str(data.get("description") or ""),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class TimeSpan:
    """A coordinate in one timeframe, or an explicitly unknown date.

    ``before_span_ids`` records relative order independently of coordinates or
    conversions.  Unknown spans can therefore participate in a chronology
    without being assigned a fabricated absolute date.
    """

    id: str
    project_id: str
    timeframe_id: str | None
    precision: str
    start: int | float | None
    end: int | float | None
    created_at: str
    label: str = ""
    before_span_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("time_span", self),
            "timeframe_id": self.timeframe_id,
            "precision": self.precision,
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "before_span_ids": list(self.before_span_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeSpan":
        data = _header(data, "time_span")
        precision = data.get("precision")
        if precision not in TIMESPAN_PRECISIONS:
            raise ProjectValidationError(f"unknown time_span.precision: {precision!r}")
        timeframe_id = _optional_id(data.get("timeframe_id"), "time_span.timeframe_id")
        start = data.get("start")
        end = data.get("end")
        if start is not None:
            _number(start, "time_span.start")
        if end is not None:
            _number(end, "time_span.end")
        if precision == "unknown":
            if start is not None or end is not None:
                raise ProjectValidationError("unknown time_span cannot have coordinates")
        else:
            if timeframe_id is None or start is None:
                raise ProjectValidationError("dated time_span requires timeframe_id and start")
            if precision == "exact" and end != start:
                raise ProjectValidationError("exact time_span requires end == start")
            if precision == "range" and end is None:
                raise ProjectValidationError("range time_span requires an end")
        if start is not None and end is not None and end < start:
            raise ProjectValidationError("time_span.end cannot precede start")
        return cls(
            id=data["id"], project_id=data["project_id"], timeframe_id=timeframe_id,
            precision=precision, start=start, end=end,
            label=str(data.get("label") or ""),
            before_span_ids=_id_tuple(
                data.get("before_span_ids", []), "time_span.before_span_ids",
            ),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class TimeConversion:
    """An explicit order-preserving affine conversion between two timeframes."""

    id: str
    project_id: str
    source_timeframe_id: str
    target_timeframe_id: str
    scale: int | float
    offset: int | float
    created_at: str

    def convert(self, value: int | float) -> float:
        _number(value, "conversion input")
        return float(value) * float(self.scale) + float(self.offset)

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("time_conversion", self),
            "source_timeframe_id": self.source_timeframe_id,
            "target_timeframe_id": self.target_timeframe_id,
            "scale": self.scale,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeConversion":
        data = _header(data, "time_conversion")
        source = validate_id(data.get("source_timeframe_id"), "source_timeframe_id")
        target = validate_id(data.get("target_timeframe_id"), "target_timeframe_id")
        if source == target:
            raise ProjectValidationError("time conversion endpoints must differ")
        return cls(
            id=data["id"], project_id=data["project_id"],
            source_timeframe_id=source, target_timeframe_id=target,
            scale=_number(data.get("scale"), "time_conversion.scale", positive=True),
            offset=_number(data.get("offset"), "time_conversion.offset"),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class Region:
    id: str
    project_id: str
    name: str
    parent_region_id: str | None
    valid_span_id: str | None
    created_at: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("region", self),
            "name": self.name,
            "parent_region_id": self.parent_region_id,
            "valid_span_id": self.valid_span_id,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Region":
        data = _header(data, "region")
        return cls(
            id=data["id"], project_id=data["project_id"],
            name=_nonempty(data.get("name"), "region.name"),
            parent_region_id=_optional_id(data.get("parent_region_id"), "parent_region_id"),
            valid_span_id=_optional_id(data.get("valid_span_id"), "region.valid_span_id"),
            description=str(data.get("description") or ""),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class SpatialRelation:
    id: str
    project_id: str
    source_region_id: str
    target_region_id: str
    kind: str
    travel_days: int | float | None
    valid_span_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("spatial_relation", self),
            "source_region_id": self.source_region_id,
            "target_region_id": self.target_region_id,
            "kind": self.kind,
            "travel_days": self.travel_days,
            "valid_span_id": self.valid_span_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpatialRelation":
        data = _header(data, "spatial_relation")
        source = validate_id(data.get("source_region_id"), "source_region_id")
        target = validate_id(data.get("target_region_id"), "target_region_id")
        if source == target:
            raise ProjectValidationError("spatial relation endpoints must differ")
        travel = data.get("travel_days")
        if travel is not None:
            _number(travel, "spatial_relation.travel_days", positive=True)
        return cls(
            id=data["id"], project_id=data["project_id"],
            source_region_id=source, target_region_id=target,
            kind=_nonempty(data.get("kind"), "spatial_relation.kind"),
            travel_days=travel,
            valid_span_id=_optional_id(data.get("valid_span_id"), "valid_span_id"),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class Culture:
    id: str
    project_id: str
    name: str
    created_at: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("culture", self),
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Culture":
        data = _header(data, "culture")
        return cls(
            id=data["id"], project_id=data["project_id"],
            name=_nonempty(data.get("name"), "culture.name"),
            description=str(data.get("description") or ""),
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class CultureState:
    id: str
    project_id: str
    culture_id: str
    valid_span_id: str | None
    region_ids: tuple[str, ...]
    attributes: dict[str, Any]
    previous_state_id: str | None
    content_version: str
    created_at: str

    @classmethod
    def create(cls, **values: Any) -> "CultureState":
        record = cls(content_version="", **values)
        return replace(record, content_version=record_version(record.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("culture_state", self),
            "culture_id": self.culture_id,
            "valid_span_id": self.valid_span_id,
            "region_ids": list(self.region_ids),
            "attributes": self.attributes,
            "previous_state_id": self.previous_state_id,
            "content_version": self.content_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CultureState":
        data = _header(data, "culture_state")
        _check_version(data)
        attributes = _mapping(data.get("attributes", {}), "culture_state.attributes")
        canonical_json(attributes)
        return cls(
            id=data["id"], project_id=data["project_id"],
            culture_id=validate_id(data.get("culture_id"), "culture_state.culture_id"),
            valid_span_id=_optional_id(data.get("valid_span_id"), "valid_span_id"),
            region_ids=_id_tuple(data.get("region_ids", []), "culture_state.region_ids"),
            attributes=dict(attributes),
            previous_state_id=_optional_id(
                data.get("previous_state_id"), "culture_state.previous_state_id",
            ),
            content_version=data["content_version"],
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class CultureStateRelation:
    id: str
    project_id: str
    kind: str
    source_state_id: str
    target_state_id: str
    valid_span_id: str | None
    created_at: str
    attributes: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("culture_state_relation", self),
            "kind": self.kind,
            "source_state_id": self.source_state_id,
            "target_state_id": self.target_state_id,
            "valid_span_id": self.valid_span_id,
            "attributes": dict(self.attributes or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CultureStateRelation":
        data = _header(data, "culture_state_relation")
        kind = data.get("kind")
        if kind not in CULTURE_RELATION_KINDS:
            raise ProjectValidationError(f"unknown culture state relation: {kind!r}")
        source = validate_id(data.get("source_state_id"), "source_state_id")
        target = validate_id(data.get("target_state_id"), "target_state_id")
        if source == target:
            raise ProjectValidationError("culture state relation endpoints must differ")
        attributes = _mapping(data.get("attributes", {}), "relation.attributes")
        canonical_json(attributes)
        return cls(
            id=data["id"], project_id=data["project_id"], kind=kind,
            source_state_id=source, target_state_id=target,
            valid_span_id=_optional_id(data.get("valid_span_id"), "valid_span_id"),
            attributes=dict(attributes), created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class CanonScope:
    kind: str
    reference_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "reference_id": self.reference_id}

    @classmethod
    def from_dict(cls, data: Any) -> "CanonScope":
        data = _mapping(data, "canon_scope")
        kind = data.get("kind")
        if kind not in CANON_SCOPE_KINDS:
            raise ProjectValidationError(f"unknown canon scope: {kind!r}")
        reference = _optional_id(data.get("reference_id"), "canon_scope.reference_id")
        if (kind == "global") != (reference is None):
            raise ProjectValidationError(
                "global scope has no reference_id; other scopes require one"
            )
        return cls(kind=kind, reference_id=reference)


@dataclass(frozen=True)
class CanonSource:
    node_id: str
    revision_id: str
    artifact: ArtifactRef
    json_pointer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "artifact": self.artifact.to_dict(),
            "json_pointer": self.json_pointer,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CanonSource":
        data = _mapping(data, "canon_source")
        pointer = data.get("json_pointer", "")
        _validate_pointer(pointer)
        return cls(
            node_id=validate_id(data.get("node_id"), "canon_source.node_id"),
            revision_id=validate_id(data.get("revision_id"), "canon_source.revision_id"),
            artifact=ArtifactRef.from_dict(data.get("artifact")),
            json_pointer=pointer,
        )


def _validate_pointer(pointer: Any) -> str:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ProjectValidationError("json_pointer must be empty or start with '/'")
    index = 0
    while index < len(pointer):
        if pointer[index] == "~":
            if index + 1 >= len(pointer) or pointer[index + 1] not in {"0", "1"}:
                raise ProjectValidationError("json_pointer has an invalid '~' escape")
            index += 1
        index += 1
    return pointer


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve the RFC 6901 subset needed for JSON canon adoption."""
    _validate_pointer(pointer)
    current = document
    if not pointer:
        return current
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ProjectValidationError(f"json_pointer key is missing: {token}")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise ProjectValidationError(f"json_pointer array index is invalid: {token}")
            index = int(token)
            if index >= len(current):
                raise ProjectValidationError(f"json_pointer array index is missing: {token}")
            current = current[index]
        else:
            raise ProjectValidationError(f"json_pointer traverses a scalar at {token}")
    canonical_json(current)
    return current


@dataclass(frozen=True)
class WorldCanonEntry:
    id: str
    project_id: str
    scope: CanonScope
    subject: str
    content: Any
    valid_span_id: str | None
    source: CanonSource | None
    supersedes_id: str | None
    content_version: str
    created_at: str

    @classmethod
    def create(cls, **values: Any) -> "WorldCanonEntry":
        record = cls(content_version="", **values)
        return replace(record, content_version=record_version(record.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("world_canon_entry", self),
            "scope": self.scope.to_dict(),
            "subject": self.subject,
            "content": self.content,
            "valid_span_id": self.valid_span_id,
            "source": self.source.to_dict() if self.source else None,
            "supersedes_id": self.supersedes_id,
            "content_version": self.content_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldCanonEntry":
        data = _header(data, "world_canon_entry")
        _check_version(data)
        if "content" not in data:
            raise ProjectValidationError("world canon content is required")
        canonical_json(data["content"])
        source = data.get("source")
        return cls(
            id=data["id"], project_id=data["project_id"],
            scope=CanonScope.from_dict(data.get("scope")),
            subject=_nonempty(data.get("subject"), "world_canon_entry.subject"),
            content=data["content"],
            valid_span_id=_optional_id(data.get("valid_span_id"), "valid_span_id"),
            source=CanonSource.from_dict(source) if source is not None else None,
            supersedes_id=_optional_id(data.get("supersedes_id"), "supersedes_id"),
            content_version=data["content_version"],
            created_at=_timestamp(data.get("created_at")),
        )


@dataclass(frozen=True)
class WorkWorldBinding:
    """Explicit, revision-pinned world references for one work node."""

    id: str
    project_id: str
    node_id: str
    revision_id: str
    time_span_ids: tuple[str, ...]
    region_ids: tuple[str, ...]
    culture_state_ids: tuple[str, ...]
    content_version: str
    created_at: str

    @classmethod
    def create(cls, **values: Any) -> "WorkWorldBinding":
        record = cls(content_version="", **values)
        return replace(record, content_version=record_version(record.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {
            **_base_dict("work_world_binding", self),
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "time_span_ids": list(self.time_span_ids),
            "region_ids": list(self.region_ids),
            "culture_state_ids": list(self.culture_state_ids),
            "content_version": self.content_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkWorldBinding":
        data = _header(data, "work_world_binding")
        _check_version(data)
        return cls(
            id=data["id"], project_id=data["project_id"],
            node_id=validate_id(data.get("node_id"), "binding.node_id"),
            revision_id=validate_id(data.get("revision_id"), "binding.revision_id"),
            time_span_ids=_id_tuple(data.get("time_span_ids", []), "binding.time_span_ids"),
            region_ids=_id_tuple(data.get("region_ids", []), "binding.region_ids"),
            culture_state_ids=_id_tuple(
                data.get("culture_state_ids", []), "binding.culture_state_ids",
            ),
            content_version=data["content_version"],
            created_at=_timestamp(data.get("created_at")),
        )


WORLD_RECORD_MODELS = {
    "timeframes": TimeFrame,
    "time_spans": TimeSpan,
    "time_conversions": TimeConversion,
    "regions": Region,
    "spatial_relations": SpatialRelation,
    "cultures": Culture,
    "culture_states": CultureState,
    "culture_state_relations": CultureStateRelation,
    "canon_entries": WorldCanonEntry,
    "bindings": WorkWorldBinding,
}

WORLD_RECORD_TYPES = {
    "timeframes": "time_frame",
    "time_spans": "time_span",
    "time_conversions": "time_conversion",
    "regions": "region",
    "spatial_relations": "spatial_relation",
    "cultures": "culture",
    "culture_states": "culture_state",
    "culture_state_relations": "culture_state_relation",
    "canon_entries": "world_canon_entry",
    "bindings": "work_world_binding",
}
