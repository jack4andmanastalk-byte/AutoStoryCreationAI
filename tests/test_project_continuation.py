from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    GenerationRequest,
    ReplayProvider,
    ResponsePendingError,
    RunLedger,
    ScriptedProvider,
    build_design,
    generation_request_key,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    BundleError,
    PROJECT_PROTOCOL,
    ProjectRunError,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    ReplayBundle,
    WorkSpec,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
SCRIPT = ROOT / "scripts" / "story_project.py"


def project_responses() -> dict[str, str]:
    responses = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            responses[":".join(parts[:-1])] = text
    return responses


def continuation_responses() -> dict[str, str]:
    responses = project_responses()
    plan = json.loads(responses["plan"])
    plan["timeline"]["chapters"].append({"id": "ch04", "day": 10, "location": "灯台"})
    responses["plan"] = json.dumps(plan, ensure_ascii=False)
    responses["draft:ch04"] = (
        "{{time: day=10}}{{location: 灯台}}\n" + "追加の章の本文です。" * 40
    )
    # The three-chapter fixture's plot/scene documents need a repair round when
    # a fourth chapter is introduced.  Keeping the same offline response makes
    # the test exercise the fail-open design path without a real model.
    for doc in ("brief", "world", "history", "character", "relation", "plot", "scene", "voice"):
        responses[f"design:{doc}:repair"] = responses[f"design:{doc}"]
    return responses


def make_project(store: ProjectStore, project_id: str = "prj-continuation"):
    return store.create_project(
        WorkSpec(
            title="続きの灯台",
            premise="完成した三章の作品に新しい章を追加する。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        project_id=project_id,
    )


def run_base(store: ProjectStore, snapshot):
    return ProjectRunner(store).run(
        snapshot.project.id, ScriptedProvider(project_responses()),
    )


class PendingAt:
    name = "pending-continuation"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, response_path: Path):
        self.delegate = delegate
        self.purpose = purpose
        self.response_path = response_path

    def generate(self, request: GenerationRequest):
        if request.purpose == self.purpose:
            raise ResponsePendingError(
                f"NEED RESPONSE key={self.purpose} file={self.response_path}",
                key=self.purpose, response_path=str(self.response_path), request=request,
            )
        return self.delegate.generate(request)


