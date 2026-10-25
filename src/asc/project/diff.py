"""Record-level comparison of two ContextPackets or two compilation views.

``context show`` already answers *does the recorded packet still match the
current state*, but it reports the world selection as counts plus
``added/removed/changed`` tuples.  Dogfood needed the next question: *which
record changed, from which version to which version*, both for packets
recorded by different stages/revisions and for two compilations of the same
profile.  This module answers it without generating, resuming, or adopting
anything.

Two kinds of documents can be compared:

``context-packet``
    A packet read from a run's ``project-input.json``, from the checkpoint of
    a stage of the current revision, or built from the current state.  Records
    are the world references the packet selected (with their content versions)
    plus each ancestor's compact canon items (hashed, because canon items carry
    no content version of their own).

``compilation``
    A stored world/work compilation artifact.  Records are the manifest's
    ``source_references``.

Both sides must be the same kind of document: comparing a packet against a
compilation would only report every record as added and removed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import context_view
from .context import build_context_packet
from .schema import canonical_json
from .store import DEFAULT_STAGES, ProjectError, ProjectStore
from .world_compile import COMPILATION_RECORD

DIFF_SCHEMA = "asc-project-diff-v1"
PACKET_SOURCE = "context-packet"
COMPILATION_SOURCE = "compilation"
ANCESTOR_COLLECTIONS = (
    "characters", "facts", "locations", "chapters", "foreshadowing",
)
_WORLD_ATTRIBUTES = (
    ("binding_id", lambda world, selection: (world.get("binding") or {}).get("id")),
    (
        "binding_content_version",
        lambda world, selection: (world.get("binding") or {}).get("content_version"),
    ),
    ("overlay_order", lambda world, selection: list(selection.get("overlay_order") or ())),
    (
        "omitted_canon_count",
        lambda world, selection: selection.get("omitted_canon_count", 0),
    ),
)


class DiffError(ProjectError):
    """A requested diff side cannot be read, or the two sides do not compare."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _item_hash(item: Any) -> str:
    """Stable short hash for a canon item that has no content_version field."""
    return _sha256_text(canonical_json(item))[:16]


@dataclass(frozen=True)
class DiffSide:
    """One document in a diff, reduced to comparable records and attributes."""

    spec: str
    source: str
    identity: dict[str, Any]
    document_sha256: str
    records: tuple[dict[str, str], ...]
    attributes: dict[str, Any]
    ancestors: tuple[dict[str, str], ...] = ()

    @property
    def record_count(self) -> int:
        return len(self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec,
            "source": self.source,
            "identity": self.identity,
            "document_sha256": self.document_sha256,
            "record_count": self.record_count,
            "attributes": self.attributes,
            "ancestors": [dict(row) for row in self.ancestors],
        }


def _record_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["scope"], row["record_type"], row["id"])


def _packet_records(packet: dict[str, Any]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    world = packet.get("world")
    if isinstance(world, dict):
        for reference in world.get("references") or ():
            rows.append({
                "scope": "world",
                "record_type": str(reference.get("record_type")),
                "id": str(reference.get("id")),
                "content_version": str(reference.get("content_version") or ""),
            })
    for ancestor in packet.get("ancestors") or ():
        canon = ancestor.get("canon")
        if not isinstance(canon, dict):
            continue
        scope = f"ancestor:{ancestor.get('node_id')}"
        for collection in ANCESTOR_COLLECTIONS:
            for item in canon.get(collection) or ():
                if not isinstance(item, dict) or item.get("id") is None:
                    continue
                rows.append({
                    "scope": scope,
                    "record_type": collection,
                    "id": str(item["id"]),
                    "content_version": _item_hash(item),
                })
    return tuple(sorted(rows, key=_record_key))


def _packet_attributes(packet: dict[str, Any]) -> dict[str, Any]:
    selection = packet.get("selection") or {}
    attributes: dict[str, Any] = {
        "kind": packet.get("record_type"),
        "node_id": packet.get("node_id"),
        "revision_id": packet.get("revision_id"),
        "selection_scope": selection.get("scope"),
        "knowledge_character_id": (selection.get("knowledge") or {}).get("character_id"),
    }
    world = packet.get("world")
    if isinstance(world, dict):
        for name, read in _WORLD_ATTRIBUTES:
            attributes[name] = read(world, selection)
        attributes["ancestor_count"] = len(packet.get("ancestors") or ())
    else:
        attributes["binding_id"] = None
    return attributes


def _packet_side(
    spec: str, packet: dict[str, Any] | None, identity: dict[str, Any],
) -> DiffSide:
    if packet is None:
        raise DiffError(
            f"{spec}: no ContextPacket is recorded or built here "
            "(no ancestors and no world binding)"
        )
    return DiffSide(
        spec=spec,
        source=PACKET_SOURCE,
        identity=identity,
        document_sha256=_sha256_text(canonical_json(packet)),
        records=_packet_records(packet),
        attributes=_packet_attributes(packet),
        ancestors=tuple(
            {
                "node_id": str(ancestor.get("node_id")),
                "revision_id": str(ancestor.get("revision_id")),
            }
            for ancestor in packet.get("ancestors") or ()
        ),
    )


def _compilation_manifests(
    store: ProjectStore, project_id: str,
) -> list[tuple[Path, dict[str, Any]]]:
    directory = store.project_dir(project_id) / "artifacts" / "world"
    if not directory.is_dir():
        return []
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(data, dict)
            and data.get("record_type") == COMPILATION_RECORD
            and data.get("project_id") == project_id
        ):
            found.append((path, data))
    return found


