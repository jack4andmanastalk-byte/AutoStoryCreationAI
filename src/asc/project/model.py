"""Typed records for persistent creative projects.

A project points at a root work node.  A node has a mutable *current revision*
pointer, while revision records contain an immutable generation specification
and content-addressed artifact references.  Runs and generated text remain
outside Git under ``runs/projects/``.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .schema import (
    CHECKPOINT_RECORD,
    LINK_RECORD,
    NODE_RECORD,
    PROJECT_RECORD,
    REVISION_RECORD,
    SCHEMA_VERSION,
    canonical_json,
    spec_sha256 as hash_spec,
    validate_artifact,
    validate_checkpoint,
    validate_derived,
    validate_link,
    validate_node,
    validate_project,
    validate_revision,
    validate_spec,
)


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp suitable for a project record."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    """Create an id whose value does not depend on a title or premise."""
    return f"{prefix}-{uuid.uuid4().hex}"


@dataclass(frozen=True)
class WorkSpec:
    """Inputs needed to create one work, independent of a frozen benchmark."""

    title: str
    premise: str
    language: str = "ja"
    chapter_count: int = 3
    target_chars_per_chapter: int = 1600
    form: str = "novel"
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "premise": self.premise,
            "language": self.language,
            "chapter_count": self.chapter_count,
            "target_chars_per_chapter": self.target_chars_per_chapter,
            "form": self.form,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkSpec":
        validate_spec(data)
        return cls(
            title=data["title"],
            premise=data["premise"],
            language=data["language"],
            chapter_count=data["chapter_count"],
            target_chars_per_chapter=data["target_chars_per_chapter"],
            form=data["form"],
            options=dict(data.get("options") or {}),
        )


@dataclass(frozen=True)
class ArtifactRef:
    """A logical artifact version identified by its content SHA-256."""

    artifact_id: str
    path: str
    sha256: str
    media_type: str
    producer_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "producer_run_id": self.producer_run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRef":
        validate_artifact(data)
        return cls(
            artifact_id=data["artifact_id"],
            path=data["path"],
            sha256=data["sha256"],
            media_type=data["media_type"],
            producer_run_id=data.get("producer_run_id"),
        )


@dataclass(frozen=True)
class WorkProject:
    """Project-level identity and the root of its work containment tree."""

    id: str
    root_node_id: str
    title: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": PROJECT_RECORD,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "root_node_id": self.root_node_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkProject":
        validate_project(data)
        return cls(
            id=data["id"],
            root_node_id=data["root_node_id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class WorkNode:
    """A work's stable identity; only its small current record is mutable."""

    id: str
    project_id: str
    parent_id: str | None
    kind: str
    current_revision_id: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": NODE_RECORD,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "kind": self.kind,
            "current_revision_id": self.current_revision_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkNode":
        validate_node(data)
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            parent_id=data.get("parent_id"),
            kind=data["kind"],
            current_revision_id=data["current_revision_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class WorkNodeRevision:
    """An immutable work specification with versioned artifact references."""

    id: str
    node_id: str
    project_id: str
    spec: WorkSpec
    spec_sha256: str
    created_at: str
    parent_revision_id: str | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    parent_runs: dict[str, str] = field(default_factory=dict)
    #: Set when the revision carries an older revision's content forward.
    derived: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        *,
        revision_id: str,
        node_id: str,
        project_id: str,
        spec: WorkSpec,
        created_at: str,
        parent_revision_id: str | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        parent_runs: dict[str, str] | None = None,
        derived: dict[str, Any] | None = None,
    ) -> "WorkNodeRevision":
        revision = cls(
            id=revision_id,
            node_id=node_id,
            project_id=project_id,
            spec=spec,
            spec_sha256=hash_spec(spec.to_dict()),
            created_at=created_at,
            parent_revision_id=parent_revision_id,
            artifacts=artifacts,
            parent_runs=dict(parent_runs or {}),
            derived=dict(derived) if derived is not None else None,
        )
        validate_revision(revision.to_dict())
        return revision

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": REVISION_RECORD,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "node_id": self.node_id,
            "project_id": self.project_id,
            "parent_revision_id": self.parent_revision_id,
            "parent_runs": dict(sorted(self.parent_runs.items())),
            "spec": self.spec.to_dict(),
            "spec_sha256": self.spec_sha256,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "derived": self.derived,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkNodeRevision":
        validate_revision(data)
        return cls(
            id=data["id"],
            node_id=data["node_id"],
            project_id=data["project_id"],
            parent_revision_id=data.get("parent_revision_id"),
            spec=WorkSpec.from_dict(data["spec"]),
            spec_sha256=data["spec_sha256"],
            artifacts=tuple(ArtifactRef.from_dict(row) for row in data["artifacts"]),
            parent_runs=dict(data.get("parent_runs") or {}),
            derived=dict(data["derived"]) if data.get("derived") is not None else None,
            created_at=data["created_at"],
        )


