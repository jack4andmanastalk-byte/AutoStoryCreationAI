"""Retrying a failed stage: a fresh run that keeps the failed attempt visible."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from types import SimpleNamespace  # noqa: E402

from asc.pipeline import (  # noqa: E402
    GenerationRequest,
    ProviderError,
    ReplayProvider,
    ResponsePendingError,
    RunLedger,
    ScriptedProvider,
    build_design,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    PROJECT_PROTOCOL,
    ProjectRunner,
    ProjectRunError,
    ProjectRunPending,
    ProjectStore,
    WorkSpec,
    inspect_project,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
SCRIPT = ROOT / "scripts" / "story_project.py"


def responses() -> dict[str, str]:
    out = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            out[":".join(parts[:-1])] = text
    return out


def spec(title: str = "再試行") -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の短い物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


class FailOnce:
    """Behave like a provider command that fails on its first call."""

    name = "fail-once"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, message: str = "provider exited 2"):
        self.delegate = delegate
        self.purpose = purpose
        self.message = message
        self.failed = False

    def generate(self, request: GenerationRequest):
        if request.purpose == self.purpose and not self.failed:
            self.failed = True
            raise ProviderError(self.message)
        return self.delegate.generate(request)


class FailOnceProcess(FailOnce):
    """A realistic interruption: the process dies without a usable response."""

    name = "command"


def failed_project(tmp_path: Path, purpose: str = "plan", project_id: str = "prj-retry"):
    store = ProjectStore(tmp_path)
    store.create_project(spec(), project_id=project_id)
    provider = FailOnce(ScriptedProvider(responses()), purpose)
    with pytest.raises(ProjectRunError) as caught:
        ProjectRunner(store).run(project_id, provider)
    return store, caught.value


def test_failed_stage_needs_an_explicit_retry(tmp_path: Path):
    store, error = failed_project(tmp_path)
    assert error.stage == "plan"
    status = store.status("prj-retry")
    assert status["state"] == "failed"
    assert status["checkpoints"]["plan"]["status"] == "failed"
    assert status["checkpoints"]["plan"]["error"]
    with pytest.raises(ProjectRunError, match="not interrupted"):
        ProjectRunner(store).resume("prj-retry", ScriptedProvider(responses()))
    # The refusal names the way forward.
    with pytest.raises(ProjectRunError, match="--retry-failed"):
        ProjectRunner(store).resume("prj-retry", ScriptedProvider(responses()))
    # Nothing changed while refusing.
    assert store.status("prj-retry")["state"] == "failed"


def test_retry_starts_a_new_run_and_keeps_the_failed_one(tmp_path: Path):
    store, error = failed_project(tmp_path, purpose="plan")
    failed_run = error.run_id
    project_dir = store.project_dir("prj-retry")
    failed_manifest = (project_dir / "runs" / failed_run / "manifest.json").read_bytes()

    result = ProjectRunner(store).resume(
        "prj-retry", ScriptedProvider(responses()), retry_failed=True,
    )
    status = result.status
    assert status["state"] == "complete"
    plan = status["checkpoints"]["plan"]
    assert plan["status"] == "done"
    assert plan["retry_of"] == failed_run
    assert plan["run_id"] != failed_run
    assert plan["error"] is None
    # The failed attempt is intact and still names its error.
    assert (project_dir / "runs" / failed_run / "manifest.json").read_bytes() == (
        failed_manifest
    )
    manifest = json.loads((project_dir / "runs" / failed_run / "manifest.json")
                          .read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    new_input = json.loads(
        (project_dir / "runs" / plan["run_id"] / "project-input.json")
        .read_text(encoding="utf-8")
    )
    assert new_input["retry_of"] == failed_run
    assert new_input["resume_of"] is None
    # The retry is a normal, healthy revision afterwards.
    report = inspect_project(store, "prj-retry")
    assert report.ok is True
    assert report.findings == ()


def test_retry_keeps_completed_stages_and_only_reruns_the_failed_one(tmp_path: Path):
    store, error = failed_project(tmp_path, purpose="design:world")
    plan_run = store.status("prj-retry")["checkpoints"]["plan"]["run_id"]
    failed_run = error.run_id
    result = ProjectRunner(store).resume(
        "prj-retry", ScriptedProvider(responses()), retry_failed=True,
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["checkpoints"]["plan"]["run_id"] == plan_run
    assert status["checkpoints"]["design"]["retry_of"] == failed_run
    assert status["checkpoints"]["design"]["run_id"] != failed_run


def test_retry_of_a_draft_failure_regenerates_the_chapters(tmp_path: Path):
    store, error = failed_project(tmp_path, purpose="draft:ch02")
    assert error.stage == "draft"
    failed_run = error.run_id
    result = ProjectRunner(store).resume(
        "prj-retry", ScriptedProvider(responses()), retry_failed=True,
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["checkpoints"]["draft"]["retry_of"] == failed_run
    texts = {
        row["artifact_id"]: row["sha256"]
        for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    }
    assert set(texts) == {"draft-text-ch01.md", "draft-text-ch02.md", "draft-text-ch03.md"}
    # No resume audit: a retry replays nothing from the failed run.
    draft_run = store.project_dir("prj-retry") / "runs" / status["checkpoints"]["draft"]["run_id"]
    assert not (draft_run / "resume-audit.json").exists()


class InterruptOnce(FailOnce):
    """Stop the stage and wait for an operator response instead of failing."""

    def generate(self, request: GenerationRequest):
        if request.purpose == self.purpose and not self.failed:
            self.failed = True
            raise ResponsePendingError(
                f"NEED RESPONSE key={self.purpose}",
                key=self.purpose,
                response_path=str(self.response_path),
                request=request,
            )
        return self.delegate.generate(request)


def test_retry_rejects_a_stage_that_is_not_failed(tmp_path: Path):
    store = ProjectStore(tmp_path)
    store.create_project(spec(), project_id="prj-fresh")
    with pytest.raises(ProjectRunError, match="has not started"):
        ProjectRunner(store).resume(
            "prj-fresh", ScriptedProvider(responses()), retry_failed=True,
        )

    store2 = ProjectStore(tmp_path / "done")
    store2.create_project(spec(), project_id="prj-done")
    ProjectRunner(store2).run("prj-done", ScriptedProvider(responses()))
    with pytest.raises(ProjectRunError, match="already complete"):
        ProjectRunner(store2).resume(
            "prj-done", ScriptedProvider(responses()), retry_failed=True,
        )

    # An interrupted stage has its own resume path; --retry-failed must not
    # silently discard the recorded responses waiting for the operator.
    store3 = ProjectStore(tmp_path / "waiting")
    store3.create_project(spec(), project_id="prj-waiting")
    pending_path = tmp_path / "waiting" / "operator" / "design-world.json"
    interrupted = InterruptOnce(
        ScriptedProvider(responses()), "design:world",
    )
    interrupted.response_path = pending_path
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store3).run("prj-waiting", interrupted)
    with pytest.raises(ProjectRunError, match="needs a failed stage"):
        ProjectRunner(store3).resume(
            "prj-waiting", ScriptedProvider(responses()), retry_failed=True,
        )
    # Plain resume still works for the interrupted stage.
    assert store3.status("prj-waiting")["state"] == "waiting_response"


def test_retry_after_a_failed_revise_keeps_the_carried_bytes(tmp_path: Path):
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("改訂"), project_id="prj-revise-retry")
    runner = ProjectRunner(store)
    runner.run("prj-revise-retry", ScriptedProvider(responses()))
    source_hashes = {
        row["artifact_id"]: row["sha256"]
        for row in store.status("prj-revise-retry")["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    }
    failing = FailOnce(ScriptedProvider(responses()), "draft:ch02")
    with pytest.raises(ProjectRunError) as caught:
        runner.revise(
            "prj-revise-retry", failing, chapters=("ch02",),
        )
    assert caught.value.stage == "draft"
    failed_run = caught.value.run_id
    result = runner.resume(
        "prj-revise-retry", ScriptedProvider(responses()), retry_failed=True,
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["derived"]["chapters"] == ["ch02"]
    assert status["checkpoints"]["draft"]["retry_of"] == failed_run
    hashes = {
        row["artifact_id"]: row["sha256"]
        for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    }
    assert hashes["draft-text-ch01.md"] == source_hashes["draft-text-ch01.md"]
    assert hashes["draft-text-ch03.md"] == source_hashes["draft-text-ch03.md"]
    draft_run = store.project_dir("prj-revise-retry") / "runs" / status["checkpoints"]["draft"]["run_id"]
    record = json.loads((draft_run / "revise.json").read_text(encoding="utf-8"))
    assert record["copied"] == ["text/ch01.md", "text/ch03.md"]
    assert inspect_project(store, "prj-revise-retry").ok is True


def test_resume_cli_retry_flag(tmp_path: Path):
    store, error = failed_project(tmp_path, purpose="plan", project_id="prj-cli-retry")
    refused = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "resume",
         "prj-cli-retry", "--provider", "scripted",
         "--script", str(FIXTURE)],
        capture_output=True, text=True, check=False,
    )
    assert refused.returncode == 2
    assert "--retry-failed" in refused.stderr

    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps({"responses": responses()}, ensure_ascii=False), encoding="utf-8",
    )
    retried = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "resume",
         "prj-cli-retry", "--provider", "scripted", "--script", str(script_path),
         "--retry-failed", "--json"],
        capture_output=True, text=True, check=False,
    )
    assert retried.returncode == 0, retried.stderr
    payload = json.loads(retried.stdout)
    assert payload["state"] == "complete"
    assert payload["checkpoints"]["plan"]["retry_of"] == error.run_id

    shown = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "status", "prj-cli-retry"],
        capture_output=True, text=True, check=True,
    )
    assert f"Retried stages: plan<-{error.run_id}" in shown.stdout
    assert "Failed stages:" not in shown.stdout


def test_doctor_points_at_the_retry_command(tmp_path: Path):
    store, _ = failed_project(tmp_path, purpose="plan")
    report = inspect_project(store, "prj-retry")
    assert report.ok is True
    finding = next(
        item for item in report.findings if item.code == "checkpoint.failed"
    )
    assert finding.severity == "warning"
    assert "resume --retry-failed" in finding.message
    assert finding.details["stage"] == "plan"
    assert finding.details["run_id"] == store.status("prj-retry")["checkpoints"]["plan"]["run_id"]


def test_retried_runs_support_strict_offline_replay(tmp_path: Path):
    store, error = failed_project(tmp_path, purpose="plan")
    result = ProjectRunner(store).resume(
        "prj-retry", ScriptedProvider(responses()), retry_failed=True,
    )
    runner = ProjectRunner(store)
    current = store.load_snapshot("prj-retry")
    attempt = runner._attempt(current)
    project_dir = store.project_dir("prj-retry")
    replay_root = tmp_path / "strict-replay"
    replayed = {}

    for stage in ("plan", "design", "draft"):
        source_dir = project_dir / "runs" / result.stage_runs[stage]
        source_manifest = json.loads(
            (source_dir / "manifest.json").read_text(encoding="utf-8")
        )
        provider = ReplayProvider(source_dir)
        ledger = RunLedger.create(
            replay_root,
            task_id=current.root_node.id,
            system="s1",
            seed=source_manifest["seed"],
            protocol_version=PROJECT_PROTOCOL,
            run_id=f"replay-{stage}",
            provider="replay",
            temperature=source_manifest["temperature"],
            # A plain run is not revision-namespaced, so the replay key must not
            # add a revision either.
        )
        if stage == "plan":
            value = runner._plan(attempt, ledger, provider, source_manifest["seed"])
        elif stage == "design":
            value = build_design(
                attempt.pipeline.task, provider, ledger, replayed["plan"],
                temperature=source_manifest["temperature"],
                seed=source_manifest["seed"],
            )
        else:
            value = runner._draft(
                attempt, ledger,
                SimpleNamespace(value=replayed["plan"]),
                SimpleNamespace(run_dir=replayed["design_dir"]),
                provider,
                SimpleNamespace(
                    seed=source_manifest["seed"],
                    temperature=source_manifest["temperature"],
                ),
            )
        replayed[stage] = value
        if stage == "design":
            replayed["design_dir"] = ledger.path
        audit = provider.finalize(ledger)
        assert audit["summary"]["ok"] is True, (stage, audit["summary"])
        assert audit["summary"]["all_source_responses_consumed"] is True
        assert audit["summary"]["artifacts_match"] is True
