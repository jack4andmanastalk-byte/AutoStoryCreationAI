from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    CommandProvider,
    GenerationRequest,
    GenerationResult,
    ResponsePendingError,
    RunLedger,
    ScriptedProvider,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    PROJECT_PROTOCOL,
    ProjectRunError,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    ResumeError,
    ResumeProvider,
    WorkSpec,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
SCRIPT = ROOT / "scripts" / "story_project.py"
OPERATOR = ROOT / "scripts" / "chat_operator.py"


def project_responses() -> dict[str, str]:
    responses = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            responses[":".join(parts[:-1])] = text
    return responses


def make_project(store: ProjectStore, project_id: str = "prj-resume"):
    return store.create_project(
        WorkSpec(
            title="再開する灯台",
            premise="中断した応答を無駄にせず三章を完成させる。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        project_id=project_id,
    )


class InterruptProvider:
    name = "interrupt"
    model = "interrupt-fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, response_path: Path):
        self.delegate = delegate
        self.purpose = purpose
        self.response_path = response_path
        self.calls = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if request.purpose == self.purpose:
            raise ResponsePendingError(
                f"NEED RESPONSE key={self.purpose} file={self.response_path}",
                key=self.purpose,
                response_path=str(self.response_path),
                request=request,
            )
        return self.delegate.generate(request)


def response_lines(run_dir: Path) -> list[dict]:
    path = run_dir / "responses.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fill_pending(status: dict, text: str = "operator answer") -> None:
    row = status["pending"][0]
    path = Path(row["response_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")


def test_resume_plan_repair_uses_recorded_invalid_first_attempt(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    responses = project_responses()
    responses["plan"] = "not valid canon JSON"
    pending_path = tmp_path / "operator" / "responses" / "plan-repair.json"
    provider = InterruptProvider(ScriptedProvider(responses), "plan-repair", pending_path)
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).run(snapshot.project.id, provider)

    waiting = store.status(snapshot.project.id)
    assert waiting["stages"]["plan"] == "waiting_response"
    old_run = waiting["checkpoints"]["plan"]["run_id"]
    old_dir = store.project_dir(snapshot.project.id) / "runs" / old_run
    assert len(response_lines(old_dir)) == 1
    old_bytes = (old_dir / "responses.jsonl").read_bytes()
    fill_pending(waiting)

    resume_responses = project_responses()
    resume_responses["plan-repair"] = project_responses()["plan"]
    delegate = ScriptedProvider(resume_responses)
    result = ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert result.status["state"] == "complete"
    purposes = [request.purpose for request in delegate.calls]
    assert "plan" not in purposes
    assert "plan-repair" in purposes
    assert (old_dir / "responses.jsonl").read_bytes() == old_bytes

    new_dir = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["plan"]
    entries = response_lines(new_dir)
    assert len(entries) == 2
    assert entries[0]["response"]["provenance"]["origin"] == "resume"
    assert entries[1]["response"]["provenance"]["origin"] == "scripted"
    audit = json.loads((new_dir / "resume-audit.json").read_text(encoding="utf-8"))
    assert audit["reused_responses"] == 1
    assert audit["delegated_responses"] == 1


def test_resume_design_preserves_plan_and_recorded_prefix(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    pending_path = tmp_path / "operator" / "responses" / "design-world.json"
    provider = InterruptProvider(
        ScriptedProvider(project_responses()), "design:world", pending_path,
    )
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).run(snapshot.project.id, provider)
    waiting = store.status(snapshot.project.id)
    assert waiting["state"] == "waiting_response"
    assert waiting["stages"] == {
        "plan": "done", "design": "waiting_response", "draft": "pending",
    }
    assert waiting["pending"][0]["project_id"] == snapshot.project.id
    assert waiting["pending"][0]["node_id"] == snapshot.root_node.id
    old_plan = waiting["checkpoints"]["plan"]["run_id"]
    old_design = waiting["checkpoints"]["design"]["run_id"]
    plan_bytes = (
        store.project_dir(snapshot.project.id) / "runs" / old_plan / "responses.jsonl"
    ).read_bytes()
    run_count = len(waiting["runs"])

    early_delegate = ScriptedProvider(project_responses())
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).resume(snapshot.project.id, early_delegate)
    assert early_delegate.calls == []
    assert len(store.status(snapshot.project.id)["runs"]) == run_count

    fill_pending(waiting)
    delegate = ScriptedProvider(project_responses())
    result = ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert result.status["state"] == "complete"
    assert result.stage_runs["plan"] == old_plan
    assert result.stage_runs["design"] != old_design
    purposes = [request.purpose for request in delegate.calls]
    assert "plan" not in purposes
    assert "design:brief" not in purposes
    assert "design:world" in purposes
    assert "draft:ch01" in purposes
    assert result.status["pending"] == []
    assert result.status["attempt_id"] == result.attempt_id
    assert len(result.status["attempt_ids"]) > 1
    assert (
        store.project_dir(snapshot.project.id) / "runs" / old_plan / "responses.jsonl"
    ).read_bytes() == plan_bytes

    design_dir = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["design"]
    assert len(response_lines(design_dir)) == 8
    audit = json.loads((design_dir / "resume-audit.json").read_text(encoding="utf-8"))
    assert audit["reused_responses"] == 1
    assert audit["delegated_responses"] == 7
    assert result.status["checkpoints"]["design"]["resume_of"] == old_design


def test_resume_draft_does_not_repeat_completed_stages_or_chapter(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    pending_path = tmp_path / "operator" / "responses" / "draft-ch02.json"
    provider = InterruptProvider(
        ScriptedProvider(project_responses()), "draft:ch02", pending_path,
    )
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).run(snapshot.project.id, provider)
    waiting = store.status(snapshot.project.id)
    fill_pending(waiting)
    old_draft = waiting["checkpoints"]["draft"]["run_id"]

    delegate = ScriptedProvider(project_responses())
    result = ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert result.status["state"] == "complete"
    purposes = [request.purpose for request in delegate.calls]
    assert purposes == ["draft:ch02", "draft:ch03"]
    assert result.stage_runs["plan"] == waiting["checkpoints"]["plan"]["run_id"]
    assert result.stage_runs["design"] == waiting["checkpoints"]["design"]["run_id"]
    assert result.stage_runs["draft"] != old_draft

    draft_dir = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["draft"]
    assert len(response_lines(draft_dir)) == 3
    audit = json.loads((draft_dir / "resume-audit.json").read_text(encoding="utf-8"))
    assert audit["reused_responses"] == 1
    assert audit["delegated_responses"] == 2
    assert sorted(path.name for path in (draft_dir / "text").glob("*.md")) == [
        "ch01.md", "ch02.md", "ch03.md",
    ]


def test_resume_covers_crash_after_ledger_ok_before_done_checkpoint(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    original_save = store.save_checkpoint

    def crash_before_design_done(checkpoint):
        if checkpoint.stage == "design" and checkpoint.status == "done":
            raise KeyboardInterrupt("simulated process stop")
        return original_save(checkpoint)

    store.save_checkpoint = crash_before_design_done
    try:
        with pytest.raises(KeyboardInterrupt):
            ProjectRunner(store).run(
                snapshot.project.id, ScriptedProvider(project_responses()),
            )
    finally:
        store.save_checkpoint = original_save

    interrupted = store.status(snapshot.project.id)
    assert interrupted["stages"]["design"] == "running"
    source_run = interrupted["checkpoints"]["design"]["run_id"]
    source_manifest = json.loads((
        store.project_dir(snapshot.project.id) / "runs" / source_run / "manifest.json"
    ).read_text(encoding="utf-8"))
    assert source_manifest["status"] == "ok"

    delegate = ScriptedProvider(project_responses())
    result = ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert result.status["state"] == "complete"
    assert [request.purpose for request in delegate.calls] == [
        "draft:ch01", "draft:ch02", "draft:ch03",
    ]
    new_design = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["design"]
    audit = json.loads((new_design / "resume-audit.json").read_text(encoding="utf-8"))
    assert audit["reused_responses"] == 8
    assert audit["delegated_responses"] == 0


def _resume_source(tmp_path: Path) -> tuple[Path, dict, GenerationRequest, GenerationRequest]:
    source = tmp_path / "source"
    ledger = RunLedger.create(
        source, task_id="node-source", system="s1", seed=0,
        protocol_version=PROJECT_PROTOCOL, run_id="att-source-design",
        model="fixture", provider="scripted", temperature=0.6,
    )
    expected = {
        "project_id": "prj-source",
        "node_id": "node-source",
        "revision_id": "rev-source",
        "spec_sha256": "a" * 64,
        "stage": "design",
    }
    ledger.write_json("project-input.json", {"attempt_id": "att-source", **expected})
    first = GenerationRequest(
        purpose="design:brief", prompt="recorded brief", temperature=0.6,
        max_tokens=2000, seed=0,
        context={"task_id": "node-source", "system": "s1", "attempt": 1},
    )
    second = GenerationRequest(
        purpose="design:world", prompt="new world", temperature=0.6,
        max_tokens=2000, seed=0,
        context={"task_id": "node-source", "system": "s1", "attempt": 1},
    )
    ledger.record(first, GenerationResult(text="brief result", provider="scripted", model="m"))
    ledger.error = "NEED RESPONSE"
    ledger.finish("waiting_response")
    return ledger.path, expected, first, second


def test_resume_provider_verifies_prefix_then_delegates(tmp_path: Path):
    source, expected, first, second = _resume_source(tmp_path)
    delegate = ScriptedProvider({"design:world": "world result"})
    provider = ResumeProvider(
        source, delegate, expected_input=expected,
        expected_seed=0, expected_temperature=0.6,
    )
    reused = provider.generate(first)
    fresh = provider.generate(second)
    assert reused.text == "brief result"
    assert reused.provenance["origin"] == "resume"
    assert fresh.text == "world result"
    assert fresh.provenance["origin"] == "scripted"
    audit = provider.finalize()
    assert audit["reused_responses"] == 1
    assert audit["delegated_responses"] == 1

    mismatched_delegate = ScriptedProvider({"design:brief": "must not be called"})
    mismatched = ResumeProvider(
        source, mismatched_delegate, expected_input=expected,
        expected_seed=0, expected_temperature=0.6,
    )
    with pytest.raises(ResumeError, match="prompt hash|full prompt"):
        mismatched.generate(GenerationRequest(
            purpose=first.purpose, prompt="changed prompt", temperature=0.6,
            max_tokens=2000, seed=0, context=first.context,
        ))
    assert mismatched_delegate.calls == []
    with pytest.raises(ResumeError, match="max_tokens"):
        mismatched.generate(GenerationRequest(
            purpose=first.purpose, prompt=first.prompt, temperature=0.6,
            max_tokens=2001, seed=0, context=first.context,
        ))
    with pytest.raises(ResumeError, match="seed"):
        ResumeProvider(
            source, delegate, expected_input=expected,
            expected_seed=1, expected_temperature=0.6,
        )
    with pytest.raises(ResumeError, match="temperature"):
        ResumeProvider(
            source, delegate, expected_input=expected,
            expected_seed=0, expected_temperature=0.7,
        )
    with pytest.raises(ResumeError, match="spec_sha256"):
        ResumeProvider(
            source, delegate, expected_input={**expected, "spec_sha256": "b" * 64},
            expected_seed=0, expected_temperature=0.6,
        )


def test_command_provider_exposes_operator_pending(tmp_path: Path):
    request = GenerationRequest(
        purpose="plan", prompt="未回答のrequest", temperature=0.6,
        context={"task_id": "node-operator", "system": "s1", "attempt": 1},
    )
    provider = CommandProvider(
        f"{sys.executable} {OPERATOR} --dir {tmp_path / 'operator'}"
    )
    with pytest.raises(ResponsePendingError) as caught:
        provider.generate(request)
    assert caught.value.key.startswith("s1-node-operator-s0-plan-a1")
    assert Path(caught.value.response_path).name.endswith(".json")


def test_resume_rejects_changed_source_revision_before_creating_attempt(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    pending_path = tmp_path / "operator" / "responses" / "design-world.json"
    provider = InterruptProvider(
        ScriptedProvider(project_responses()), "design:world", pending_path,
    )
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).run(snapshot.project.id, provider)
    before = store.status(snapshot.project.id)
    source_run = before["checkpoints"]["design"]["run_id"]
    input_path = (
        store.project_dir(snapshot.project.id) / "runs" / source_run / "project-input.json"
    )
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload["spec"]["premise"] = "変更された別revisionのpremise"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fill_pending(before)

    with pytest.raises(ProjectRunError, match="cannot resume design"):
        ProjectRunner(store).resume(
            snapshot.project.id, ScriptedProvider(project_responses()),
        )
    after = store.status(snapshot.project.id)
    assert after["state"] == "waiting_response"
    assert after["runs"] == before["runs"]


def test_failed_validation_is_not_automatically_resumed(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    responses = project_responses()
    del responses["design:world"]
    with pytest.raises(ProjectRunError):
        ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(responses))
    delegate = ScriptedProvider(project_responses())
    with pytest.raises(ProjectRunError, match="failed, not interrupted"):
        ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert delegate.calls == []


def test_cli_operator_style_pending_and_resume(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store, project_id="prj-cli-resume")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps({"responses": project_responses()}, ensure_ascii=False), encoding="utf-8",
    )
    provider_script = tmp_path / "provider.py"
    provider_script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "responses=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['responses']\n"
        "stop=sys.argv[2]\n"
        "operator=Path(sys.argv[3])\n"
        "req=json.load(sys.stdin)\n"
        "purpose=req['purpose']\n"
        "if purpose == stop:\n"
        "    response=operator/'responses'/'design-world.json'\n"
        "    request=operator/'requests'/'design-world.json'\n"
        "    request.parent.mkdir(parents=True, exist_ok=True)\n"
        "    request.write_text(json.dumps(req, ensure_ascii=False), encoding='utf-8')\n"
        "    if not response.is_file():\n"
        "        print(f'NEED RESPONSE key=operator-design-world file={response}', file=sys.stderr)\n"
        "        raise SystemExit(3)\n"
        "    text=json.loads(response.read_text(encoding='utf-8'))['text']\n"
        "else:\n"
        "    task=req['context']['task_id']; system=req['context']['system']\n"
        "    keys=[f'{purpose}:{system}:{task}', f'{purpose}:{task}', purpose]\n"
        "    text=next(responses[key] for key in keys if key in responses)\n"
        "print(json.dumps({'text':text,'model':'fixture','provenance':{'origin':'fresh'}}))\n",
        encoding="utf-8",
    )
    command = shlex.join([
        sys.executable, str(provider_script), str(responses_path),
        "design:world", str(tmp_path / "operator"),
    ])
    initial = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "run",
            snapshot.project.id, "--provider", "command", "--command", command, "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert initial.returncode == 3, initial.stderr
    waiting = json.loads(initial.stdout)
    assert waiting["state"] == "waiting_response"
    old_design = waiting["checkpoints"]["design"]["run_id"]
    old_manifest = (
        store.project_dir(snapshot.project.id) / "runs" / old_design / "manifest.json"
    ).read_bytes()
    pending_path = Path(waiting["pending"][0]["response_path"])
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(
        json.dumps({"text": project_responses()["design:world"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    pending = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "pending",
            snapshot.project.id, "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert pending.returncode == 0, pending.stderr
    assert json.loads(pending.stdout)["pending"][0]["response_ready"] is True

    resumed = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "resume",
            snapshot.project.id, "--provider", "command", "--command", command, "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert resumed.returncode == 0, resumed.stderr
    completed = json.loads(resumed.stdout)
    assert completed["state"] == "complete"
    assert completed["pending"] == []
    assert completed["checkpoints"]["design"]["resume_of"] == old_design
    assert len(completed["runs"]) == 4
    assert (
        store.project_dir(snapshot.project.id) / "runs" / old_design / "manifest.json"
    ).read_bytes() == old_manifest
