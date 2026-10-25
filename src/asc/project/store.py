"""Atomic JSON storage for creative projects.

There is intentionally one writer at a time.  Readers never take the lock:
small current-state files are replaced atomically, and a new project is built
in a temporary directory before it becomes visible at its final path.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from .model import (
    ArtifactRef,
    ProjectSnapshot,
    StageCheckpoint,
    WorkLink,
    WorkNode,
    WorkNodeRevision,
    WorkProject,
    WorkSpec,
    new_id,
    utc_now,
)
from .schema import (
    SCHEMA_VERSION,
    ProjectValidationError,
    validate_checkpoint,
    validate_id,
    validate_link,
    validate_node,
    validate_project,
    validate_revision,
    validate_spec,
)

DEFAULT_STAGES = ("plan", "design", "draft")
T = TypeVar("T")


class ProjectError(Exception):
    """Base class for project storage failures."""


class ProjectNotFoundError(ProjectError):
    """The requested project, node, or revision does not exist."""


class ProjectExistsError(ProjectError):
    """A project with the requested stable id already exists."""


class ProjectLockError(ProjectError):
    """Another writer currently holds the project's non-blocking lock."""


class ProjectCorruptError(ProjectError):
    """A persisted file is invalid or its cross-record links are inconsistent."""


def _fsync_directory(path: Path) -> None:
    """Best-effort directory sync after an atomic rename."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:  # pragma: no cover - platform/filesystem dependent
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover - platform/filesystem dependent
        pass
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write one complete JSON document and atomically replace ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = json.dumps(
            data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ProjectValidationError(f"{path}: value is not JSON data: {exc}") from exc
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class ProjectStore:
    """Store projects below a root such as ``runs/projects``."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def project_dir(self, project_id: str) -> Path:
        return self.root / validate_id(project_id, "project_id")

    def node_dir(self, project_id: str, node_id: str) -> Path:
        return self.project_dir(project_id) / "nodes" / validate_id(node_id, "node_id")

    def revision_path(self, project_id: str, node_id: str, revision_id: str) -> Path:
        return (
            self.node_dir(project_id, node_id)
            / "revisions"
            / f"{validate_id(revision_id, 'revision_id')}.json"
        )

    def checkpoint_path(self, project_id: str, node_id: str, stage: str) -> Path:
        return (
            self.node_dir(project_id, node_id)
            / "checkpoints"
            / f"{validate_id(stage, 'stage')}.json"
        )

    def link_path(self, project_id: str, parent_node_id: str, link_id: str) -> Path:
        return (
            self.node_dir(project_id, parent_node_id)
            / "links"
            / f"{validate_id(link_id, 'link_id')}.json"
        )

    @staticmethod
    @contextmanager
    def _exclusive_lock(path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = path.open("a+", encoding="utf-8")
        except OSError as exc:
            raise ProjectError(f"cannot open project lock {path}: {exc}") from exc
        locked = False
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError as exc:
                raise ProjectLockError(f"project is locked by another writer: {path}") from exc
            yield
        finally:
            if locked:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    @contextmanager
    def writer_lock(self, project_id: str) -> Iterator[None]:
        """Hold the project's single-writer lock without blocking."""
        directory = self.project_dir(project_id)
        if not directory.is_dir():
            raise ProjectNotFoundError(f"project not found: {project_id}")
        with self._exclusive_lock(directory / ".lock"):
            yield

    @contextmanager
    def execution_lock(self, project_id: str) -> Iterator[None]:
        """Serialize whole generation attempts without blocking status readers."""
        directory = self.project_dir(project_id)
        if not directory.is_dir():
            raise ProjectNotFoundError(f"project not found: {project_id}")
        with self._exclusive_lock(directory / ".execution.lock"):
            yield

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProjectNotFoundError(f"project record not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectCorruptError(f"cannot read project record {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ProjectCorruptError(f"{path}: top level must be a JSON object")
        return data

    @staticmethod
    def _parse(path: Path, parser: Callable[[dict[str, Any]], T]) -> T:
        data = ProjectStore._read_json(path)
        try:
            return parser(data)
        except ProjectValidationError as exc:
            raise ProjectCorruptError(f"{path}: {exc}") from exc

    def create_project(
        self, spec: WorkSpec, *, project_id: str | None = None,
    ) -> ProjectSnapshot:
        """Create a root work and its first immutable revision.

        The final project directory appears only after all initial records have
        been written.  Existing projects are never overwritten.
        """
        validate_spec(spec.to_dict())
        project_id = project_id or new_id("prj")
        validate_id(project_id, "project_id")
        self.root.mkdir(parents=True, exist_ok=True)
        final_dir = self.project_dir(project_id)
        creation_lock = self.root / ".locks" / f"{project_id}.lock"
        with self._exclusive_lock(creation_lock):
            if final_dir.exists():
                raise ProjectExistsError(f"project already exists: {project_id}")
            temporary_dir = Path(tempfile.mkdtemp(
                prefix=f".{project_id}.tmp-", dir=self.root,
            ))
            try:
                timestamp = utc_now()
                root_node_id = new_id("node")
                revision_id = new_id("rev")
                project = WorkProject(
                    id=project_id,
                    root_node_id=root_node_id,
                    title=spec.title,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                node = WorkNode(
                    id=root_node_id,
                    project_id=project_id,
                    parent_id=None,
                    kind="story",
                    current_revision_id=revision_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                revision = WorkNodeRevision.create(
                    revision_id=revision_id,
                    node_id=root_node_id,
                    project_id=project_id,
                    spec=spec,
                    created_at=timestamp,
                )
                node_dir = temporary_dir / "nodes" / root_node_id
                (node_dir / "checkpoints").mkdir(parents=True)
                (temporary_dir / "artifacts").mkdir()
                (temporary_dir / "runs").mkdir()
                _atomic_write_json(temporary_dir / "project.json", project.to_dict())
                _atomic_write_json(node_dir / "current.json", node.to_dict())
                _atomic_write_json(
                    node_dir / "revisions" / f"{revision_id}.json", revision.to_dict(),
                )
                if final_dir.exists():  # defensive: writers are expected to use the lock
                    raise ProjectExistsError(f"project already exists: {project_id}")
                os.replace(temporary_dir, final_dir)
                _fsync_directory(self.root)
            except Exception:
                shutil.rmtree(temporary_dir, ignore_errors=True)
                raise
        return ProjectSnapshot(project=project, root_node=node, revision=revision)

    def load_project(self, project_id: str) -> WorkProject:
        directory = self.project_dir(project_id)
        if not directory.is_dir():
            raise ProjectNotFoundError(f"project not found: {project_id}")
        project = self._parse(directory / "project.json", WorkProject.from_dict)
        if project.id != project_id:
            raise ProjectCorruptError(
                f"{directory / 'project.json'}: id does not match directory name"
            )
        return project

    def load_node(self, project_id: str, node_id: str) -> WorkNode:
        self.load_project(project_id)
        path = self.node_dir(project_id, node_id) / "current.json"
        node = self._parse(path, WorkNode.from_dict)
        if node.id != node_id or node.project_id != project_id:
            raise ProjectCorruptError(f"{path}: node identity does not match its path")
        return node

    def load_revision(
        self, project_id: str, node_id: str, revision_id: str,
    ) -> WorkNodeRevision:
        path = self.revision_path(project_id, node_id, revision_id)
        revision = self._parse(path, WorkNodeRevision.from_dict)
        if (
            revision.id != revision_id
            or revision.node_id != node_id
            or revision.project_id != project_id
        ):
            raise ProjectCorruptError(f"{path}: revision identity does not match its path")
        return revision

    def load_node_snapshot(
        self, project_id: str, node_id: str | None = None,
    ) -> ProjectSnapshot:
        project = self.load_project(project_id)
        node = self.load_node(project_id, node_id or project.root_node_id)
        revision = self.load_revision(
            project_id, node.id, node.current_revision_id,
        )
        return ProjectSnapshot(project=project, root_node=node, revision=revision)

    def load_snapshot(self, project_id: str) -> ProjectSnapshot:
        return self.load_node_snapshot(project_id)

    def list_revisions(self, project_id: str, node_id: str) -> list[WorkNodeRevision]:
        """Read all immutable revisions for a node in creation order."""
        self.load_node(project_id, node_id)
        revision_dir = self.node_dir(project_id, node_id) / "revisions"
        revisions = []
        for path in sorted(revision_dir.glob("*.json")):
            revision = self._parse(path, WorkNodeRevision.from_dict)
            if (
                revision.id != path.stem
                or revision.node_id != node_id
                or revision.project_id != project_id
            ):
                raise ProjectCorruptError(f"{path}: revision identity does not match its path")
            revisions.append(revision)
        return sorted(revisions, key=lambda item: (item.created_at, item.id))

    def _validate_link_relationship(self, link: WorkLink) -> WorkNodeRevision:
        validate_link(link.to_dict())
        project = self.load_project(link.project_id)
        parent = self.load_node(link.project_id, link.parent_node_id)
        child = self.load_node(link.project_id, link.child_node_id)
        if (
            parent.id != project.root_node_id
            or parent.parent_id is not None
            or child.parent_id != parent.id
            or child.kind != "embedded_work"
        ):
            raise ProjectValidationError(
                "only depth-one embedded_work links below the root node are allowed"
            )
        revision = self.load_revision(
            link.project_id, child.id, link.child_revision_id,
        )
        expected = WorkLink.version_for(revision, link.artifacts)
        if expected != link.content_version:
            raise ProjectValidationError(
                f"link {link.id}: content_version does not match its pinned artifacts"
            )
        for artifact in link.artifacts:
            run_id = artifact.producer_run_id
            if not run_id or not artifact.path.startswith(f"runs/{run_id}/"):
                raise ProjectValidationError(
                    f"link {link.id}: artifact is not tied to its producer run"
                )
            run_dir = self.project_dir(link.project_id) / "runs" / run_id
            manifest = self._read_json(run_dir / "manifest.json")
            run_input = self._read_json(run_dir / "project-input.json")
            if (
                manifest.get("status") != "ok"
                or manifest.get("task_id") != child.id
                or run_input.get("node_id") != child.id
                or run_input.get("revision_id") != revision.id
                or run_input.get("stage") != "draft"
            ):
                raise ProjectValidationError(
                    f"link {link.id}: artifact does not belong to the pinned child draft"
                )
        return revision

    def load_link(self, project_id: str, parent_node_id: str, link_id: str) -> WorkLink:
        path = self.link_path(project_id, parent_node_id, link_id)
        link = self._parse(path, WorkLink.from_dict)
        if (
            link.id != link_id
            or link.project_id != project_id
            or link.parent_node_id != parent_node_id
        ):
            raise ProjectCorruptError(f"{path}: link identity does not match its path")
        self._validate_link_relationship(link)
        return link

    def list_links(
        self, project_id: str, parent_node_id: str | None = None,
    ) -> list[WorkLink]:
        project = self.load_project(project_id)
        parent_id = parent_node_id or project.root_node_id
        self.load_node(project_id, parent_id)
        directory = self.node_dir(project_id, parent_id) / "links"
        if not directory.is_dir():
            return []
        links = [
            self.load_link(project_id, parent_id, path.stem)
            for path in sorted(directory.glob("*.json"))
        ]
        return sorted(links, key=lambda item: (item.order, item.id))

    def create_child(
        self, project_id: str, spec: WorkSpec, *, parent_node_id: str | None = None,
        order: int | None = None, child_node_id: str | None = None,
        link_id: str | None = None,
    ) -> WorkLink:
        """Create one independent child node and an ordered root link."""
        validate_spec(spec.to_dict())
        project = self.load_project(project_id)
        parent_id = parent_node_id or project.root_node_id
        parent = self.load_node(project_id, parent_id)
        if parent.id != project.root_node_id or parent.parent_id is not None:
            raise ProjectValidationError("PR 5 allows children only directly below the root")
        child_id = child_node_id or new_id("node")
        validate_id(child_id, "child_node_id")
        link_id = link_id or new_id("link")
        validate_id(link_id, "link_id")
        with self.writer_lock(project_id):
            links = self.list_links(project_id, parent_id)
            if order is None:
                order = max((link.order for link in links), default=0) + 1
            if isinstance(order, bool) or not isinstance(order, int) or order < 1:
                raise ProjectValidationError("child order must be a positive integer")
            if any(link.order == order for link in links):
                raise ProjectValidationError(f"child order is already used: {order}")
            if any(link.id == link_id for link in links):
                raise ProjectExistsError(f"link already exists: {link_id}")
            child_dir = self.node_dir(project_id, child_id)
            if child_dir.exists():
                raise ProjectExistsError(f"node already exists: {child_id}")
            timestamp = utc_now()
            revision = WorkNodeRevision.create(
                revision_id=new_id("rev"), node_id=child_id, project_id=project_id,
                spec=spec, created_at=timestamp,
            )
            child = WorkNode(
                id=child_id, project_id=project_id, parent_id=parent_id,
                kind="embedded_work", current_revision_id=revision.id,
                created_at=timestamp, updated_at=timestamp,
            )
            link = WorkLink(
                id=link_id, project_id=project_id, parent_node_id=parent_id,
                child_node_id=child_id, child_revision_id=revision.id, order=order,
                content_version=WorkLink.version_for(revision, ()),
                created_at=timestamp, updated_at=timestamp,
            )
            nodes_dir = self.project_dir(project_id) / "nodes"
            temporary = Path(tempfile.mkdtemp(prefix=f".{child_id}.tmp-", dir=nodes_dir))
            moved = False
            try:
                (temporary / "revisions").mkdir()
                (temporary / "checkpoints").mkdir()
                _atomic_write_json(temporary / "current.json", child.to_dict())
                _atomic_write_json(
                    temporary / "revisions" / f"{revision.id}.json", revision.to_dict(),
                )
                os.replace(temporary, child_dir)
                moved = True
                self._validate_link_relationship(link)
                _atomic_write_json(self.link_path(project_id, parent_id, link_id), link.to_dict())
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                if moved:
                    shutil.rmtree(child_dir, ignore_errors=True)
                raise
        return link

    def save_link(self, link: WorkLink) -> None:
        """Update only the pinned revision/artifact metadata of an existing link."""
        with self.writer_lock(link.project_id):
            self._validate_link_relationship(link)
            path = self.link_path(link.project_id, link.parent_node_id, link.id)
            if path.exists():
                old = self._parse(path, WorkLink.from_dict)
                immutable = (
                    "id", "project_id", "parent_node_id", "child_node_id", "order", "created_at",
                )
                for field_name in immutable:
                    if getattr(old, field_name) != getattr(link, field_name):
                        raise ProjectValidationError("link identity and order are immutable")
            _atomic_write_json(path, link.to_dict())

    def sync_child_links(
        self, project_id: str, child_node_id: str, revision_id: str,
    ) -> list[WorkLink]:
        """Fill artifact refs for links already pinned to this completed revision."""
        child = self.load_node(project_id, child_node_id)
        if child.current_revision_id != revision_id:
            return []
        revision = self.load_revision(project_id, child_node_id, revision_id)
        checkpoint_path = self.checkpoint_path(project_id, child_node_id, "draft")
        if not checkpoint_path.is_file():
            return []
        checkpoint = self._parse(checkpoint_path, StageCheckpoint.from_dict)
        if checkpoint.status != "done" or checkpoint.revision_id != revision_id:
            return []
        self._verify_done_checkpoint(
            self.project_dir(project_id), checkpoint, revision.spec_sha256,
        )
        updated = []
        with self.writer_lock(project_id):
            for link in self.list_links(project_id):
                if link.child_node_id != child_node_id or link.child_revision_id != revision_id:
                    continue
                new_link = replace(
                    link, artifacts=checkpoint.artifacts,
                    content_version=WorkLink.version_for(revision, checkpoint.artifacts),
                    updated_at=utc_now(),
                )
                _atomic_write_json(
                    self.link_path(project_id, link.parent_node_id, link.id),
                    new_link.to_dict(),
                )
                updated.append(new_link)
        return updated

    def adopt_child(self, project_id: str, link_id: str) -> WorkLink:
        """Explicitly pin a link to the child's current completed revision."""
        with self.execution_lock(project_id):
            project = self.load_project(project_id)
            link = self.load_link(project_id, project.root_node_id, link_id)
            child = self.load_node(project_id, link.child_node_id)
            status = self.status(project_id, child.id)
            if status["state"] != "complete":
                raise ProjectValidationError(
                    f"child {child.id} must be complete before its revision can be adopted"
                )
            revision = self.load_revision(project_id, child.id, child.current_revision_id)
            artifacts = tuple(
                ArtifactRef.from_dict(row)
                for row in status["checkpoints"]["draft"]["artifacts"]
            )
            updated = replace(
                link, child_revision_id=revision.id, artifacts=artifacts,
                content_version=WorkLink.version_for(revision, artifacts), updated_at=utc_now(),
            )
            self.save_link(updated)
            return updated

    def save_revision(self, revision: WorkNodeRevision) -> None:
        """Append an immutable revision and validate its optional parent runs."""
        validate_revision(revision.to_dict())
        with self.writer_lock(revision.project_id):
            path = self.revision_path(
                revision.project_id, revision.node_id, revision.id,
            )
            if path.exists():
                existing = self._read_json(path)
                if existing != revision.to_dict():
                    raise ProjectValidationError("revision records are immutable")
                return
            if revision.parent_revision_id is not None:
                parent = self.load_revision(
                    revision.project_id, revision.node_id, revision.parent_revision_id,
                )
                if parent.id == revision.id:
                    raise ProjectValidationError("revision cannot be its own parent")
                for stage, run_id in revision.parent_runs.items():
                    run_dir = self.project_dir(revision.project_id) / "runs" / run_id
                    manifest = self._read_json(run_dir / "manifest.json")
                    run_input = self._read_json(run_dir / "project-input.json")
                    if (
                        manifest.get("run_id") != run_id
                        or manifest.get("status") != "ok"
                        or manifest.get("task_id") != revision.node_id
                        or run_input.get("revision_id") != parent.id
                        or run_input.get("stage") != stage
                    ):
                        raise ProjectValidationError(
                            f"parent run {run_id} does not belong to revision {parent.id}"
                        )
            _atomic_write_json(path, revision.to_dict())

    def save_project(self, project: WorkProject) -> None:
        """Atomically save project metadata while preserving its root identity."""
        validate_project(project.to_dict())
        with self.writer_lock(project.id):
            existing = self.load_project(project.id)
            if existing.root_node_id != project.root_node_id:
                raise ProjectValidationError("project.root_node_id cannot be changed")
            if existing.created_at != project.created_at:
                raise ProjectValidationError("project.created_at cannot be changed")
            _atomic_write_json(self.project_dir(project.id) / "project.json", project.to_dict())

    def save_node(self, node: WorkNode) -> None:
        """Atomically update a node's current pointer after validating its target."""
        validate_node(node.to_dict())
        with self.writer_lock(node.project_id):
            existing = self.load_node(node.project_id, node.id)
            if existing.created_at != node.created_at:
                raise ProjectValidationError("node.created_at cannot be changed")
            if existing.parent_id != node.parent_id or existing.kind != node.kind:
                raise ProjectValidationError("node.parent_id and node.kind are immutable")
            if node.parent_id is not None:
                project = self.load_project(node.project_id)
                if node.id == project.root_node_id or node.parent_id != project.root_node_id:
                    raise ProjectValidationError(
                        "PR 5 allows only non-root children directly below the root"
                    )
            self.load_revision(node.project_id, node.id, node.current_revision_id)
            _atomic_write_json(
                self.node_dir(node.project_id, node.id) / "current.json", node.to_dict(),
            )

    def save_checkpoint(self, checkpoint: StageCheckpoint) -> None:
        """Atomically persist a stage state for the node's current revision."""
        validate_checkpoint(checkpoint.to_dict())
        with self.writer_lock(checkpoint.project_id):
            node = self.load_node(checkpoint.project_id, checkpoint.node_id)
            if node.current_revision_id != checkpoint.revision_id:
                raise ProjectValidationError(
                    "checkpoint.revision_id is not the node's current revision"
                )
            _atomic_write_json(
                self.checkpoint_path(
                    checkpoint.project_id, checkpoint.node_id, checkpoint.stage,
                ),
                checkpoint.to_dict(),
            )

    @staticmethod
    def _project_file(directory: Path, relative: str) -> Path:
        root = directory.resolve()
        target = (directory / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ProjectCorruptError(f"artifact path escapes the project: {relative}") from exc
        return target

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def artifact_ref(
        self, project_id: str, run_id: str, relative: str, artifact_id: str,
    ) -> ArtifactRef:
        """Reference a final run artifact by project-relative path and content hash."""
        directory = self.project_dir(project_id)
        validate_id(run_id, "run_id")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ProjectValidationError("artifact relative path must stay inside its run")
        project_relative = f"runs/{run_id}/{relative}"
        target = self._project_file(directory, project_relative)
        if not target.is_file():
            raise ProjectNotFoundError(f"run artifact not found: {target}")
        suffix = target.suffix.lower()
        media_type = (
            "application/json" if suffix == ".json"
            else "text/markdown" if suffix in {".md", ".markdown"}
            else "text/plain"
        )
        return ArtifactRef(
            artifact_id=artifact_id,
            path=project_relative,
            sha256=self._sha256_file(target),
            media_type=media_type,
            producer_run_id=run_id,
        )

    def read_artifact(self, project_id: str, artifact: ArtifactRef) -> bytes:
        """Read a pinned artifact only after checking its path and content hash."""
        target = self._project_file(self.project_dir(project_id), artifact.path)
        if not target.is_file():
            raise ProjectNotFoundError(f"artifact is missing: {target}")
        if self._sha256_file(target) != artifact.sha256:
            raise ProjectCorruptError(f"artifact hash differs: {target}")
        return target.read_bytes()

    def _verify_done_checkpoint(
        self, directory: Path, checkpoint: StageCheckpoint, expected_spec_sha256: str,
    ) -> None:
        if checkpoint.run_id is None:  # guarded by schema validation
            raise ProjectCorruptError("done checkpoint has no run_id")
        run_dir = directory / "runs" / checkpoint.run_id
        manifest_path = run_dir / "manifest.json"
        manifest = self._read_json(manifest_path)
        if (
            manifest.get("run_id") != checkpoint.run_id
            or manifest.get("status") != "ok"
            or manifest.get("task_id") != checkpoint.node_id
        ):
            raise ProjectCorruptError(
                f"{manifest_path}: done checkpoint requires an ok manifest for the same node run"
            )
        input_path = run_dir / "project-input.json"
        run_input = self._read_json(input_path)
        expected_input = {
            "project_id": checkpoint.project_id,
            "node_id": checkpoint.node_id,
            "revision_id": checkpoint.revision_id,
            "attempt_id": checkpoint.attempt_id,
            "stage": checkpoint.stage,
            "spec_sha256": expected_spec_sha256,
        }
        for field, expected in expected_input.items():
            if run_input.get(field) != expected:
                raise ProjectCorruptError(
                    f"{input_path}: {field} does not match the current checkpoint"
                )
        for artifact in checkpoint.artifacts:
            if artifact.producer_run_id != checkpoint.run_id:
                raise ProjectCorruptError(
                    f"checkpoint {checkpoint.stage}: artifact producer does not match run_id"
                )
            target = self._project_file(directory, artifact.path)
            if not target.is_file():
                raise ProjectCorruptError(f"checkpoint artifact is missing: {target}")
            if self._sha256_file(target) != artifact.sha256:
                raise ProjectCorruptError(f"checkpoint artifact hash differs: {target}")

    def _run_ids_for_node(self, directory: Path, node_id: str) -> list[str]:
        runs_dir = directory / "runs"
        if not runs_dir.is_dir():
            return []
        runs = []
        for path in sorted(runs_dir.iterdir()):
            if not path.is_dir():
                continue
            owner = None
            input_path = path / "project-input.json"
            if input_path.is_file():
                owner = self._read_json(input_path).get("node_id")
            if owner is None:
                manifest_path = path / "manifest.json"
                if manifest_path.is_file():
                    owner = self._read_json(manifest_path).get("task_id")
            if owner == node_id:
                runs.append(path.name)
        return runs

    def _link_ready(self, project_id: str, link: WorkLink) -> bool:
        if not link.artifacts:
            return False
        for artifact in link.artifacts:
            self.read_artifact(project_id, artifact)
        return True

    def status(
        self, project_id: str, node_id: str | None = None,
    ) -> dict[str, Any]:
        """Return a machine-readable summary for the root or one child node."""
        snapshot = self.load_node_snapshot(project_id, node_id)
        project = snapshot.project
        node = snapshot.root_node
        revision = snapshot.revision
        directory = self.project_dir(project_id)
        revision_records = self.list_revisions(project_id, node.id)
        checkpoint_dir = self.node_dir(project_id, node.id) / "checkpoints"
        stages = {stage: "pending" for stage in DEFAULT_STAGES}
        checkpoints: dict[str, StageCheckpoint] = {}
        if checkpoint_dir.is_dir():
            for path in sorted(checkpoint_dir.glob("*.json")):
                checkpoint = self._parse(path, StageCheckpoint.from_dict)
                if (
                    checkpoint.project_id != project_id
                    or checkpoint.node_id != node.id
                    or checkpoint.revision_id != revision.id
                    or checkpoint.stage != path.stem
                ):
                    raise ProjectCorruptError(f"{path}: checkpoint identity does not match its path")
                if checkpoint.status == "done":
                    self._verify_done_checkpoint(directory, checkpoint, revision.spec_sha256)
                checkpoints[checkpoint.stage] = checkpoint
                stages[checkpoint.stage] = checkpoint.status
        all_artifacts = sorted(
            str(path.relative_to(directory).as_posix())
            for path in (directory / "artifacts").rglob("*")
            if path.is_file()
        )
        artifacts = all_artifacts
        if node.id != project.root_node_id:
            prefix = f"artifacts/{node.id}/"
            artifacts = [path for path in all_artifacts if path.startswith(prefix)]
        runs = self._run_ids_for_node(directory, node.id)
        stage_order = list(DEFAULT_STAGES) + sorted(set(checkpoints) - set(DEFAULT_STAGES))
        artifact_refs = [
            artifact.to_dict()
            for stage in stage_order
            if stage in checkpoints
            for artifact in checkpoints[stage].artifacts
        ]
        pending = []
        for stage in stage_order:
            checkpoint = checkpoints.get(stage)
            if checkpoint is None or checkpoint.status != "waiting_response":
                continue
            details = dict(checkpoint.pending or {})
            response_path = details.get("response_path")
            pending.append({
                "project_id": project_id,
                "node_id": node.id,
                "revision_id": revision.id,
                "attempt_id": checkpoint.attempt_id,
                "stage": stage,
                "run_id": checkpoint.run_id,
                **details,
                "response_ready": bool(
                    response_path and Path(response_path).is_file()
                ),
            })
        values = set(stages.values())
        if all(stages.get(stage) == "done" for stage in DEFAULT_STAGES):
            state = "complete"
        elif "waiting_response" in values:
            state = "waiting_response"
        elif values & {"ready", "running"}:
            state = "in_progress"
        elif "failed" in values:
            state = "failed"
        elif runs or artifacts or artifact_refs or values - {"pending"}:
            state = "in_progress"
        else:
            state = "not_started"
        checkpoint_times = [item.updated_at for item in checkpoints.values()]
        attempt_ids = sorted({item.attempt_id for item in checkpoints.values()})
        latest_attempt = (
            max(checkpoints.values(), key=lambda item: item.updated_at).attempt_id
            if checkpoints else None
        )

        links: list[dict[str, Any]] = []
        children: list[dict[str, Any]] = []
        link_times: list[str] = []
        if node.id == project.root_node_id:
            for link in self.list_links(project_id, node.id):
                child = self.load_node(project_id, link.child_node_id)
                child_status = self.status(project_id, child.id)
                ready = self._link_ready(project_id, link)
                stale = child.current_revision_id != link.child_revision_id
                link_data = link.to_dict()
                link_data.update({
                    "stale": stale,
                    "ready": ready,
                    "state": "stale" if stale else "ready" if ready else "pending",
                    "current_child_revision_id": child.current_revision_id,
                    "child_state": child_status["state"],
                })
                links.append(link_data)
                children.append({
                    "node_id": child.id,
                    "parent_node_id": node.id,
                    "kind": child.kind,
                    "title": child_status["title"],
                    "state": child_status["state"],
                    "current_revision_id": child.current_revision_id,
                    "revision_ids": child_status["revision_ids"],
                    "link_id": link.id,
                    "order": link.order,
                    "stale": stale,
                })
                pending.extend(child_status["pending"])
                link_times.append(link.updated_at)

        title = project.title if node.id == project.root_node_id else revision.spec.title
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project.id,
            "node_id": node.id,
            "parent_node_id": node.parent_id,
            "kind": node.kind,
            "title": title,
            "state": state,
            "attempt_id": latest_attempt,
            "attempt_ids": attempt_ids,
            "root_node_id": project.root_node_id,
            "current_revision_id": revision.id,
            "parent_revision_id": revision.parent_revision_id,
            "parent_runs": dict(sorted(revision.parent_runs.items())),
            "revision_ids": [item.id for item in revision_records],
            "revisions": [
                {
                    "id": item.id,
                    "parent_revision_id": item.parent_revision_id,
                    "parent_runs": dict(sorted(item.parent_runs.items())),
                    "spec_sha256": item.spec_sha256,
                    "chapter_count": item.spec.chapter_count,
                }
                for item in revision_records
            ],
            "spec_sha256": revision.spec_sha256,
            "spec": revision.spec.to_dict(),
            "created_at": project.created_at,
            "updated_at": max([
                project.updated_at, node.updated_at, *checkpoint_times, *link_times,
            ]),
            "stages": stages,
            "checkpoints": {
                stage: checkpoints[stage].to_dict()
                for stage in stage_order
                if stage in checkpoints
            },
            "artifacts": artifacts,
            "artifact_refs": artifact_refs,
            "pending": pending,
            "runs": runs,
            "links": links,
            "children": children,
            "project_dir": str(directory),
        }
