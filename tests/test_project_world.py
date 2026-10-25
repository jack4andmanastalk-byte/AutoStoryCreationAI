from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    CanonScope,
    ProjectRunner,
    ProjectStore,
    ProjectValidationError,
    ReplayBundle,
    WorkNodeRevision,
    WorkSpec,
    WorldStore,
)
from asc.project.model import utc_now  # noqa: E402
from asc.project.world import resolve_json_pointer  # noqa: E402

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
    for doc in ("brief", "world", "history", "character", "relation", "plot", "scene", "voice"):
        responses[f"design:{doc}:repair"] = responses[f"design:{doc}"]
    return responses


def spec(title: str = "世界") -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def add_base_world(world: WorldStore, project_id: str) -> None:
    world.add_record(project_id, "timeframe", {
        "id": "tf-empire", "name": "帝国暦", "calendar": "solar", "epoch": "建国",
    })
    world.add_record(project_id, "time-span", {
        "id": "span-empire", "timeframe_id": "tf-empire", "precision": "exact",
        "start": 120, "end": 120,
    })
    world.add_record(project_id, "region", {"id": "region-coast", "name": "沿岸"})
    world.add_record(project_id, "culture", {"id": "culture-tide", "name": "潮の文化"})


def plan_artifact(status: dict, suffix: str = "/canon/facts.json") -> dict:
    return next(
        row for row in status["checkpoints"]["plan"]["artifacts"]
        if row["path"].endswith(suffix)
    )


