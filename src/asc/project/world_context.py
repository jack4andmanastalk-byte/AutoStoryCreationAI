"""Select revision-pinned world records for a creative work's context packet.

Only explicitly bound spans, regions, and culture states are expanded.  Canon
is filtered independently by scope and validity, so adding a future culture
state or an unrelated timeframe cannot silently alter an existing selection.
"""
from __future__ import annotations

from typing import Any

from .schema import SCHEMA_VERSION, ProjectValidationError, canonical_json
from .store import ProjectStore
from .world import WorldCanonEntry, record_version
from .world_store import WorldRecords, WorldStore

WORLD_CONTEXT_KIND = "asc-world-context-v1"
MAX_WORLD_CANON_ENTRIES = 64
CANON_OVERLAY_ORDER = (
    "global", "timeframe", "region", "culture", "work", "node",
)
_SCOPE_RANK = {kind: index for index, kind in enumerate(CANON_OVERLAY_ORDER)}
_WORLD_COLLECTIONS = (
    "timeframes", "time_spans", "time_conversions", "regions",
    "spatial_relations", "cultures", "culture_states",
    "culture_state_relations", "canon_entries",
)


def versioned_reference(record: Any) -> dict[str, str]:
    """Return a stable content version even for immutable unversioned records."""
    data = record.to_dict()
    return {
        "record_type": data["record_type"],
        "id": data["id"],
        "content_version": record_version(data),
    }


def current_canon_entries(records: WorldRecords) -> list[WorldCanonEntry]:
    superseded = {
        entry.supersedes_id for entry in records.canon_entries if entry.supersedes_id
    }
    return [entry for entry in records.canon_entries if entry.id not in superseded]


def _canon_applies(
    entry: WorldCanonEntry, *, root_node_id: str, node_id: str,
    timeframe_ids: set[str], span_ids: set[str], region_ids: set[str],
    culture_ids: set[str],
) -> bool:
    if entry.valid_span_id is not None and entry.valid_span_id not in span_ids:
        return False
    kind = entry.scope.kind
    reference = entry.scope.reference_id
    if kind == "global":
        return True
    if kind == "timeframe":
        return reference in timeframe_ids
    if kind == "region":
        return reference in region_ids
    if kind == "culture":
        return reference in culture_ids
    if kind == "work":
        return reference == root_node_id
    if kind == "node":
        return reference == node_id
    raise ProjectValidationError(f"unknown canon scope: {kind}")


def _canon_sort_key(entry: WorldCanonEntry) -> tuple[int, int, str]:
    return (
        _SCOPE_RANK[entry.scope.kind],
        1 if entry.valid_span_id is not None else 0,
        entry.id,
    )


def _select_canon(
    records: WorldRecords, *, root_node_id: str, node_id: str,
    timeframe_ids: set[str], span_ids: set[str], region_ids: set[str],
    culture_ids: set[str],
) -> tuple[list[WorldCanonEntry], int]:
    applicable = [
        entry for entry in current_canon_entries(records)
        if _canon_applies(
            entry, root_node_id=root_node_id, node_id=node_id,
            timeframe_ids=timeframe_ids, span_ids=span_ids,
            region_ids=region_ids, culture_ids=culture_ids,
        )
    ]
    omitted = max(0, len(applicable) - MAX_WORLD_CANON_ENTRIES)
    if omitted:
        # Preserve the most specific/local overlays when an operator has
        # created a large global ledger.  The omission is explicit in metadata.
        prioritized = sorted(
            applicable,
            key=lambda entry: (
                -_SCOPE_RANK[entry.scope.kind],
                entry.valid_span_id is None,
                entry.id,
            ),
        )
        keep = {entry.id for entry in prioritized[:MAX_WORLD_CANON_ENTRIES]}
        applicable = [entry for entry in applicable if entry.id in keep]
    return sorted(applicable, key=_canon_sort_key), omitted


