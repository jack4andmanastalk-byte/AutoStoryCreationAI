"""Read-only integrity inspection for a creative project.

``ProjectDoctor`` answers one operational question: *is this project still
consistent, and what is waiting or stale right now?*  It never generates,
resumes, adopts a child revision, promotes canon, or repairs a record.  Every
check reads the files that are already on disk; a problem becomes a finding
instead of an exception.

Findings carry a stable ``code`` so a later tool can filter them, and a
``severity`` with three values:

``error``
    The project cannot be read or its records contradict each other, a
    referenced artifact is missing or its content hash differs, or world
    records reference something that does not exist.  These are the only
    findings that make the report ``ok: false``.
``warning``
    A recorded state that needs an operator decision: a stale pinned link, a
    stale adopted canon entry, a failed stage, or a ``running`` checkpoint left
    behind by an interrupted process.
``info``
    Normal bookkeeping, such as a binding that belongs to an older revision.

The report always separates *pending* operator responses and *stale*
references from error findings, because those are normal states of a project
that is being written, not corruption.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import StageCheckpoint
from .store import ProjectError, ProjectNotFoundError, ProjectStore
from .world_store import WorldStore

DOCTOR_SCHEMA = "asc-project-doctor-v1"
ERROR = "error"
WARNING = "warning"
INFO = "info"
SEVERITIES = (ERROR, WARNING, INFO)


@dataclass(frozen=True)
class Finding:
    """One machine-readable inspection result."""

    code: str
    severity: str
    message: str
    scope: str
    node_id: str | None = None
    path: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "scope": self.scope,
        }
        if self.node_id is not None:
            data["node_id"] = self.node_id
        if self.path is not None:
            data["path"] = self.path
        if self.details:
            data["details"] = self.details
        return data


@dataclass(frozen=True)
class DoctorReport:
    """The complete result of one read-only inspection."""

    project_id: str
    ok: bool
    findings: tuple[Finding, ...]
    checks: tuple[dict[str, Any], ...]
    pending: tuple[dict[str, Any], ...]
    stale: dict[str, Any]
    summary: dict[str, Any]
    project_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DOCTOR_SCHEMA,
            "project_id": self.project_id,
            "ok": self.ok,
            "read_only": True,
            "findings": [finding.to_dict() for finding in self.findings],
            "checks": list(self.checks),
            "pending": list(self.pending),
            "stale": self.stale,
            "summary": self.summary,
            "project_dir": self.project_dir,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProjectDoctor:
    """Inspect one project without changing it."""

    def __init__(self, store: ProjectStore):
        self.store = store
        self._findings: list[Finding] = []
        self._checks: list[dict[str, Any]] = []
        self._pending: list[dict[str, Any]] = []
        self._stale: dict[str, list[dict[str, Any]]] = {
            "links": [], "canon": [], "bindings": [],
        }

    # -- small helpers -----------------------------------------------------
    def _add(
        self, code: str, severity: str, message: str, scope: str, *,
        node_id: str | None = None, path: str | Path | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._findings.append(Finding(
            code=code, severity=severity, message=message, scope=scope,
            node_id=node_id,
            path=str(path) if path is not None else None,
            details=details,
        ))

    def _check(self, name: str, before: int, *, status: str | None = None) -> None:
        """Record one named check and the severities it produced.

        ``failed`` means the check found an ``error``.  A check that only found
        a warning or an informational finding is ``warn``: the project is
        readable and consistent, but an operator decision is outstanding.
        """
        raised = self._findings[before:]
        errors = sum(1 for item in raised if item.severity == ERROR)
        warnings = sum(1 for item in raised if item.severity == WARNING)
        if status is None:
            status = "failed" if errors else "warn" if warnings else "pass"
        self._checks.append({
            "name": name, "status": status, "findings": len(raised),
            "errors": errors, "warnings": warnings,
        })

    def _artifact_problem(self, project_id: str, artifact: Any) -> str | None:
        """Return a code describing why a pinned artifact is unusable."""
        directory = self.store.project_dir(project_id).resolve()
        target = (directory / artifact.path).resolve()
        try:
            target.relative_to(directory)
        except ValueError:
            return "artifact.path_escapes"
        if not target.is_file():
            return "artifact.missing"
        try:
            if _sha256_file(target) != artifact.sha256:
                return "artifact.hash_differs"
        except OSError:
            return "artifact.unreadable"
        return None

    # -- individual checks -------------------------------------------------
    def _inspect_project(self, project_id: str) -> Any:
        directory = self.store.project_dir(project_id)  # validates the id
        if not directory.is_dir():
            raise ProjectNotFoundError(f"project not found: {project_id}")
        try:
            project = self.store.load_project(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "project.unreadable", ERROR, str(exc), "project",
                path=self.store.project_dir(project_id),
            )
            self._check("project", 0)
            return None
        self._check("project", 0)
        return project

    def _inspect_nodes(self, project_id: str, project: Any) -> list[Any]:
        before = len(self._findings)
        try:
            nodes = self.store.list_nodes(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "node.tree_invalid", ERROR, str(exc), "node",
                path=self.store.project_dir(project_id) / "nodes",
            )
            self._check("node_tree", before)
            return []
        by_id = {node.id: node for node in nodes}
        if project.root_node_id not in by_id:
            self._add(
                "project.root_missing", ERROR,
                f"root node {project.root_node_id} has no current.json", "project",
                path=self.store.project_dir(project_id) / "nodes" / project.root_node_id,
            )
        links = []
        try:
            links = self.store.list_all_links(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            self._add("link.unreadable", ERROR, str(exc), "link")
        linked_children = {link.child_node_id for link in links}
        for node in nodes:
            if node.parent_id is None:
                if node.id != project.root_node_id:
                    self._add(
                        "node.multiple_roots", ERROR,
                        "only the project root may have no parent", "node",
                        node_id=node.id,
                    )
                continue
            if node.id not in linked_children:
                self._add(
                    "node.orphan", ERROR,
                    f"node {node.id} names parent {node.parent_id} but no link pins it",
                    "node", node_id=node.id,
                )
            if node.parent_id not in by_id:
                self._add(
                    "node.parent_missing", ERROR,
                    f"node {node.id} names a parent that does not exist: {node.parent_id}",
                    "node", node_id=node.id,
                )
                continue
            try:
                self.store.node_depth(project_id, node.id)
            except ValueError as exc:
                self._add(
                    "node.depth_invalid", ERROR, str(exc), "node", node_id=node.id,
                )
        self._check("node_tree", before)
        return nodes

    def _inspect_revisions(self, project_id: str, nodes: list[Any]) -> None:
        before = len(self._findings)
        for node in nodes:
            try:
                revisions = self.store.list_revisions(project_id, node.id)
            except (ProjectError, OSError, ValueError) as exc:
                self._add(
                    "revision.unreadable", ERROR, str(exc), "revision", node_id=node.id,
                )
                continue
            if not any(item.id == node.current_revision_id for item in revisions):
                self._add(
                    "node.current_revision_missing", ERROR,
                    f"current revision {node.current_revision_id} has no record", "node",
                    node_id=node.id,
                    details={"current_revision_id": node.current_revision_id},
                )
                continue
            for revision in revisions:
                self._inspect_derived(project_id, node.id, revision)
                for artifact in revision.artifacts:
                    problem = self._artifact_problem(project_id, artifact)
                    if problem is not None:
                        self._add(
                            problem, ERROR,
                            f"revision artifact is unusable: {artifact.path}",
                            "artifact", node_id=node.id, path=artifact.path,
                            details={
                                "revision_id": revision.id,
                                "artifact_id": artifact.artifact_id,
                                "expected_sha256": artifact.sha256,
                            },
                        )
        self._check("revisions", before)

    def _inspect_derived(self, project_id: str, node_id: str, revision: Any) -> None:
        """Check that a revised/branched revision still points at its source."""
        derived = revision.derived
        if not derived:
            return
        try:
            self.store.load_revision(
                project_id, derived["source_node_id"], derived["source_revision_id"],
            )
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "revision.derived_source_missing", ERROR,
                f"{derived['kind']} source revision is unreadable: "
                f"{derived['source_revision_id']}",
                "revision", node_id=node_id,
                details={
                    "revision_id": revision.id,
                    "source_node_id": derived["source_node_id"],
                    "source_revision_id": derived["source_revision_id"],
                    "error": str(exc),
                },
            )
        runs = derived.get("source_runs") or {}
        for stage, run_id in sorted(runs.items()):
            directory = self.store.project_dir(project_id) / "runs" / run_id
            if not (directory / "manifest.json").is_file():
                self._add(
                    "revision.derived_run_missing", ERROR,
                    f"{derived['kind']} source run for {stage} is missing: {run_id}",
                    "revision", node_id=node_id,
                    details={"revision_id": revision.id, "stage": stage, "run_id": run_id},
                )

    def _inspect_checkpoints(self, project_id: str, nodes: list[Any]) -> None:
        before = len(self._findings)
        for node in nodes:
            checkpoint_dir = self.store.node_dir(project_id, node.id) / "checkpoints"
            if not checkpoint_dir.is_dir():
                continue
            for path in sorted(checkpoint_dir.glob("*.json")):
                try:
                    checkpoint = self.store._parse(path, StageCheckpoint.from_dict)
                except (ProjectError, OSError, ValueError) as exc:
                    self._add(
                        "checkpoint.unreadable", ERROR, str(exc), "checkpoint",
                        node_id=node.id, path=path,
                    )
                    continue
                if (
                    checkpoint.project_id != project_id
                    or checkpoint.node_id != node.id
                    or checkpoint.stage != path.stem
                ):
                    self._add(
                        "checkpoint.identity_mismatch", ERROR,
                        "checkpoint identity does not match its path", "checkpoint",
                        node_id=node.id, path=path,
                    )
                    continue
                if checkpoint.revision_id != node.current_revision_id:
                    # Historical checkpoints belong to an older revision.  That
                    # is expected after a continuation; it is not an error.
                    continue
                if checkpoint.status == "done":
                    self._inspect_done_checkpoint(
                        project_id, node.id, checkpoint, path,
                    )
                elif checkpoint.status == "waiting_response":
                    self._add_pending(project_id, node, checkpoint)
                elif checkpoint.status == "failed":
                    self._add(
                        "checkpoint.failed", WARNING,
                        f"stage {checkpoint.stage} is recorded as failed "
                        "(retry it with resume --retry-failed)",
                        "checkpoint", node_id=node.id, path=path,
                        details={
                            "stage": checkpoint.stage,
                            "run_id": checkpoint.run_id,
                            "error": checkpoint.error,
                        },
                    )
                elif checkpoint.status == "running":
                    self._add(
                        "checkpoint.running", WARNING,
                        f"stage {checkpoint.stage} is still marked running",
                        "checkpoint", node_id=node.id, path=path,
                        details={"stage": checkpoint.stage, "run_id": checkpoint.run_id},
                    )
                for artifact in checkpoint.artifacts:
                    if checkpoint.status == "done":
                        continue  # verified together with its done checkpoint
                    problem = self._artifact_problem(project_id, artifact)
                    if problem is not None:
                        self._add(
                            problem, ERROR,
                            f"checkpoint artifact is unusable: {artifact.path}",
                            "artifact", node_id=node.id, path=artifact.path,
                            details={
                                "stage": checkpoint.stage,
                                "run_id": checkpoint.run_id,
                            },
                        )
        self._check("checkpoints", before)

    def _inspect_done_checkpoint(
        self, project_id: str, node_id: str, checkpoint: Any, path: Path,
    ) -> None:
        if checkpoint.run_id is None:  # pragma: no cover - schema guarantees it
            self._add(
                "checkpoint.run_missing", ERROR,
                f"done stage {checkpoint.stage} has no run id", "checkpoint",
                node_id=node_id, path=path,
            )
            return
        run_dir = self.store.project_dir(project_id) / "runs" / checkpoint.run_id
        if not run_dir.is_dir():
            self._add(
                "run.missing", ERROR,
                f"run {checkpoint.run_id} for stage {checkpoint.stage} is missing",
                "run", node_id=node_id, path=run_dir,
                details={"stage": checkpoint.stage},
            )
            return
        try:
            manifest = self.store._read_json(run_dir / "manifest.json")
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "run.manifest_unreadable", ERROR, str(exc), "run",
                node_id=node_id, path=run_dir / "manifest.json",
            )
            return
        problems = []
        if manifest.get("run_id") != checkpoint.run_id:
            problems.append("run_id differs")
        if manifest.get("status") != "ok":
            problems.append(f"status is {manifest.get('status')!r}")
        if manifest.get("task_id") != node_id:
            problems.append("task_id differs")
        if problems:
            self._add(
                "run.manifest_invalid", ERROR,
                "done checkpoint requires an ok manifest for its node run",
                "run", node_id=node_id, path=run_dir / "manifest.json",
                details={"stage": checkpoint.stage, "problems": problems},
            )
        try:
            run_input = self.store._read_json(run_dir / "project-input.json")
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "run.input_unreadable", ERROR, str(exc), "run",
                node_id=node_id, path=run_dir / "project-input.json",
            )
            run_input = {}
        expected = {
            "project_id": project_id,
            "node_id": node_id,
            "revision_id": checkpoint.revision_id,
            "attempt_id": checkpoint.attempt_id,
            "stage": checkpoint.stage,
        }
        mismatched = [
            field for field, value in expected.items() if run_input.get(field) != value
        ]
        if mismatched:
            self._add(
                "run.input_mismatch", ERROR,
                "project-input does not match the current checkpoint",
                "run", node_id=node_id, path=run_dir / "project-input.json",
                details={"stage": checkpoint.stage, "fields": mismatched},
            )
        for artifact in checkpoint.artifacts:
            if artifact.producer_run_id != checkpoint.run_id:
                self._add(
                    "artifact.producer_mismatch", ERROR,
                    f"artifact {artifact.path} does not belong to run {checkpoint.run_id}",
                    "artifact", node_id=node_id, path=artifact.path,
                    details={"stage": checkpoint.stage},
                )
            problem = self._artifact_problem(project_id, artifact)
            if problem is not None:
                self._add(
                    problem, ERROR,
                    f"checkpoint artifact is unusable: {artifact.path}",
                    "artifact", node_id=node_id, path=artifact.path,
                    details={"stage": checkpoint.stage, "run_id": checkpoint.run_id},
                )

    def _add_pending(self, project_id: str, node: Any, checkpoint: Any) -> None:
        details = dict(checkpoint.pending or {})
        response_path = details.get("response_path")
        self._pending.append({
            "project_id": project_id,
            "node_id": node.id,
            "revision_id": checkpoint.revision_id,
            "stage": checkpoint.stage,
            "attempt_id": checkpoint.attempt_id,
            "run_id": checkpoint.run_id,
            "key": details.get("key"),
            "request_path": details.get("request_path"),
            "response_path": response_path,
            "response_ready": bool(response_path and Path(response_path).is_file()),
        })

    def _inspect_links(self, project_id: str, nodes: list[Any]) -> None:
        before = len(self._findings)
        by_id = {node.id: node for node in nodes}
        try:
            links = self.store.list_all_links(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            self._add("link.unreadable", ERROR, str(exc), "link")
            self._check("links", before)
            return
        orders: set[tuple[str, int]] = set()
        for link in links:
            key = (link.parent_node_id, link.order)
            if key in orders:
                self._add(
                    "link.order_duplicate", WARNING,
                    f"order {link.order} is used twice below {link.parent_node_id}",
                    "link", node_id=link.parent_node_id,
                    details={"link_id": link.id},
                )
            orders.add(key)
            child = by_id.get(link.child_node_id)
            if child is None:
                self._add(
                    "link.child_missing", ERROR,
                    f"link {link.id} pins a child node that does not exist",
                    "link", node_id=link.parent_node_id,
                    details={"child_node_id": link.child_node_id},
                )
                continue
            try:
                self.store.load_revision(project_id, child.id, link.child_revision_id)
            except (ProjectError, OSError, ValueError) as exc:
                self._add(
                    "link.pinned_revision_missing", ERROR, str(exc), "link",
                    node_id=child.id,
                    details={"link_id": link.id},
                )
            for artifact in link.artifacts:
                problem = self._artifact_problem(project_id, artifact)
                if problem is not None:
                    self._add(
                        problem, ERROR,
                        f"pinned link artifact is unusable: {artifact.path}",
                        "artifact", node_id=child.id, path=artifact.path,
                        details={"link_id": link.id},
                    )
            if child.current_revision_id != link.child_revision_id:
                self._stale["links"].append({
                    "link_id": link.id,
                    "parent_node_id": link.parent_node_id,
                    "child_node_id": child.id,
                    "pinned_revision_id": link.child_revision_id,
                    "current_child_revision_id": child.current_revision_id,
                    "adopt_command": (
                        f"story_project.py adopt-child <project> {link.id}"
                    ),
                })
                self._add(
                    "link.stale", WARNING,
                    "child has a newer revision than the pinned link; adoption is explicit",
                    "link", node_id=child.id,
                    details={
                        "link_id": link.id,
                        "pinned_revision_id": link.child_revision_id,
                        "current_child_revision_id": child.current_revision_id,
                    },
                )
        self._check("links", before)

    def _inspect_world(self, project_id: str) -> None:
        before = len(self._findings)
        try:
            records = WorldStore(self.store).validate(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            self._add(
                "world.invalid", ERROR, str(exc), "world",
                path=self.store.project_dir(project_id) / "world",
            )
            self._check("world", before)
            return
        try:
            superseded = {
                entry.supersedes_id
                for entry in records.canon_entries if entry.supersedes_id
            }
            for entry in records.canon_entries:
                if entry.id in superseded or entry.source is None:
                    continue
                try:
                    node = self.store.load_node(project_id, entry.source.node_id)
                except (ProjectError, OSError, ValueError):
                    continue  # already reported by world validation
                if node.current_revision_id == entry.source.revision_id:
                    continue
                self._stale["canon"].append({
                    "entry_id": entry.id,
                    "subject": entry.subject,
                    "scope": entry.scope.to_dict(),
                    "source_node_id": entry.source.node_id,
                    "source_revision_id": entry.source.revision_id,
                    "current_source_revision_id": node.current_revision_id,
                })
                self._add(
                    "world.canon_stale", WARNING,
                    "adopted canon still points at an older source revision",
                    "world", node_id=entry.source.node_id,
                    details={
                        "entry_id": entry.id,
                        "subject": entry.subject,
                        "source_revision_id": entry.source.revision_id,
                        "current_source_revision_id": node.current_revision_id,
                    },
                )
            for binding in records.bindings:
                try:
                    node = self.store.load_node(project_id, binding.node_id)
                except (ProjectError, OSError, ValueError):
                    continue
                if node.current_revision_id == binding.revision_id:
                    continue
                self._stale["bindings"].append({
                    "binding_id": binding.id,
                    "node_id": binding.node_id,
                    "revision_id": binding.revision_id,
                    "current_revision_id": node.current_revision_id,
                })
        except (ProjectError, OSError, ValueError) as exc:  # pragma: no cover
            self._add("world.unreadable", ERROR, str(exc), "world")
        self._check("world", before)

    def _inspect_runs(self, project_id: str) -> None:
        before = len(self._findings)
        runs_dir = self.store.project_dir(project_id) / "runs"
        if not runs_dir.is_dir():
            self._check("runs", before, status="skipped")
            return
        for path in sorted(runs_dir.iterdir()):
            if not path.is_dir():
                continue
            manifest = path / "manifest.json"
            if not manifest.is_file():
                self._add(
                    "run.manifest_missing", WARNING,
                    "run directory has no manifest", "run", path=path,
                )
                continue
            try:
                payload = self.store._read_json(manifest)
            except (ProjectError, OSError, ValueError) as exc:
                self._add("run.manifest_unreadable", ERROR, str(exc), "run", path=manifest)
                continue
            status = payload.get("status")
            if status == "running":
                self._add(
                    "run.running", WARNING,
                    "run never recorded a finish (interrupted process?)", "run",
                    path=manifest,
                    details={"run_id": path.name},
                )
            elif status not in {"ok", "failed", "waiting_response"}:
                self._add(
                    "run.status_unknown", WARNING,
                    f"run status is {status!r}", "run", path=manifest,
                    details={"run_id": path.name},
                )
        self._check("runs", before)

    # -- public entry point -------------------------------------------------
    def inspect(self, project_id: str) -> DoctorReport:
        self._findings = []
        self._checks = []
        self._pending = []
        self._stale = {"links": [], "canon": [], "bindings": []}
        project = self._inspect_project(project_id)
        if project is None:
            report = self._build_report(project_id, ())
            return report
        nodes = self._inspect_nodes(project_id, project)
        self._inspect_revisions(project_id, nodes)
        self._inspect_checkpoints(project_id, nodes)
        self._inspect_links(project_id, nodes)
        self._inspect_world(project_id)
        self._inspect_runs(project_id)
        return self._build_report(project_id, tuple(nodes))

    def _build_report(self, project_id: str, nodes: tuple[Any, ...]) -> DoctorReport:
        counts = {severity: 0 for severity in SEVERITIES}
        for finding in self._findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        stale_total = sum(len(rows) for rows in self._stale.values())
        summary = {
            "nodes": len(nodes),
            "findings": len(self._findings),
            "errors": counts[ERROR],
            "warnings": counts[WARNING],
            "info": counts[INFO],
            "pending": len(self._pending),
            "stale": stale_total,
            "checks": len(self._checks),
            "checks_failed": sum(
                1 for check in self._checks if check["status"] == "failed"
            ),
            "checks_warn": sum(
                1 for check in self._checks if check["status"] == "warn"
            ),
        }
        return DoctorReport(
            project_id=project_id,
            ok=counts[ERROR] == 0,
            findings=tuple(self._findings),
            checks=tuple(self._checks),
            pending=tuple(self._pending),
            stale={
                "links": list(self._stale["links"]),
                "canon": list(self._stale["canon"]),
                "bindings": list(self._stale["bindings"]),
                "total": stale_total,
            },
            summary=summary,
            project_dir=str(self.store.project_dir(project_id)),
        )


def inspect_project(store: ProjectStore, project_id: str) -> DoctorReport:
    """Convenience wrapper for the CLI and callers that do not need the class."""
    return ProjectDoctor(store).inspect(project_id)
