from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    CanonScope,
    ProjectRunner,
    ProjectStore,
    ReplayBundle,
    WorkSpec,
    WorldCompiler,
    WorldStore,
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
    for doc in ("brief", "world", "history", "character", "relation", "plot", "scene", "voice"):
        responses[f"design:{doc}:repair"] = responses[f"design:{doc}"]
    return responses


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def make_world(store: ProjectStore, project_id: str = "prj-compile"):
    snapshot = store.create_project(spec("世界"), project_id=project_id)
    world = WorldStore(store)
    rows = {
        "timeframe": [
            {"id": "tf-a", "name": "A暦", "calendar": "solar", "epoch": "A"},
            {"id": "tf-b", "name": "B暦", "calendar": "lunar", "epoch": "B"},
        ],
        "time-span": [
            {"id": "span-a1", "timeframe_id": "tf-a", "precision": "exact", "start": 1, "end": 1, "label": "A元年"},
            {"id": "span-a2", "timeframe_id": "tf-a", "precision": "range", "start": 2, "end": 3, "before_span_ids": ["span-a1"]},
            {"id": "span-a-unknown", "timeframe_id": "tf-a", "precision": "unknown", "label": "年代不明"},
            {"id": "span-b1", "timeframe_id": "tf-b", "precision": "exact", "start": 1, "end": 1, "label": "B元年"},
        ],
        "region": [
            {"id": "region-coast", "name": "沿岸"},
            {"id": "region-harbor", "name": "港", "parent_region_id": "region-coast"},
            {"id": "region-remote", "name": "遠隔地", "description": "REMOTE-REGION-SECRET"},
        ],
        "spatial-relation": [{
            "id": "spatial-road", "source_region_id": "region-harbor",
            "target_region_id": "region-coast", "kind": "road", "valid_span_id": "span-a1",
        }],
        "culture": [
            {"id": "culture-tide", "name": "潮の文化"},
            {"id": "culture-mainland", "name": "内陸の文化"},
        ],
        "culture-state": [
            {
                "id": "state-tide-early", "culture_id": "culture-tide",
                "valid_span_id": "span-a1", "region_ids": ["region-harbor"],
                "attributes": {"marker": "TIDE-EARLY"},
            },
            {
                "id": "state-tide-late", "culture_id": "culture-tide",
                "valid_span_id": "span-a2", "region_ids": ["region-harbor"],
                "previous_state_id": "state-tide-early", "attributes": {"marker": "TIDE-LATE"},
            },
            {
                "id": "state-mainland", "culture_id": "culture-mainland",
                "valid_span_id": "span-a1", "region_ids": ["region-remote"],
                "attributes": {"marker": "MAINLAND-SECRET"},
            },
        ],
        "culture-relation": [
            {
                "id": "rel-inherit", "kind": "inheritance",
                "source_state_id": "state-tide-early", "target_state_id": "state-tide-late",
            },
            {
                "id": "rel-contact", "kind": "contact",
                "source_state_id": "state-tide-early", "target_state_id": "state-mainland",
            },
        ],
    }
    for kind, records in rows.items():
        for record in records:
            world.add_record(project_id, kind, record)
    for entry_id, scope, span_id, marker in [
        ("canon-global", CanonScope("global"), None, "GLOBAL"),
        ("canon-global-a1", CanonScope("global"), "span-a1", "GLOBAL-A1"),
        ("canon-global-b1", CanonScope("global"), "span-b1", "GLOBAL-B1"),
        ("canon-frame-a", CanonScope("timeframe", "tf-a"), "span-a1", "FRAME-A"),
        ("canon-frame-b", CanonScope("timeframe", "tf-b"), "span-b1", "FRAME-B"),
        ("canon-harbor", CanonScope("region", "region-harbor"), "span-a2", "HARBOR"),
        ("canon-remote", CanonScope("region", "region-remote"), "span-a1", "REMOTE-CANON"),
        ("canon-culture", CanonScope("culture", "culture-tide"), "span-a2", "CULTURE"),
    ]:
        world.author_world_canon(
            project_id, scope=scope, subject=entry_id, content={"marker": marker},
            valid_span_id=span_id, entry_id=entry_id,
        )
    return snapshot


