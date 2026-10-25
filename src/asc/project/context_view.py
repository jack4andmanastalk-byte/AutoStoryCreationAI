"""Read-only views of a node's ContextPacket.

A ``ContextPacket`` is recorded in every stage's ``project-input.json``, and a
resume reuses exactly the recorded packet.  Operators still need to answer two
questions that the recorded run cannot: *which world records and content
versions were selected*, and *would the packet differ if it were rebuilt from
the current state*.  This module reads both without generating anything.

``mode="current"``
    Build the packet from the current project state.  Ancestor canon is read
    from the ancestors' completed runs; world records come from the current
    revision's binding.  Nothing is written.

``mode="recorded"``
    Return the packet stored in one run's ``project-input.json`` (or in the run
    of a named stage of the current revision).  The recorded packet is parsed
    with :meth:`ContextPacket.from_dict`, so an invalid record is reported
    instead of being trusted.

A current view also lists the packets recorded for the same revision and says
whether each one still matches, which exposes drift after an ancestor or world
change.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .context import ContextPacket, build_context_packet
from .model import StageCheckpoint
from .schema import ProjectValidationError, canonical_json
from .store import DEFAULT_STAGES, ProjectError, ProjectStore

CONTEXT_VIEW_SCHEMA = "asc-project-context-view-v1"


class ContextViewError(ProjectError):
    """A requested packet cannot be read or is inconsistent with its records."""


def _packet_summary(packet: dict[str, Any]) -> dict[str, Any]:
    """Return the stable, printable part of one packet document."""
    encoded = canonical_json(packet)
    summary: dict[str, Any] = {
        "kind": packet.get("record_type"),
        "packet_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "packet_bytes": len(encoded.encode("utf-8")),
        "ancestors": [
            {
                "node_id": ancestor.get("node_id"),
                "revision_id": ancestor.get("revision_id"),
                "state": ancestor.get("state"),
                "has_canon": ancestor.get("canon") is not None,
                "canon_bytes": (
                    len(canonical_json(ancestor["canon"]).encode("utf-8"))
                    if ancestor.get("canon") is not None else 0
                ),
                "chapter_count": len(ancestor.get("chapters") or ()),
            }
            for ancestor in packet.get("ancestors") or ()
        ],
        "selection": packet.get("selection"),
    }
    world = packet.get("world")
    if isinstance(world, dict):
        selection = world.get("selection") or {}
        summary["world"] = {
            "binding_id": (world.get("binding") or {}).get("id"),
            "binding_revision_id": (world.get("binding") or {}).get("revision_id"),
            "binding_content_version": (world.get("binding") or {}).get("content_version"),
            "overlay_order": list(selection.get("overlay_order") or ()),
            "canon_entries": len(world.get("canon_entries") or ()),
            "omitted_canon_count": selection.get("omitted_canon_count", 0),
            "references": list(world.get("references") or ()),
            "reference_count": len(world.get("references") or ()),
            "time_span_ids": [
                row.get("id") for row in world.get("time_spans") or ()
            ],
            "region_ids": [row.get("id") for row in world.get("regions") or ()],
            "culture_state_ids": [
                row.get("id") for row in world.get("culture_states") or ()
            ],
        }
    else:
        summary["world"] = None
    knowledge = (packet.get("selection") or {}).get("knowledge")
    summary["knowledge"] = knowledge
    return summary


@dataclass(frozen=True)
class ContextView:
    """One packet view plus the recorded packets for the same revision.

    ``revision_id`` is the revision the returned packet belongs to.  For a
    recorded run of an older revision it differs from ``current_revision_id``,
    and no current/differing comparison is attempted.
    """

    project_id: str
    node_id: str
    revision_id: str
    mode: str
    packet: dict[str, Any] | None
    current_revision_id: str = ""
    run_id: str | None = None
    stage: str | None = None
    recorded_packets: tuple[dict[str, Any], ...] = ()
    drift: dict[str, Any] | None = None

    @property
    def summary(self) -> dict[str, Any]:
        if self.packet is None:
            return {"kind": None, "packet_sha256": None, "packet_bytes": 0}
        return _packet_summary(self.packet)

    def to_dict(self, *, include_packet: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema": CONTEXT_VIEW_SCHEMA,
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "current_revision_id": self.current_revision_id or self.revision_id,
            "same_revision": (
                (self.current_revision_id or self.revision_id) == self.revision_id
            ),
            "mode": self.mode,
            "read_only": True,
            "run_id": self.run_id,
            "stage": self.stage,
            "summary": self.summary,
            "recorded_packets": list(self.recorded_packets),
            "drift": self.drift,
        }
        if include_packet:
            data["packet"] = self.packet
        return data


def _checkpoint_for_stage(
    store: ProjectStore, project_id: str, node_id: str, stage: str, revision_id: str,
) -> StageCheckpoint:
    path = store.checkpoint_path(project_id, node_id, stage)
    checkpoint = store._parse(path, StageCheckpoint.from_dict)
    if (
        checkpoint.project_id != project_id
        or checkpoint.node_id != node_id
        or checkpoint.stage != stage
    ):
        raise ContextViewError(f"{path}: checkpoint identity does not match its path")
    if checkpoint.revision_id != revision_id:
        raise ContextViewError(
            f"stage {stage} belongs to revision {checkpoint.revision_id}, "
            f"not the current revision {revision_id}"
        )
    return checkpoint


def _read_run_packet(
    store: ProjectStore, project_id: str, run_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Read one run's recorded packet and the identity fields next to it."""
    run_dir = store.project_dir(project_id) / "runs" / run_id
    if not run_dir.is_dir():
        raise ContextViewError(f"run not found: {run_dir}")
    try:
        payload = json.loads((run_dir / "project-input.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextViewError(f"cannot read {run_dir / 'project-input.json'}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContextViewError(f"{run_dir / 'project-input.json'}: not a JSON object")
    identity = {
        "run_id": run_id,
        "project_id": payload.get("project_id"),
        "node_id": payload.get("node_id"),
        "revision_id": payload.get("revision_id"),
        "stage": payload.get("stage"),
        "attempt_id": payload.get("attempt_id"),
    }
    raw = payload.get("context_packet")
    if raw is None:
        return None, identity
    if not isinstance(raw, dict):
        raise ContextViewError(f"run {run_id}: context_packet must be an object")
    try:
        packet = ContextPacket.from_dict(raw)
    except (ValueError, ProjectValidationError) as exc:
        raise ContextViewError(f"run {run_id}: invalid context packet: {exc}") from exc
    if (
        packet.project_id != project_id
        or packet.node_id != identity["node_id"]
        or packet.revision_id != identity["revision_id"]
    ):
        raise ContextViewError(
            f"run {run_id}: context packet identity does not match its project-input"
        )
    return packet.to_dict(), identity


def _recorded_runs_for_revision(
    store: ProjectStore, project_id: str, node_id: str, revision_id: str,
) -> list[dict[str, Any]]:
    """Summarise packets recorded by runs of one node revision."""
    rows: list[dict[str, Any]] = []
    runs_dir = store.project_dir(project_id) / "runs"
    if not runs_dir.is_dir():
        return rows
    for path in sorted(runs_dir.iterdir()):
        input_path = path / "project-input.json"
        if not path.is_dir() or not input_path.is_file():
            continue
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            not isinstance(payload, dict)
            or payload.get("node_id") != node_id
            or payload.get("revision_id") != revision_id
        ):
            continue
        raw = payload.get("context_packet")
        if not isinstance(raw, dict):
            continue
        summary = _packet_summary(raw)
        rows.append({
            "run_id": path.name,
            "stage": payload.get("stage"),
            "attempt_id": payload.get("attempt_id"),
            "packet_sha256": summary["packet_sha256"],
            "packet_bytes": summary["packet_bytes"],
            "kind": summary["kind"],
        })
    rows.sort(key=lambda row: (
        DEFAULT_STAGES.index(row["stage"]) if row["stage"] in DEFAULT_STAGES else 99,
        row["run_id"],
    ))
    return rows


def _drift(
    current: dict[str, Any], recorded: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if recorded is None:
        return None
    current_summary = _packet_summary(current)
    recorded_summary = _packet_summary(recorded)
    differences: dict[str, Any] = {}
    if current_summary["kind"] != recorded_summary["kind"]:
        differences["kind"] = {
            "current": current_summary["kind"], "recorded": recorded_summary["kind"],
        }
    current_world = current_summary.get("world")
    recorded_world = recorded_summary.get("world")
    if (current_world is None) != (recorded_world is None):
        differences["world"] = {
            "current": current_world is not None,
            "recorded": recorded_world is not None,
        }
    elif current_world is not None and recorded_world is not None:
        if current_world["binding_id"] != recorded_world["binding_id"]:
            differences["binding_id"] = {
                "current": current_world["binding_id"],
                "recorded": recorded_world["binding_id"],
            }
        current_refs = {
            (row.get("record_type"), row.get("id")): row.get("content_version")
            for row in current_world["references"]
        }
        recorded_refs = {
            (row.get("record_type"), row.get("id")): row.get("content_version")
            for row in recorded_world["references"]
        }
        added = sorted(key for key in current_refs if key not in recorded_refs)
        removed = sorted(key for key in recorded_refs if key not in current_refs)
        changed = sorted(
            key for key in current_refs
            if key in recorded_refs and current_refs[key] != recorded_refs[key]
        )
        if added or removed or changed:
            differences["references"] = {
                "added": [list(row) for row in added],
                "removed": [list(row) for row in removed],
                "changed": [list(row) for row in changed],
            }
        if current_world["canon_entries"] != recorded_world["canon_entries"]:
            differences["canon_entries"] = {
                "current": current_world["canon_entries"],
                "recorded": recorded_world["canon_entries"],
            }
        if current_world["omitted_canon_count"] != recorded_world["omitted_canon_count"]:
            differences["omitted_canon_count"] = {
                "current": current_world["omitted_canon_count"],
                "recorded": recorded_world["omitted_canon_count"],
            }
    current_ancestors = {
        row["node_id"]: row["revision_id"] for row in current_summary["ancestors"]
    }
    recorded_ancestors = {
        row["node_id"]: row["revision_id"] for row in recorded_summary["ancestors"]
    }
    if current_ancestors != recorded_ancestors:
        differences["ancestors"] = {
            "current": current_ancestors, "recorded": recorded_ancestors,
        }
    return {
        "recorded_packet_sha256": recorded_summary["packet_sha256"],
        "current_packet_sha256": current_summary["packet_sha256"],
        "recorded_packet_bytes": recorded_summary["packet_bytes"],
        "current_packet_bytes": current_summary["packet_bytes"],
        "differs": bool(differences),
        "differences": differences,
    }


def build_context_view(
    store: ProjectStore, project_id: str, node_id: str | None = None, *,
    run_id: str | None = None, stage: str | None = None,
) -> ContextView:
    """Read the current or a recorded packet without generating anything."""
    if run_id is not None and stage is not None:
        raise ContextViewError("specify only one of run_id and stage")
    if stage is not None and stage not in DEFAULT_STAGES:
        raise ContextViewError(
            f"unknown stage {stage!r}; expected one of {', '.join(DEFAULT_STAGES)}"
        )
    snapshot = store.load_node_snapshot(project_id, node_id)
    current_revision_id = snapshot.revision.id

    selected_run: str | None = None
    if stage is not None:
        checkpoint = _checkpoint_for_stage(
            store, project_id, snapshot.root_node.id, stage, current_revision_id,
        )
        if checkpoint.run_id is None:
            raise ContextViewError(
                f"stage {stage} has no run yet (status {checkpoint.status})"
            )
        selected_run = checkpoint.run_id
    elif run_id is not None:
        selected_run = run_id

    if selected_run is None:
        packet = build_context_packet(store, project_id, snapshot.root_node.id)
        current_packet = packet.to_dict() if packet is not None else None
        return ContextView(
            project_id=project_id,
            node_id=snapshot.root_node.id,
            revision_id=current_revision_id,
            current_revision_id=current_revision_id,
            mode="current",
            packet=current_packet,
            recorded_packets=tuple(_recorded_runs_for_revision(
                store, project_id, snapshot.root_node.id, current_revision_id,
            )),
        )

    recorded_packet, identity = _read_run_packet(store, project_id, selected_run)
    if identity["project_id"] != project_id:
        raise ContextViewError(
            f"run {selected_run} belongs to project {identity['project_id']!r}"
        )
    if identity["node_id"] not in (None, snapshot.root_node.id):
        raise ContextViewError(
            f"run {selected_run} belongs to node {identity['node_id']!r}"
        )
    packet_revision_id = identity["revision_id"] or current_revision_id
    current_packet: dict[str, Any] | None = None
    drift: dict[str, Any] | None = None
    if packet_revision_id == current_revision_id:
        packet = build_context_packet(store, project_id, snapshot.root_node.id)
        current_packet = packet.to_dict() if packet is not None else None
        drift = _drift(current_packet, recorded_packet) if current_packet else None
    return ContextView(
        project_id=project_id,
        node_id=snapshot.root_node.id,
        revision_id=packet_revision_id,
        current_revision_id=current_revision_id,
        mode="recorded",
        packet=recorded_packet,
        run_id=selected_run,
        stage=identity.get("stage"),
        recorded_packets=tuple(_recorded_runs_for_revision(
            store, project_id, snapshot.root_node.id, packet_revision_id,
        )),
        drift=drift,
    )
