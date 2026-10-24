"""Run the single-work S1 vertical slice for a persistent creative project.

One attempt contains three independent run ledgers (plan, design, draft).  A
shared attempt id links them, while each stage gets its own success/failure
manifest and content-hashed output references.  Later stages read earlier run
artifacts without copying or rewriting them.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from ..pipeline import (
    Draft,
    Provider,
    RunLedger,
    build_design,
    build_plan,
    build_story,
)
from ..story.canon import Canon, load_canon
from .adapter import PROJECT_PROTOCOL, PipelineInput, adapt_work_spec
from .model import ArtifactRef, ProjectSnapshot, StageCheckpoint, new_id, utc_now
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
    seed: int


@dataclass(frozen=True)
class _StageResult:
    value: Any
    ledger: RunLedger
    artifacts: tuple[ArtifactRef, ...]


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
            attempt = _Attempt(
                snapshot=snapshot,
                pipeline=adapt_work_spec(snapshot.root_node.id, snapshot.revision.spec),
                attempt_id=new_id("att"),
                seed=seed,
            )
            for stage in DEFAULT_STAGES:
                now = utc_now()
                self.store.save_checkpoint(StageCheckpoint(
                    project_id=project_id,
                    node_id=snapshot.root_node.id,
                    revision_id=snapshot.revision.id,
                    stage=stage,
                    status="pending",
                    attempt_id=attempt.attempt_id,
                    created_at=now,
                    updated_at=now,
                ))

            plan = self._run_stage(
                attempt, "plan", provider,
                temperature=temperature if temperature is not None else 0.6,
                input_artifacts=(),
                operation=lambda ledger: self._plan(attempt, ledger, provider),
            )
            design = self._run_stage(
                attempt, "design", provider,
                temperature=temperature if temperature is not None else 0.6,
                input_artifacts=plan.artifacts,
                operation=lambda ledger: build_design(
                    attempt.pipeline.task, provider, ledger, plan.value,
                    temperature=temperature if temperature is not None else 0.6,
                    seed=seed,
                ),
            )
            self._run_stage(
                attempt, "draft", provider,
                temperature=temperature if temperature is not None else 0.8,
                input_artifacts=(*plan.artifacts, *design.artifacts),
                operation=lambda ledger: self._draft(
                    attempt, ledger, plan, design, provider, temperature, seed,
                ),
            )
            current = self.store.load_snapshot(project_id)
            if current.root_node.current_revision_id != snapshot.revision.id:
                raise ProjectRunError(
                    "current revision changed during the attempt",
                    project_id=project_id,
                )
            now = utc_now()
            self.store.save_node(replace(current.root_node, updated_at=now))
            self.store.save_project(replace(current.project, updated_at=now))
            stage_runs = {
                stage: f"{attempt.attempt_id}-{stage}" for stage in DEFAULT_STAGES
            }
            return ProjectRunResult(
                attempt_id=attempt.attempt_id,
                stage_runs=stage_runs,
                status=self.store.status(project_id),
            )

    def _plan(self, attempt: _Attempt, ledger: RunLedger, provider: Provider) -> Canon:
        plan = build_plan(
            attempt.pipeline.task,
            provider,
            ledger,
            chapters=attempt.pipeline.chapters,
            target_chars=attempt.pipeline.total_target,
            temperature=ledger.temperature if ledger.temperature is not None else 0.6,
            seed=attempt.seed,
        )
        # build_plan's frozen-task note is accurate for experiments but not for
        # an arbitrary creative project.  Replace only the derived brief file;
        # prompts, responses, canon, and frozen pipeline code remain untouched.
        ledger.write_text("brief.md", _project_brief(attempt))
        canon = load_canon(ledger.path / "canon")
        if len(canon.chapters) != attempt.pipeline.chapters:
            raise ValueError(
                f"plan produced {len(canon.chapters)} chapters; "
                f"WorkSpec requires {attempt.pipeline.chapters}"
            )
        if plan.task.id != attempt.snapshot.root_node.id:  # defensive association check
            raise ValueError("plan task does not match project node")
        return canon

    def _draft(
        self, attempt: _Attempt, ledger: RunLedger, plan: _StageResult,
        design: _StageResult, provider: Provider, temperature: float | None, seed: int,
    ) -> Draft:
        draft = build_story(
            attempt.pipeline.task, provider, ledger,
            canon=plan.value,
            chapters=attempt.pipeline.chapters,
            target=attempt.pipeline.chapter_target,
            temperature=temperature if temperature is not None else 0.8,
            seed=seed,
            design_dir=design.ledger.path / "design",
        )
        if len(draft.chapters) != attempt.pipeline.chapters:
            raise ValueError(
                f"draft produced {len(draft.chapters)} chapters; "
                f"WorkSpec requires {attempt.pipeline.chapters}"
            )
        return draft

    def _run_stage(
        self, attempt: _Attempt, stage: str, provider: Provider, *,
        temperature: float, input_artifacts: tuple[ArtifactRef, ...],
        operation: Callable[[RunLedger], Any],
    ) -> _StageResult:
        project_id = attempt.snapshot.project.id
        run_id = f"{attempt.attempt_id}-{stage}"
        now = utc_now()
        checkpoint = StageCheckpoint(
            project_id=project_id,
            node_id=attempt.snapshot.root_node.id,
            revision_id=attempt.snapshot.revision.id,
            stage=stage,
            status="ready",
            attempt_id=attempt.attempt_id,
            run_id=run_id,
            created_at=now,
            updated_at=now,
        )
        self.store.save_checkpoint(checkpoint)
        ledger: RunLedger | None = None
        try:
            ledger = RunLedger.create(
                self.store.project_dir(project_id) / "runs",
                task_id=attempt.pipeline.task.id,
                system="s1",
                seed=attempt.seed,
                protocol_version=PROJECT_PROTOCOL,
                run_id=run_id,
                model=provider.model,
                provider=provider.name,
                temperature=temperature,
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
            })
            ledger.write_manifest()
            checkpoint = replace(checkpoint, status="running", updated_at=utc_now())
            self.store.save_checkpoint(checkpoint)

            value = operation(ledger)
            if ledger.status != "ok":
                raise ValueError(f"stage finished with unexpected ledger status {ledger.status}")
            artifacts = self._collect_artifacts(project_id, stage, ledger)
        except Exception as exc:
            message = str(exc) or type(exc).__name__
            if ledger is not None and ledger.status != "failed":
                ledger.fail(f"{stage}: {message}")
            checkpoint = replace(
                checkpoint, status="failed", error=message,
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
            error=None, updated_at=utc_now(),
        )
        self.store.save_checkpoint(checkpoint)
        return _StageResult(value=value, ledger=ledger, artifacts=artifacts)

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
        return tuple(
            self.store.artifact_ref(
                project_id, ledger.run_id, relative,
                artifact_id=f"{stage}-{relative.replace('/', '-')}",
            )
            for relative in relatives
        )
