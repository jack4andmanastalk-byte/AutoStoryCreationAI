"""One work summary and one set of next actions for ``status`` and ``doctor``.

Also covers the record-edit warning that closes the PR 9 known limitation:
an unversioned world record rewritten in place is invisible to the record
itself, but visible against a packet an earlier run recorded.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    GenerationRequest,
    ResponsePendingError,
    ScriptedProvider,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    CanonScope,
    ProjectRunner,
    ProjectRunPending,
    ProjectStore,
    WorkSpec,
    WorldCompiler,
    WorldStore,
    build_actions,
    inspect_project,
    summarize,
)
from asc.project.observability import (  # noqa: E402
    UNVERSIONED_WORLD_TYPES,
    WORK_SUMMARY_SCHEMA,
    actions_from_record_changes,
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


def spec(title: str, chapters: int = 3) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の短い物語。", chapter_count=chapters,
        target_chars_per_chapter=1200,
    )


def add_world(store: ProjectStore, project_id: str, node_id: str, *,
              binding_id: str = "binding-lamp") -> None:
    world = WorldStore(store)
    world.add_record(project_id, "timeframe", {
        "id": "tf-tide", "name": "潮汐暦", "calendar": "lunar", "epoch": "開港",
    })
    world.add_record(project_id, "time-span", {
        "id": "span-120", "timeframe_id": "tf-tide", "precision": "exact",
        "start": 120, "end": 120, "label": "開港120年",
    })
    world.add_record(project_id, "region", {"id": "region-harbor", "name": "港"})
    world.add_record(project_id, "culture", {"id": "culture-lamp", "name": "灯台守"})
    world.add_record(project_id, "culture-state", {
        "id": "state-lamp", "culture_id": "culture-lamp",
        "valid_span_id": "span-120", "region_ids": ["region-harbor"],
        "attributes": {"marker": "LAMP"},
    })
    world.bind_work(
        project_id, node_id, time_span_ids=("span-120",),
        region_ids=("region-harbor",), culture_state_ids=("state-lamp",),
        binding_id=binding_id,
    )


def make_child(store: ProjectStore):
    root = store.create_project(spec("親"), project_id="prj-obs")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    return root, child


class Interrupt:
    """Stop the stage and wait for an operator response."""

    name = "interrupt"
    model = "interrupt-fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, response_path: Path):
        self.delegate = delegate
        self.purpose = purpose
        self.response_path = response_path
        self.calls = []

    def generate(self, request: GenerationRequest):
        self.calls.append(request)
        if request.purpose == self.purpose:
            raise ResponsePendingError(
                f"NEED RESPONSE key={self.purpose}",
                key=self.purpose, response_path=str(self.response_path),
                request=request,
            )
        return self.delegate.generate(request)


def test_summary_shape_marks_uninspected_counts(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    ProjectRunner(store).run(root.project.id, ScriptedProvider(responses()))
    status = store.status(root.project.id)
    assert status["work"]["schema"] == WORK_SUMMARY_SCHEMA
    assert status["work"]["scope"] == "node"
    assert status["work"]["node_id"] == root.root_node.id
    assert status["work"]["state"] == "complete"
    assert status["work"]["completed_stages"] == ["plan", "design", "draft"]
    assert status["work"]["next_stage"] is None
    # status never reads world records or run manifests, and says so.
    assert status["work"]["stale"] == {
        "links": 0, "canon": None, "bindings": None,
    }
    assert status["work"]["runs"]["interrupted"] is None
    assert "world_canon" not in status["work"]["inspected"]
    assert "runs" not in status["work"]["inspected"]
    # The summary is JSON-stable and additive: existing keys are untouched.
    json.dumps(status["work"], sort_keys=True)
    for key in ("state", "stages", "pending", "links", "children", "checkpoints"):
        assert key in status


def test_status_and_doctor_agree_on_the_work_summary(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    ProjectRunner(store).run(root.project.id, ScriptedProvider(responses()))
    ProjectRunner(store).run(
        root.project.id, ScriptedProvider(responses()), node_id=child.child_node_id,
    )
    status = store.status(root.project.id)
    report = inspect_project(store, root.project.id).to_dict()
    assert report["work"]["schema"] == status["work"]["schema"]
    assert report["work"]["scope"] == status["work"]["scope"]
    assert report["work"]["node_id"] == status["work"]["node_id"]
    for key in ("state", "stages", "completed_stages", "failed_stages",
                "waiting_stages", "next_stage"):
        assert report["work"][key] == status["work"][key], key
    assert report["work"]["pending"]["count"] == status["work"]["pending"]["count"]
    assert report["work"]["stale"]["links"] == status["work"]["stale"]["links"]
    # doctor inspected strictly more than status, and the summary records that.
    assert set(status["work"]["inspected"]) < set(report["work"]["inspected"])
    assert report["work"]["stale"]["canon"] == 0
    assert report["work"]["stale"]["bindings"] == 0
    assert report["work"]["runs"]["interrupted"] == 0
    # Both commands expose the same action list for the same state.
    assert report["next_actions"] == status["next_actions"] == []


def test_failed_stage_offers_the_retry_action(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(
        WorkSpec(
            title="失敗", premise="失敗の短い物語。", chapter_count=2,
            target_chars_per_chapter=800,
        ),
        project_id="prj-failed",
    )
    # The fixture plan always has three chapters, so a two-chapter spec fails.
    from asc.project import ProjectRunError
    with pytest.raises(ProjectRunError):
        ProjectRunner(store).run(root.project.id, ScriptedProvider(responses()))
    status = store.status(root.project.id)
    assert status["work"]["state"] == "failed"
    assert status["work"]["failed_stages"] == ["plan"]
    assert status["next_actions"][0]["action"] == "resume --retry-failed"
    assert status["next_actions"][0]["command"].endswith(
        "resume prj-failed --retry-failed"
    )
    assert "plan is failed" in status["next_actions"][0]["reason"]
    report = inspect_project(store, root.project.id).to_dict()
    assert report["work"]["failed_stages"] == ["plan"]
    assert report["next_actions"] == status["next_actions"]
    finding = next(
        item for item in report["findings"] if item["code"] == "checkpoint.failed"
    )
    assert "resume --retry-failed" in finding["message"]


def test_pending_and_stale_states_produce_matching_actions(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    pending_path = tmp_path / "operator" / "design-world.json"
    with pytest.raises(ProjectRunPending):
        run = ProjectRunner(store)
        run.run(
            root.project.id,
            Interrupt(ScriptedProvider(responses()), "design:world", pending_path),
            node_id=child.child_node_id,
        )
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    assert status["work"]["state"] == "waiting_response"
    assert status["work"]["pending"] == {
        "count": 1, "ready": 0, "waiting_for_reply": 1,
    }
    action = status["next_actions"][0]
    # The waiting hint names the standard flow (U-02): export, answer, submit.
    assert action["action"] == "relay export"
    assert action["command"].endswith("relay export prj-obs")
    assert "then submit the answer" in action["reason"]
    report = inspect_project(store, root.project.id).to_dict()
    assert [row["action"] for row in report["next_actions"]] == ["relay export"]

    # Writing the response turns the hint into a plain resume.
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(json.dumps({"text": responses()["design:world"]}),
                            encoding="utf-8")
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    assert status["work"]["pending"]["ready"] == 1
    assert status["next_actions"][0]["action"] == "resume"
    assert "response file exists" in status["next_actions"][0]["reason"]


def test_stale_link_and_binding_actions_come_from_one_place(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    run = ProjectRunner(store)
    run.run(root.project.id, ScriptedProvider(responses()))
    run.run(root.project.id, ScriptedProvider(responses()), node_id=child.child_node_id)
    # A continuation of the child makes the parent's pinned link stale.
    continuation = responses()
    plan = json.loads(continuation["plan"])
    plan["timeline"]["chapters"].append({"id": "ch04", "day": 10, "location": "港"})
    continuation["plan"] = json.dumps(plan, ensure_ascii=False)
    continuation["draft:ch04"] = "{{time: day=10}}{{location: 港}}\n" + "追記。" * 80
    for doc in ("brief", "world", "history", "character", "relation", "plot",
                "scene", "voice"):
        continuation[f"design:{doc}:repair"] = continuation[f"design:{doc}"]
    run.continue_project(
        root.project.id, ScriptedProvider(continuation), additional_chapters=1,
        node_id=child.child_node_id,
    )
    parent_status = store.status(root.project.id)
    actions = {row["action"]: row for row in parent_status["next_actions"]}
    assert "adopt-child" in actions
    assert actions["adopt-child"]["command"].endswith("adopt-child prj-obs link-child")
    report = inspect_project(store, root.project.id).to_dict()
    doctor_actions = {row["action"]: row for row in report["next_actions"]}
    assert doctor_actions["adopt-child"]["command"] == actions["adopt-child"]["command"]

    # Only doctor reads world bindings, and it says so in the summary.
    assert parent_status["work"]["stale"]["bindings"] is None
    assert report["work"]["stale"]["bindings"] == 1
    doctor_binding = next(
        row for row in report["next_actions"] if row["action"] == "world bind"
    )
    assert doctor_binding["command"].endswith("world bind prj-obs --node node-child")
    assert all(
        row["action"] != "world bind" for row in parent_status["next_actions"]
    )

    # Re-binding at the current revision resolves the hint.  The older binding
    # stays in doctor's informational stale list because it pins an old
    # revision, so the list and the action must not be the same number.
    WorldStore(store).bind_work(
        root.project.id, child.child_node_id, time_span_ids=("span-120",),
        region_ids=("region-harbor",), culture_state_ids=("state-lamp",),
        binding_id="binding-lamp-new",
    )
    report = inspect_project(store, root.project.id).to_dict()
    assert report["work"]["stale"]["bindings"] == 1
    assert all(
        row["action"] != "world bind" for row in report["next_actions"]
    )


def test_one_edited_record_is_one_finding_and_one_action(tmp_path: Path):
    """One edited record is one fact, even when every bound node recorded it.

    Before grouping, seven bound nodes produced seven nearly identical
    warnings and seven ``diff`` commands for a single renamed region, which
    buried the one line an operator needed.
    """
    store = ProjectStore(tmp_path)
    root = store.create_project(spec("親"), project_id="prj-group")
    children = [
        store.create_child(
            root.project.id, spec(f"子{i}"), order=i,
            child_node_id=f"node-g{i}", link_id=f"link-g{i}",
        )
        for i in (1, 2, 3)
    ]
    # The records are created once; every node gets its own explicit binding so
    # each one records the world selection it actually generated from.
    add_world(store, root.project.id, root.root_node.id, binding_id="binding-g0")
    for index, child in enumerate(children, start=1):
        WorldStore(store).bind_work(
            root.project.id, child.child_node_id, time_span_ids=("span-120",),
            region_ids=("region-harbor",), culture_state_ids=("state-lamp",),
            binding_id=f"binding-g{index}",
        )
    run = ProjectRunner(store)
    run.run(root.project.id, ScriptedProvider(responses()))
    for child in children:
        run.run(
            root.project.id, ScriptedProvider(responses()),
            node_id=child.child_node_id,
        )
    assert inspect_project(store, root.project.id).findings == ()

    world_file = (
        store.project_dir(root.project.id) / "world" / "regions" / "region-harbor.json"
    )
    payload = json.loads(world_file.read_text(encoding="utf-8"))
    payload["name"] = "港（改称）"
    world_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    changes = [item for item in report.findings if item.code == "world.record_changed"]
    assert len(changes) == 1
    change = changes[0]
    assert change.severity == "warning"
    # The finding is project-wide, so it names no single node.
    assert change.node_id is None
    assert change.details["record_type"] == "region"
    assert change.details["record_id"] == "region-harbor"
    node_ids = change.details["node_ids"]
    assert node_ids == sorted(node_ids)
    assert sorted(node_ids) == sorted(
        [root.root_node.id] + [child.child_node_id for child in children]
    )
    assert change.details["node_count"] == len(node_ids)
    assert [row["node_id"] for row in change.details["nodes"]] == node_ids
    run_ids = {row["run_id"] for row in change.details["nodes"]}
    assert len(run_ids) == len(node_ids)
    assert all(row["recorded_content_version"] for row in change.details["nodes"])
    # The legacy keys still describe the first affected node.
    assert change.details["run_id"] == change.details["nodes"][0]["run_id"]
    assert change.details["recorded_content_version"] == (
        change.details["nodes"][0]["recorded_content_version"]
    )
    assert f"run:{change.details['run_id']}" in change.message
    assert f"{len(node_ids)} nodes are affected" in change.message

    diffs = [row for row in report.to_dict()["next_actions"] if row["action"] == "diff"]
    assert len(diffs) == 1
    assert diffs[0]["node_id"] == node_ids[0]
    assert diffs[0]["node_ids"] == node_ids
    assert diffs[0]["record_id"] == "region-harbor"
    assert f"--left run:{change.details['run_id']}" in diffs[0]["command"]
    assert f"{len(node_ids)} runs recorded" in diffs[0]["reason"]

    # A second edited record is a second question, not more noise per node.
    span_file = (
        store.project_dir(root.project.id) / "world" / "time_spans" / "span-120.json"
    )
    span = json.loads(span_file.read_text(encoding="utf-8"))
    span["label"] = "開港百二十年"
    span_file.write_text(json.dumps(span, ensure_ascii=False), encoding="utf-8")
    report = inspect_project(store, root.project.id)
    pairs = [
        (item.details["record_type"], item.details["record_id"])
        for item in report.findings if item.code == "world.record_changed"
    ]
    assert pairs == [("region", "region-harbor"), ("time_span", "span-120")]
    diffs = [row for row in report.to_dict()["next_actions"] if row["action"] == "diff"]
    assert len(diffs) == 2


def test_build_actions_is_pure_and_ordered():
    changes = actions_from_record_changes([
        {
            "record_type": "region", "record_id": "region-harbor",
            "current_content_version": "c" * 64,
            "nodes": [
                {"node_id": "node-b", "run_id": "att-2-plan",
                 "recorded_content_version": "b" * 64},
                {"node_id": "node-a", "run_id": "att-1-plan",
                 "recorded_content_version": "a" * 64},
            ],
        },
    ])
    # One edited record is one action, whichever nodes recorded it.
    assert len(changes) == 1
    assert changes[0]["node_id"] == "node-a"
    assert changes[0]["run_id"] == "att-1-plan"
    assert changes[0]["node_ids"] == ["node-a", "node-b"]
    actions = build_actions(
        project_id="prj-x",
        state="failed",
        failed_stages=("design",),
        interrupted_runs=1,
        stale_bindings=1,
        stale_canon=2,
        stale_links=1,
        record_changes=changes,
    )
    assert [row["action"] for row in actions] == [
        "resume --retry-failed", "resume", "world bind", "world adopt-canon",
        "adopt-child", "diff",
    ]
    assert actions[0]["command"] == (
        "python3 scripts/story_project.py resume prj-x --retry-failed"
    )
    assert actions[-1]["command"] == (
        "python3 scripts/story_project.py diff prj-x --node node-a "
        "--left run:att-1-plan --right current"
    )
    assert "region-harbor" in actions[-1]["reason"]
    assert "2 runs recorded" in actions[-1]["reason"]
    assert actions[-1]["record_id"] == "region-harbor"
    assert actions[-1]["node_ids"] == ["node-a", "node-b"]

    # Two different edited records stay two separate questions.
    two = actions_from_record_changes([
        {"record_type": "region", "record_id": "region-harbor", "nodes": [
            {"node_id": "node-a", "run_id": "att-1-plan"}]},
        {"record_type": "time_frame", "record_id": "tf-main", "nodes": [
            {"node_id": "node-a", "run_id": "att-1-plan"}]},
    ])
    assert [(row["record_type"], row["record_id"]) for row in two] == [
        ("region", "region-harbor"), ("time_frame", "tf-main"),
    ]
    single = build_actions(
        project_id="prj-x", state="complete", record_changes=two[:1],
    )
    assert single[0]["reason"] == (
        "world record region region-harbor differs from the recorded version"
    )

    # The older per-run shape is still accepted and collapses to one action.
    legacy = actions_from_record_changes([
        {"run_id": "att-1-plan", "node_id": "node-a", "count": 2},
        {"run_id": "att-1-plan", "node_id": "node-a", "count": 2},
    ])
    assert len(legacy) == 1 and legacy[0]["count"] == 1

    assert summarize(state="not_started")["next_stage"] is None
    assert build_actions(project_id="prj-x", state="not_started")[0]["action"] == "run"


def test_unversioned_record_edit_warns_and_points_at_diff(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    run = ProjectRunner(store)
    run.run(root.project.id, ScriptedProvider(responses()))
    run.run(root.project.id, ScriptedProvider(responses()), node_id=child.child_node_id)
    assert inspect_project(store, root.project.id).findings == ()

    world_file = (
        store.project_dir(root.project.id) / "world" / "regions" / "region-harbor.json"
    )
    payload = json.loads(world_file.read_text(encoding="utf-8"))
    payload["name"] = "港（改称）"
    world_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = inspect_project(store, root.project.id)
    assert report.ok is True
    change = next(
        item for item in report.findings if item.code == "world.record_changed"
    )
    assert change.severity == "warning"
    assert change.node_id == child.child_node_id
    assert change.details["record_type"] == "region"
    assert change.details["record_id"] == "region-harbor"
    assert change.details["recorded_content_version"] != (
        change.details["current_content_version"]
    )
    assert f"run:{change.details['run_id']}" in change.message
    action = next(
        row for row in report.to_dict()["next_actions"] if row["action"] == "diff"
    )
    assert f"--left run:{change.details['run_id']}" in action["command"]
    assert "--right current" in action["command"]
    # The warning stays a warning: the project is readable, exit code is 0.
    assert all(
        item.severity != "error" for item in report.findings
    )
    # doctor is still read-only.
    digest = {
        str(path.relative_to(tmp_path)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(tmp_path.rglob("*")) if path.is_file()
    }
    inspect_project(store, root.project.id)
    after = {
        str(path.relative_to(tmp_path)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(tmp_path.rglob("*")) if path.is_file()
    }
    assert after == digest


def test_append_only_changes_do_not_warn(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    run = ProjectRunner(store)
    run.run(root.project.id, ScriptedProvider(responses()))
    run.run(root.project.id, ScriptedProvider(responses()), node_id=child.child_node_id)

    world = WorldStore(store)
    world.add_record(root.project.id, "region", {"id": "region-cliff", "name": "崖"})
    world.author_world_canon(
        root.project.id, scope=CanonScope("global"), subject="共有",
        content={"marker": "SHARED"}, entry_id="canon-shared",
    )
    world.adopt_world_canon(
        root.project.id, child.child_node_id,
        source_artifact_path=next(
            row["path"] for row in store.status(
                root.project.id, child.child_node_id,
            )["checkpoints"]["plan"]["artifacts"]
            if row["path"].endswith("/canon/facts.json")
        ),
        json_pointer="/facts/0", scope=CanonScope("region", "region-harbor"),
        subject="adopted", entry_id="canon-old",
    )
    world.adopt_world_canon(
        root.project.id, child.child_node_id,
        source_artifact_path=next(
            row["path"] for row in store.status(
                root.project.id, child.child_node_id,
            )["checkpoints"]["plan"]["artifacts"]
            if row["path"].endswith("/canon/facts.json")
        ),
        json_pointer="/facts/0", scope=CanonScope("region", "region-harbor"),
        subject="adopted", supersedes_id="canon-old", entry_id="canon-new",
    )
    report = inspect_project(store, root.project.id)
    assert [
        item.code for item in report.findings if item.code.startswith("world.record")
    ] == []
    # A new record and a superseded entry are visible as additions, not edits.
    assert "world.record_changed" not in {item.code for item in report.to_dict()["findings"]}


def test_unversioned_types_are_the_ones_without_a_stored_version(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    WorldStore(store).author_world_canon(
        root.project.id, scope=CanonScope("global"), subject="共有",
        content={"marker": "SHARED"}, entry_id="canon-shared",
    )
    records = WorldStore(store).validate(root.project.id)
    for record in (
        *records.timeframes, *records.time_spans, *records.regions,
        *records.cultures,
    ):
        data = record.to_dict()
        assert "content_version" not in data, data["record_type"]
        assert data["record_type"] in UNVERSIONED_WORLD_TYPES
    # Versioned records verify themselves on load; a rewrite is already an error.
    for record in (*records.culture_states, *records.canon_entries, *records.bindings):
        data = record.to_dict()
        assert "content_version" in data, data["record_type"]
        assert data["record_type"] not in UNVERSIONED_WORLD_TYPES


def test_status_and_doctor_cli_share_the_summary(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    ProjectRunner(store).run(root.project.id, ScriptedProvider(responses()))

    status_json = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "status",
         root.project.id, "--json"],
        capture_output=True, text=True, check=True,
    ).stdout)
    doctor_json = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor",
         root.project.id, "--json"],
        capture_output=True, text=True, check=True,
    ).stdout)
    assert status_json["work"]["schema"] == doctor_json["work"]["schema"]
    assert status_json["work"]["state"] == doctor_json["work"]["state"]
    assert status_json["work"]["stages"] == doctor_json["work"]["stages"]
    assert status_json["next_actions"] == doctor_json["next_actions"] == []

    human = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "doctor", root.project.id],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "Work (node " in human
    assert "inspected: checkpoints, links, pending, world_canon" in human
    assert "Next:" not in human


def test_editor_and_world_compile_still_work_after_the_warning(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_child(store)
    add_world(store, root.project.id, child.child_node_id)
    run = ProjectRunner(store)
    run.run(root.project.id, ScriptedProvider(responses()))
    run.run(root.project.id, ScriptedProvider(responses()), node_id=child.child_node_id)
    compiler = WorldCompiler(store)
    compiler.add_profile(root.project.id, {
        "id": "profile-region", "kind": "gazetteer", "title": "港の地誌",
        "region_id": "region-harbor",
    })
    before = compiler.compile(root.project.id, "profile-region")
    world_file = (
        store.project_dir(root.project.id) / "world" / "regions" / "region-harbor.json"
    )
    payload = json.loads(world_file.read_text(encoding="utf-8"))
    payload["name"] = "港（改称）"
    world_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    after = compiler.compile(root.project.id, "profile-region")
    assert after.content_version != before.content_version
    assert "港（改称）" in after.text
    assert before.path.read_bytes()
    report = inspect_project(store, root.project.id)
    assert [item.code for item in report.findings] == ["world.record_changed"]
