"""``diff``: record-level comparison of two ContextPackets or two compilations."""
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
    DIFF_SCHEMA,
    CanonScope,
    DiffError,
    DiffSide,
    ProjectRunner,
    ProjectStore,
    WorkSpec,
    WorldCompiler,
    WorldStore,
    build_diff,
    compare_sides,
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
    plan["timeline"]["chapters"].append(
        {"id": "ch04", "day": 10, "location": "灯台"}
    )
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
    root = store.create_project(spec("親"), project_id="prj-diff")
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


def test_same_revision_stages_diff_as_identical(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id)
    design_run = status["checkpoints"]["design"]["run_id"]

    report = build_diff(
        store, root.project.id,
        f"run:{design_run}", f"stage:{'design'}",
        node_id=child.child_node_id,
    )
    data = report.to_dict()
    assert data["schema"] == DIFF_SCHEMA
    assert data["read_only"] is True
    assert data["identical"] is True
    assert data["counts"]["added"] == 0
    assert data["counts"]["removed"] == 0
    assert data["counts"]["changed"] == 0
    assert data["counts"]["unchanged"] == data["left"]["record_count"]
    assert data["left"]["record_count"] > 0
    # World references and ancestor canon items are both listed as records.
    scopes = {row["scope"] for row in report.left.records}
    assert scopes == {"world", f"ancestor:{root.root_node.id}"}
    record_types = {row["record_type"] for row in report.left.records}
    assert "world_canon_entry" in record_types
    assert {"characters", "chapters", "facts"} <= record_types
    # A plain-run project is not revision-namespaced, but the packet identity is.
    assert data["left"]["identity"]["revision_id"] == status["current_revision_id"]


def test_adopted_canon_shows_added_and_removed_records(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    status = store.status(root.project.id, child.child_node_id)
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

    before_continue = build_diff(
        store, root.project.id, "stage:design", "current",
        node_id=child.child_node_id,
    )
    assert before_continue.identical is False
    assert {row["id"] for row in before_continue.added} == {"canon-adopted-old"}
    assert [row["scope"] for row in before_continue.added] == ["world"]
    assert "omitted_canon_count" not in before_continue.attribute_changes
    assert "binding_id" not in before_continue.attribute_changes
    record = before_continue.added[0]
    assert record["record_type"] == "world_canon_entry"
    assert len(record["content_version"]) == 64

    # A continuation records the old entry, so a later supersession is visible
    # as one removal plus one addition instead of a silent replacement.
    continued = ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=child.child_node_id,
        world_binding_id="binding-empire",
    )
    recorded_run = continued.stage_runs["design"]
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
    after = build_diff(
        store, root.project.id, f"run:{recorded_run}", "current",
        node_id=child.child_node_id,
    ).to_dict()
    assert [row["id"] for row in after["records"]["added"]] == ["canon-adopted-new"]
    assert [row["id"] for row in after["records"]["removed"]] == ["canon-adopted-old"]
    assert after["counts"]["changed"] == 0
    # The recorded side still lists the old entry: the diff wrote nothing.
    recorded = build_diff(
        store, root.project.id, f"run:{recorded_run}", "current",
        node_id=child.child_node_id,
    ).left
    recorded_world = {
        (row["record_type"], row["id"])
        for row in recorded.records if row["scope"] == "world"
    }
    assert ("world_canon_entry", "canon-adopted-old") in recorded_world
    assert ("world_canon_entry", "canon-adopted-new") not in recorded_world
    # The continuation pinned its own binding record; the diff reports it as a
    # record like any other instead of hiding it behind a count.
    assert any(kind == "work_world_binding" for kind, _ in recorded_world)