def _compilation_side(
    store: ProjectStore, project_id: str, spec: str, profile_id: str,
    content_version: str | None,
) -> DiffSide:
    manifests = [
        (path, data) for path, data in _compilation_manifests(store, project_id)
        if data.get("profile_id") == profile_id
    ]
    if not manifests:
        raise DiffError(
            f"{spec}: no compiled artifact for profile {profile_id!r} in this project"
        )
    if content_version is not None:
        manifests = [
            (path, data) for path, data in manifests
            if data.get("content_version") == content_version
        ]
        if not manifests:
            raise DiffError(
                f"{spec}: profile {profile_id!r} has no compilation "
                f"{content_version}"
            )
    if len(manifests) > 1:
        versions = sorted({str(data.get('content_version')) for _, data in manifests})
        raise DiffError(
            f"{spec}: profile {profile_id!r} has {len(versions)} compilations; "
            f"pick one with compile:{profile_id}@<content_version> "
            f"(available: {', '.join(versions)})"
        )
    path, manifest = manifests[0]
    records = tuple(sorted(
        (
            {
                "scope": "compilation",
                "record_type": str(reference.get("record_type")),
                "id": str(reference.get("id")),
                "content_version": str(reference.get("content_version") or ""),
            }
            for reference in manifest.get("source_references") or ()
        ),
        key=_record_key,
    ))
    profile = manifest.get("profile") or {}
    attributes = {
        "kind": COMPILATION_SOURCE,
        "profile_id": manifest.get("profile_id"),
        "compilation_kind": manifest.get("kind"),
        "content_version": manifest.get("content_version"),
        "profile_content_version": profile.get("content_version"),
        "text_sha256": manifest.get("text_sha256"),
        "output": manifest.get("output"),
    }
    return DiffSide(
        spec=spec,
        source=COMPILATION_SOURCE,
        identity={
            "project_id": project_id,
            "profile_id": manifest.get("profile_id"),
            "compilation_kind": manifest.get("kind"),
            "content_version": manifest.get("content_version"),
            "manifest": _relative(store, project_id, path),
        },
        document_sha256=_sha256_text(canonical_json(manifest)),
        records=records,
        attributes=attributes,
    )


def _relative(store: ProjectStore, project_id: str, path: Path) -> str:
    try:
        return str(path.relative_to(store.project_dir(project_id)))
    except ValueError:
        return str(path)