@dataclass(frozen=True)
class WorkLink:
    """A parent's ordered, explicitly pinned reference to a child work.

    The link stores references to the child's draft artifacts, never their
    text.  ``content_version`` covers the pinned revision and artifact hashes;
    a child's newer current revision does not mutate this record.
    """

    id: str
    project_id: str
    parent_node_id: str
    child_node_id: str
    child_revision_id: str
    order: int
    content_version: str
    created_at: str
    updated_at: str
    artifacts: tuple[ArtifactRef, ...] = ()

    @staticmethod
    def version_for(
        revision: "WorkNodeRevision", artifacts: tuple[ArtifactRef, ...],
    ) -> str:
        payload = {
            "node_id": revision.node_id,
            "revision_id": revision.id,
            "spec_sha256": revision.spec_sha256,
            "artifacts": [artifact.to_dict() for artifact in artifacts],
        }
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": LINK_RECORD,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "project_id": self.project_id,
            "parent_node_id": self.parent_node_id,
            "child_node_id": self.child_node_id,
            "child_revision_id": self.child_revision_id,
            "order": self.order,
            "content_version": self.content_version,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkLink":
        validate_link(data)
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            parent_node_id=data["parent_node_id"],
            child_node_id=data["child_node_id"],
            child_revision_id=data["child_revision_id"],
            order=data["order"],
            content_version=data["content_version"],
            artifacts=tuple(ArtifactRef.from_dict(row) for row in data["artifacts"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class StageCheckpoint:
    """The current durable state of one pipeline stage for a node revision."""

    project_id: str
    node_id: str
    revision_id: str
    stage: str
    status: str
    attempt_id: str
    created_at: str
    updated_at: str
    run_id: str | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    error: str | None = None
    seed: int | None = None
    temperature: float | None = None
    resume_of: str | None = None
    #: Set when the stage was started again after a failed attempt.
    retry_of: str | None = None
    pending: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": CHECKPOINT_RECORD,
            "schema_version": SCHEMA_VERSION,
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "stage": self.stage,
            "status": self.status,
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "error": self.error,
            "seed": self.seed,
            "temperature": self.temperature,
            "resume_of": self.resume_of,
            "retry_of": self.retry_of,
            "pending": self.pending,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageCheckpoint":
        validate_checkpoint(data)
        return cls(
            project_id=data["project_id"],
            node_id=data["node_id"],
            revision_id=data["revision_id"],
            stage=data["stage"],
            status=data["status"],
            attempt_id=data["attempt_id"],
            run_id=data.get("run_id"),
            artifacts=tuple(ArtifactRef.from_dict(row) for row in data["artifacts"]),
            error=data.get("error"),
            seed=data.get("seed"),
            temperature=data.get("temperature"),
            resume_of=data.get("resume_of"),
            retry_of=data.get("retry_of"),
            pending=data.get("pending"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class ProjectSnapshot:
    """The project, root node, and currently selected root revision."""

    project: WorkProject
    root_node: WorkNode
    revision: WorkNodeRevision