def test_three_world_views_are_deterministic_and_use_selected_sources(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = make_world(store)
    world = WorldStore(store)
    compiler = WorldCompiler(store)
    for payload in [
        {"id": "profile-chronicle", "kind": "chronicle", "title": "A暦の年代記", "timeframe_id": "tf-a"},
        {"id": "profile-gazetteer", "kind": "gazetteer", "title": "沿岸の地誌", "region_id": "region-coast"},
        {"id": "profile-culture", "kind": "culture", "title": "潮の文化圏", "culture_id": "culture-tide"},
    ]:
        compiler.add_profile(snapshot.project.id, payload)
    assert [item.id for item in compiler.list_profiles(snapshot.project.id)] == [
        "profile-chronicle", "profile-culture", "profile-gazetteer",
    ]

    chronicle = compiler.compile(snapshot.project.id, "profile-chronicle")
    chronicle_bytes = chronicle.path.read_bytes()
    manifest_bytes = chronicle.manifest_path.read_bytes()
    assert "A元年" in chronicle.text and "年代不明" in chronicle.text
    assert "FRAME-A" in chronicle.text and "GLOBAL-A1" in chronicle.text
    assert "B元年" not in chronicle.text and "FRAME-B" not in chronicle.text
    assert "GLOBAL-B1" not in chronicle.text and "HARBOR" not in chronicle.text
    assert chronicle.text.index("A元年") < chronicle.text.index("span-a2")

    # A different timeframe and its period-specific canon do not perturb A's view.
    world.add_record(snapshot.project.id, "time-span", {
        "id": "span-b2", "timeframe_id": "tf-b", "precision": "exact", "start": 2, "end": 2,
    })
    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="b2",
        content={"marker": "GLOBAL-B2"}, valid_span_id="span-b2", entry_id="canon-global-b2",
    )
    unchanged = compiler.compile(snapshot.project.id, "profile-chronicle")
    assert unchanged.content_version == chronicle.content_version
    assert unchanged.path == chronicle.path
    assert unchanged.path.read_bytes() == chronicle_bytes
    assert unchanged.manifest_path.read_bytes() == manifest_bytes

    gazetteer = compiler.compile(snapshot.project.id, "profile-gazetteer")
    assert gazetteer.path.read_bytes() == compiler.compile(
        snapshot.project.id, "profile-gazetteer",
    ).path.read_bytes()
    assert "region-harbor" in gazetteer.text and "HARBOR" in gazetteer.text
    assert "REMOTE-REGION-SECRET" not in gazetteer.text
    assert "REMOTE-CANON" not in gazetteer.text

    culture = compiler.compile(snapshot.project.id, "profile-culture")
    assert culture.path.read_bytes() == compiler.compile(
        snapshot.project.id, "profile-culture",
    ).path.read_bytes()
    assert "TIDE-EARLY" in culture.text and "TIDE-LATE" in culture.text
    assert "rel-inherit" in culture.text and "rel-contact" in culture.text
    assert "CULTURE" in culture.text and "MAINLAND-SECRET" not in culture.text

    # A relevant new current entry creates a new version without replacing the old view.
    world.author_world_canon(
        snapshot.project.id, scope=CanonScope("global"), subject="new-global",
        content={"marker": "NEW-GLOBAL"}, entry_id="canon-new-global",
    )
    revised = compiler.compile(snapshot.project.id, "profile-chronicle")
    assert revised.content_version != chronicle.content_version
    assert revised.path != chronicle.path and "NEW-GLOBAL" in revised.text
    assert chronicle.path.read_bytes() == chronicle_bytes
    manifest = json.loads(revised.manifest_path.read_text(encoding="utf-8"))
    assert manifest["content_version"] == revised.content_version
    assert manifest["text_sha256"] == hashlib.sha256(revised.text.encode("utf-8")).hexdigest()
    assert manifest["profile"]["content_version"]
    assert {row["id"] for row in manifest["source_references"]} >= {
        "tf-a", "span-a1", "span-a2", "canon-new-global",
    }


