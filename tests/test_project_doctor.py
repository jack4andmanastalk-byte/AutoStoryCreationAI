"""Read-only ``doctor`` inspection: integration, tampering, and CLI behaviour."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    GenerationRequest,
    GenerationResult,
    ResponsePendingError,
    ScriptedProvider,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    CanonScope,
    ProjectDoctor,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    WorkSpec,
    WorldStore,
    inspect_project,
)
from asc.project.model import StageCheckpoint  # noqa: E402

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
    for doc in (
        "brief", "world", "history", "character", "relation", "plot", "scene", "voice",
    ):
        responses[f"design:{doc}:repair"] = responses[f"design:{doc}"]
    return responses


def spec(title: str = "作品") -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


class PendingAt:
    name = "pending-doctor"
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
                key=self.purpose, response_path=str(self.response_path),
                request=request,
            )
        return self.delegate.generate(request)


def make_family(store: ProjectStore):
    root = store.create_project(spec("親"), project_id="prj-doctor")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    grandchild = store.create_child(
        root.project.id, spec("孫"), parent_node_id=child.child_node_id,
        child_node_id="node-grandchild", link_id="link-grandchild",
    )
    return root, child, grandchild


def add_world(store: ProjectStore, project_id: str, node_id: str) -> None:
    world = WorldStore(store)
    world.add_record(project_id, "timeframe", {
        "id": "tf-empire", "name": "帝国暦", "calendar": "solar", "epoch": "建国",
    })
    world.add_record(project_id, "time-span", {
        "id": "span-empire", "timeframe_id": "tf-empire", "precision": "exact",
        "start": 120, "end": 120,
    })
    world.add_record(project_id, "region", {"id": "region-coast", "name": "沿岸"})
    world.add_record(project_id, "culture", {"id": "culture-tide", "name": "潮の文化"})
    world.add_record(project_id, "culture-state", {
        "id": "state-tide", "culture_id": "culture-tide",
        "valid_span_id": "span-empire", "region_ids": ["region-coast"],
        "attributes": {"marker": "TIDE"},
    })
    world.author_world_canon(
        project_id, scope=CanonScope("global"), subject="共有", content={"marker": "SHARED"},
        entry_id="canon-shared",
    )
    world.bind_work(
        project_id, node_id, time_span_ids=("span-empire",),
        region_ids=("region-coast",), culture_state_ids=("state-tide",),
        binding_id="binding-empire",
    )


def run_node(store: ProjectStore, project_id: str, node_id: str, responses=None):
    return ProjectRunner(store).run(
        project_id, ScriptedProvider(responses or project_responses()), node_id=node_id,
    )


def tree_digest(directory: Path) -> dict[str, str]:
    """Hash every file so a read-only claim can be checked exactly."""
    digest = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest[str(path.relative_to(directory))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digest


def test_healthy_complete_project_has_no_findings(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    assert report.findings == ()
    assert report.pending == ()
    assert report.stale["total"] == 0
    assert report.summary["nodes"] == 3
    assert report.summary["checks_failed"] == 0
    assert {check["name"] for check in report.checks} == {
        "project", "node_tree", "revisions", "checkpoints", "links", "world", "runs",
    }
    assert all(check["status"] == "pass" for check in report.checks)
    data = report.to_dict()
    assert data["read_only"] is True
    assert data["ok"] is True
    assert data["schema"] == "asc-project-doctor-v1"


def test_pending_response_and_stale_link_are_reported(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    run_node(store, root.project.id, root.root_node.id)
    response_file = tmp_path / "operator" / "child-draft.json"
    provider = PendingAt(
        ScriptedProvider(project_responses()), "draft:ch01", response_file,
    )
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).run(
            root.project.id, provider, node_id=child.child_node_id,
        )

    report = inspect_project(store, root.project.id)
    assert report.ok is True  # a pending answer is not corruption
    assert len(report.pending) == 1
    pending = report.pending[0]
    assert pending["node_id"] == child.child_node_id
    assert pending["stage"] == "draft"
    assert pending["response_ready"] is False
    assert pending["response_path"] == str(response_file)

    response_file.parent.mkdir(parents=True, exist_ok=True)
    response_file.write_text('{"text": "x"}\n', encoding="utf-8")
    report = inspect_project(store, root.project.id)
    assert report.pending[0]["response_ready"] is True

    # Complete the pending child stage, then leave a continuation waiting.
    ProjectRunner(store).resume(
        root.project.id, ScriptedProvider(project_responses()),
        node_id=child.child_node_id,
    )
    continuation = PendingAt(
        ScriptedProvider(continuation_responses()), "plan",
        tmp_path / "operator" / "child-continuation-plan.json",
    )
    with pytest.raises(ProjectRunPending):
        ProjectRunner(store).continue_project(
            root.project.id, continuation, additional_chapters=1,
            node_id=child.child_node_id,
        )
    report = inspect_project(store, root.project.id)
    assert report.ok is True
    assert [row["stage"] for row in report.pending] == ["plan"]
    assert [row["link_id"] for row in report.stale["links"]] == [child.id]
    assert report.stale["links"][0]["pinned_revision_id"] == child.child_revision_id
    codes = {finding.code for finding in report.findings}
    assert codes == {"link.stale"}
    stale = [finding for finding in report.findings if finding.code == "link.stale"][0]
    assert stale.severity == "warning"
    assert stale.node_id == child.child_node_id


def test_missing_artifact_is_an_error_finding_and_nothing_is_written(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)

    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    text_artifact = next(
        row for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    )
    before = tree_digest(project_dir)
    (project_dir / text_artifact["path"]).unlink()

    report = inspect_project(store, root.project.id)
    assert report.ok is False
    codes = {finding.code for finding in report.findings}
    assert "artifact.missing" in codes
    finding = next(
        item for item in report.findings if item.code == "artifact.missing"
    )
    assert finding.severity == "error"
    assert finding.node_id == child.child_node_id
    assert finding.path == text_artifact["path"]
    failed = [check for check in report.checks if check["status"] == "failed"]
    # The same draft file is pinned by the link, so both checks report it.
    assert {check["name"] for check in failed} == {"checkpoints", "links"}

    after = tree_digest(project_dir)
    assert before.keys() - {text_artifact["path"]} == after.keys()
    for path, value in after.items():
        assert before[path] == value
    assert inspect_project(store, root.project.id).to_dict()["ok"] is False


def test_hash_mismatch_and_invalid_world_record_are_error_findings(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)

    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    artifact = status["checkpoints"]["draft"]["artifacts"][0]
    (project_dir / artifact["path"]).write_text("tampered\n", encoding="utf-8")
    world_file = project_dir / "world" / "culture_states" / "state-tide.json"
    payload = json.loads(world_file.read_text(encoding="utf-8"))
    payload["attributes"] = {"marker": "TAMPERED"}
    world_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = inspect_project(store, root.project.id)
    assert report.ok is False
    codes = {finding.code for finding in report.findings}
    assert "artifact.hash_differs" in codes
    assert "world.invalid" in codes
    assert "world" in {
        check["name"] for check in report.checks if check["status"] == "failed"
    }


def test_failed_stage_is_a_warning_not_an_error(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    plan = status["checkpoints"]["plan"]
    failed = StageCheckpoint.from_dict({
        **plan,
        "status": "failed",
        "error": "provider exited 1",
        "artifacts": [],
        "pending": None,
    })
    store.save_checkpoint(failed)

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    failed_findings = [
        finding for finding in report.findings if finding.code == "checkpoint.failed"
    ]
    assert len(failed_findings) == 1
    assert failed_findings[0].severity == "warning"
    assert failed_findings[0].details["stage"] == "plan"


def test_stale_canon_and_non_current_binding_are_reported(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    world = WorldStore(store)
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    facts = next(
        row for row in status["checkpoints"]["plan"]["artifacts"]
        if row["path"].endswith("/canon/facts.json")
    )
    world.adopt_world_canon(
        root.project.id, child.child_node_id, source_artifact_path=facts["path"],
        json_pointer="/facts/0", scope=CanonScope("region", "region-coast"),
        subject="adopted", entry_id="canon-adopted",
    )
    assert inspect_project(store, root.project.id).findings == ()

    ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=child.child_node_id,
    )

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    assert [row["entry_id"] for row in report.stale["canon"]] == ["canon-adopted"]
    assert [row["link_id"] for row in report.stale["links"]] == [child.id]
    codes = [finding.code for finding in report.findings]
    assert "world.canon_stale" in codes
    assert report.stale["canon"][0]["source_revision_id"] == child.child_revision_id
    assert report.stale["canon"][0]["current_source_revision_id"] != child.child_revision_id


def test_derived_revision_is_healthy_and_a_missing_source_run_is_an_error(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    run_node(store, root.project.id, child.child_node_id)
    ProjectRunner(store).revise(
        root.project.id, ScriptedProvider(project_responses()),
        node_id=child.child_node_id, chapters=("ch02",),
    )
    report = inspect_project(store, root.project.id)
    assert report.ok is True
    # The revise makes the parent's link stale until it is explicitly adopted.
    assert {finding.code for finding in report.findings} == {"link.stale"}
    store.adopt_child(root.project.id, child.id)
    assert inspect_project(store, root.project.id).findings == ()
    revision = store.load_revision(
        root.project.id, child.child_node_id,
        store.status(root.project.id, child.child_node_id)["current_revision_id"],
    )
    assert revision.derived is not None

    source_run = revision.derived["source_runs"]["draft"]
    shutil.rmtree(store.project_dir(root.project.id) / "runs" / source_run)
    broken = inspect_project(store, root.project.id)
    assert broken.ok is False
    codes = {finding.code for finding in broken.findings}
    assert "revision.derived_run_missing" in codes
    finding = next(
        item for item in broken.findings
        if item.code == "revision.derived_run_missing"
    )
    assert finding.details["stage"] == "draft"
    assert finding.details["run_id"] == source_run


def test_doctor_cli_json_and_exit_codes(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    run_node(store, root.project.id, child.child_node_id)
    healthy = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor",
         root.project.id, "--json"],
        capture_output=True, text=True, check=False,
    )
    assert healthy.returncode == 0, healthy.stderr
    payload = json.loads(healthy.stdout)
    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert "pending" in payload and "stale" in payload

    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    artifact = status["checkpoints"]["draft"]["artifacts"][0]
    (store.project_dir(root.project.id) / artifact["path"]).unlink()
    broken = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor",
         root.project.id, "--json"],
        capture_output=True, text=True, check=False,
    )
    assert broken.returncode == 1
    payload = json.loads(broken.stdout)
    assert payload["ok"] is False
    assert any(
        row["code"] == "artifact.missing" for row in payload["findings"]
    )

    missing = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor", "prj-nope"],
        capture_output=True, text=True, check=False,
    )
    assert missing.returncode == 2
    assert "not found" in missing.stderr


def test_unversioned_world_record_edit_is_detected_against_a_recorded_packet(
    tmp_path: Path,
):
    """A region name has no stored ``content_version``, so the record alone
    cannot tell an edit from the original.  The packet recorded by an earlier
    run pins the hash it saw, so the edit becomes a warning instead of silence.
    """
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    world_file = store.project_dir(root.project.id) / "world" / "regions" / "region-coast.json"
    payload = json.loads(world_file.read_text(encoding="utf-8"))
    payload["name"] = "書き換えられた地域"
    world_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = inspect_project(store, root.project.id)
    assert report.ok is True
    finding = next(
        item for item in report.findings if item.code == "world.record_changed"
    )
    assert finding.severity == "warning"
    assert finding.node_id == child.child_node_id
    assert finding.details["record_type"] == "region"
    assert finding.details["record_id"] == "region-coast"
    assert finding.details["run_id"]
    assert (
        finding.details["recorded_content_version"]
        != finding.details["current_content_version"]
    )
    # No stored hash is rewritten to match: the check stays read-only.
    assert report.ok is True


class BadDesign:
    """Answer some design documents with text that never passes its checkers.

    The design stage is fail-open, so the run still completes; the recorded
    report is the only place the unresolved documents remain visible.
    """

    name = "bad-design"
    model = "bad-design-fixture"
    model_version = "v1"

    #: Parses, but the brief checker rejects it (no similar works, short logline).
    BAD_BRIEF = json.dumps({
        "logline": "短い", "premise": "x", "theme": "務め対情",
        "elements": {"who": "a", "where": "b", "wants": "c", "obstacle": "d"},
        "similar": [], "prohibitions": [], "failure_questions": [],
        "genre": "幻想短編", "audience": "大人",
    }, ensure_ascii=False)

    def __init__(self, delegate):
        self.delegate = delegate

    @staticmethod
    def _result(text: str):
        return GenerationResult(
            text=text, provider="bad-design", model="bad-design-fixture",
            model_version="v1",
        )

    def generate(self, request: GenerationRequest):
        if request.purpose in {"design:brief", "design:brief:repair"}:
            return self._result(self.BAD_BRIEF)
        if request.purpose in {"design:voice", "design:voice:repair"}:
            return self._result("これはJSONではない")
        return self.delegate.generate(request)


def test_unresolved_design_documents_are_reported_per_node(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    run = ProjectRunner(store)
    run.run(root.project.id, BadDesign(ScriptedProvider(project_responses())))
    run.run(
        root.project.id, BadDesign(ScriptedProvider(project_responses())),
        node_id=child.child_node_id,
    )
    before = tree_digest(tmp_path)

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    changes = [item for item in report.findings if item.code == "design.unresolved"]
    assert len(changes) == 2
    assert sorted(item.node_id for item in changes) == sorted(
        [root.root_node.id, child.child_node_id]
    )
    for item in changes:
        assert item.severity == "warning"
        assert item.details["stage"] == "design"
        assert item.details["unresolved"] == ["brief"]
        assert item.details["missing"] == ["voice"]
        assert item.details["unresolved_count"] == 1
        assert item.details["missing_count"] == 1
        assert item.details["run_id"]
        assert item.details["report_path"].endswith("/design.json")
        assert item.details["attempts"] >= 1
        assert "fail-open" in item.message
        assert "brief, voice" in item.message
    # Structural information, not an operational blocker: nothing is suggested
    # and nothing is regenerated.
    assert report.to_dict()["next_actions"] == []
    statuses = {check["name"]: check["status"] for check in report.to_dict()["checks"]}
    assert statuses["checkpoints"] == "warn"
    assert statuses["runs"] == "pass"
    # Read-only, like every other doctor check.
    assert tree_digest(tmp_path) == before


def test_clean_design_reports_do_not_warn(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec(), project_id="prj-doctor-clean")
    run_node(store, root.project.id, root.root_node.id)
    report = inspect_project(store, root.project.id)
    assert [item.code for item in report.findings] == []
    assert report.to_dict()["next_actions"] == []


def test_design_checkpoint_without_a_report_is_not_a_finding(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec(), project_id="prj-doctor-noreport")
    run_node(store, root.project.id, root.root_node.id)
    path = (
        store.node_dir(root.project.id, root.root_node.id) / "checkpoints" / "design.json"
    )
    checkpoint = StageCheckpoint.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert [item.path for item in checkpoint.artifacts if item.path.endswith("/design.json")]
    doctor = ProjectDoctor(store)
    doctor._inspect_design_report(
        root.project.id, root.root_node.id,
        replace(checkpoint, artifacts=tuple(
            item for item in checkpoint.artifacts
            if not item.path.endswith("/design.json")
        )),
    )
    assert doctor._findings == []


def test_unreadable_design_report_is_a_warning(tmp_path: Path, monkeypatch):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec(), project_id="prj-doctor-badreport")
    run_node(store, root.project.id, root.root_node.id)
    original = ProjectStore.read_artifact

    def broken(self, project_id, artifact):
        if artifact.path.endswith("/design.json"):
            raise ValueError("report is not valid JSON")
        return original(self, project_id, artifact)

    monkeypatch.setattr(ProjectStore, "read_artifact", broken)
    report = inspect_project(store, root.project.id)
    codes = [item.code for item in report.findings]
    assert codes == ["design.report_unreadable"]
    assert report.ok is True
    assert report.findings[0].severity == "warning"
    assert "report is not valid JSON" in report.findings[0].message


def test_doctor_cli_reports_unresolved_design_without_failing(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec(), project_id="prj-doctor-cli-design")
    ProjectRunner(store).run(
        root.project.id, BadDesign(ScriptedProvider(project_responses())),
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor",
         root.project.id, "--json"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    rows = [row for row in payload["findings"] if row["code"] == "design.unresolved"]
    assert len(rows) == 1
    assert rows[0]["severity"] == "warning"
    assert rows[0]["details"]["unresolved"] == ["brief"]
    assert payload["next_actions"] == []
    # The human-readable output names the documents instead of a bare count.
    text = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor",
         root.project.id],
        capture_output=True, text=True, check=False,
    )
    assert text.returncode == 0, text.stderr
    assert "design.unresolved" in text.stdout
    assert "brief, voice" in text.stdout


def test_untrusted_index_never_hides_project_corruption(tmp_path: Path):
    """An index alone must not turn a full doctor inspection into a clean result."""
    store = ProjectStore(tmp_path)
    root, child, _ = make_family(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)

    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    artifact = next(
        row for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    )
    (project_dir / artifact["path"]).unlink()
    world_file = project_dir / "world" / "culture_states" / "state-tide.json"
    data = json.loads(world_file.read_text(encoding="utf-8"))
    data["attributes"] = {"marker": "TAMPERED"}
    world_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    baseline = inspect_project(store, root.project.id)
    baseline_codes = {item.code for item in baseline.findings}
    assert {"artifact.missing", "world.invalid"} <= baseline_codes
    # Mimic an old, incomplete index with a previous inspection and no checksums.
    # It must never be trusted to skip revisions, checkpoints, links or world.
    (project_dir / ".index.json").write_text(json.dumps({
        "schema": "asc-project-index-v1", "project_id": root.project.id,
        "summary": {"last_inspected_at": "2026-10-28T00:00:00Z"},
        "nodes": {}, "revisions": {}, "checksums": {},
    }), encoding="utf-8")
    before = tree_digest(project_dir)
    report = inspect_project(store, root.project.id)
    assert report.ok is False
    assert {item.code for item in report.findings} == baseline_codes
    statuses = {check["name"]: check["status"] for check in report.checks}
    assert all(statuses[name] != "skipped" for name in ("revisions", "checkpoints", "links", "world"))
    assert tree_digest(project_dir) == before