def fill_pending(status: dict) -> None:
    path = Path(status["pending"][0]["response_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"text": "回答"}, ensure_ascii=False), encoding="utf-8")


def test_continue_appends_revision_and_preserves_old_chapter_bytes(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    base = run_base(store, snapshot)
    project_dir = store.project_dir(snapshot.project.id)
    old_revision_path = store.revision_path(
        snapshot.project.id, snapshot.root_node.id, snapshot.revision.id,
    )
    old_revision_bytes = old_revision_path.read_bytes()
    old_draft_dir = project_dir / "runs" / base.stage_runs["draft"] / "text"
    old_chapter_bytes = {
        path.name: path.read_bytes() for path in old_draft_dir.glob("*.md")
    }

    provider = ScriptedProvider(continuation_responses())
    result = ProjectRunner(store).continue_project(
        snapshot.project.id, provider, additional_chapters=1,
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["current_revision_id"] != snapshot.revision.id
    assert status["parent_revision_id"] == snapshot.revision.id
    assert status["parent_runs"] == base.stage_runs
    assert len(status["revision_ids"]) == 2
    assert status["spec"]["chapter_count"] == 4
    assert old_revision_path.read_bytes() == old_revision_bytes

    new_draft_dir = project_dir / "runs" / result.stage_runs["draft"] / "text"
    assert sorted(path.name for path in new_draft_dir.glob("*.md")) == [
        "ch01.md", "ch02.md", "ch03.md", "ch04.md",
    ]
    for name, content in old_chapter_bytes.items():
        assert (new_draft_dir / name).read_bytes() == content
        assert (old_draft_dir / name).read_bytes() == content
    draft_calls = [request.purpose for request in provider.calls if request.purpose.startswith("draft:")]
    assert draft_calls == ["draft:ch04"]
    plan_request = next(request for request in provider.calls if request.purpose == "plan")
    assert "前版からのcontinuation" in plan_request.prompt
    assert "ch03" in plan_request.prompt
    assert plan_request.context["revision_id"] == status["current_revision_id"]
    assert status["current_revision_id"] in generation_request_key(plan_request)

    run_input = json.loads(
        (project_dir / "runs" / result.stage_runs["draft"] / "project-input.json")
        .read_text(encoding="utf-8")
    )
    assert run_input["continuation"]["parent_revision_id"] == snapshot.revision.id
    assert run_input["continuation"]["reused_chapters"] == ["ch01", "ch02", "ch03"]


def test_continuation_runs_support_strict_offline_replay(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store)
    run_base(store, snapshot)
    continued = ProjectRunner(store).continue_project(
        snapshot.project.id, ScriptedProvider(continuation_responses()),
    )
    current = store.load_snapshot(snapshot.project.id)
    runner = ProjectRunner(store)
    attempt = runner._attempt(
        current, continuation=runner._continuation_for_snapshot(current),
    )
    replay_root = tmp_path / "strict-replay"
    project_dir = store.project_dir(snapshot.project.id)
    replayed = {}

    for stage in ("plan", "design", "draft"):
        source_dir = project_dir / "runs" / continued.stage_runs[stage]
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
            revision_id=current.revision.id,
        )
        if stage == "plan":
            value = runner._plan(attempt, ledger, provider, source_manifest["seed"])
        elif stage == "design":
            value = runner._design(
                attempt, ledger, replayed["plan"], provider,
                SimpleNamespace(
                    seed=source_manifest["seed"],
                    temperature=source_manifest["temperature"],
                ),
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


def test_continuation_can_be_resumed_without_repeating_parent_chapters(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    base = run_base(store, snapshot)
    pending_path = tmp_path / "operator" / "responses" / "draft-ch04.json"
    initial = PendingAt(ScriptedProvider(continuation_responses()), "draft:ch04", pending_path)
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).continue_project(snapshot.project.id, initial)
    waiting = store.status(snapshot.project.id)
    assert waiting["state"] == "waiting_response"
    new_revision = waiting["current_revision_id"]
    assert new_revision != snapshot.revision.id
    fill_pending(waiting)

    delegate = ScriptedProvider(continuation_responses())
    result = ProjectRunner(store).resume(snapshot.project.id, delegate)
    assert result.status["state"] == "complete"
    assert result.status["current_revision_id"] == new_revision
    assert [request.purpose for request in delegate.calls] == ["draft:ch04"]
    old_draft = store.project_dir(snapshot.project.id) / "runs" / base.stage_runs["draft"] / "text"
    new_draft = store.project_dir(snapshot.project.id) / "runs" / result.stage_runs["draft"] / "text"
    for old_file in old_draft.glob("*.md"):
        assert (new_draft / old_file.name).read_bytes() == old_file.read_bytes()


def test_continuation_rejects_changes_to_parent_canon(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    base = run_base(store, snapshot)
    old_revision_path = store.revision_path(
        snapshot.project.id, snapshot.root_node.id, snapshot.revision.id,
    )
    old_revision_bytes = old_revision_path.read_bytes()
    responses = continuation_responses()
    plan = json.loads(responses["plan"])
    plan["characters"][0]["name"] = "旧版から勝手に変更された名前"
    responses["plan"] = json.dumps(plan, ensure_ascii=False)

    with pytest.raises(ProjectRunError, match="parent canon characters"):
        ProjectRunner(store).continue_project(
            snapshot.project.id, ScriptedProvider(responses),
        )
    assert old_revision_path.read_bytes() == old_revision_bytes
    assert store.status(snapshot.project.id)["state"] == "failed"
    assert (
        store.project_dir(snapshot.project.id) / "runs" / base.stage_runs["draft"]
        / "text" / "ch01.md"
    ).is_file()


def test_continuation_requires_a_complete_revision(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    with pytest.raises(ProjectRunError, match="continuation requires a complete revision"):
        ProjectRunner(store).continue_project(
            snapshot.project.id, ScriptedProvider(continuation_responses()),
        )
    assert store.status(snapshot.project.id)["revision_ids"] == [snapshot.revision.id]


def test_bundle_export_verify_restore_and_tamper_detection(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store)
    base = run_base(store, snapshot)
    continued = ProjectRunner(store).continue_project(
        snapshot.project.id, ScriptedProvider(continuation_responses()),
    )
    bundle_dir = tmp_path / "external" / "replay-bundle"
    exported = ReplayBundle(store).export(snapshot.project.id, bundle_dir)
    assert exported["ok"] is True
    assert exported["file_count"] > 20
    verified = ReplayBundle.verify(bundle_dir)
    assert verified["status"]["state"] == "complete"
    assert verified["status"]["current_revision_id"] == continued.status["current_revision_id"]

    restored_root = tmp_path / "restored-projects"
    restored = ReplayBundle.restore(bundle_dir, restored_root)
    assert restored["status"]["state"] == "complete"
    assert restored["status"]["revision_ids"] == continued.status["revision_ids"]
    source_dir = store.project_dir(snapshot.project.id)
    restored_dir = restored_root / snapshot.project.id
    for source_file in source_dir.rglob("*"):
        if not source_file.is_file() or any(
            part.startswith(".") for part in source_file.relative_to(source_dir).parts
        ):
            continue
        relative = source_file.relative_to(source_dir)
        assert (restored_dir / relative).read_bytes() == source_file.read_bytes()

    with pytest.raises(BundleError, match="already exists"):
        ReplayBundle.restore(bundle_dir, restored_root)
    tampered = bundle_dir / "payload" / snapshot.project.id / "project.json"
    tampered.write_text("{}", encoding="utf-8")
    with pytest.raises(BundleError, match="hash differs"):
        ReplayBundle.verify(bundle_dir)


def test_bundle_cli_export_verify_restore(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store, project_id="prj-bundle-cli")
    run_base(store, snapshot)
    bundle_dir = tmp_path / "cli-bundle"
    exported = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "bundle", "export",
            snapshot.project.id, "--out", str(bundle_dir), "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout)["ok"] is True
    verified = subprocess.run(
        [sys.executable, str(SCRIPT), "bundle", "verify", str(bundle_dir), "--json"],
        check=False, capture_output=True, text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"]["state"] == "complete"
    restored_root = tmp_path / "cli-restored"
    restored = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(restored_root), "bundle", "restore",
            str(bundle_dir), "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)["status"]["state"] == "complete"


def test_continuation_carries_chapter_independent_design_docs_by_default(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    base = run_base(store, snapshot)
    provider = ScriptedProvider(continuation_responses())
    continued = ProjectRunner(store).continue_project(snapshot.project.id, provider)

    assert [request.purpose for request in provider.calls] == [
        "plan",
        "design:world",
        "design:relation",
        "design:plot",
        "design:plot:repair",
        "design:scene",
        "design:scene:repair",
        "draft:ch04",
    ]
    current = store.load_snapshot(snapshot.project.id)
    assert current.revision.continuation_design == (
        "world", "relation", "plot", "scene",
    )
    old_design = (
        store.project_dir(snapshot.project.id) / "runs" / base.stage_runs["design"] / "design"
    )
    new_design = (
        store.project_dir(snapshot.project.id)
        / "runs" / continued.stage_runs["design"] / "design"
    )
    for carried in ("brief", "history", "character", "voice"):
        assert (new_design / f"{carried}.json").read_bytes() == (
            old_design / f"{carried}.json"
        ).read_bytes()
    design_summary = json.loads(
        (new_design.parent / "design.json").read_text(encoding="utf-8")
    )
    assert design_summary["carried"] == ["brief", "history", "character", "voice"]
    for carried in ("brief", "history", "character", "voice"):
        assert design_summary["docs"][carried]["status"] == "carried"
    for generated in ("world", "relation"):
        assert design_summary["docs"][generated]["status"] == "clean"


def test_continuation_can_select_specific_design_docs_or_regenerate_all(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_project(store)
    run_base(store, snapshot)

    selective_provider = ScriptedProvider(continuation_responses())
    selective = ProjectRunner(store).continue_project(
        snapshot.project.id, selective_provider, design=("plot", "scene"),
    )
    assert [request.purpose for request in selective_provider.calls] == [
        "plan",
        "design:plot",
        "design:plot:repair",
        "design:scene",
        "design:scene:repair",
        "draft:ch04",
    ]
    current = store.load_snapshot(snapshot.project.id)
    assert current.revision.continuation_design == ("plot", "scene")

    store_all = ProjectStore(tmp_path / "all-design")
    snap_all = make_project(store_all)
    run_base(store_all, snap_all)
    full_provider = ScriptedProvider(continuation_responses())
    ProjectRunner(store_all).continue_project(
        snap_all.project.id, full_provider, carry_design=False,
    )
    assert [request.purpose for request in full_provider.calls] == [
        "plan",
        "design:brief",
        "design:world",
        "design:history",
        "design:character",
        "design:relation",
        "design:plot",
        "design:plot:repair",
        "design:scene",
        "design:scene:repair",
        "design:voice",
        "draft:ch04",
    ]
    assert store_all.load_snapshot(snap_all.project.id).revision.continuation_design is None
    assert selective.status["state"] == "complete"


def test_continuation_cli_supports_design_and_all_design_flags(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store, project_id="prj-cont-cli")
    run_base(store, snapshot)
    script_path = tmp_path / "continuation-script.json"
    script_path.write_text(
        json.dumps({"responses": continuation_responses()}, ensure_ascii=False),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root), "continue",
            snapshot.project.id, "--add-chapters", "1",
            "--design", "plot", "--design", "scene",
            "--provider", "scripted", "--script", str(script_path), "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["state"] == "complete"
    assert store.load_snapshot(snapshot.project.id).revision.continuation_design == (
        "plot", "scene",
    )

