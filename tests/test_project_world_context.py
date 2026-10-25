from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    ResponsePendingError,
    ScriptedProvider,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    CanonScope,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    WorkSpec,
    WorldStore,
)
from asc.project.context import (  # noqa: E402
    CONTEXT_PACKET_KIND,
    CONTEXT_PACKET_WORLD_KIND,
    ContextPacket,
    build_context_packet,
)
from asc.project.world import record_version  # noqa: E402

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


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def make_project(store: ProjectStore, project_id: str = "prj-context"):
    snapshot = store.create_project(spec("親"), project_id=project_id)
    early = store.create_child(
        project_id, spec("早い子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-early", link_id="link-early",
    )
    late = store.create_child(
        project_id, spec("遅い子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-late", link_id="link-late",
    )
    unbound = store.create_child(
        project_id, spec("bindingなし"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-unbound", link_id="link-unbound",
    )
    return snapshot, early, late, unbound


def populate_world(world: WorldStore, project_id: str) -> None:
    rows = {
        "timeframe": [
            {"id": "tf-empire", "name": "帝国暦", "calendar": "solar", "epoch": "建国"},
            {"id": "tf-tide", "name": "潮位暦", "calendar": "lunar", "epoch": "大潮"},
        ],
        "time-span": [
            {"id": "span-early", "timeframe_id": "tf-empire", "precision": "exact", "start": 100, "end": 100},
            {"id": "span-late", "timeframe_id": "tf-empire", "precision": "exact", "start": 900, "end": 900},
            {"id": "span-tide", "timeframe_id": "tf-tide", "precision": "exact", "start": 12, "end": 12},
            {"id": "span-remote", "timeframe_id": "tf-tide", "precision": "exact", "start": 13, "end": 13},
        ],
        "time-conversion": [{
            "id": "conv-empire-tide", "source_timeframe_id": "tf-empire",
            "target_timeframe_id": "tf-tide", "scale": 1, "offset": -88,
        }],
        "region": [
            {"id": "region-coast", "name": "沿岸"},
            {"id": "region-harbor", "name": "港", "parent_region_id": "region-coast"},
            {"id": "region-remote", "name": "遠隔地"},
        ],
        "spatial-relation": [{
            "id": "spatial-harbor-coast", "source_region_id": "region-harbor",
            "target_region_id": "region-coast", "kind": "road",
        }],
        "culture": [
            {"id": "culture-tide", "name": "潮の文化"},
            {"id": "culture-mainland", "name": "内陸の文化"},
        ],
        "culture-state": [
            {
                "id": "state-tide-early", "culture_id": "culture-tide",
                "valid_span_id": "span-early", "region_ids": ["region-harbor"],
                "attributes": {"marker": "EARLY-CULTURE"},
            },
            {
                "id": "state-tide-late", "culture_id": "culture-tide",
                "valid_span_id": "span-late", "previous_state_id": "state-tide-early",
                "attributes": {"marker": "LATE-CULTURE"},
            },
            {
                "id": "state-mainland-early", "culture_id": "culture-mainland",
                "valid_span_id": "span-early", "region_ids": ["region-coast"],
                "attributes": {"marker": "MAINLAND-EARLY"},
            },
        ],
        "culture-relation": [
            {
                "id": "rel-inherit", "kind": "inheritance",
                "source_state_id": "state-tide-early", "target_state_id": "state-tide-late",
            },
            {
                "id": "rel-contact", "kind": "contact",
                "source_state_id": "state-tide-early", "target_state_id": "state-mainland-early",
            },
        ],
    }
    for kind, records in rows.items():
        for record in records:
            world.add_record(project_id, kind, record)


def populate_canon(world: WorldStore, project_id: str, root_node_id: str) -> None:
    entries = [
        ("canon-shared", CanonScope("global"), "shared", "SHARED", None),
        ("canon-era", CanonScope("global"), "era", "EARLY-SECRET", "span-early"),
        ("canon-future", CanonScope("global"), "future", "FUTURE-SECRET", "span-late"),
        ("canon-empire", CanonScope("timeframe", "tf-empire"), "empire", "EMPIRE", "span-early"),
        ("canon-tide", CanonScope("timeframe", "tf-tide"), "tide", "TIDE", "span-tide"),
        ("canon-harbor", CanonScope("region", "region-harbor"), "harbor", "HARBOR", "span-early"),
        ("canon-remote", CanonScope("region", "region-remote"), "remote", "REMOTE-SECRET", "span-early"),
        ("canon-culture", CanonScope("culture", "culture-tide"), "culture", "CULTURE", "span-early"),
        ("canon-work", CanonScope("work", root_node_id), "work", "WORK", "span-early"),
        ("canon-node-early", CanonScope("node", "node-early"), "node", "NODE-EARLY", "span-early"),
        ("canon-node-late", CanonScope("node", "node-late"), "node", "NODE-LATE", "span-late"),
    ]
    for entry_id, scope, subject, marker, span_id in entries:
        world.author_world_canon(
            project_id, scope=scope, subject=subject, content={"marker": marker},
            valid_span_id=span_id, entry_id=entry_id,
        )
    world.author_world_canon(
        project_id, scope=CanonScope("global"), subject="versioned",
        content={"marker": "OLD-SECRET"}, valid_span_id="span-early",
        entry_id="canon-versioned-old",
    )
    world.author_world_canon(
        project_id, scope=CanonScope("global"), subject="versioned",
        content={"marker": "CURRENT-VERSION"}, valid_span_id="span-early",
        supersedes_id="canon-versioned-old", entry_id="canon-versioned-new",
    )


def bind_early(world: WorldStore, project_id: str) -> None:
    world.bind_work(
        project_id, "node-early", time_span_ids=("span-early", "span-tide"),
        region_ids=("region-harbor",),
        culture_state_ids=("state-tide-early", "state-mainland-early"),
        binding_id="binding-early",
    )


def test_context_packets_are_per_child_and_exclude_future_and_unselected_records(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path)
    snapshot, _, _, _ = make_project(store)
    world = WorldStore(store)
    populate_world(world, snapshot.project.id)
    populate_canon(world, snapshot.project.id, snapshot.root_node.id)
    bind_early(world, snapshot.project.id)
    world.bind_work(
        snapshot.project.id, "node-late", time_span_ids=("span-late",),
        region_ids=("region-coast",), culture_state_ids=("state-tide-late",),
        binding_id="binding-late",
    )

    early = build_context_packet(store, snapshot.project.id, "node-early")
    assert early is not None and early.world is not None
    assert early.to_dict()["record_type"] == CONTEXT_PACKET_WORLD_KIND
    world_data = early.world
    assert {row["id"] for row in world_data["timeframes"]} == {"tf-empire", "tf-tide"}
    assert {row["id"] for row in world_data["regions"]} == {"region-harbor"}
    assert {row["id"] for row in world_data["culture_states"]} == {
        "state-tide-early", "state-mainland-early",
    }
    assert [row["id"] for row in world_data["culture_state_relations"]] == ["rel-contact"]
    assert world_data["spatial_relations"] == []  # coast was not explicitly bound
    canon_ids = [row["id"] for row in world_data["canon_entries"]]
    assert set(canon_ids) == {
        "canon-shared", "canon-era", "canon-versioned-new", "canon-empire",
        "canon-tide", "canon-harbor", "canon-culture", "canon-work",
        "canon-node-early",
    }
    assert canon_ids.index("canon-shared") < canon_ids.index("canon-harbor") < canon_ids.index("canon-node-early")
    prompt = early.prompt_suffix()
    assert "EARLY-SECRET" in prompt and "CURRENT-VERSION" in prompt
    for excluded in (
        "FUTURE-SECRET", "REMOTE-SECRET", "OLD-SECRET", "LATE-CULTURE", "NODE-LATE",
    ):
        assert excluded not in prompt

    references = {
        (row["record_type"], row["id"]): row["content_version"]
        for row in world_data["references"]
    }
    for key in (
        "timeframes", "time_spans", "time_conversions", "regions", "cultures",
        "culture_states", "culture_state_relations", "canon_entries",
    ):
        for row in world_data[key]:
            assert references[(row["record_type"], row["id"])] == record_version(row)
    assert ContextPacket.from_dict(early.to_dict()).content_sha256 == early.content_sha256

    # Adding later records does not rebuild an early binding into a future context.
    world.add_record(snapshot.project.id, "time-span", {
        "id": "span-far-future", "timeframe_id": "tf-empire", "precision": "exact",
        "start": 2000, "end": 2000,
    })
    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="far-future",
        content={"marker": "FAR-FUTURE-SECRET"}, valid_span_id="span-far-future",
        entry_id="canon-far-future",
    )
    rebuilt = build_context_packet(store, snapshot.project.id, "node-early")
    assert rebuilt is not None and rebuilt.to_dict() == early.to_dict()

    late = build_context_packet(store, snapshot.project.id, "node-late")
    assert late is not None and late.world is not None
    assert [row["id"] for row in late.world["culture_states"]] == ["state-tide-late"]
    late_canon = {row["id"] for row in late.world["canon_entries"]}
    assert "canon-future" in late_canon and "canon-node-late" in late_canon
    assert "canon-era" not in late_canon and "canon-node-early" not in late_canon
    assert late.content_sha256 != early.content_sha256

    assert build_context_packet(store, snapshot.project.id, snapshot.root_node.id) is None
    legacy = build_context_packet(store, snapshot.project.id, "node-unbound")
    assert legacy is not None and legacy.world is None
    assert legacy.to_dict()["record_type"] == CONTEXT_PACKET_KIND
    assert "world" not in legacy.to_dict()

    world.bind_work(
        snapshot.project.id, snapshot.root_node.id, time_span_ids=("span-early",),
        binding_id="binding-root",
    )
    root_packet = build_context_packet(store, snapshot.project.id, snapshot.root_node.id)
    assert root_packet is not None and root_packet.world is not None
    assert root_packet.ancestors == ()
    assert root_packet.to_dict()["selection"]["scope"] == "world"


def test_generation_records_world_packet_and_unbound_root_keeps_legacy_prompts(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path)
    snapshot, _, _, _ = make_project(store)
    world = WorldStore(store)
    populate_world(world, snapshot.project.id)
    populate_canon(world, snapshot.project.id, snapshot.root_node.id)
    bind_early(world, snapshot.project.id)
    runner = ProjectRunner(store)

    root_provider = ScriptedProvider(project_responses())
    root_result = runner.run(snapshot.project.id, root_provider)
    assert root_provider.calls
    assert all("asc-world-context-v1" not in request.prompt for request in root_provider.calls)
    root_input = json.loads((
        store.project_dir(snapshot.project.id) / "runs" / root_result.stage_runs["plan"]
        / "project-input.json"
    ).read_text(encoding="utf-8"))
    assert "context_packet" not in root_input

    child_provider = ScriptedProvider(project_responses())
    result = runner.run(
        snapshot.project.id, child_provider, node_id="node-early",
    )
    assert child_provider.calls
    assert all("asc-world-context-v1" in request.prompt for request in child_provider.calls)
    assert all("FUTURE-SECRET" not in request.prompt for request in child_provider.calls)
    packets = []
    for stage, run_id in result.stage_runs.items():
        data = json.loads((
            store.project_dir(snapshot.project.id) / "runs" / run_id / "project-input.json"
        ).read_text(encoding="utf-8"))
        packet = data["context_packet"]
        assert packet["record_type"] == CONTEXT_PACKET_WORLD_KIND
        assert packet["world"]["binding"]["id"] == "binding-early"
        assert packet["world"]["binding"]["revision_id"] == result.status["current_revision_id"]
        assert "canon-future" not in json.dumps(packet)
        packets.append(packet)
    assert packets[0] == packets[1] == packets[2]


def test_character_knowledge_filters_ancestor_facts_without_changing_legacy_default(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec("親"), project_id="prj-knowledge")
    for node_id, character_id in (("node-aria", "aria"), ("node-boris", "boris")):
        knowledgeable = WorkSpec(
            title=node_id, premise="人物の既知事実だけを参照する。",
            chapter_count=3, target_chars_per_chapter=1200,
            options={"context_knowledge": {"character_id": character_id}},
        )
        store.create_child(
            snapshot.project.id, knowledgeable, parent_node_id=snapshot.root_node.id,
            child_node_id=node_id, link_id=f"link-{node_id}",
        )
    store.create_child(
        snapshot.project.id, spec("従来"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-default", link_id="link-default",
    )
    ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(project_responses()))

    aria = build_context_packet(store, snapshot.project.id, "node-aria")
    boris = build_context_packet(store, snapshot.project.id, "node-boris")
    default = build_context_packet(store, snapshot.project.id, "node-default")
    assert aria is not None and boris is not None and default is not None
    aria_canon = aria.ancestors[0].canon
    boris_canon = boris.ancestors[0].canon
    assert aria_canon is not None and boris_canon is not None
    assert [row["id"] for row in aria_canon["facts"]] == ["F-01"]
    assert [row["id"] for row in boris_canon["facts"]] == ["F-02"]
    assert aria_canon["knowledge"]["known_fact_ids"] == ["F-01"]
    assert aria_canon["foreshadowing"] == []
    assert aria.to_dict()["selection"]["knowledge"]["character_id"] == "aria"
    assert ContextPacket.from_dict(aria.to_dict()).to_dict() == aria.to_dict()
    assert default.ancestors[0].canon is not None
    assert len(default.ancestors[0].canon["facts"]) == 3
    assert "knowledge" not in default.ancestors[0].canon
    assert "knowledge" not in default.to_dict()["selection"]

    created = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(tmp_path / "cli"), "init",
            "--project-id", "prj-knowledge-cli", "--title", "CLI",
            "--premise", "人物知識を保存する。", "--knowledge-character", "aria", "--json",
        ],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(created.stdout)["spec"]["options"] == {
        "context_knowledge": {"character_id": "aria"},
    }


class PendingAt:
    name = "pending-world-context"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, response_path: Path):
        self.delegate = delegate
        self.purpose = purpose
        self.response_path = response_path

    def generate(self, request):
        if request.purpose == self.purpose:
            raise ResponsePendingError(
                f"NEED RESPONSE key={request.purpose} file={self.response_path}",
                key=request.purpose, response_path=str(self.response_path), request=request,
            )
        return self.delegate.generate(request)


