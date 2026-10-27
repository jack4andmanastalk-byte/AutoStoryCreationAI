"""Atomic JSON persistence and cross-record validation for the world graph."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import ArtifactRef, new_id, utc_now
from .schema import ProjectValidationError, canonical_json, validate_id
from .store import ProjectExistsError, ProjectStore, _atomic_write_json
from .world import (
    WORLD_RECORD_MODELS,
    WORLD_RECORD_TYPES,
    VERSIONED_RECORDS,
    CanonScope,
    CanonSource,
    WorkWorldBinding,
    WorldCanonEntry,
    record_version,
    resolve_json_pointer,
)


@dataclass(frozen=True)
class WorldRecords:
    timeframes: tuple[Any, ...] = ()
    time_spans: tuple[Any, ...] = ()
    time_conversions: tuple[Any, ...] = ()
    regions: tuple[Any, ...] = ()
    spatial_relations: tuple[Any, ...] = ()
    cultures: tuple[Any, ...] = ()
    culture_states: tuple[Any, ...] = ()
    culture_state_relations: tuple[Any, ...] = ()
    canon_entries: tuple[Any, ...] = ()
    bindings: tuple[Any, ...] = ()


_RECORD_ALIASES = {
    "timeframe": "timeframes",
    "timeframes": "timeframes",
    "time-span": "time_spans",
    "time_spans": "time_spans",
    "time-conversion": "time_conversions",
    "time_conversions": "time_conversions",
    "region": "regions",
    "regions": "regions",
    "spatial-relation": "spatial_relations",
    "spatial_relations": "spatial_relations",
    "culture": "cultures",
    "cultures": "cultures",
    "culture-state": "culture_states",
    "culture_states": "culture_states",
    "culture-relation": "culture_state_relations",
    "culture_state_relations": "culture_state_relations",
    "canon": "canon_entries",
    "canon_entries": "canon_entries",
    "binding": "bindings",
    "bindings": "bindings",
}

_ID_PREFIXES = {
    "timeframes": "time",
    "time_spans": "span",
    "time_conversions": "conv",
    "regions": "region",
    "spatial_relations": "spatial",
    "cultures": "culture",
    "culture_states": "cstate",
    "culture_state_relations": "crel",
    "canon_entries": "canon",
    "bindings": "binding",
}


def _dag(node_ids: set[str], edges: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ProjectValidationError(f"cycle detected in {label}: {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in edges.get(node_id, []):
            if target not in node_ids:
                raise ProjectValidationError(f"missing {label} reference: {target}")
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(node_ids):
        visit(node_id)


class WorldStore:
    """World records below ``<project>/world`` using the project's writer lock."""

    def __init__(self, store: ProjectStore):
        self.store = store

    def world_dir(self, project_id: str) -> Path:
        self.store.load_project(project_id)
        return self.store.project_dir(project_id) / "world"

    def record_path(self, project_id: str, kind: str, record_id: str) -> Path:
        kind = _RECORD_ALIASES.get(kind, kind)
        if kind not in WORLD_RECORD_MODELS:
            raise ProjectValidationError(f"unknown world record kind: {kind}")
        return self.world_dir(project_id) / kind / f"{validate_id(record_id)}.json"

    @staticmethod
    def _empty() -> WorldRecords:
        return WorldRecords()

    def _load_records(self, project_id: str) -> WorldRecords:
        directory = self.world_dir(project_id)
        values: dict[str, list[Any]] = {kind: [] for kind in WORLD_RECORD_MODELS}
        for kind, model in WORLD_RECORD_MODELS.items():
            record_dir = directory / kind
            if not record_dir.is_dir():
                continue
            for path in sorted(record_dir.glob("*.json"), key=lambda item: item.name):
                record = self.store._parse(path, model.from_dict)
                if record.id != path.stem or record.project_id != project_id:
                    raise ProjectValidationError(
                        f"{path}: world record identity does not match its path"
                    )
                values[kind].append(record)
        return WorldRecords(**{
            kind: tuple(sorted(rows, key=lambda item: item.id))
            for kind, rows in values.items()
        })

    def add_record(
        self, project_id: str, kind: str, data: dict[str, Any],
    ) -> Any:
        """Normalize one CLI/API record, then append it immutably."""
        normalized_kind = _RECORD_ALIASES.get(kind)
        if normalized_kind is None:
            raise ProjectValidationError(f"unknown world record kind: {kind}")
        if not isinstance(data, dict):
            raise ProjectValidationError("world record must be a JSON object")
        payload = dict(data)
        payload.setdefault("record_type", WORLD_RECORD_TYPES[normalized_kind])
        payload.setdefault("schema_version", 1)
        payload.setdefault("project_id", project_id)
        if payload["project_id"] != project_id:
            raise ProjectValidationError("world record project_id differs from the target")
        payload.setdefault("id", new_id(_ID_PREFIXES[normalized_kind]))
        payload.setdefault("created_at", utc_now())
        # Version hashes cover normalized content, including explicit empty
        # references and null optionals, rather than incidental JSON omission.
        version_defaults = {
            "culture_states": {
                "valid_span_id": None, "region_ids": [], "attributes": {},
                "previous_state_id": None,
            },
            "canon_entries": {
                "valid_span_id": None, "source": None, "supersedes_id": None,
            },
            "bindings": {
                "time_span_ids": [], "region_ids": [], "culture_state_ids": [],
            },
        }
        if WORLD_RECORD_TYPES[normalized_kind] in VERSIONED_RECORDS:
            for key, value in version_defaults[normalized_kind].items():
                payload.setdefault(key, value)
            if normalized_kind == "canon_entries":
                payload["scope"] = dict(payload.get("scope") or {})
                payload["scope"].setdefault("reference_id", None)
                if payload["source"] is not None:
                    payload["source"] = dict(payload["source"])
                    payload["source"].setdefault("json_pointer", "")
            if not payload.get("content_version"):
                payload["content_version"] = record_version(payload)
        record = WORLD_RECORD_MODELS[normalized_kind].from_dict(payload)
        return self._save(normalized_kind, record)

    def _save(self, kind: str, record: Any) -> Any:
        model = WORLD_RECORD_MODELS[kind]
        record = model.from_dict(record.to_dict())
        project_id = record.project_id
        path = self.record_path(project_id, kind, record.id)
        with self.store.writer_lock(project_id):
            if path.exists():
                existing = self.store._read_json(path)
                if existing == record.to_dict():
                    return record
                raise ProjectExistsError(f"world record already exists: {record.id}")
            _atomic_write_json(path, record.to_dict())
            try:
                self.validate(project_id)
            except Exception:
                path.unlink(missing_ok=True)
                raise
        return record

    def save_timeframe(self, record: Any) -> Any:
        return self._save("timeframes", record)

    def save_time_span(self, record: Any) -> Any:
        return self._save("time_spans", record)

    def save_time_conversion(self, record: Any) -> Any:
        return self._save("time_conversions", record)

    def save_region(self, record: Any) -> Any:
        return self._save("regions", record)

    def save_spatial_relation(self, record: Any) -> Any:
        return self._save("spatial_relations", record)

    def save_culture(self, record: Any) -> Any:
        return self._save("cultures", record)

    def save_culture_state(self, record: Any) -> Any:
        return self._save("culture_states", record)

    def save_culture_state_relation(self, record: Any) -> Any:
        return self._save("culture_state_relations", record)

    def save_canon_entry(self, record: WorldCanonEntry) -> WorldCanonEntry:
        return self._save("canon_entries", record)

    def save_binding(self, record: WorkWorldBinding) -> WorkWorldBinding:
        return self._save("bindings", record)

    def bind_work(
        self, project_id: str, node_id: str, *,
        time_span_ids: tuple[str, ...] = (), region_ids: tuple[str, ...] = (),
        culture_state_ids: tuple[str, ...] = (), binding_id: str | None = None,
    ) -> WorkWorldBinding:
        # Pin the same current revision throughout the read/validate/write
        # sequence; a continuation cannot move the node midway through binding.
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_node_snapshot(project_id, node_id)
            record = WorkWorldBinding.create(
                id=binding_id or new_id("binding"), project_id=project_id,
                node_id=node_id, revision_id=snapshot.revision.id,
                time_span_ids=tuple(time_span_ids), region_ids=tuple(region_ids),
                culture_state_ids=tuple(culture_state_ids), created_at=utc_now(),
            )
            return self.save_binding(record)

    def author_world_canon(
        self, project_id: str, *, scope: CanonScope, subject: str, content: Any,
        valid_span_id: str | None = None, supersedes_id: str | None = None,
        entry_id: str | None = None,
    ) -> WorldCanonEntry:
        record = WorldCanonEntry.create(
            id=entry_id or new_id("canon"), project_id=project_id,
            scope=scope, subject=subject, content=content,
            valid_span_id=valid_span_id, source=None, supersedes_id=supersedes_id,
            created_at=utc_now(),
        )
        return self.save_canon_entry(record)

    def adopt_world_canon(
        self, project_id: str, node_id: str, *, source_artifact_path: str,
        json_pointer: str = "", scope: CanonScope, subject: str,
        valid_span_id: str | None = None, supersedes_id: str | None = None,
        entry_id: str | None = None,
    ) -> WorldCanonEntry:
        """Explicitly adopt a JSON value from a completed node's plan artifact."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_node_snapshot(project_id, node_id)
            status = self.store.status(project_id, node_id, include_descendants=False)
            if status["state"] != "complete":
                raise ProjectValidationError(
                    f"node {node_id} must be complete before canon adoption"
                )
            artifacts = [
                ArtifactRef.from_dict(row)
                for row in status["checkpoints"]["plan"]["artifacts"]
            ]
            matches = [
                item for item in artifacts
                if item.path == source_artifact_path
                or (
                    not source_artifact_path.startswith("runs/")
                    and item.path.endswith(f"/{source_artifact_path.lstrip('/')}")
                )
            ]
            if len(matches) != 1:
                raise ProjectValidationError(
                    "source_artifact_path must identify one pinned plan artifact"
                )
            artifact = matches[0]
            try:
                document = json.loads(self.store.read_artifact(project_id, artifact))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProjectValidationError("canon source artifact must be JSON") from exc
            content = resolve_json_pointer(document, json_pointer)
            record = WorldCanonEntry.create(
                id=entry_id or new_id("canon"), project_id=project_id,
                scope=scope, subject=subject, content=content,
                valid_span_id=valid_span_id,
                source=CanonSource(
                    node_id=node_id, revision_id=snapshot.revision.id,
                    artifact=artifact, json_pointer=json_pointer,
                ),
                supersedes_id=supersedes_id, created_at=utc_now(),
            )
            return self.save_canon_entry(record)

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise ProjectValidationError(message)

    def _verify_canon_source(self, project_id: str, entry: WorldCanonEntry) -> None:
        source = entry.source
        if source is None:
            return
        self.store.load_revision(project_id, source.node_id, source.revision_id)
        artifact = source.artifact
        run_id = artifact.producer_run_id
        self._require(bool(run_id), "canon source artifact requires a producer run")
        self._require(
            artifact.path.startswith(f"runs/{run_id}/"),
            "canon source artifact does not belong to its producer run",
        )
        run_dir = self.store.project_dir(project_id) / "runs" / run_id
        manifest = self.store._read_json(run_dir / "manifest.json")
        run_input = self.store._read_json(run_dir / "project-input.json")
        self._require(
            manifest.get("status") == "ok"
            and manifest.get("task_id") == source.node_id
            and run_input.get("node_id") == source.node_id
            and run_input.get("revision_id") == source.revision_id
            and run_input.get("stage") == "plan",
            "canon source is not a successful plan run for the pinned node revision",
        )
        try:
            document = json.loads(self.store.read_artifact(project_id, artifact))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectValidationError("canon source artifact must be JSON") from exc
        selected = resolve_json_pointer(document, source.json_pointer)
        self._require(
            canonical_json(selected) == canonical_json(entry.content),
            f"canon entry {entry.id} content differs from its pinned source",
        )

    def validate(self, project_id: str) -> WorldRecords:
        """Validate every world record and every cross-record reference."""
        records = self._load_records(project_id)
        project = self.store.load_project(project_id)
        frames = {item.id: item for item in records.timeframes}
        spans = {item.id: item for item in records.time_spans}
        regions = {item.id: item for item in records.regions}
        cultures = {item.id: item for item in records.cultures}
        states = {item.id: item for item in records.culture_states}

        for span in records.time_spans:
            if span.timeframe_id is not None:
                self._require(span.timeframe_id in frames, f"missing timeframe: {span.timeframe_id}")
            for before_id in span.before_span_ids:
                self._require(before_id != span.id, "time span cannot precede itself")
        _dag(
            set(spans),
            {item.id: list(item.before_span_ids) for item in records.time_spans},
            "time span ordering",
        )
        conversion_pairs: set[tuple[str, str]] = set()
        for conversion in records.time_conversions:
            self._require(conversion.source_timeframe_id in frames, "missing conversion source")
            self._require(conversion.target_timeframe_id in frames, "missing conversion target")
            pair = (conversion.source_timeframe_id, conversion.target_timeframe_id)
            self._require(pair not in conversion_pairs, f"ambiguous time conversion: {pair}")
            conversion_pairs.add(pair)

        for region in records.regions:
            if region.parent_region_id is not None:
                self._require(region.parent_region_id in regions, "missing parent region")
                self._require(region.parent_region_id != region.id, "region cannot parent itself")
            if region.valid_span_id is not None:
                self._require(region.valid_span_id in spans, "missing region validity span")
        _dag(
            set(regions),
            {
                item.id: [item.parent_region_id] if item.parent_region_id else []
                for item in records.regions
            },
            "region containment",
        )
        for relation in records.spatial_relations:
            self._require(relation.source_region_id in regions, "missing spatial source region")
            self._require(relation.target_region_id in regions, "missing spatial target region")
            if relation.valid_span_id is not None:
                self._require(relation.valid_span_id in spans, "missing spatial validity span")

        for state in records.culture_states:
            self._require(state.culture_id in cultures, f"missing culture: {state.culture_id}")
            if state.valid_span_id is not None:
                self._require(state.valid_span_id in spans, "missing culture validity span")
            for region_id in state.region_ids:
                self._require(region_id in regions, f"missing culture region: {region_id}")
            if state.previous_state_id is not None:
                self._require(state.previous_state_id in states, "missing previous culture state")
                self._require(
                    states[state.previous_state_id].culture_id == state.culture_id,
                    "previous_state_id must belong to the same culture",
                )
        _dag(
            set(states),
            {
                item.id: [item.previous_state_id] if item.previous_state_id else []
                for item in records.culture_states
            },
            "culture state versions",
        )
        relation_edges = {state_id: [] for state_id in states}
        for relation in records.culture_state_relations:
            self._require(relation.source_state_id in states, "missing source culture state")
            self._require(relation.target_state_id in states, "missing target culture state")
            if relation.valid_span_id is not None:
                self._require(relation.valid_span_id in spans, "missing relation validity span")
            if relation.kind in {"inheritance", "split"}:
                relation_edges[relation.source_state_id].append(relation.target_state_id)
        _dag(set(states), relation_edges, "culture inheritance/split")

        canon = {item.id: item for item in records.canon_entries}
        canon_edges = {item.id: [] for item in records.canon_entries}
        superseded: dict[str, str] = {}
        for entry in records.canon_entries:
            reference = entry.scope.reference_id
            if entry.scope.kind == "timeframe":
                self._require(reference in frames, "missing canon timeframe scope")
                if entry.valid_span_id is not None:
                    self._require(entry.valid_span_id in spans, "missing canon validity span")
                    self._require(
                        spans[entry.valid_span_id].timeframe_id == reference,
                        "canon validity span differs from its timeframe scope",
                    )
            elif entry.scope.kind == "region":
                self._require(reference in regions, "missing canon region scope")
            elif entry.scope.kind == "culture":
                self._require(reference in cultures, "missing canon culture scope")
            elif entry.scope.kind in {"work", "node"}:
                node = self.store.load_node(project_id, reference)
                if entry.scope.kind == "work":
                    self._require(node.id == project.root_node_id, "work scope requires the root")
            if entry.scope.kind != "timeframe" and entry.valid_span_id is not None:
                self._require(entry.valid_span_id in spans, "missing canon validity span")
            if entry.supersedes_id is not None:
                self._require(entry.supersedes_id in canon, "missing superseded canon entry")
                previous = canon[entry.supersedes_id]
                self._require(
                    previous.scope == entry.scope and previous.subject == entry.subject,
                    "canon supersession must retain scope and subject",
                )
                self._require(
                    entry.supersedes_id not in superseded,
                    "canon entry already has a successor; refusing a branch",
                )
                superseded[entry.supersedes_id] = entry.id
                canon_edges[entry.id].append(entry.supersedes_id)
            self._verify_canon_source(project_id, entry)
        _dag(set(canon), canon_edges, "canon supersession")

        binding_keys: set[tuple[str, str]] = set()
        for binding in records.bindings:
            self.store.load_revision(project_id, binding.node_id, binding.revision_id)
            key = (binding.node_id, binding.revision_id)
            self._require(key not in binding_keys, "duplicate world binding for node revision")
            binding_keys.add(key)
            self._require(
                bool(binding.time_span_ids or binding.region_ids or binding.culture_state_ids),
                "world binding requires at least one reference",
            )
            for span_id in binding.time_span_ids:
                self._require(span_id in spans, f"missing binding time span: {span_id}")
            for region_id in binding.region_ids:
                self._require(region_id in regions, f"missing binding region: {region_id}")
            for state_id in binding.culture_state_ids:
                self._require(state_id in states, f"missing binding culture state: {state_id}")
        return records

    def status(self, project_id: str, node_id: str | None = None) -> dict[str, Any]:
        records = self.validate(project_id)
        project = self.store.load_project(project_id)
        selected = self.store.load_node(project_id, node_id or project.root_node_id)
        superseded = {
            entry.supersedes_id for entry in records.canon_entries if entry.supersedes_id
        }
        canon_rows = []
        for entry in records.canon_entries:
            row = entry.to_dict()
            current_source = None
            if entry.source is not None:
                current_source = self.store.load_node(
                    project_id, entry.source.node_id,
                ).current_revision_id
            row.update({
                "current": entry.id not in superseded,
                "stale": bool(
                    entry.source is not None
                    and current_source != entry.source.revision_id
                ),
                "current_source_revision_id": current_source,
            })
            canon_rows.append(row)
        binding_rows = []
        selected_binding = None
        for binding in records.bindings:
            node = self.store.load_node(project_id, binding.node_id)
            row = binding.to_dict()
            row["current"] = node.current_revision_id == binding.revision_id
            binding_rows.append(row)
            if binding.node_id == selected.id and row["current"]:
                selected_binding = row
        result = {
            "schema_version": 1,
            "project_id": project_id,
            "selected_node_id": selected.id,
            "selected_revision_id": selected.current_revision_id,
            "selected_binding": selected_binding,
            "canon_entries": canon_rows,
            "bindings": binding_rows,
        }
        for kind in (
            "timeframes", "time_spans", "time_conversions", "regions",
            "spatial_relations", "cultures", "culture_states",
            "culture_state_relations",
        ):
            result[kind] = [item.to_dict() for item in getattr(records, kind)]
        result["counts"] = {
            kind: len(result[kind]) for kind in (
                "timeframes", "time_spans", "time_conversions", "regions",
                "spatial_relations", "cultures", "culture_states",
                "culture_state_relations", "canon_entries", "bindings",
            )
        }
        return result
