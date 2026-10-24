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
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from .model import (
    ArtifactRef,
    ProjectSnapshot,
    StageCheckpoint,
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
    validate_node,
    validate_project,
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

    def load_snapshot(self, project_id: str) -> ProjectSnapshot:
        project = self.load_project(project_id)
        node = self.load_node(project_id, project.root_node_id)
        revision = self.load_revision(
            project_id, node.id, node.current_revision_id,
        )
        return ProjectSnapshot(project=project, root_node=node, revision=revision)

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

    def status(self, project_id: str) -> dict[str, Any]:
        """Return a machine-readable summary derived from persisted records."""
        snapshot = self.load_snapshot(project_id)
        project = snapshot.project
        node = snapshot.root_node
        revision = snapshot.revision
        directory = self.project_dir(project_id)
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
        artifacts = sorted(
            str(path.relative_to(directory).as_posix())
            for path in (directory / "artifacts").rglob("*")
            if path.is_file()
        )
        runs_dir = directory / "runs"
        runs = sorted(path.name for path in runs_dir.iterdir() if path.is_dir())
        stage_order = list(DEFAULT_STAGES) + sorted(set(checkpoints) - set(DEFAULT_STAGES))
        artifact_refs = [
            artifact.to_dict()
            for stage in stage_order
            if stage in checkpoints
            for artifact in checkpoints[stage].artifacts
        ]
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
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project.id,
            "title": project.title,
            "state": state,
            "attempt_id": attempt_ids[0] if len(attempt_ids) == 1 else None,
            "root_node_id": node.id,
            "current_revision_id": revision.id,
            "spec_sha256": revision.spec_sha256,
            "spec": revision.spec.to_dict(),
            "created_at": project.created_at,
            "updated_at": max([project.updated_at, node.updated_at, *checkpoint_times]),
            "stages": stages,
            "checkpoints": {
                stage: checkpoints[stage].to_dict()
                for stage in stage_order
                if stage in checkpoints
            },
            "artifacts": artifacts,
            "artifact_refs": artifact_refs,
            "runs": runs,
            "project_dir": str(directory),
        }
