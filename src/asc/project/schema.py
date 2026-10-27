"""Validation for the versioned creative-project records.

The project store deliberately uses JSON rather than a database in its first
increment.  Every persisted top-level record carries ``record_type`` and
``schema_version`` so an incompatible file cannot be mistaken for a current
project.  This module has no model imports, keeping validation usable by both
the models and external tooling.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
PROJECT_RECORD = "work_project"
NODE_RECORD = "work_node"
REVISION_RECORD = "work_node_revision"
LINK_RECORD = "work_link"
CHECKPOINT_RECORD = "stage_checkpoint"
STAGE_STATUSES = {
    "pending", "ready", "running", "waiting_response", "done", "failed",
    "stale", "skipped",
}

#: Kinds of revision derived from earlier content instead of a fresh run.
DERIVED_KINDS = {"revise", "branch"}
DERIVED_FIELDS = {
    "kind", "source_node_id", "source_revision_id", "source_runs",
    "chapters", "design",
}

_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,62}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ProjectValidationError(ValueError):
    """A project record or creation argument violates the current schema."""


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectValidationError(f"{field} must be a JSON object")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{field} must be a non-empty string")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProjectValidationError(f"{field} must be a positive integer")
    return value


def validate_id(value: Any, field: str = "id") -> str:
    """Return a path-safe stable id, or raise a validation error."""
    value = _nonempty(value, field)
    if not _ID_RE.fullmatch(value):
        raise ProjectValidationError(
            f"{field} must match [a-z0-9][a-z0-9._-]{{0,62}}: {value!r}"
        )
    return value


def _optional_id(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return validate_id(value, field)


def _timestamp(value: Any, field: str) -> str:
    value = _nonempty(value, field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    return value


def _header(data: dict[str, Any], record_type: str) -> None:
    if data.get("record_type") != record_type:
        raise ProjectValidationError(
            f"record_type must be {record_type!r}, got {data.get('record_type')!r}"
        )
    version = data.get("schema_version")
    if isinstance(version, bool) or version != SCHEMA_VERSION:
        raise ProjectValidationError(
            f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}"
        )


def canonical_json(data: Any) -> str:
    """Encode canonical JSON for content hashes and persisted-value comparisons."""
    try:
        return json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProjectValidationError(f"value is not canonical JSON data: {exc}") from exc


def spec_sha256(spec: dict[str, Any]) -> str:
    """Hash the complete generation specification, not just its premise."""
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()


def validate_spec(data: Any) -> None:
    data = _mapping(data, "spec")
    for field in ("title", "premise", "language", "form"):
        _nonempty(data.get(field), f"spec.{field}")
    _positive_int(data.get("chapter_count"), "spec.chapter_count")
    _positive_int(data.get("target_chars_per_chapter"), "spec.target_chars_per_chapter")
    options = _mapping(data.get("options", {}), "spec.options")
    canonical_json(options)


def validate_project(data: Any) -> None:
    data = _mapping(data, "project")
    _header(data, PROJECT_RECORD)
    validate_id(data.get("id"), "project.id")
    validate_id(data.get("root_node_id"), "project.root_node_id")
    _nonempty(data.get("title"), "project.title")
    _timestamp(data.get("created_at"), "project.created_at")
    _timestamp(data.get("updated_at"), "project.updated_at")


def validate_node(data: Any) -> None:
    data = _mapping(data, "node")
    _header(data, NODE_RECORD)
    validate_id(data.get("id"), "node.id")
    validate_id(data.get("project_id"), "node.project_id")
    _optional_id(data.get("parent_id"), "node.parent_id")
    _nonempty(data.get("kind"), "node.kind")
    validate_id(data.get("current_revision_id"), "node.current_revision_id")
    _timestamp(data.get("created_at"), "node.created_at")
    _timestamp(data.get("updated_at"), "node.updated_at")


def validate_artifact(data: Any, field: str = "artifact") -> None:
    data = _mapping(data, field)
    validate_id(data.get("artifact_id"), f"{field}.artifact_id")
    path = _nonempty(data.get("path"), f"{field}.path")
    if "\\" in path or PurePosixPath(path).is_absolute():
        raise ProjectValidationError(f"{field}.path must be a relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise ProjectValidationError(f"{field}.path contains an unsafe path component")
    digest = data.get("sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ProjectValidationError(f"{field}.sha256 must be 64 lowercase hex characters")
    _nonempty(data.get("media_type"), f"{field}.media_type")
    producer = data.get("producer_run_id")
    if producer is not None:
        _nonempty(producer, f"{field}.producer_run_id")


def validate_revision(data: Any) -> None:
    data = _mapping(data, "revision")
    _header(data, REVISION_RECORD)
    validate_id(data.get("id"), "revision.id")
    validate_id(data.get("node_id"), "revision.node_id")
    validate_id(data.get("project_id"), "revision.project_id")
    parent_revision_id = _optional_id(
        data.get("parent_revision_id"), "revision.parent_revision_id",
    )
    parent_runs = _mapping(data.get("parent_runs", {}), "revision.parent_runs")
    if parent_runs and parent_revision_id is None:
        raise ProjectValidationError("revision.parent_runs requires parent_revision_id")
    for stage, run_id in parent_runs.items():
        validate_id(stage, "revision.parent_runs stage")
        validate_id(run_id, f"revision.parent_runs.{stage}")
    _timestamp(data.get("created_at"), "revision.created_at")
    spec = _mapping(data.get("spec"), "revision.spec")
    validate_spec(spec)
    recorded_hash = data.get("spec_sha256")
    if not isinstance(recorded_hash, str) or not _SHA256_RE.fullmatch(recorded_hash):
        raise ProjectValidationError("revision.spec_sha256 must be 64 lowercase hex characters")
    if recorded_hash != spec_sha256(spec):
        raise ProjectValidationError("revision.spec_sha256 does not match revision.spec")
    if data.get("derived") is not None:
        validate_derived(data["derived"], "revision.derived")
    if data.get("continuation_design") is not None:
        if parent_revision_id is None:
            raise ProjectValidationError(
                "revision.continuation_design requires parent_revision_id"
            )
        design_values = data["continuation_design"]
        if not isinstance(design_values, list):
            raise ProjectValidationError(
                "revision.continuation_design must be a list"
            )
        seen_design: set[str] = set()
        for index, value in enumerate(design_values):
            validate_id(value, f"revision.continuation_design[{index}]")
            if value in seen_design:
                raise ProjectValidationError(
                    f"revision.continuation_design repeats {value}"
                )
            seen_design.add(value)
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ProjectValidationError("revision.artifacts must be a list")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        validate_artifact(artifact, f"revision.artifacts[{index}]")
        artifact_id = artifact["artifact_id"]
        path = artifact["path"]
        if artifact_id in artifact_ids:
            raise ProjectValidationError(f"duplicate artifact_id: {artifact_id}")
        if path in artifact_paths:
            raise ProjectValidationError(f"duplicate artifact path: {path}")
        artifact_ids.add(artifact_id)
        artifact_paths.add(path)


def validate_derived(data: Any, field: str = "derived") -> dict[str, Any]:
    """Validate the provenance of a revision carried over from older content.

    A ``revise`` keeps the same node and names the revision it was derived from
    as ``parent_revision_id``.  A ``branch`` starts a new node, so it records
    the source node and revision here instead.  Both list the chapters and
    design documents that may be regenerated; everything else is carried
    byte-for-byte from the source runs.
    """
    data = _mapping(data, field)
    unknown = sorted(set(data) - DERIVED_FIELDS)
    if unknown:
        raise ProjectValidationError(f"{field} has unknown fields: {', '.join(unknown)}")
    kind = _nonempty(data.get("kind"), f"{field}.kind")
    if kind not in DERIVED_KINDS:
        raise ProjectValidationError(
            f"{field}.kind must be one of {', '.join(sorted(DERIVED_KINDS))}"
        )
    validate_id(data.get("source_node_id"), f"{field}.source_node_id")
    validate_id(data.get("source_revision_id"), f"{field}.source_revision_id")
    runs = _mapping(data.get("source_runs") or {}, f"{field}.source_runs")
    for stage, run_id in runs.items():
        validate_id(stage, f"{field}.source_runs stage")
        validate_id(run_id, f"{field}.source_runs.{stage}")
    for key in ("chapters", "design"):
        values = data.get(key) or []
        if not isinstance(values, list):
            raise ProjectValidationError(f"{field}.{key} must be a list")
        seen: set[str] = set()
        for index, value in enumerate(values):
            validate_id(value, f"{field}.{key}[{index}]")
            if value in seen:
                raise ProjectValidationError(f"{field}.{key} repeats {value}")
            seen.add(value)
    return data


def validate_link(data: Any) -> None:
    data = _mapping(data, "link")
    _header(data, LINK_RECORD)
    validate_id(data.get("id"), "link.id")
    validate_id(data.get("project_id"), "link.project_id")
    parent_id = validate_id(data.get("parent_node_id"), "link.parent_node_id")
    child_id = validate_id(data.get("child_node_id"), "link.child_node_id")
    if parent_id == child_id:
        raise ProjectValidationError("link parent and child must differ")
    validate_id(data.get("child_revision_id"), "link.child_revision_id")
    _positive_int(data.get("order"), "link.order")
    content_version = data.get("content_version")
    if not isinstance(content_version, str) or not _SHA256_RE.fullmatch(content_version):
        raise ProjectValidationError("link.content_version must be 64 lowercase hex characters")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ProjectValidationError("link.artifacts must be a list")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        validate_artifact(artifact, f"link.artifacts[{index}]")
        if artifact["artifact_id"] in artifact_ids:
            raise ProjectValidationError(f"duplicate artifact_id: {artifact['artifact_id']}")
        if artifact["path"] in artifact_paths:
            raise ProjectValidationError(f"duplicate artifact path: {artifact['path']}")
        artifact_ids.add(artifact["artifact_id"])
        artifact_paths.add(artifact["path"])
    _timestamp(data.get("created_at"), "link.created_at")
    _timestamp(data.get("updated_at"), "link.updated_at")


def validate_checkpoint(data: Any) -> None:
    data = _mapping(data, "checkpoint")
    _header(data, CHECKPOINT_RECORD)
    validate_id(data.get("project_id"), "checkpoint.project_id")
    validate_id(data.get("node_id"), "checkpoint.node_id")
    validate_id(data.get("revision_id"), "checkpoint.revision_id")
    validate_id(data.get("stage"), "checkpoint.stage")
    validate_id(data.get("attempt_id"), "checkpoint.attempt_id")
    status = data.get("status")
    if status not in STAGE_STATUSES:
        raise ProjectValidationError(f"checkpoint.status is unknown: {status!r}")
    run_id = _optional_id(data.get("run_id"), "checkpoint.run_id")
    if status in {"running", "waiting_response", "done", "failed"} and run_id is None:
        raise ProjectValidationError(f"checkpoint.run_id is required when status is {status}")
    seed = data.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ProjectValidationError("checkpoint.seed must be an integer")
    temperature = data.get("temperature")
    if temperature is not None and (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not math.isfinite(temperature)
    ):
        raise ProjectValidationError("checkpoint.temperature must be a finite number")
    _optional_id(data.get("resume_of"), "checkpoint.resume_of")
    _optional_id(data.get("retry_of"), "checkpoint.retry_of")
    pending = data.get("pending")
    if status == "waiting_response":
        pending = _mapping(pending, "checkpoint.pending")
        _nonempty(pending.get("key"), "checkpoint.pending.key")
        _nonempty(pending.get("response_path"), "checkpoint.pending.response_path")
        for field in ("request_path", "prompt_hash", "purpose"):
            if pending.get(field) is not None:
                _nonempty(pending[field], f"checkpoint.pending.{field}")
    elif pending is not None:
        raise ProjectValidationError("checkpoint.pending is only valid while waiting_response")
    _timestamp(data.get("created_at"), "checkpoint.created_at")
    _timestamp(data.get("updated_at"), "checkpoint.updated_at")
    error = data.get("error")
    if status == "failed":
        _nonempty(error, "checkpoint.error")
    elif error is not None:
        raise ProjectValidationError("checkpoint.error is only valid for a failed checkpoint")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ProjectValidationError("checkpoint.artifacts must be a list")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        validate_artifact(artifact, f"checkpoint.artifacts[{index}]")
        if artifact["artifact_id"] in artifact_ids:
            raise ProjectValidationError(f"duplicate artifact_id: {artifact['artifact_id']}")
        if artifact["path"] in artifact_paths:
            raise ProjectValidationError(f"duplicate artifact path: {artifact['path']}")
        artifact_ids.add(artifact["artifact_id"])
        artifact_paths.add(artifact["path"])