def test_child_stores_two_timeframes_and_versioned_culture_states(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec("親"), project_id="prj-world")
    child = store.create_child(
        snapshot.project.id, spec("子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    world = WorldStore(store)
    project_id = snapshot.project.id
    add_base_world(world, project_id)
    world.add_record(project_id, "timeframe", {
        "id": "tf-tide", "name": "潮位暦", "calendar": "lunar", "epoch": "大潮",
    })
    # Create the later span first so the earlier span can explicitly point to it.
    world.add_record(project_id, "time-span", {
        "id": "span-late", "timeframe_id": "tf-empire", "precision": "range",
        "start": 900, "end": 950,
    })
    world.add_record(project_id, "time-span", {
        "id": "span-early", "timeframe_id": "tf-empire", "precision": "approximate",
        "start": 100, "end": 110, "before_span_ids": ["span-late"],
    })
    world.add_record(project_id, "time-span", {
        "id": "span-tide", "timeframe_id": "tf-tide", "precision": "exact",
        "start": 12, "end": 12,
    })
    world.add_record(project_id, "time-span", {
        "id": "span-undated", "precision": "unknown",
        "label": "伝承上はspan-lateより前", "before_span_ids": ["span-late"],
    })
    conversion = world.add_record(project_id, "time-conversion", {
        "id": "conv-empire-tide", "source_timeframe_id": "tf-empire",
        "target_timeframe_id": "tf-tide", "scale": 2, "offset": -188,
    })
    assert conversion.convert(100) == 12

    world.add_record(project_id, "region", {
        "id": "region-harbor", "name": "港", "parent_region_id": "region-coast",
        "valid_span_id": "span-early",
    })
    relation = world.add_record(project_id, "spatial-relation", {
        "id": "spatial-ferry", "source_region_id": "region-harbor",
        "target_region_id": "region-coast", "kind": "ferry",
        "valid_span_id": "span-early",
    })
    assert relation.travel_days is None  # No legacy plan travel_days are inferred.

    world.add_record(project_id, "culture", {"id": "culture-mainland", "name": "内陸の文化"})
    world.add_record(project_id, "culture-state", {
        "id": "state-tide-early", "culture_id": "culture-tide",
        "valid_span_id": "span-early", "region_ids": ["region-coast", "region-harbor"],
        "attributes": {"ritual": "初潮"},
    })
    world.add_record(project_id, "culture-state", {
        "id": "state-mainland-early", "culture_id": "culture-mainland",
        "valid_span_id": "span-early", "region_ids": ["region-coast"],
        "attributes": {"ritual": "種まき"},
    })
    binding = world.bind_work(
        project_id, child.child_node_id,
        time_span_ids=("span-early", "span-tide", "span-undated"),
        region_ids=("region-harbor",),
        culture_state_ids=("state-tide-early", "state-mainland-early"),
        binding_id="binding-child-early",
    )
    assert binding.revision_id == store.load_node(project_id, child.child_node_id).current_revision_id

    # A later state is a new explicitly related record, not a mutation of the
    # child's selected early state.
    world.add_record(project_id, "culture-state", {
        "id": "state-tide-late", "culture_id": "culture-tide",
        "valid_span_id": "span-late", "region_ids": ["region-harbor"],
        "previous_state_id": "state-tide-early", "attributes": {"ritual": "満潮"},
    })
    world.add_record(project_id, "culture-relation", {
        "id": "rel-inherit", "kind": "inheritance",
        "source_state_id": "state-tide-early", "target_state_id": "state-tide-late",
    })
    world.add_record(project_id, "culture-relation", {
        "id": "rel-split", "kind": "split",
        "source_state_id": "state-tide-late", "target_state_id": "state-mainland-early",
    })
    world.add_record(project_id, "culture-relation", {
        "id": "rel-contact", "kind": "contact",
        "source_state_id": "state-tide-early", "target_state_id": "state-mainland-early",
        "valid_span_id": "span-early", "attributes": {"route": "spatial-ferry"},
    })

    status = world.status(project_id, child.child_node_id)
    assert status["counts"]["timeframes"] == 2
    assert {row["id"] for row in status["culture_states"]} == {
        "state-tide-early", "state-tide-late", "state-mainland-early",
    }
    assert status["selected_binding"]["id"] == "binding-child-early"
    assert status["selected_binding"]["culture_state_ids"] == [
        "state-tide-early", "state-mainland-early",
    ]
    assert "state-tide-late" not in status["selected_binding"]["culture_state_ids"]
    assert world.status(project_id)["selected_binding"] is None
    assert next(
        row for row in status["time_spans"] if row["id"] == "span-undated"
    )["start"] is None


def test_world_reference_cycles_and_revision_bindings_are_validated(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec(), project_id="prj-validation")
    world = WorldStore(store)
    add_base_world(world, snapshot.project.id)
    world.add_record(snapshot.project.id, "culture-state", {
        "id": "state-one", "culture_id": "culture-tide", "region_ids": ["region-coast"],
    })
    binding = world.bind_work(
        snapshot.project.id, snapshot.root_node.id,
        time_span_ids=("span-empire",), binding_id="binding-one",
    )
    with pytest.raises(ProjectValidationError, match="duplicate world binding"):
        world.bind_work(
            snapshot.project.id, snapshot.root_node.id, time_span_ids=("span-empire",),
        )
    assert [path.name for path in (
        world.world_dir(snapshot.project.id) / "bindings"
    ).glob("*.json")] == ["binding-one.json"]

    with pytest.raises(ProjectValidationError, match="missing parent region"):
        world.add_record(snapshot.project.id, "region", {
            "id": "region-orphan", "name": "孤立", "parent_region_id": "region-missing",
        })
    assert not world.record_path(snapshot.project.id, "region", "region-orphan").exists()

    # Public writes are append-only.  A hand-edited containment cycle is still
    # rejected by readers rather than being silently flattened.
    region_path = world.record_path(snapshot.project.id, "region", "region-coast")
    original = json.loads(region_path.read_text(encoding="utf-8"))
    world.add_record(snapshot.project.id, "region", {
        "id": "region-inner", "name": "内側", "parent_region_id": "region-coast",
    })
    damaged = dict(original, parent_region_id="region-inner")
    region_path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="cycle"):
        world.validate(snapshot.project.id)
    region_path.write_text(json.dumps(original), encoding="utf-8")

    # A new work revision never inherits the old binding implicitly.
    node = store.load_node(snapshot.project.id, snapshot.root_node.id)
    revision = WorkNodeRevision.create(
        revision_id="rev-second", node_id=node.id, project_id=node.project_id,
        spec=replace(snapshot.revision.spec, premise="改訂したpremise"),
        parent_revision_id=snapshot.revision.id, created_at=utc_now(),
    )
    store.save_revision(revision)
    store.save_node(replace(node, current_revision_id=revision.id, updated_at=utc_now()))
    status = world.status(snapshot.project.id)
    assert status["selected_binding"] is None
    assert status["bindings"][0]["id"] == binding.id
    assert status["bindings"][0]["current"] is False


def test_scoped_canon_overlays_and_json_pointers(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec(), project_id="prj-scopes")
    child = store.create_child(
        snapshot.project.id, spec("子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-local", link_id="link-local",
    )
    world = WorldStore(store)
    add_base_world(world, snapshot.project.id)
    scopes = [
        CanonScope("global"), CanonScope("timeframe", "tf-empire"),
        CanonScope("region", "region-coast"), CanonScope("culture", "culture-tide"),
        CanonScope("work", snapshot.root_node.id), CanonScope("node", child.child_node_id),
    ]
    for index, scope in enumerate(scopes):
        values = {
            "id": f"canon-{scope.kind}", "subject": f"subject-{index}",
            "content": {"scope": scope.kind}, "valid_span_id": "span-empire",
        }
        if scope.kind == "global":
            # Generic JSON input also normalizes omitted optional scope/source
            # fields before hashing the versioned canon content.
            world.add_record(snapshot.project.id, "canon", {
                **values, "scope": {"kind": "global"},
            })
        else:
            world.author_world_canon(
                snapshot.project.id, scope=scope, entry_id=values["id"],
                subject=values["subject"], content=values["content"],
                valid_span_id=values["valid_span_id"],
            )
    status = world.status(snapshot.project.id)
    assert len(status["canon_entries"]) == 6
    assert all(row["current"] and not row["stale"] for row in status["canon_entries"])
    assert {row["scope"]["kind"] for row in status["canon_entries"]} == {
        "global", "timeframe", "region", "culture", "work", "node",
    }

    first = world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="linear",
        content={"version": 1}, entry_id="canon-linear-one",
    )
    second = world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="linear",
        content={"version": 2}, supersedes_id=first.id, entry_id="canon-linear-two",
    )
    with pytest.raises(ProjectValidationError, match="refusing a branch"):
        world.author_world_canon(
            snapshot.project.id, scope=CanonScope("global"), subject="linear",
            content={"version": 3}, supersedes_id=first.id,
        )
    rows = {row["id"]: row for row in world.status(snapshot.project.id)["canon_entries"]}
    assert not rows[first.id]["current"]
    assert rows[second.id]["current"] and rows[second.id]["content"] == {"version": 2}

    document = {"a/b": {"~key": [{"value": 7}]}}
    assert resolve_json_pointer(document, "/a~1b/~0key/0/value") == 7
    with pytest.raises(ProjectValidationError, match="array index"):
        resolve_json_pointer(document, "/a~1b/~0key/01")