def test_collection_view_preserves_pinned_works_and_survives_bundle_restore(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = store.create_project(spec("親"), project_id="prj-collection")
    store.create_child(
        snapshot.project.id, spec("子"), parent_node_id=snapshot.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    runner = ProjectRunner(store)
    runner.run(snapshot.project.id, ScriptedProvider(project_responses()))
    runner.run(
        snapshot.project.id, ScriptedProvider(project_responses()), node_id="node-child",
    )
    compiler = WorldCompiler(store)
    profile = compiler.add_profile(snapshot.project.id, {
        "id": "profile-collection", "kind": "collection", "title": "世界作品集",
    })
    assert profile.node_id == snapshot.root_node.id
    initial = compiler.compile(snapshot.project.id, "profile-collection")
    initial_bytes = initial.path.read_bytes()
    initial_manifest = initial.manifest_path.read_bytes()
    assert "親" in initial.text and "子" in initial.text and "asc-embedded" in initial.text

    runner.continue_project(
        snapshot.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id="node-child",
    )
    # The parent's link still pins the old child, so the collection is unchanged.
    pinned = compiler.compile(snapshot.project.id, "profile-collection")
    assert pinned.content_version == initial.content_version
    assert pinned.path.read_bytes() == initial_bytes

    bundle_dir = tmp_path / "external" / "bundle"
    ReplayBundle(store).export(snapshot.project.id, bundle_dir)
    bundle_manifest = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    assert any("/compilations/profiles/" in row["path"] for row in bundle_manifest["files"])
    assert any("/artifacts/world/collection-" in row["path"] for row in bundle_manifest["files"])
    assert ReplayBundle.verify(bundle_dir)["ok"]
    restored_root = tmp_path / "restored"
    ReplayBundle.restore(bundle_dir, restored_root)
    restored = WorldCompiler(ProjectStore(restored_root)).compile(
        snapshot.project.id, "profile-collection",
    )
    assert restored.content_version == initial.content_version
    assert restored.text == initial.text
    assert restored.path.read_bytes() == initial_bytes
    assert restored.manifest_path.read_bytes() == initial_manifest


def test_world_compilation_cli(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec("CLI"), project_id="prj-compile-cli")
    world = WorldStore(store)
    world.add_record(snapshot.project.id, "timeframe", {
        "id": "tf-cli", "name": "CLI暦", "calendar": "solar", "epoch": "開始",
    })
    world.add_record(snapshot.project.id, "time-span", {
        "id": "span-cli", "timeframe_id": "tf-cli", "precision": "exact", "start": 1, "end": 1,
    })
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({
        "id": "profile-cli", "kind": "chronicle", "title": "CLI年代記",
        "timeframe_id": "tf-cli",
    }), encoding="utf-8")

    def command(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(tmp_path), "world", *args],
            check=True, capture_output=True, text=True,
        )

    added = json.loads(command(
        "add-profile", snapshot.project.id, "--file", str(profile_path), "--json",
    ).stdout)
    assert added["record"]["record_type"] == "compilation_profile"
    profiles = json.loads(command("profiles", snapshot.project.id, "--json").stdout)
    assert [row["id"] for row in profiles["profiles"]] == ["profile-cli"]
    output = tmp_path / "views" / "chronicle.md"
    compiled = json.loads(command(
        "compile", snapshot.project.id, "profile-cli", "--out", str(output), "--json",
    ).stdout)
    assert output.read_text(encoding="utf-8") == compiled["text"]
    assert "CLI年代記" in compiled["text"] and "span-cli" in compiled["text"]
    assert Path(compiled["manifest_path"]).is_file()
    repeated = json.loads(command(
        "compile", snapshot.project.id, "profile-cli", "--json",
    ).stdout)
    assert repeated["content_version"] == compiled["content_version"]
    assert repeated["text"] == compiled["text"]