def _read_run(
    store: ProjectStore, project_id: str, run_id: str, spec: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        return context_view._read_run_packet(store, project_id, run_id)
    except context_view.ContextViewError as exc:
        raise DiffError(f"{spec}: {exc}") from exc


def load_diff_side(
    store: ProjectStore, project_id: str, spec: str, *,
    node_id: str | None = None,
) -> DiffSide:
    """Read one diff side read-only.

    ``spec`` is one of ``current``, ``stage:<stage>``, ``run:<run_id>``,
    ``compile:<profile_id>``, or ``compile:<profile_id>@<content_version>``.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise DiffError("diff side must be a non-empty spec")
    spec = spec.strip()
    if spec == "current":
        snapshot = store.load_node_snapshot(project_id, node_id)
        packet = build_context_packet(store, project_id, snapshot.root_node.id)
        return _packet_side(
            spec, packet.to_dict() if packet is not None else None,
            {
                "project_id": project_id,
                "node_id": snapshot.root_node.id,
                "revision_id": snapshot.revision.id,
                "stage": None,
                "run_id": None,
            },
        )
    if spec.startswith("stage:"):
        stage = spec.split(":", 1)[1]
        if stage not in DEFAULT_STAGES:
            raise DiffError(
                f"unknown stage {stage!r}; expected one of {', '.join(DEFAULT_STAGES)}"
            )
        snapshot = store.load_node_snapshot(project_id, node_id)
        try:
            checkpoint = context_view._checkpoint_for_stage(
                store, project_id, snapshot.root_node.id, stage, snapshot.revision.id,
            )
        except context_view.ContextViewError as exc:
            raise DiffError(f"{spec}: {exc}") from exc
        if checkpoint.run_id is None:
            raise DiffError(
                f"{spec}: stage {stage} has no run yet (status {checkpoint.status})"
            )
        packet, identity = _read_run(store, project_id, checkpoint.run_id, spec)
        identity["stage"] = stage
        return _packet_side(spec, packet, identity)
    if spec.startswith("run:"):
        run_id = spec.split(":", 1)[1]
        if not run_id:
            raise DiffError("run: needs a run id")
        packet, identity = _read_run(store, project_id, run_id, spec)
        return _packet_side(spec, packet, identity)
    if spec.startswith("compile:"):
        value = spec.split(":", 1)[1]
        if not value:
            raise DiffError("compile: needs a profile id")
        profile_id, _, content_version = value.partition("@")
        return _compilation_side(
            store, project_id, spec, profile_id, content_version or None,
        )
    raise DiffError(
        f"unknown diff side {spec!r}; expected current, stage:<stage>, "
        "run:<run_id>, or compile:<profile_id>[@<content_version>]"
    )


@dataclass(frozen=True)
class ProjectDiff:
    """Record-level difference between two documents of one project."""

    project_id: str
    left: DiffSide
    right: DiffSide
    added: tuple[dict[str, str], ...]
    removed: tuple[dict[str, str], ...]
    changed: tuple[dict[str, Any], ...]
    unchanged: int
    attribute_changes: dict[str, dict[str, Any]]
    ancestor_changes: dict[str, dict[str, str]]

    @property
    def identical(self) -> bool:
        return not (
            self.added or self.removed or self.changed
            or self.attribute_changes or self.ancestor_changes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DIFF_SCHEMA,
            "project_id": self.project_id,
            "read_only": True,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "identical": self.identical,
            "records": {
                "added": [dict(row) for row in self.added],
                "removed": [dict(row) for row in self.removed],
                "changed": [dict(row) for row in self.changed],
            },
            "counts": {
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
                "unchanged": self.unchanged,
            },
            "attributes": self.attribute_changes,
            "ancestors": self.ancestor_changes,
        }


def _ancestor_changes(
    left: DiffSide, right: DiffSide,
) -> dict[str, dict[str, str]]:
    left_map = {row["node_id"]: row["revision_id"] for row in left.ancestors}
    right_map = {row["node_id"]: row["revision_id"] for row in right.ancestors}
    changes: dict[str, dict[str, str]] = {}
    for node in sorted(set(left_map) | set(right_map)):
        if left_map.get(node) == right_map.get(node):
            continue
        changes[node] = {
            "left": left_map.get(node, ""), "right": right_map.get(node, ""),
        }
    return changes


def _attribute_changes(
    left: DiffSide, right: DiffSide,
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(left.attributes) | set(right.attributes)):
        left_value = left.attributes.get(key)
        right_value = right.attributes.get(key)
        if canonical_json(left_value) == canonical_json(right_value):
            continue
        changes[key] = {"left": left_value, "right": right_value}
    return changes


def compare_sides(
    project_id: str, left: DiffSide, right: DiffSide,
) -> ProjectDiff:
    """Compare two already-loaded sides record by record."""
    if left.source != right.source:
        raise DiffError(
            f"cannot diff {left.source} ({left.spec}) against "
            f"{right.source} ({right.spec})"
        )
    left_records = {_record_key(row): row for row in left.records}
    right_records = {_record_key(row): row for row in right.records}
    added = tuple(
        right_records[key] for key in sorted(right_records) if key not in left_records
    )
    removed = tuple(
        left_records[key] for key in sorted(left_records) if key not in right_records
    )
    changed: list[dict[str, Any]] = []
    unchanged = 0
    for key in sorted(set(left_records) & set(right_records)):
        before = left_records[key]["content_version"]
        after = right_records[key]["content_version"]
        if before == after:
            unchanged += 1
            continue
        changed.append({
            "scope": key[0],
            "record_type": key[1],
            "id": key[2],
            "left_content_version": before,
            "right_content_version": after,
        })
    return ProjectDiff(
        project_id=project_id,
        left=left,
        right=right,
        added=added,
        removed=removed,
        changed=tuple(changed),
        unchanged=unchanged,
        attribute_changes=_attribute_changes(left, right),
        ancestor_changes=_ancestor_changes(left, right),
    )


def build_diff(
    store: ProjectStore, project_id: str, left_spec: str, right_spec: str, *,
    node_id: str | None = None,
) -> ProjectDiff:
    """Compare two recorded or current documents of one project, read-only."""
    left = load_diff_side(store, project_id, left_spec, node_id=node_id)
    right = load_diff_side(store, project_id, right_spec, node_id=node_id)
    return compare_sides(project_id, left, right)


__all__ = [
    "COMPILATION_SOURCE",
    "DIFF_SCHEMA",
    "DiffError",
    "DiffSide",
    "PACKET_SOURCE",
    "ProjectDiff",
    "build_diff",
    "compare_sides",
    "load_diff_side",
]