def test_generated_canon_requires_adoption_and_source_revision_only_goes_stale(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path / "projects")
    snapshot = store.create_project(spec("親"), project_id="prj-canon")
    child = store.create_child(
        snapshot.project.id, spec("子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-author", link_id="link-author",
    )
    world = WorldStore(store)
    add_base_world(world, snapshot.project.id)
    world.bind_work(
        snapshot.project.id, child.child_node_id, time_span_ids=("span-empire",),
        binding_id="binding-author-old",
    )
    runner = ProjectRunner(store)
    runner.run(snapshot.project.id, ScriptedProvider(project_responses()))
    runner.run(
        snapshot.project.id, ScriptedProvider(project_responses()),
        node_id=child.child_node_id,
    )
    # Generation alone never promotes either root or child facts to world canon.
    assert world.status(snapshot.project.id)["canon_entries"] == []
    old_revision = store.load_node(snapshot.project.id, child.child_node_id).current_revision_id
    old_status = store.status(snapshot.project.id, child.child_node_id, include_descendants=False)
    old_artifact = plan_artifact(old_status)
    adopted = world.adopt_world_canon(
        snapshot.project.id, child.child_node_id,
        source_artifact_path=old_artifact["path"], json_pointer="/facts/0",
        scope=CanonScope("global"), subject="F-01", valid_span_id="span-empire",
        entry_id="canon-global-f01",
    )
    assert adopted.source is not None
    assert adopted.source.revision_id == old_revision
    assert adopted.content["id"] == "F-01"
    # A node-scoped overlay can coexist with the global entry; neither rewrites
    # the other's content or applicability.
    local = world.author_world_canon(
        snapshot.project.id, scope=CanonScope("node", child.child_node_id),
        subject="F-01", content={"summary": "この子作品だけの解釈"},
        valid_span_id="span-empire", entry_id="canon-local-f01",
    )

    continued = runner.continue_project(
        snapshot.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=child.child_node_id,
    )
    new_revision = continued.status["current_revision_id"]
    assert new_revision != old_revision
    stale_status = world.status(snapshot.project.id, child.child_node_id)
    rows = {row["id"]: row for row in stale_status["canon_entries"]}
    assert rows[adopted.id]["stale"] is True
    assert rows[adopted.id]["current_source_revision_id"] == new_revision
    assert rows[adopted.id]["source"]["revision_id"] == old_revision
    assert rows[adopted.id]["content"] == adopted.content
    assert rows[local.id]["stale"] is False
    # The pinned old artifact and its content remain valid after continuation.
    world.validate(snapshot.project.id)

    new_artifact = plan_artifact(continued.status)
    replacement = world.adopt_world_canon(
        snapshot.project.id, child.child_node_id,
        source_artifact_path=new_artifact["path"], json_pointer="/facts/0",
        scope=CanonScope("global"), subject="F-01", valid_span_id="span-empire",
        supersedes_id=adopted.id, entry_id="canon-global-f01-v2",
    )
    rows = {row["id"]: row for row in world.status(snapshot.project.id)["canon_entries"]}
    assert rows[adopted.id]["current"] is False
    assert rows[replacement.id]["current"] is True
    assert rows[replacement.id]["stale"] is False
    assert replacement.source.revision_id == new_revision

    bundle_dir = tmp_path / "external" / "bundle"
    exported = ReplayBundle(store).export(snapshot.project.id, bundle_dir)
    assert exported["ok"]
    manifest = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    assert any("/world/canon_entries/" in row["path"] for row in manifest["files"])
    assert any("/world/bindings/binding-author-old.json" in row["path"] for row in manifest["files"])
    assert ReplayBundle.verify(bundle_dir)["ok"]
    restored_root = tmp_path / "restored"
    ReplayBundle.restore(bundle_dir, restored_root)
    restored = WorldStore(ProjectStore(restored_root)).status(
        snapshot.project.id, child.child_node_id,
    )
    assert restored == world.status(snapshot.project.id, child.child_node_id)


def test_world_cli_add_bind_and_status(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec(), project_id="prj-world-cli")
    timeframe = tmp_path / "timeframe.json"
    timeframe.write_text(json.dumps({
        "id": "tf-cli", "name": "CLI暦", "calendar": "solar", "epoch": "開始",
    }), encoding="utf-8")
    span = tmp_path / "span.json"
    span.write_text(json.dumps({
        "id": "span-cli", "timeframe_id": "tf-cli", "precision": "unknown",
    }), encoding="utf-8")

    def command(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(tmp_path), "world", *args],
            check=True, capture_output=True, text=True,
        )

    added = json.loads(command(
        "add", snapshot.project.id, "timeframe", "--file", str(timeframe), "--json",
    ).stdout)
    assert added["record"]["record_type"] == "time_frame"
    command("add", snapshot.project.id, "time-span", "--file", str(span))
    bound = json.loads(command(
        "bind", snapshot.project.id, "--time-span", "span-cli",
        "--binding-id", "binding-cli", "--json",
    ).stdout)
    assert bound["record"]["revision_id"] == snapshot.revision.id
    status = json.loads(command("status", snapshot.project.id, "--json").stdout)
    assert status["selected_binding"]["id"] == "binding-cli"
    assert status["counts"] == {
        "timeframes": 1, "time_spans": 1, "time_conversions": 0,
        "regions": 0, "spatial_relations": 0, "cultures": 0,
        "culture_states": 0, "culture_state_relations": 0,
        "canon_entries": 0, "bindings": 1,
    }
