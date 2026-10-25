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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context import build_context_packet
from .observability import (
    STAGE_ORDER,
    UNVERSIONED_WORLD_TYPES,
    actions_from_record_changes,
    build_actions,
    summarize,
)
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
    work: dict[str, Any] = field(default_factory=dict)
    next_actions: tuple[dict[str, Any], ...] = ()

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
            "work": self.work,
            "next_actions": [dict(row) for row in self.next_actions],
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
        self._node_stages: dict[str, dict[str, str]] = {}
        self._record_changes: list[dict[str, Any]] = []
        self._run_count = 0
        self._interrupted_runs = 0
        self._binding_gaps: list[str] = []

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
                self._node_stages.setdefault(node.id, {})[checkpoint.stage] = (
                    checkpoint.status
                )
                if checkpoint.status == "done":
                    self._inspect_done_checkpoint(
                        project_id, node.id, checkpoint, path,
                    )
                elif checkpoint.status == "waiting_response":
                    self._add_pending(project_id, node, checkpoint)
                elif checkpoint.status == "failed":
                    retry = build_actions(
                        project_id=project_id, state="failed",
                        failed_stages=(checkpoint.stage,),
                    )[0]["action"]
                    self._add(
                        "checkpoint.failed", WARNING,
                        f"stage {checkpoint.stage} is recorded as failed "
                        f"(retry it with {retry})",
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

    def _recorded_packet(self, project_id: str, node: Any) -> tuple[str, dict] | None:
        """Return the newest packet recorded for a node's current revision."""
        runs_dir = self.store.project_dir(project_id) / "runs"
        if not runs_dir.is_dir():
            return None
        best: tuple[tuple[int, str], str, dict] | None = None
        for path in sorted(runs_dir.iterdir()):
            input_path = path / "project-input.json"
            if not path.is_dir() or not input_path.is_file():
                continue
            try:
                payload = self.store._read_json(input_path)
            except (ProjectError, OSError, ValueError):
                continue
            if (
                not isinstance(payload, dict)
                or payload.get("node_id") != node.id
                or payload.get("revision_id") != node.current_revision_id
            ):
                continue
            packet = payload.get("context_packet")
            if not isinstance(packet, dict):
                continue
            stage = str(payload.get("stage") or "")
            rank = (
                -STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -99,
                path.name,
            )
            if best is None or rank > best[0]:
                best = (rank, path.name, packet)
        if best is None:
            return None
        return best[1], best[2]

    def _check_record_changes(self, project_id: str, nodes: list[Any]) -> None:
        """Warn when an append-only world record was rewritten in place.

        ``region``, ``time_frame`` and the other unversioned record types store
        no ``content_version`` of their own, so a hand edit of the stored JSON
        cannot be detected from the record alone.  A packet recorded by an
        earlier run pins the hash it saw; comparing that with the current value
        is the only read-only way to notice the change.
        """
        for node in nodes:
            try:
                current = build_context_packet(self.store, project_id, node.id)
            except (ProjectError, OSError, ValueError):
                continue
            if current is None:
                continue
            recorded = self._recorded_packet(project_id, node)
            if recorded is None:
                continue
            run_id, packet = recorded
            now = {
                (row.get("record_type"), row.get("id")): row.get("content_version")
                for row in (current.world or {}).get("references") or ()
            }
            then = {
                (row.get("record_type"), row.get("id")): row.get("content_version")
                for row in (packet.get("world") or {}).get("references") or ()
            }
            for key in sorted(now):
                record_type, record_id = key
                if record_type not in UNVERSIONED_WORLD_TYPES:
                    continue
                if key not in then or then[key] == now[key]:
                    continue
                self._record_changes.append({
                    "node_id": node.id,
                    "run_id": run_id,
                    "record_type": record_type,
                    "record_id": record_id,
                    "recorded_content_version": then[key],
                    "current_content_version": now[key],
                })
                self._add(
                    "world.record_changed", WARNING,
                    f"world record {record_type} {record_id} differs from the "
                    f"version recorded by run {run_id} "
                    f"(inspect with diff --left run:{run_id} --right current)",
                    "world", node_id=node.id,
                    details={
                        "run_id": run_id,
                        "record_type": record_type,
                        "record_id": record_id,
                        "recorded_content_version": then[key],
                        "current_content_version": now[key],
                        "note": (
                            "this record type stores no content_version; world "
                            "records are append-only, so a difference means the "
                            "stored JSON was edited after the run"
                        ),
                    },
                )

    def _inspect_world(self, project_id: str, nodes: list[Any] | None = None) -> None:
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
            current_revisions: dict[str, str] = {}
            for binding in records.bindings:
                try:
                    node = self.store.load_node(project_id, binding.node_id)
                except (ProjectError, OSError, ValueError):
                    continue
                current_revisions[node.id] = node.current_revision_id
            bound_now = {
                binding.node_id for binding in records.bindings
                if current_revisions.get(binding.node_id) == binding.revision_id
            }
            # A binding pinned to an older revision is history; it needs an
            # action only when the current revision has no binding at all.
            self._binding_gaps = sorted(
                {binding.node_id for binding in records.bindings} - bound_now
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
        if nodes:
            self._check_record_changes(project_id, list(nodes))
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
            self._run_count += 1
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
                self._interrupted_runs += 1
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
        self._node_stages = {}
        self._record_changes = []
        self._run_count = 0
        self._interrupted_runs = 0
        self._binding_gaps = []
        project = self._inspect_project(project_id)
        if project is None:
            report = self._build_report(project_id, ())
            return report
        nodes = self._inspect_nodes(project_id, project)
        self._inspect_revisions(project_id, nodes)
        self._inspect_checkpoints(project_id, nodes)
        self._inspect_links(project_id, nodes)
        self._inspect_world(project_id, nodes)
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
        root_id = None
        try:
            root_id = self.store.load_project(project_id).root_node_id
        except (ProjectError, OSError, ValueError):
            root_id = None
        root_stages = self._node_stages.get(root_id or "", None)
        root_pending = [
            row for row in self._pending if row.get("node_id") == (root_id or row.get("node_id"))
        ]
        work = summarize(
            state=_state_from_stages(root_stages),
            stages=root_stages,
            pending=root_pending,
            stale_links=len(self._stale["links"]),
            stale_canon=len(self._stale["canon"]),
            stale_bindings=len(self._stale["bindings"]),
            run_count=self._run_count,
            interrupted_runs=self._interrupted_runs,
            node_id=root_id,
            scope="node",
        )
        failed_stages = sorted({
            stage for stages in self._node_stages.values()
            for stage, value in stages.items() if value == "failed"
        })
        waiting_stages = sorted({
            stage for stages in self._node_stages.values()
            for stage, value in stages.items() if value == "waiting_response"
        })
        next_actions = build_actions(
            project_id=project_id,
            state=_aggregate_state(self._node_stages),
            failed_stages=failed_stages,
            waiting_stages=waiting_stages,
            pending_ready=sum(1 for row in self._pending if row.get("response_ready")),
            stale_links=len(self._stale["links"]),
            stale_canon=len(self._stale["canon"]),
            stale_bindings=len(self._binding_gaps),
            interrupted_runs=self._interrupted_runs,
            record_changes=actions_from_record_changes(self._record_changes),
            link_id=(self._stale["links"][0].get("link_id")
                     if self._stale["links"] else None),
            binding_node_id=(self._binding_gaps[0] if self._binding_gaps else None),
            canon_entry_id=(self._stale["canon"][0].get("entry_id")
                            if self._stale["canon"] else None),
        )
        summary["work"] = work
        summary["next_actions"] = len(next_actions)
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
            work=work,
            next_actions=tuple(next_actions),
        )


def _aggregate_state(node_stages: dict[str, dict[str, str]]) -> str:
    """Project-wide state used for next-action hints.

    ``doctor`` inspects every node, so the hint list must not claim the project
    has not started just because one node (often a fresh child) has not.
    """
    if not node_stages:
        return "not_started"
    values = {value for stages in node_stages.values() for value in stages.values()}
    per_node = [_state_from_stages(stages) for stages in node_stages.values()]
    if "failed" in values:
        return "failed"
    if "waiting_response" in values:
        return "waiting_response"
    if per_node and all(state == "complete" for state in per_node):
        return "complete"
    if values & {"done", "ready", "running"}:
        return "in_progress"
    return "not_started"


def _state_from_stages(stages: dict[str, str] | None) -> str:
    """Stage-only state, matching ``status`` for every stage-driven case."""
    if not stages:
        return "not_started"
    values = set(stages.values())
    if all(stages.get(stage) == "done" for stage in STAGE_ORDER):
        return "complete"
    if "waiting_response" in values:
        return "waiting_response"
    if values & {"ready", "running"}:
        return "in_progress"
    if "failed" in values:
        return "failed"
    if values & {"done"}:
        return "in_progress"
    return "not_started"


def inspect_project(store: ProjectStore, project_id: str) -> DoctorReport:
    """Convenience wrapper for the CLI and callers that do not need the class."""
    return ProjectDoctor(store).inspect(project_id)