def test_resume_reuses_recorded_world_packet_after_ledger_changes(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot, _, _, _ = make_project(store)
    world = WorldStore(store)
    populate_world(world, snapshot.project.id)
    populate_canon(world, snapshot.project.id, snapshot.root_node.id)
    bind_early(world, snapshot.project.id)
    runner = ProjectRunner(store)
    response_path = tmp_path / "operator" / "design-world.json"
    with pytest.raises(ProjectRunPending):
        runner.run(
            snapshot.project.id,
            PendingAt(ScriptedProvider(project_responses()), "design:world", response_path),
            node_id="node-early",
        )

    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="resume-new",
        content={"marker": "RESUME-NEW-SECRET"}, entry_id="canon-resume-new",
    )
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps({"text": project_responses()["design:world"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    provider = ScriptedProvider(project_responses())
    result = runner.resume(snapshot.project.id, provider, node_id="node-early")
    assert result.status["state"] == "complete"
    assert provider.calls
    assert all("RESUME-NEW-SECRET" not in request.prompt for request in provider.calls)
    for run_id in result.stage_runs.values():
        data = json.loads((
            store.project_dir(snapshot.project.id) / "runs" / run_id / "project-input.json"
        ).read_text(encoding="utf-8"))
        assert "canon-resume-new" not in json.dumps(data["context_packet"])
        assert data["context_packet"]["world"]["binding"]["id"] == "binding-early"


def test_continuation_reuses_world_binding_only_when_explicitly_requested(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot, _, _, _ = make_project(store)
    world = WorldStore(store)
    populate_world(world, snapshot.project.id)
    populate_canon(world, snapshot.project.id, snapshot.root_node.id)
    bind_early(world, snapshot.project.id)
    runner = ProjectRunner(store)
    runner.run(
        snapshot.project.id, ScriptedProvider(project_responses()), node_id="node-early",
    )
    old_revision = store.load_node(snapshot.project.id, "node-early").current_revision_id
    provider = ScriptedProvider(continuation_responses())
    result = runner.continue_project(
        snapshot.project.id, provider, additional_chapters=1, node_id="node-early",
        world_binding_id="binding-early",
    )
    new_revision = result.status["current_revision_id"]
    assert new_revision != old_revision
    status = world.status(snapshot.project.id, "node-early")
    assert status["selected_binding"]["revision_id"] == new_revision
    assert status["selected_binding"]["id"] != "binding-early"
    assert status["selected_binding"]["time_span_ids"] == ["span-early", "span-tide"]
    old = next(row for row in status["bindings"] if row["id"] == "binding-early")
    assert old["revision_id"] == old_revision and old["current"] is False
    assert all("asc-world-context-v1" in request.prompt for request in provider.calls)
    for run_id in result.stage_runs.values():
        data = json.loads((
            store.project_dir(snapshot.project.id) / "runs" / run_id / "project-input.json"
        ).read_text(encoding="utf-8"))
        assert data["context_packet"]["world"]["binding"]["revision_id"] == new_revision
