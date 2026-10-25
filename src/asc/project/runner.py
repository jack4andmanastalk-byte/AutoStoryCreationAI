"""Run and resume the single-work S1 vertical slice for a creative project.

An attempt contains independent plan/design/draft run ledgers.  Resume never
rewrites an old run: completed stages are loaded from their pinned artifacts,
and the interrupted stage gets a new run whose provider consumes the old
response prefix before delegating new requests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from ..pipeline import (
    ChapterDraft,
    Draft,
    Provider,
    ResponsePendingError,
    RunLedger,
    build_design,
    build_plan,
    build_story,
)
from ..story.canon import Canon, load_canon
from .adapter import PROJECT_PROTOCOL, PipelineInput, adapt_work_spec
from .continuation import ContinuationContext, validate_continuation_canon
from .context import ContextPacket, build_context_packet
from .model import (
    ArtifactRef, ProjectSnapshot, StageCheckpoint, WorkNodeRevision, new_id, utc_now,
)
from .resume import ResumeError, ResumeProvider
from .schema import SCHEMA_VERSION
from .store import DEFAULT_STAGES, ProjectError, ProjectStore


class ProjectRunError(ProjectError):
    """A project attempt cannot start or a stage cannot complete."""

    def __init__(
        self, message: str, *, project_id: str, stage: str | None = None,
        run_id: str | None = None, run_dir: Path | None = None,
    ):
        super().__init__(message)
        self.project_id = project_id
        self.stage = stage
        self.run_id = run_id
        self.run_dir = run_dir


class ProjectDependencyError(ProjectRunError):
    """A tree attempt cannot safely cross an unfinished dependency."""

    def __init__(
        self, message: str, *, project_id: str, node_id: str,
        dependency_id: str | None = None, dependency_state: str | None = None,
    ):
        super().__init__(message, project_id=project_id)
        self.node_id = node_id
        self.dependency_id = dependency_id
        self.dependency_state = dependency_state


class ProjectRunPending(ProjectRunError):
    """Generation stopped at an operator request that still needs a response."""

    def __init__(
        self, message: str, *, project_id: str, stage: str, run_id: str,
        run_dir: Path | None, pending: dict[str, Any], status: dict[str, Any],
    ):
        super().__init__(
            message, project_id=project_id, stage=stage, run_id=run_id, run_dir=run_dir,
        )
        self.pending = pending
        self.status = status


@dataclass(frozen=True)
class ProjectRunResult:
    attempt_id: str
    stage_runs: dict[str, str]
    status: dict[str, Any]


@dataclass(frozen=True)
class ProjectTreeRunResult:
    """Results of a parent-before-descendant attempt over a containment tree."""

    project_id: str
    root_node_id: str
    order: tuple[str, ...]
    results: tuple[ProjectRunResult, ...]
    status: dict[str, Any]

    @property
    def stage_runs(self) -> dict[str, dict[str, str]]:
        return {
            result.status["node_id"]: result.stage_runs for result in self.results
        }


@dataclass(frozen=True)
class _Attempt:
    snapshot: ProjectSnapshot
    pipeline: PipelineInput
    attempt_id: str
    continuation: ContinuationContext | None = None
    context_packet: ContextPacket | None = None


@dataclass(frozen=True)
class _StageConfig:
    seed: int
    temperature: float


@dataclass(frozen=True)
class _StageResult:
    value: Any
    run_id: str
    run_dir: Path
    artifacts: tuple[ArtifactRef, ...]


def _default_temperature(stage: str) -> float:
    return 0.8 if stage == "draft" else 0.6


class _ContextProvider:
    """Add the same recorded ancestor packet to design/draft requests only."""

    def __init__(self, delegate: Provider, suffix: str):
        self.delegate = delegate
        self.suffix = suffix
        self.name = delegate.name
        self.model = delegate.model
        self.model_version = delegate.model_version

    def generate(self, request):
        return self.delegate.generate(replace(request, prompt=request.prompt + self.suffix))


def _project_brief(attempt: _Attempt) -> str:
    spec = attempt.snapshot.revision.spec
    pipeline = attempt.pipeline
    return "\n".join([
        f"# {spec.title}",
        "",
        f"- Project: `{attempt.snapshot.project.id}`",
        f"- Node: `{attempt.snapshot.root_node.id}`",
        f"- Revision: `{attempt.snapshot.revision.id}`",
        f"- 章数: {pipeline.chapters}",
        f"- 目安: 各章 {pipeline.chapter_target[0]} 字"
        f"（全体 {pipeline.total_target[0]} 字）",
        "",
        f"前提: {spec.premise}",
        "",
        "これは創作projectのS1 vertical sliceであり、protocol-v1の固定taskではありません。",
        "",
    ])


class ProjectRunner:
    def __init__(self, store: ProjectStore):
        self.store = store

    def run(
        self, project_id: str, provider: Provider, *, seed: int = 0,
        temperature: float | None = None, node_id: str | None = None,
    ) -> ProjectRunResult:
        """Run plan -> design -> draft once for a not-started current revision."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_node_snapshot(project_id, node_id)
            state = self.store.status(project_id, node_id)["state"]
            if state != "not_started":
                raise ProjectRunError(
                    f"project {project_id} is {state}; run requires a not-started revision "
                    "(resume and continuation are separate operations)",
                    project_id=project_id,
                )
            if snapshot.revision.parent_revision_id is not None:
                raise ProjectRunError(
                    "a continuation revision must be resumed, not started as a new run",
                    project_id=project_id,
                )
            attempt = self._attempt(snapshot)
            configs = {
                stage: _StageConfig(
                    seed=seed,
                    temperature=temperature if temperature is not None
                    else _default_temperature(stage),
                )
                for stage in DEFAULT_STAGES
            }
            existing: dict[str, StageCheckpoint] = {}
            for stage, config in configs.items():
                checkpoint = self._new_checkpoint(attempt, stage, "pending", config=config)
                self.store.save_checkpoint(checkpoint)
                existing[stage] = checkpoint
            return self._execute(attempt, provider, configs, existing)

    def continue_project(
        self, project_id: str, provider: Provider, *,
        additional_chapters: int | None = None, total_chapters: int | None = None,
        seed: int = 0, temperature: float | None = None,
        title: str | None = None, premise: str | None = None,
        node_id: str | None = None,
    ) -> ProjectRunResult:
        """Append a new revision while retaining the parent runs and chapter text."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_node_snapshot(project_id, node_id)
            status = self.store.status(project_id, node_id)
            if status["state"] != "complete":
                raise ProjectRunError(
                    f"project {project_id} is {status['state']}; "
                    "continuation requires a complete revision",
                    project_id=project_id,
                )
            old_revision = snapshot.revision
            if additional_chapters is not None and total_chapters is not None:
                raise ProjectRunError(
                    "specify only one of additional_chapters and total_chapters",
                    project_id=project_id,
                )
            if total_chapters is not None:
                if isinstance(total_chapters, bool) or not isinstance(total_chapters, int):
                    raise ProjectRunError(
                        "total_chapters must be an integer", project_id=project_id,
                    )
                additional_chapters = total_chapters - old_revision.spec.chapter_count
            if additional_chapters is None:
                additional_chapters = 1
            if (
                isinstance(additional_chapters, bool)
                or not isinstance(additional_chapters, int)
                or additional_chapters < 1
            ):
                raise ProjectRunError(
                    "additional_chapters must be a positive integer",
                    project_id=project_id,
                )
            parent_runs = {
                stage: status["checkpoints"][stage]["run_id"]
                for stage in DEFAULT_STAGES
            }
            if any(run_id is None for run_id in parent_runs.values()):
                raise ProjectRunError(
                    "complete revision has a stage without a run", project_id=project_id,
                )
            new_spec = replace(
                old_revision.spec,
                title=old_revision.spec.title if title is None else title,
                premise=old_revision.spec.premise if premise is None else premise,
                chapter_count=old_revision.spec.chapter_count + additional_chapters,
            )
            new_revision = WorkNodeRevision.create(
                revision_id=new_id("rev"),
                node_id=snapshot.root_node.id,
                project_id=project_id,
                spec=new_spec,
                created_at=utc_now(),
                parent_revision_id=old_revision.id,
                parent_runs=parent_runs,
            )
            self.store.save_revision(new_revision)
            self.store.save_node(replace(
                snapshot.root_node,
                current_revision_id=new_revision.id,
                updated_at=utc_now(),
            ))
            continued = self.store.load_node_snapshot(
                project_id, snapshot.root_node.id,
            )
            attempt = self._attempt(
                continued, continuation=self._continuation_for_snapshot(continued),
            )
            configs = {
                stage: _StageConfig(
                    seed=seed,
                    temperature=temperature if temperature is not None
                    else _default_temperature(stage),
                )
                for stage in DEFAULT_STAGES
            }
            existing: dict[str, StageCheckpoint] = {}
            for stage, config in configs.items():
                checkpoint = self._new_checkpoint(attempt, stage, "pending", config=config)
                self.store.save_checkpoint(checkpoint)
                existing[stage] = checkpoint
            return self._execute(attempt, provider, configs, existing)

    # Readable alias for callers that use the roadmap's noun for this operation.
    continuation = continue_project

    def resume(
        self, project_id: str, provider: Provider, *, node_id: str | None = None,
    ) -> ProjectRunResult:
        """Resume the first unfinished stage without regenerating completed work."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_node_snapshot(project_id, node_id)
            status = self.store.status(project_id, node_id)
            state = status["state"]
            if state == "complete":
                raise ProjectRunError(
                    f"project {project_id} is already complete", project_id=project_id,
                )
            if state == "not_started":
                raise ProjectRunError(
                    f"project {project_id} has not started; use run", project_id=project_id,
                )
            existing = {
                stage: StageCheckpoint.from_dict(data)
                for stage, data in status["checkpoints"].items()
            }
            if not existing and snapshot.revision.parent_revision_id is None:
                raise ProjectRunError(
                    f"project {project_id} has no checkpoint for the current revision; "
                    "refusing to resume a different revision or orphan run",
                    project_id=project_id,
                )
            target = next(
                (stage for stage in DEFAULT_STAGES
                 if existing.get(stage) is None or existing[stage].status != "done"),
                None,
            )
            if target is None:
                raise ProjectRunError(
                    f"project {project_id} has no resumable stage", project_id=project_id,
                )
            checkpoint = existing.get(target)
            if checkpoint is not None and checkpoint.status == "failed":
                raise ProjectRunError(
                    f"{target} is failed, not interrupted; resume only accepts "
                    "running, waiting_response, ready, or pending stages",
                    project_id=project_id, stage=target, run_id=checkpoint.run_id,
                )
            if checkpoint is not None and checkpoint.status == "waiting_response":
                pending = checkpoint.pending or {}
                response_path = pending.get("response_path")
                if response_path and not Path(response_path).is_file():
                    raise ProjectRunPending(
                        f"response is still missing for {pending.get('key')}",
                        project_id=project_id, stage=target,
                        run_id=checkpoint.run_id or "",
                        run_dir=(self.store.project_dir(project_id) / "runs"
                                 / (checkpoint.run_id or "")),
                        pending=pending,
                        status=status,
                    )

            source_dir: Path | None = None
            source_manifest: dict[str, Any] = {}
            if checkpoint is not None and checkpoint.run_id:
                candidate = (
                    self.store.project_dir(project_id) / "runs" / checkpoint.run_id
                )
                if (candidate / "manifest.json").is_file():
                    source_manifest = self._read_run_json(candidate / "manifest.json")
                    if (candidate / "project-input.json").is_file():
                        source_dir = candidate
                if checkpoint.status in {"running", "waiting_response"} and source_dir is None:
                    raise ProjectRunError(
                        f"{target} has no complete resume source records",
                        project_id=project_id, stage=target, run_id=checkpoint.run_id,
                    )
            base_seed = (
                checkpoint.seed if checkpoint is not None and checkpoint.seed is not None
                else source_manifest.get("seed", 0)
            )
            base_temperature = (
                checkpoint.temperature
                if checkpoint is not None and checkpoint.temperature is not None
                else source_manifest.get("temperature", _default_temperature(target))
            )
            configs = {}
            for stage in DEFAULT_STAGES:
                old = existing.get(stage)
                configs[stage] = _StageConfig(
                    seed=old.seed if old is not None and old.seed is not None else base_seed,
                    temperature=(
                        old.temperature
                        if old is not None and old.temperature is not None
                        else base_temperature if stage == target
                        else _default_temperature(stage)
                    ),
                )
            recorded_context = self._recorded_context_override(
                snapshot, existing, source_dir,
            )
            attempt = self._attempt(
                snapshot, continuation=self._continuation_for_snapshot(snapshot),
                context_packet_override=recorded_context,
            )
            return self._execute(
                attempt, provider, configs, existing,
                resume_stage=target if source_dir is not None else None,
            )

    def _recorded_context_override(
        self, snapshot: ProjectSnapshot, existing: dict[str, StageCheckpoint],
        preferred_source: Path | None,
    ) -> tuple[bool, ContextPacket | None] | None:
        """Pin resume to the packet recorded by the original attempt.

        An ancestor may finish or gain a revision while a child is waiting.  That
        must not make the child's recorded prompt impossible to resume.  The old
        packet is therefore an explicit input to the new attempt, just like the
        old response prefix.  A legacy run without the field uses no packet.
        """
        candidates: list[Path] = []
        if preferred_source is not None:
            candidates.append(preferred_source)
        for stage in DEFAULT_STAGES:
            checkpoint = existing.get(stage)
            if checkpoint is not None and checkpoint.run_id:
                candidates.append(
                    self.store.project_dir(snapshot.project.id) / "runs" / checkpoint.run_id
                )
        seen: set[Path] = set()
        for run_dir in candidates:
            if run_dir in seen:
                continue
            seen.add(run_dir)
            input_path = run_dir / "project-input.json"
            if not input_path.is_file():
                continue
            data = self._read_run_json(input_path)
            raw = data.get("context_packet")
            if raw is None:
                return True, None
            try:
                packet = ContextPacket.from_dict(raw)
            except (KeyError, TypeError, ValueError) as exc:
                raise ProjectRunError(
                    f"invalid recorded context packet: {input_path}: {exc}",
                    project_id=snapshot.project.id,
                ) from exc
            if (
                packet.project_id != snapshot.project.id
                or packet.node_id != snapshot.root_node.id
                or packet.revision_id != snapshot.revision.id
            ):
                raise ProjectRunError(
                    "recorded context packet does not match the current node/revision",
                    project_id=snapshot.project.id,
                )
            return True, packet
        return None

    def dependency_order(
        self, project_id: str, node_id: str | None = None,
    ) -> list[str]:
        """Return stable parent-before-descendant topological order.

        Links are already order-checked by the store.  The explicit visiting
        set is a second line of defence for malformed hand-edited projects.
        """
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ProjectDependencyError(
                    f"cycle detected in work containment at {node_id}",
                    project_id=project_id, node_id=node_id,
                )
            if node_id in visited:
                return
            visiting.add(node_id)
            order.append(node_id)
            for link in self.store.list_links(project_id, node_id):
                visit(link.child_node_id)
            visiting.remove(node_id)
            visited.add(node_id)

        visit(snapshot.root_node.id)
        return order

    # Both names are useful to callers: this is a topological sort restricted
    # to the containment tree, not a general reference-graph sort.
    topological_order = dependency_order

    def _check_tree_dependencies(self, project_id: str, node_id: str) -> None:
        node = self.store.load_node(project_id, node_id)
        seen: set[str] = set()
        while node.parent_id is not None:
            if node.id in seen:
                raise ProjectDependencyError(
                    f"cycle detected in work containment at {node.id}",
                    project_id=project_id, node_id=node.id,
                )
            seen.add(node.id)
            dependency = self.store.load_node(project_id, node.parent_id)
            dependency_status = self.store.status(
                project_id, dependency.id, include_descendants=False,
            )
            if dependency_status["state"] != "complete":
                raise ProjectDependencyError(
                    f"node {node_id} is blocked by {dependency.id} "
                    f"({dependency_status['state']}); complete or resume the dependency first",
                    project_id=project_id, node_id=node_id,
                    dependency_id=dependency.id,
                    dependency_state=dependency_status["state"],
                )
            node = dependency

    def run_tree(
        self, project_id: str, provider: Provider, *, node_id: str | None = None,
        seed: int = 0, temperature: float | None = None,
    ) -> ProjectTreeRunResult:
        """Run every not-started node in parent-first order, stopping safely.

        Completed nodes are left untouched.  A failed, waiting, or otherwise
        unfinished node is never bypassed, so descendants cannot be generated
        against an incomplete ancestor.  Individual ``resume`` and
        ``continue_project`` operations remain available for that node.
        """
        order = self.dependency_order(project_id, node_id)
        results: list[ProjectRunResult] = []
        for current_id in order:
            self._check_tree_dependencies(project_id, current_id)
            state = self.store.status(
                project_id, current_id, include_descendants=False,
            )["state"]
            if state == "complete":
                continue
            if state != "not_started":
                raise ProjectDependencyError(
                    f"node {current_id} is {state}; run-tree will not skip an "
                    "unfinished or failed dependency (use resume for an interrupted run)",
                    project_id=project_id, node_id=current_id,
                    dependency_id=current_id, dependency_state=state,
                )
            results.append(self.run(
                project_id, provider, node_id=current_id,
                seed=seed, temperature=temperature,
            ))
        selected = self.store.load_node_snapshot(project_id, node_id).root_node.id
        return ProjectTreeRunResult(
            project_id=project_id,
            root_node_id=selected,
            order=tuple(order),
            results=tuple(results),
            status=self.store.status(project_id, selected),
        )

    def _attempt(
        self, snapshot: ProjectSnapshot, *, continuation: ContinuationContext | None = None,
        context_packet_override: tuple[bool, ContextPacket | None] | None = None,
    ) -> _Attempt:
        packet = (
            build_context_packet(self.store, snapshot.project.id, snapshot.root_node.id)
            if context_packet_override is None
            else context_packet_override[1]
        )
        return _Attempt(
            snapshot=snapshot,
            pipeline=adapt_work_spec(snapshot.root_node.id, snapshot.revision.spec),
            attempt_id=new_id("att"),
            continuation=continuation,
            context_packet=packet,
        )

    def _continuation_for_snapshot(
        self, snapshot: ProjectSnapshot,
    ) -> ContinuationContext | None:
        revision = snapshot.revision
        if revision.parent_revision_id is None:
            return None
        missing = [stage for stage in DEFAULT_STAGES if stage not in revision.parent_runs]
        if missing:
            raise ProjectRunError(
                f"continuation revision is missing parent runs: {', '.join(missing)}",
                project_id=snapshot.project.id,
            )
        parent = self.store.load_revision(
            snapshot.project.id, snapshot.root_node.id, revision.parent_revision_id,
        )
        run_dirs = {}
        for stage in DEFAULT_STAGES:
            run_id = revision.parent_runs[stage]
            run_dir = self.store.project_dir(snapshot.project.id) / "runs" / run_id
            run_input = self._read_run_json(run_dir / "project-input.json")
            if (
                run_input.get("revision_id") != parent.id
                or run_input.get("node_id") != snapshot.root_node.id
                or run_input.get("stage") != stage
            ):
                raise ProjectRunError(
                    f"parent run {run_id} does not match continuation parent revision",
                    project_id=snapshot.project.id,
                )
            run_dirs[stage] = run_dir
        canon = load_canon(run_dirs["plan"] / "canon")
        order = canon.chapter_order()
        if len(order) != parent.spec.chapter_count:
            raise ProjectRunError(
                "parent canon chapter count differs from parent WorkSpec",
                project_id=snapshot.project.id,
            )
        drafts = []
        for chapter_id in order:
            path = run_dirs["draft"] / "text" / f"{chapter_id}.md"
            if not path.is_file():
                raise ProjectRunError(
                    f"parent chapter text is missing: {path}",
                    project_id=snapshot.project.id,
                )
            chapter = canon.chapters[chapter_id]
            drafts.append(ChapterDraft(
                id=chapter_id,
                text=path.read_text(encoding="utf-8"),
                day=chapter.day,
                location=chapter.location,
                preserve_text=True,
            ))
        return ContinuationContext(
            parent_revision_id=parent.id,
            parent_runs=dict(revision.parent_runs),
            parent_chapter_count=parent.spec.chapter_count,
            canon=canon,
            drafts=tuple(drafts),
        )

    @staticmethod
    def _read_run_json(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectRunError(f"cannot read run record {path}: {exc}", project_id="") from exc
        if not isinstance(data, dict):
            raise ProjectRunError(f"run record must be an object: {path}", project_id="")
        return data

    def _execute(
        self,
        attempt: _Attempt,
        provider: Provider,
        configs: dict[str, _StageConfig],
        existing: dict[str, StageCheckpoint],
        *,
        resume_stage: str | None = None,
    ) -> ProjectRunResult:
        project_id = attempt.snapshot.project.id
        results: dict[str, _StageResult] = {}
        for stage in DEFAULT_STAGES:
            old = existing.get(stage)
            if old is not None and old.status == "done":
                results[stage] = self._load_done_stage(attempt, old)
                continue
            if old is None:
                old = self._new_checkpoint(
                    attempt, stage, "pending", config=configs[stage],
                )
                self.store.save_checkpoint(old)
                existing[stage] = old

            source_run_id = old.run_id if stage == resume_stage else None
            resume_provider = None
            stage_provider = provider
            if attempt.context_packet is not None and stage != "plan":
                stage_provider = _ContextProvider(
                    provider, attempt.context_packet.prompt_suffix(),
                )
            if source_run_id is not None:
                try:
                    resume_provider = ResumeProvider(
                        self.store.project_dir(project_id) / "runs" / source_run_id,
                        stage_provider,
                        expected_input=self._expected_input(attempt, stage),
                        expected_seed=configs[stage].seed,
                        expected_temperature=configs[stage].temperature,
                        # The coordinator selected a non-done checkpoint.  An ok
                        # ledger here means a crash before its done checkpoint.
                        allow_ok=True,
                    )
                except ResumeError as exc:
                    raise ProjectRunError(
                        f"cannot resume {stage}: {exc}",
                        project_id=project_id, stage=stage, run_id=source_run_id,
                        run_dir=self.store.project_dir(project_id) / "runs" / source_run_id,
                    ) from exc
                stage_provider = resume_provider
            input_artifacts = self._input_artifacts(stage, results)
            if stage == "plan":
                operation = lambda ledger: self._plan(
                    attempt, ledger, stage_provider, configs[stage].seed,
                )
            elif stage == "design":
                operation = lambda ledger: build_design(
                    attempt.pipeline.task, stage_provider, ledger, results["plan"].value,
                    temperature=configs[stage].temperature,
                    seed=configs[stage].seed,
                )
            else:
                operation = lambda ledger: self._draft(
                    attempt, ledger, results["plan"], results["design"],
                    stage_provider, configs[stage],
                )
            results[stage] = self._run_stage(
                attempt, stage, stage_provider,
                config=configs[stage],
                input_artifacts=input_artifacts,
                operation=operation,
                resume_of=source_run_id,
                resume_provider=resume_provider,
            )

        current = self.store.load_node_snapshot(
            project_id, attempt.snapshot.root_node.id,
        )
        if current.root_node.current_revision_id != attempt.snapshot.revision.id:
            raise ProjectRunError(
                "current revision changed during the attempt", project_id=project_id,
            )
        now = utc_now()
        self.store.save_node(replace(current.root_node, updated_at=now))
        self.store.save_project(replace(current.project, updated_at=now))
        self.store.sync_child_links(
            project_id, current.root_node.id, current.root_node.current_revision_id,
        )
        return ProjectRunResult(
            attempt_id=attempt.attempt_id,
            stage_runs={stage: results[stage].run_id for stage in DEFAULT_STAGES},
            status=self.store.status(project_id, current.root_node.id),
        )

    @staticmethod
    def _expected_input(attempt: _Attempt, stage: str) -> dict[str, Any]:
        return {
            "project_id": attempt.snapshot.project.id,
            "node_id": attempt.snapshot.root_node.id,
            "revision_id": attempt.snapshot.revision.id,
            "spec_sha256": attempt.snapshot.revision.spec_sha256,
            "spec": attempt.snapshot.revision.spec.to_dict(),
            "stage": stage,
            **(
                {"context_packet": attempt.context_packet.to_dict()}
                if attempt.context_packet else {}
            ),
        }

    @staticmethod
    def _input_artifacts(
        stage: str, results: dict[str, _StageResult],
    ) -> tuple[ArtifactRef, ...]:
        if stage == "plan":
            return ()
        if stage == "design":
            return results["plan"].artifacts
        return (*results["plan"].artifacts, *results["design"].artifacts)

    def _load_done_stage(
        self, attempt: _Attempt, checkpoint: StageCheckpoint,
    ) -> _StageResult:
        if checkpoint.run_id is None:
            raise ProjectRunError(
                "done checkpoint has no run", project_id=attempt.snapshot.project.id,
                stage=checkpoint.stage,
            )
        run_dir = self.store.project_dir(attempt.snapshot.project.id) / "runs" / checkpoint.run_id
        value = None
        if checkpoint.stage == "plan":
            value = load_canon(run_dir / "canon")
            if len(value.chapters) != attempt.pipeline.chapters:
                raise ProjectRunError(
                    "completed plan chapter count differs from WorkSpec",
                    project_id=attempt.snapshot.project.id, stage="plan",
                    run_id=checkpoint.run_id,
                )
        return _StageResult(
            value=value,
            run_id=checkpoint.run_id,
            run_dir=run_dir,
            artifacts=checkpoint.artifacts,
        )

    @staticmethod
    def _new_checkpoint(
        attempt: _Attempt, stage: str, status: str, *, config: _StageConfig,
    ) -> StageCheckpoint:
        now = utc_now()
        return StageCheckpoint(
            project_id=attempt.snapshot.project.id,
            node_id=attempt.snapshot.root_node.id,
            revision_id=attempt.snapshot.revision.id,
            stage=stage,
            status=status,
            attempt_id=attempt.attempt_id,
            created_at=now,
            updated_at=now,
            seed=config.seed,
            temperature=config.temperature,
        )

    def _plan(
        self, attempt: _Attempt, ledger: RunLedger, provider: Provider, seed: int,
    ) -> Canon:
        plan = build_plan(
            attempt.pipeline.task,
            provider,
            ledger,
            chapters=attempt.pipeline.chapters,
            target_chars=attempt.pipeline.total_target,
            temperature=ledger.temperature if ledger.temperature is not None else 0.6,
            seed=seed,
            prompt_suffix=(
                (attempt.continuation.prompt_suffix if attempt.continuation else "")
                + (
                    attempt.context_packet.prompt_suffix()
                    if attempt.context_packet else ""
                )
            ),
        )
        # Keep the frozen-task implementation untouched; replace only its
        # derived note with the creative project's actual provenance.
        ledger.write_text("brief.md", _project_brief(attempt))
        canon = load_canon(ledger.path / "canon")
        if len(canon.chapters) != attempt.pipeline.chapters:
            raise ValueError(
                f"plan produced {len(canon.chapters)} chapters; "
                f"WorkSpec requires {attempt.pipeline.chapters}"
            )
        if plan.task.id != attempt.snapshot.root_node.id:
            raise ValueError("plan task does not match project node")
        if attempt.continuation is not None:
            validate_continuation_canon(attempt.continuation, canon)
        return canon

    def _draft(
        self, attempt: _Attempt, ledger: RunLedger, plan: _StageResult,
        design: _StageResult, provider: Provider, config: _StageConfig,
    ) -> Draft:
        draft = build_story(
            attempt.pipeline.task, provider, ledger,
            canon=plan.value,
            chapters=attempt.pipeline.chapters,
            target=attempt.pipeline.chapter_target,
            temperature=config.temperature,
            seed=config.seed,
            design_dir=design.run_dir / "design",
            initial_drafts=(
                attempt.continuation.drafts if attempt.continuation else ()
            ),
        )
        if len(draft.chapters) != attempt.pipeline.chapters:
            raise ValueError(
                f"draft produced {len(draft.chapters)} chapters; "
                f"WorkSpec requires {attempt.pipeline.chapters}"
            )
        return draft

    def _run_stage(
        self, attempt: _Attempt, stage: str, provider: Provider, *,
        config: _StageConfig,
        input_artifacts: tuple[ArtifactRef, ...],
        operation: Callable[[RunLedger], Any],
        resume_of: str | None,
        resume_provider: ResumeProvider | None,
    ) -> _StageResult:
        project_id = attempt.snapshot.project.id
        run_id = f"{attempt.attempt_id}-{stage}"
        checkpoint = replace(
            self._new_checkpoint(attempt, stage, "ready", config=config),
            run_id=run_id,
            resume_of=resume_of,
        )
        self.store.save_checkpoint(checkpoint)
        ledger: RunLedger | None = None
        try:
            ledger = RunLedger.create(
                self.store.project_dir(project_id) / "runs",
                task_id=attempt.pipeline.task.id,
                system="s1",
                seed=config.seed,
                protocol_version=PROJECT_PROTOCOL,
                run_id=run_id,
                model=provider.model,
                provider=provider.name,
                temperature=config.temperature,
                revision_id=(
                    attempt.snapshot.revision.id if attempt.continuation else None
                ),
            )
            ledger.write_json("project-input.json", {
                "schema_version": SCHEMA_VERSION,
                "attempt_id": attempt.attempt_id,
                "stage": stage,
                "project_id": project_id,
                "node_id": attempt.snapshot.root_node.id,
                "revision_id": attempt.snapshot.revision.id,
                "spec_sha256": attempt.snapshot.revision.spec_sha256,
                "spec": attempt.snapshot.revision.spec.to_dict(),
                **(
                    {"context_packet": attempt.context_packet.to_dict()}
                    if attempt.context_packet else {}
                ),
                "input_artifacts": [item.to_dict() for item in input_artifacts],
                "resume_of": resume_of,
                "resume_source_responses_sha256": (
                    resume_provider.source_responses_sha256 if resume_provider else None
                ),
                "continuation": (
                    attempt.continuation.as_dict() if attempt.continuation else None
                ),
            })
            ledger.write_manifest()
            checkpoint = replace(checkpoint, status="running", updated_at=utc_now())
            self.store.save_checkpoint(checkpoint)

            value = operation(ledger)
            if ledger.status != "ok":
                raise ValueError(f"stage finished with unexpected ledger status {ledger.status}")
            if resume_provider is not None:
                ledger.write_json("resume-audit.json", resume_provider.finalize())
                ledger.write_manifest()
            artifacts = self._collect_artifacts(project_id, stage, ledger)
        except ResponsePendingError as exc:
            if ledger is None:  # pragma: no cover - providers run after ledger creation
                raise
            raise self._pending_result(
                attempt, stage, run_id, ledger, checkpoint, exc,
            ) from exc
        except Exception as exc:
            pending_error = self._find_pending(exc)
            if pending_error is not None and ledger is not None:
                raise self._pending_result(
                    attempt, stage, run_id, ledger, checkpoint, pending_error,
                ) from exc
            message = str(exc) or type(exc).__name__
            if ledger is not None and ledger.status != "failed":
                ledger.fail(f"{stage}: {message}")
            checkpoint = replace(
                checkpoint, status="failed", error=message, pending=None,
                artifacts=(), updated_at=utc_now(),
            )
            self.store.save_checkpoint(checkpoint)
            raise ProjectRunError(
                f"{stage} stage failed: {message}",
                project_id=project_id, stage=stage, run_id=run_id,
                run_dir=ledger.path if ledger is not None else None,
            ) from exc
        checkpoint = replace(
            checkpoint, status="done", artifacts=artifacts,
            error=None, pending=None, updated_at=utc_now(),
        )
        self.store.save_checkpoint(checkpoint)
        return _StageResult(
            value=value, run_id=run_id, run_dir=ledger.path, artifacts=artifacts,
        )

    @staticmethod
    def _find_pending(exc: BaseException) -> ResponsePendingError | None:
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            if isinstance(current, ResponsePendingError):
                return current
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return None

    def _pending_result(
        self, attempt: _Attempt, stage: str, run_id: str, ledger: RunLedger,
        checkpoint: StageCheckpoint, exc: ResponsePendingError,
    ) -> ProjectRunPending:
        project_id = attempt.snapshot.project.id
        ledger.error = str(exc)
        ledger.finish("waiting_response")
        pending = self._pending_details(exc)
        self.store.save_checkpoint(replace(
            checkpoint, status="waiting_response", error=None,
            pending=pending, artifacts=(), updated_at=utc_now(),
        ))
        return ProjectRunPending(
            f"{stage} is waiting for operator response {exc.key}",
            project_id=project_id, stage=stage, run_id=run_id,
            run_dir=ledger.path, pending=pending,
            status=self.store.status(project_id, attempt.snapshot.root_node.id),
        )

    @staticmethod
    def _pending_details(exc: ResponsePendingError) -> dict[str, Any]:
        response_path = Path(exc.response_path).expanduser().resolve()
        request_path = None
        if response_path.parent.name == "responses":
            request_path = response_path.parent.parent / "requests" / response_path.name
        return {
            "key": exc.key,
            "purpose": exc.purpose,
            "prompt_hash": exc.prompt_hash,
            "response_path": str(response_path),
            "request_path": str(request_path) if request_path is not None else None,
        }

    def _collect_artifacts(
        self, project_id: str, stage: str, ledger: RunLedger,
    ) -> tuple[ArtifactRef, ...]:
        if stage == "plan":
            relatives = ["brief.md", "plan.json"] + [
                str(path.relative_to(ledger.path).as_posix())
                for path in sorted((ledger.path / "canon").glob("*.json"))
            ]
        elif stage == "design":
            relatives = ["design.json"] + [
                str(path.relative_to(ledger.path).as_posix())
                for path in sorted((ledger.path / "design").glob("*.json"))
            ]
        elif stage == "draft":
            relatives = ["draft.json"] + [
                str(path.relative_to(ledger.path).as_posix())
                for path in sorted((ledger.path / "text").glob("*.md"))
            ]
        else:  # pragma: no cover - runner passes only DEFAULT_STAGES
            raise ValueError(f"unknown project stage: {stage}")
        if (ledger.path / "resume-audit.json").is_file():
            relatives.append("resume-audit.json")
        return tuple(
            self.store.artifact_ref(
                project_id, ledger.run_id, relative,
                artifact_id=f"{stage}-{relative.replace('/', '-')}",
            )
            for relative in relatives
        )
