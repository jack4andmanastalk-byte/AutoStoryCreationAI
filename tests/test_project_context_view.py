"""``context show``: current vs recorded ContextPacket views, references, drift."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    CanonScope,
    ContextViewError,
    ProjectRunner,
    ProjectStore,
    WorkSpec,
    WorldStore,
    build_context_view,
)
from asc.project.context import CONTEXT_PACKET_KIND, CONTEXT_PACKET_WORLD_KIND  # noqa: E402

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


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def make_project(store: ProjectStore):
    root = store.create_project(spec("親"), project_id="prj-context-view")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    return root, child


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
        project_id, scope=CanonScope("global"), subject="共有",
        content={"marker": "SHARED"}, entry_id="canon-shared",
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
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


def test_current_packet_lists_references_and_matches_recorded_runs(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)

    view = build_context_view(store, root.project.id, child.child_node_id)
    assert view.mode == "current"
    assert view.packet is not None
    data = view.to_dict()
    assert data["read_only"] is True
    assert data["summary"]["kind"] == CONTEXT_PACKET_WORLD_KIND
    assert data["summary"]["packet_bytes"] > 0
    assert len(data["summary"]["packet_sha256"]) == 64
    world = data["summary"]["world"]
    assert world["binding_id"] == "binding-empire"
    assert world["overlay_order"] == [
        "global", "timeframe", "region", "culture", "work", "node",
    ]
    assert world["canon_entries"] == 1
    assert world["omitted_canon_count"] == 0
    reference_ids = {row["id"] for row in world["references"]}
    assert {
        "tf-empire", "span-empire", "region-coast", "culture-tide",
        "state-tide", "canon-shared", "binding-empire",
    } == reference_ids
    for row in world["references"]:
        assert len(row["content_version"]) == 64
    assert data["summary"]["ancestors"][0]["node_id"] == root.root_node.id
    assert [row["stage"] for row in data["recorded_packets"]] == [
        "plan", "design", "draft",
    ]
    for row in data["recorded_packets"]:
        assert row["packet_sha256"] == data["summary"]["packet_sha256"]
    assert data["drift"] is None


def test_recorded_packet_by_stage_and_by_run_equals_project_input(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    design_run = status["checkpoints"]["design"]["run_id"]

    by_stage = build_context_view(
        store, root.project.id, child.child_node_id, stage="design",
    )
    assert by_stage.mode == "recorded"
    assert by_stage.run_id == design_run
    assert by_stage.stage == "design"
    assert by_stage.drift is not None and by_stage.drift["differs"] is False

    by_run = build_context_view(
        store, root.project.id, child.child_node_id, run_id=design_run,
    )
    assert by_run.packet == by_stage.packet
    payload = json.loads(
        (store.project_dir(root.project.id) / "runs" / design_run
         / "project-input.json").read_text(encoding="utf-8")
    )
    assert by_run.packet == payload["context_packet"]


def test_recorded_packet_of_older_revision_is_readable_but_not_compared(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    first_revision = status["current_revision_id"]
    design_run = status["checkpoints"]["design"]["run_id"]

    ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=child.child_node_id,
    )
    view = build_context_view(
        store, root.project.id, child.child_node_id, run_id=design_run,
    )
    data = view.to_dict(include_packet=False)
    assert data["mode"] == "recorded"
    assert data["revision_id"] == first_revision
    assert data["current_revision_id"] != first_revision
    assert data["same_revision"] is False
    assert data["drift"] is None
    assert data["summary"]["kind"] == CONTEXT_PACKET_WORLD_KIND
    assert view.packet is not None


def test_drift_reports_superseded_canon_in_a_recorded_packet(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    facts = next(
        row for row in status["checkpoints"]["plan"]["artifacts"]
        if row["path"].endswith("/canon/facts.json")
    )
    world = WorldStore(store)
    world.adopt_world_canon(
        root.project.id, child.child_node_id, source_artifact_path=facts["path"],
        json_pointer="/facts/0", scope=CanonScope("region", "region-coast"),
        subject="adopted", entry_id="canon-adopted-old",
    )
    ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=child.child_node_id,
        world_binding_id="binding-empire",
    )
    # The continuation run recorded the old canon entry in its packet.
    recorded = build_context_view(
        store, root.project.id, child.child_node_id, stage="design",
    )
    assert recorded.drift is not None and recorded.drift["differs"] is False
    recorded_ids = {row["id"] for row in recorded.summary["world"]["references"]}
    assert "canon-adopted-old" in recorded_ids

    current_status = store.status(root.project.id, child.child_node_id)
    facts = next(
        row for row in current_status["checkpoints"]["plan"]["artifacts"]
        if row["path"].endswith("/canon/facts.json")
    )
    world.adopt_world_canon(
        root.project.id, child.child_node_id, source_artifact_path=facts["path"],
        json_pointer="/facts/0", scope=CanonScope("region", "region-coast"),
        subject="adopted", supersedes_id="canon-adopted-old",
        entry_id="canon-adopted-new",
    )
    after = build_context_view(
        store, root.project.id, child.child_node_id, stage="design",
    )
    assert after.drift is not None
    assert after.drift["differs"] is True
    added = after.drift["differences"]["references"]["added"]
    removed = after.drift["differences"]["references"]["removed"]
    assert ["world_canon_entry", "canon-adopted-new"] in added
    assert ["world_canon_entry", "canon-adopted-old"] in removed
    assert after.summary["world"]["canon_entries"] == recorded.summary["world"]["canon_entries"]


def test_root_without_ancestors_or_binding_has_no_packet_and_no_stage_run(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, _ = make_project(store)
    view = build_context_view(store, root.project.id, root.root_node.id)
    assert view.packet is None
    assert view.mode == "current"
    assert view.to_dict()["summary"] == {
        "kind": None, "packet_sha256": None, "packet_bytes": 0,
    }

    run_node(store, root.project.id, root.root_node.id)
    recorded = build_context_view(
        store, root.project.id, root.root_node.id, stage="plan",
    )
    assert recorded.packet is None
    assert recorded.stage == "plan"

    with pytest.raises(ContextViewError):
        build_context_view(
            store, root.project.id, root.root_node.id, run_id="run-does-not-exist",
        )
    with pytest.raises(ContextViewError):
        build_context_view(
            store, root.project.id, root.root_node.id, run_id="x", stage="plan",
        )
    with pytest.raises(ContextViewError):
        build_context_view(store, root.project.id, root.root_node.id, stage="rewrite")


def test_ancestor_packet_children_stay_lightweight(tmp_path: Path):
    """A grandchild packet keeps ancestors compact and never carries prose."""
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    grandchild = store.create_child(
        root.project.id, spec("孫"), parent_node_id=child.child_node_id,
        child_node_id="node-grandchild", link_id="link-grandchild",
    )
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    view = build_context_view(store, root.project.id, grandchild.child_node_id)
    assert view.packet is not None
    data = view.to_dict()
    assert data["summary"]["kind"] == CONTEXT_PACKET_KIND
    assert data["summary"]["world"] is None
    assert [row["node_id"] for row in data["summary"]["ancestors"]] == [
        root.root_node.id, child.child_node_id,
    ]
    for ancestor in view.packet["ancestors"]:
        assert ancestor["canon"] is not None
        assert "text" not in json.dumps(ancestor["chapters"])
        for chapter in ancestor["chapters"]:
            assert "text" not in chapter


def test_context_view_is_read_only(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)
    before = tree_digest(project_dir)
    build_context_view(store, root.project.id, child.child_node_id)
    build_context_view(store, root.project.id, child.child_node_id, stage="plan")
    subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         root.project.id, "--node", child.child_node_id, "--json"],
        capture_output=True, text=True, check=True,
    )
    assert tree_digest(project_dir) == before


def test_context_show_cli_writes_packet_outside_the_project(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)
    before = tree_digest(project_dir)
    out = tmp_path / "external" / "packet.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         root.project.id, "--node", child.child_node_id, "--json", "--out", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["summary"]["kind"] == CONTEXT_PACKET_WORLD_KIND
    assert payload["external_out"] == str(out)
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["record_type"] == CONTEXT_PACKET_WORLD_KIND
    assert tree_digest(project_dir) == before

    status = store.status(root.project.id, child.child_node_id, include_descendants=False)
    design_run = status["checkpoints"]["design"]["run_id"]
    recorded = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         root.project.id, "--node", child.child_node_id, "--run", design_run, "--json"],
        capture_output=True, text=True, check=False,
    )
    assert recorded.returncode == 0, recorded.stderr
    payload = json.loads(recorded.stdout)
    assert payload["mode"] == "recorded"
    assert payload["same_revision"] is True
    assert payload["drift"]["differs"] is False

    unknown = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         root.project.id, "--run", "run-missing"],
        capture_output=True, text=True, check=False,
    )
    assert unknown.returncode == 2
    assert "run not found" in unknown.stderr


def test_json_without_out_embeds_packet_and_out_refuses_an_empty_packet(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, child.child_node_id)
    embedded = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         root.project.id, "--node", child.child_node_id, "--json"],
        capture_output=True, text=True, check=False,
    )
    assert embedded.returncode == 0, embedded.stderr
    payload = json.loads(embedded.stdout)
    assert payload["packet"]["record_type"] == CONTEXT_PACKET_WORLD_KIND
    assert "external_out" not in payload

    never_run = store.create_project(spec("単独"), project_id="prj-no-packet")
    out = tmp_path / "external" / "empty.json"
    refused = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "context", "show",
         never_run.project.id, "--out", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert refused.returncode == 2
    assert "no ContextPacket" in refused.stderr
    assert not out.exists()