def test_ancestor_continuation_adds_ancestor_records(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    child_status = store.status(root.project.id, child.child_node_id)
    recorded_run = child_status["checkpoints"]["design"]["run_id"]
    root_revision_before = store.status(root.project.id)["current_revision_id"]

    continued = ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=root.root_node.id,
    )
    report = build_diff(
        store, root.project.id, f"run:{recorded_run}", "current",
        node_id=child.child_node_id,
    ).to_dict()
    added = report["records"]["added"]
    assert any(
        row["scope"] == f"ancestor:{root.root_node.id}"
        and row["record_type"] == "chapters" and row["id"] == "ch04"
        for row in added
    )
    assert report["ancestors"] == {
        root.root_node.id: {
            "left": root_revision_before,
            "right": continued.status["current_revision_id"],
        }
    }
    # The child's own revision did not move; only its ancestor's did.
    assert "revision_id" not in report["attributes"]
    # The world binding is untouched by the ancestor's continuation.
    assert "binding_id" not in report["attributes"]
    assert "binding_content_version" not in report["attributes"]


def test_diff_is_read_only(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    project_dir = store.project_dir(root.project.id)
    before = tree_digest(project_dir)
    for _ in range(2):
        build_diff(
            store, root.project.id, "stage:plan", "current",
            node_id=child.child_node_id,
        )
        build_diff(
            store, root.project.id, "stage:plan", "stage:draft",
            node_id=child.child_node_id,
        )
    assert tree_digest(project_dir) == before


def test_compilation_versions_diff_record_by_record(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec("世界"), project_id="prj-compile-diff")
    world = WorldStore(store)
    world.add_record(snapshot.project.id, "timeframe", {
        "id": "tf-a", "name": "A暦", "calendar": "solar", "epoch": "A",
    })
    world.add_record(snapshot.project.id, "time-span", {
        "id": "span-a1", "timeframe_id": "tf-a", "precision": "exact",
        "start": 1, "end": 1, "label": "A元年",
    })
    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="global",
        content={"marker": "GLOBAL"}, valid_span_id="span-a1", entry_id="canon-global",
    )
    compiler = WorldCompiler(store)
    compiler.add_profile(snapshot.project.id, {
        "id": "profile-chronicle", "kind": "chronicle", "title": "A暦の年代記",
        "timeframe_id": "tf-a",
    })
    first = compiler.compile(snapshot.project.id, "profile-chronicle")

    identical = build_diff(
        store, snapshot.project.id,
        f"compile:profile-chronicle@{first.content_version}",
        "compile:profile-chronicle@" + first.content_version,
    ).to_dict()
    assert identical["identical"] is True
    assert identical["right"]["source"] == "compilation"

    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="new",
        content={"marker": "NEW"}, entry_id="canon-new",
    )
    second = compiler.compile(snapshot.project.id, "profile-chronicle")
    assert second.content_version != first.content_version

    report = build_diff(
        store, snapshot.project.id,
        f"compile:profile-chronicle@{first.content_version}",
        f"compile:profile-chronicle@{second.content_version}",
    ).to_dict()
    assert report["identical"] is False
    assert [row["id"] for row in report["records"]["added"]] == ["canon-new"]
    assert report["records"]["removed"] == []
    assert report["attributes"]["content_version"] == {
        "left": first.content_version, "right": second.content_version,
    }
    assert report["attributes"]["text_sha256"]["left"] == first.sha256
    # Older compilation artifacts are never rewritten by a diff.
    assert first.path.read_bytes()

    with pytest.raises(DiffError, match="pick one with compile:profile-chronicle@"):
        build_diff(
            store, snapshot.project.id,
            "compile:profile-chronicle", f"compile:profile-chronicle@{second.content_version}",
        )
    with pytest.raises(DiffError, match="has no compilation"):
        build_diff(
            store, snapshot.project.id,
            "compile:profile-chronicle@deadbeef", f"compile:profile-chronicle@{second.content_version}",
        )
    with pytest.raises(DiffError, match="no compiled artifact"):
        build_diff(
            store, snapshot.project.id, "compile:profile-missing", "current",
        )