def validate_world_context(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("record_type") != WORLD_CONTEXT_KIND:
        raise ValueError("invalid world context record")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported world context schema")
    if not isinstance(data.get("binding"), dict):
        raise ValueError("world context binding must be an object")
    selection = data.get("selection")
    if not isinstance(selection, dict) or selection.get("chapter_prose") != "excluded":
        raise ValueError("world context must exclude chapter prose")
    for key in (*_WORLD_COLLECTIONS, "references"):
        rows = data.get(key)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"world context {key} must be a list of objects")
    for row in data["references"]:
        version = row.get("content_version")
        if not row.get("id") or not isinstance(version, str) or len(version) != 64:
            raise ValueError("invalid world context reference")
    omitted = selection.get("omitted_canon_count")
    if isinstance(omitted, bool) or not isinstance(omitted, int) or omitted < 0:
        raise ValueError("invalid omitted canon count")
    canonical_json(data)
    return data


def build_world_context(
    store: ProjectStore, project_id: str, node_id: str,
) -> dict[str, Any] | None:
    """Build a world selection for the node's current binding, if one exists."""
    snapshot = store.load_node_snapshot(project_id, node_id)
    records = WorldStore(store).validate(project_id)
    binding = next((
        item for item in records.bindings
        if item.node_id == snapshot.root_node.id
        and item.revision_id == snapshot.revision.id
    ), None)
    if binding is None:
        return None

    spans = {item.id: item for item in records.time_spans}
    states = {item.id: item for item in records.culture_states}
    selected_spans = [spans[item_id] for item_id in binding.time_span_ids]
    selected_states = [states[item_id] for item_id in binding.culture_state_ids]
    timeframe_ids = {
        item.timeframe_id for item in selected_spans if item.timeframe_id is not None
    }
    culture_ids = {item.culture_id for item in selected_states}
    region_ids = set(binding.region_ids)
    span_ids = set(binding.time_span_ids)
    selected_state_ids = {item.id for item in selected_states}

    selected: dict[str, list[Any]] = {
        "timeframes": [
            item for item in records.timeframes if item.id in timeframe_ids
        ],
        "time_spans": selected_spans,
        "time_conversions": [
            item for item in records.time_conversions
            if item.source_timeframe_id in timeframe_ids
            and item.target_timeframe_id in timeframe_ids
        ],
        "regions": [item for item in records.regions if item.id in region_ids],
        "spatial_relations": [
            item for item in records.spatial_relations
            if item.source_region_id in region_ids and item.target_region_id in region_ids
        ],
        "cultures": [item for item in records.cultures if item.id in culture_ids],
        "culture_states": selected_states,
        "culture_state_relations": [
            item for item in records.culture_state_relations
            if item.source_state_id in selected_state_ids
            and item.target_state_id in selected_state_ids
        ],
    }
    canon, omitted = _select_canon(
        records, root_node_id=snapshot.project.root_node_id, node_id=node_id,
        timeframe_ids=timeframe_ids, span_ids=span_ids, region_ids=region_ids,
        culture_ids=culture_ids,
    )
    selected["canon_entries"] = canon
    included_records = [binding]
    for key in _WORLD_COLLECTIONS:
        included_records.extend(selected[key])
    references = sorted(
        (versioned_reference(record) for record in included_records),
        key=lambda row: (row["record_type"], row["id"]),
    )
    result = {
        "record_type": WORLD_CONTEXT_KIND,
        "schema_version": SCHEMA_VERSION,
        "binding": binding.to_dict(),
        "selection": {
            "time_spans": "binding_only",
            "regions": "binding_only",
            "culture_states": "binding_only",
            "canon": "current_scope_validity_overlay_v1",
            "overlay_order": list(CANON_OVERLAY_ORDER),
            "unselected_timeframes": "excluded",
            "future_states": "excluded",
            "chapter_prose": "excluded",
            "max_canon_entries": MAX_WORLD_CANON_ENTRIES,
            "omitted_canon_count": omitted,
        },
        "references": references,
    }
    for key in _WORLD_COLLECTIONS:
        result[key] = [
            item.to_dict() for item in sorted(selected[key], key=lambda row: row.id)
        ] if key != "canon_entries" else [item.to_dict() for item in canon]
    return validate_world_context(result)
