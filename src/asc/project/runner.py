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
from .model import ArtifactRef, ProjectSnapshot, StageCheckpoint, new_id, utc_now
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
class _Attempt:
    snapshot: ProjectSnapshot
    pipeline: PipelineInput
    attempt_id: str


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
        temperature: float | None = None,
    ) -> ProjectRunResult:
        """Run plan -> design -> draft once for a not-started current revision."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_snapshot(project_id)
            state = self.store.status(project_id)["state"]
            if state != "not_started":
                raise ProjectRunError(
                    f"project {project_id} is {state}; run requires a not-started revision "
                    "(resume and continuation are separate operations)",
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

    def resume(self, project_id: str, provider: Provider) -> ProjectRunResult:
        """Resume the first unfinished stage without regenerating completed work."""
        with self.store.execution_lock(project_id):
            snapshot = self.store.load_snapshot(project_id)
            status = self.store.status(project_id)
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
            if not existing:
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
            attempt = self._attempt(snapshot)
            return self._execute(
                attempt, provider, configs, existing,
                resume_stage=target if source_dir is not None else None,
            )

    @staticmethod
    def _attempt(snapshot: ProjectSnapshot) -> _Attempt:
        return _Attempt(
            snapshot=snapshot,
            pipeline=adapt_work_spec(snapshot.root_node.id, snapshot.revision.spec),
            attempt_id=new_id("att"),
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
            if source_run_id is not None:
                try:
                    resume_provider = ResumeProvider(
                        self.store.project_dir(project_id) / "runs" / source_run_id,
                        provider,
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

        current = self.store.load_snapshot(project_id)
        if current.root_node.current_revision_id != attempt.snapshot.revision.id:
            raise ProjectRunError(
                "current revision changed during the attempt", project_id=project_id,
            )
        now = utc_now()
        self.store.save_node(replace(current.root_node, updated_at=now))
        self.store.save_project(replace(current.project, updated_at=now))
        return ProjectRunResult(
            attempt_id=attempt.attempt_id,
            stage_runs={stage: results[stage].run_id for stage in DEFAULT_STAGES},
            status=self.store.status(project_id),
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
                "input_artifacts": [item.to_dict() for item in input_artifacts],
                "resume_of": resume_of,
                "resume_source_responses_sha256": (
                    resume_provider.source_responses_sha256 if resume_provider else None
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
            status=self.store.status(project_id),
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
