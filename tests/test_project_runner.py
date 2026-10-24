from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    PROJECT_PROTOCOL,
    ProjectCorruptError,
    ProjectLockError,
    ProjectRunError,
    ProjectRunner,
    ProjectStore,
    WorkSpec,
    adapt_work_spec,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
)
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "story_project.py"


def project_responses() -> dict[str, str]:
    """Move t01 fixture fallbacks to project-independent purpose keys."""
    responses = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            responses[":".join(parts[:-1])] = text
    return responses


def make_project(store: ProjectStore, project_id: str = "prj-run", chapters: int = 3):
    return store.create_project(
        WorkSpec(
            title="創作projectの灯台",
            premise="任意のpremiseから三章の作品を作る。",
            chapter_count=chapters,
            target_chars_per_chapter=1200,
        ),
        project_id=project_id,
    )


def test_work_spec_adapter_uses_project_identity_and_targets(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store, chapters=5)
    adapted = adapt_work_spec(snapshot.root_node.id, snapshot.revision.spec)
    assert adapted.task.id == snapshot.root_node.id
    assert adapted.task.logline == "任意のpremiseから三章の作品を作る。"
    assert adapted.task.control == "creative-project"
    assert adapted.task.must_include == ()
    assert adapted.chapters == 5
    assert adapted.chapter_target == (1200, 1200)
    assert adapted.total_target == (6000, 6000)


def test_runner_completes_three_stage_runs_and_verifies_artifacts(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    result = ProjectRunner(store).run(
        snapshot.project.id, ScriptedProvider(project_responses()),
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["stages"] == {"plan": "done", "design": "done", "draft": "done"}
    assert len(status["runs"]) == 3
    assert len(status["artifact_refs"]) > 10

    for stage, run_id in result.stage_runs.items():
        run_dir = store.project_dir(snapshot.project.id) / "runs" / run_id
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        run_input = json.loads((run_dir / "project-input.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "ok"
        assert manifest["protocol_version"] == PROJECT_PROTOCOL
        assert manifest["task_id"] == snapshot.root_node.id
        assert run_input["attempt_id"] == result.attempt_id
        assert run_input["stage"] == stage
        assert run_input["spec_sha256"] == snapshot.revision.spec_sha256
        assert status["checkpoints"][stage]["run_id"] == run_id
        assert status["checkpoints"][stage]["status"] == "done"

    draft_run = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["draft"]
    assert sorted(path.name for path in (draft_run / "text").glob("*.md")) == [
        "ch01.md", "ch02.md", "ch03.md",
    ]
    plan_run = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["plan"]
    brief = (plan_run / "brief.md").read_text(encoding="utf-8")
    assert "protocol-v1の固定taskではありません" in brief

    with pytest.raises(ProjectRunError, match="is complete"):
        ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(project_responses()))

    input_path = plan_run / "project-input.json"
    original_input = input_path.read_text(encoding="utf-8")
    changed_input = json.loads(original_input)
    changed_input["revision_id"] = "rev-other"
    input_path.write_text(json.dumps(changed_input), encoding="utf-8")
    with pytest.raises(ProjectCorruptError, match="revision_id"):
        store.status(snapshot.project.id)
    input_path.write_text(original_input, encoding="utf-8")

    # A done status is not trusted without the referenced bytes.
    next(path for path in (draft_run / "text").glob("*.md")).write_text(
        "changed", encoding="utf-8",
    )
    with pytest.raises(ProjectCorruptError, match="hash differs"):
        store.status(snapshot.project.id)


def test_failed_stage_preserves_completed_stage_and_pending_successor(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    responses = project_responses()
    del responses["design:world"]
    with pytest.raises(ProjectRunError) as caught:
        ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(responses))
    assert caught.value.stage == "design"
    assert caught.value.run_dir is not None

    status = store.status(snapshot.project.id)
    assert status["state"] == "failed"
    assert status["stages"] == {"plan": "done", "design": "failed", "draft": "pending"}
    assert len(status["runs"]) == 2
    design_manifest = json.loads(
        (caught.value.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert design_manifest["status"] == "failed"
    plan_run = status["checkpoints"]["plan"]["run_id"]
    plan_manifest = json.loads(
        (store.project_dir(snapshot.project.id) / "runs" / plan_run / "manifest.json")
        .read_text(encoding="utf-8")
    )
    assert plan_manifest["status"] == "ok"


def test_plan_must_respect_requested_chapter_count(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store, chapters=2)
    with pytest.raises(ProjectRunError) as caught:
        ProjectRunner(store).run(
            snapshot.project.id, ScriptedProvider(project_responses()),
        )
    assert caught.value.stage == "plan"
    assert "WorkSpec requires 2" in str(caught.value)
    status = store.status(snapshot.project.id)
    assert status["state"] == "failed"
    assert status["stages"]["plan"] == "failed"
    assert status["stages"]["design"] == "pending"
    assert len(status["runs"]) == 1


def test_execution_lock_rejects_a_concurrent_attempt(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    with store.execution_lock(snapshot.project.id):
        with pytest.raises(ProjectLockError):
            ProjectRunner(ProjectStore(tmp_path)).run(
                snapshot.project.id, ScriptedProvider(project_responses()),
            )
    assert store.status(snapshot.project.id)["state"] == "not_started"


def test_cli_run_and_status_in_another_process(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store, project_id="prj-cli-run")
    script = tmp_path / "responses.json"
    script.write_text(
        json.dumps({"responses": project_responses()}, ensure_ascii=False), encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "run",
            snapshot.project.id, "--provider", "scripted", "--script", str(script), "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    run_status = json.loads(completed.stdout)
    assert run_status["state"] == "complete"
    assert run_status["attempt_id"] in run_status["runs"][0]

    loaded = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "status",
            snapshot.project.id, "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert loaded.returncode == 0, loaded.stderr
    persisted = json.loads(loaded.stdout)
    assert persisted["state"] == "complete"
    assert persisted["stages"] == run_status["stages"]
    assert persisted["checkpoints"] == run_status["checkpoints"]
    assert persisted["artifact_refs"] == run_status["artifact_refs"]