def test_diff_rejects_mixed_kinds_and_unknown_specs(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)
    compiler = WorldCompiler(store)
    compiler.add_profile(root.project.id, {
        "id": "profile-collection", "kind": "collection", "title": "作品集",
        "node_id": root.root_node.id,
    })
    compiled = compiler.compile(root.project.id, "profile-collection")
    with pytest.raises(DiffError, match="cannot diff"):
        build_diff(
            store, root.project.id, "stage:plan",
            f"compile:profile-collection@{compiled.content_version}",
            node_id=child.child_node_id,
        )
    with pytest.raises(DiffError, match="unknown diff side"):
        build_diff(store, root.project.id, "packet:whatever", "current")
    with pytest.raises(DiffError, match="unknown stage"):
        build_diff(store, root.project.id, "stage:nope", "current")
    with pytest.raises(DiffError, match="run:"):
        build_diff(store, root.project.id, "run:", "current")
    with pytest.raises(DiffError, match="run not found"):
        build_diff(store, root.project.id, "run:att-missing-plan", "current")


def test_root_without_packet_cannot_be_diffed(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec("単独"), project_id="prj-solo")
    run_node(store, root.project.id, root.root_node.id)
    with pytest.raises(DiffError, match="no ContextPacket"):
        build_diff(store, root.project.id, "stage:plan", "current")
    with pytest.raises(DiffError, match="no ContextPacket"):
        build_diff(store, root.project.id, "current", "stage:plan")


def test_compare_sides_classifies_version_changes():
    def side(records, ancestors=()):
        return DiffSide(
            spec="synthetic", source="context-packet",
            identity={"project_id": "prj", "revision_id": "rev-1"},
            document_sha256="0" * 64,
            records=tuple(records), attributes={"kind": "packet"},
            ancestors=tuple(ancestors),
        )

    left = side(
        [
            {"scope": "world", "record_type": "world_region", "id": "r1",
             "content_version": "aaa"},
            {"scope": "world", "record_type": "world_region", "id": "r2",
             "content_version": "bbb"},
        ],
        ancestors=[{"node_id": "node-a", "revision_id": "rev-a1"}],
    )
    right = side(
        [
            {"scope": "world", "record_type": "world_region", "id": "r1",
             "content_version": "zzz"},
            {"scope": "world", "record_type": "world_region", "id": "r3",
             "content_version": "ccc"},
        ],
        ancestors=[{"node_id": "node-a", "revision_id": "rev-a2"}],
    )
    report = compare_sides("prj", left, right).to_dict()
    assert report["counts"] == {
        "added": 1, "removed": 1, "changed": 1, "unchanged": 0,
    }
    assert report["records"]["changed"] == [{
        "scope": "world", "record_type": "world_region", "id": "r1",
        "left_content_version": "aaa", "right_content_version": "zzz",
    }]
    assert report["ancestors"] == {
        "node-a": {"left": "rev-a1", "right": "rev-a2"},
    }
    assert report["identical"] is False

    with pytest.raises(DiffError, match="cannot diff"):
        compare_sides("prj", left, DiffSide(
            spec="compile:x", source="compilation", identity={},
            document_sha256="0" * 64, records=(), attributes={},
        ))


def test_diff_cli_text_and_json(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child = make_project(store)
    add_world(store, root.project.id, child.child_node_id)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, child.child_node_id)

    human = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "diff",
         root.project.id, "--node", child.child_node_id,
         "--left", "stage:plan", "--right", "current"],
        capture_output=True, text=True, check=False,
    )
    assert human.returncode == 0, human.stderr
    assert "Identical: yes" in human.stdout
    assert "Records: added=0 removed=0 changed=0" in human.stdout

    machine = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "diff",
         root.project.id, "--node", child.child_node_id,
         "--left", "stage:plan", "--right", "current", "--json"],
        capture_output=True, text=True, check=False,
    )
    assert machine.returncode == 0, machine.stderr
    payload = json.loads(machine.stdout)
    assert payload["schema"] == DIFF_SCHEMA
    assert payload["identical"] is True

    broken = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "diff",
         root.project.id, "--left", "stage:nope", "--right", "current"],
        capture_output=True, text=True, check=False,
    )
    assert broken.returncode == 2
    assert "unknown stage" in broken.stderr

    missing = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "diff",
         "prj-unknown", "--left", "current", "--right", "current"],
        capture_output=True, text=True, check=False,
    )
    assert missing.returncode == 2
