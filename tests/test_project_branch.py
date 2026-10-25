"""What-if branches: a new node that starts from another revision's content."""
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
    ProjectRunner,
    ProjectRunError,
    ProjectStore,
    ReplayBundle,
    WorkSpec,
    WorldStore,
    build_context_view,
    inspect_project,
)
from asc.project.context import CONTEXT_PACKET_WORLD_KIND  # noqa: E402

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


def branch_chapter() -> str:
    return (
        "{{time: day=5}}{{location: 港}}\n"
        + "分岐した章の本文です。灯台の記録を別の港から読む。" * 30
    )


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の短い物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def add_world(store: ProjectStore, project_id: str, node_id: str) -> None:
    world = WorldStore(store)
    world.add_record(project_id, "timeframe", {
        "id": "tf-tide", "name": "潮汐暦", "calendar": "lunar", "epoch": "開港",
    })
    world.add_record(project_id, "time-span", {
        "id": "span-tide", "timeframe_id": "tf-tide", "precision": "exact",
        "start": 120, "end": 120,
    })
    world.add_record(project_id, "region", {"id": "region-harbor", "name": "港"})
    world.add_record(project_id, "culture", {"id": "culture-tide", "name": "潮の文化"})
    world.add_record(project_id, "culture-state", {
        "id": "state-tide", "culture_id": "culture-tide",
        "valid_span_id": "span-tide", "region_ids": ["region-harbor"],
        "attributes": {"marker": "TIDE"},
    })
    world.author_world_canon(
        project_id, scope=CanonScope("global"), subject="共有",
        content={"marker": "SHARED"}, entry_id="canon-shared",
    )
    world.bind_work(
        project_id, node_id, time_span_ids=("span-tide",),
        region_ids=("region-harbor",), culture_state_ids=("state-tide",),
        binding_id="binding-tide",
    )


def text_hashes(store: ProjectStore, project_id: str, node_id: str) -> dict[str, str]:
    status = store.status(project_id, node_id, include_descendants=False)
    return {
        row["artifact_id"]: row["sha256"]
        for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    }


def test_branch_copies_the_source_and_regenerates_only_the_selected_chapter(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("親"), project_id="prj-branch")
    runner = ProjectRunner(store)
    runner.run("prj-branch", ScriptedProvider(responses()))
    source_hashes = text_hashes(store, "prj-branch", created.root_node.id)
    source_revision = created.revision.id

    scripted = responses()
    scripted["draft:ch02"] = branch_chapter()
    provider = ScriptedProvider(scripted)
    result = runner.branch(
        "prj-branch", provider,
        child_node_id="node-whatif", link_id="link-whatif",
        chapters=("ch02",), title="もう一つの潮",
    )
    assert [call.purpose for call in provider.calls] == ["draft:ch02"]

    status = result.status
    assert status["node_id"] == "node-whatif"
    assert status["state"] == "complete"
    derived = status["derived"]
    assert derived["kind"] == "branch"
    assert derived["source_revision_id"] == source_revision
    assert derived["chapters"] == ["ch02"]
    assert status["title"] == "もう一つの潮"
    assert status["parent_node_id"] == created.root_node.id

    new_hashes = text_hashes(store, "prj-branch", "node-whatif")
    assert new_hashes["draft-text-ch01.md"] == source_hashes["draft-text-ch01.md"]
    assert new_hashes["draft-text-ch03.md"] == source_hashes["draft-text-ch03.md"]
    assert new_hashes["draft-text-ch02.md"] != source_hashes["draft-text-ch02.md"]

    # The source node keeps its own revision, runs, and bytes.
    source_now = store.status("prj-branch", created.root_node.id,
                              include_descendants=False)
    assert source_now["current_revision_id"] == source_revision
    assert text_hashes(store, "prj-branch", created.root_node.id) == source_hashes
    assert source_now["checkpoints"]["draft"]["run_id"] != status["checkpoints"]["draft"]["run_id"]

    # The new node has its own link, pinned to its own completed revision.
    parent = store.status("prj-branch")
    link = next(row for row in parent["children"] if row["node_id"] == "node-whatif")
    assert link["stale"] is False
    assert link["current_revision_id"] == status["current_revision_id"]
    assert link["link_id"] == "link-whatif"
    assert inspect_project(store, "prj-branch").ok is True


def test_branch_does_not_inherit_a_world_binding_unless_named(tmp_path: Path):
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("世界"), project_id="prj-world-branch")
    add_world(store, "prj-world-branch", created.root_node.id)
    runner = ProjectRunner(store)
    runner.run("prj-world-branch", ScriptedProvider(responses()))
    source_binding = next(
        binding for binding in WorldStore(store).validate("prj-world-branch").bindings
    )
    assert source_binding.id == "binding-tide"

    plain = runner.branch(
        "prj-world-branch", ScriptedProvider(responses()),
        child_node_id="node-plain", link_id="link-plain",
    )
    plain_view = build_context_view(
        store, "prj-world-branch", "node-plain",
    )
    assert plain_view.packet is not None
    assert plain_view.summary["world"] is None
    assert plain_view.packet["record_type"] != CONTEXT_PACKET_WORLD_KIND
    assert [
        binding for binding in WorldStore(store).validate("prj-world-branch").bindings
        if binding.node_id == "node-plain"
    ] == []

    explicit = runner.branch(
        "prj-world-branch", ScriptedProvider(responses()),
        child_node_id="node-copied", link_id="link-copied",
        world_binding_id="binding-tide",
    )
    copied_view = build_context_view(store, "prj-world-branch", "node-copied")
    assert copied_view.summary["kind"] == CONTEXT_PACKET_WORLD_KIND
    assert copied_view.summary["world"]["binding_id"] != "binding-tide"
    assert copied_view.summary["world"]["binding_revision_id"] == (
        explicit.status["current_revision_id"]
    )
    copied_binding = next(
        binding for binding in WorldStore(store).validate("prj-world-branch").bindings
        if binding.node_id == "node-copied"
    )
    assert copied_binding.time_span_ids == source_binding.time_span_ids
    assert copied_binding.region_ids == source_binding.region_ids
    assert copied_binding.culture_state_ids == source_binding.culture_state_ids

    with pytest.raises(ProjectRunError, match="source revision"):
        runner.branch(
            "prj-world-branch", ScriptedProvider(responses()),
            child_node_id="node-bad", link_id="link-bad",
            world_binding_id="binding-nope",
        )


def test_branch_of_an_older_revision_uses_that_revision(tmp_path: Path):
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("履歴"), project_id="prj-history")
    runner = ProjectRunner(store)
    runner.run("prj-history", ScriptedProvider(responses()))
    first = store.status("prj-history", include_descendants=False)
    first_revision = first["current_revision_id"]
    first_hashes = text_hashes(store, "prj-history", created.root_node.id)

    runner.revise("prj-history", ScriptedProvider(responses()), chapters=("ch01",))
    assert store.status("prj-history")["current_revision_id"] != first_revision

    result = runner.branch(
        "prj-history", ScriptedProvider(responses()),
        child_node_id="node-old", link_id="link-old",
        source_revision_id=first_revision,
    )
    assert result.status["derived"]["source_revision_id"] == first_revision
    assert text_hashes(store, "prj-history", "node-old") == first_hashes


def test_revised_and_branched_revisions_survive_bundle_restore(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    created = store.create_project(spec("束"), project_id="prj-bundle")
    add_world(store, "prj-bundle", created.root_node.id)
    runner = ProjectRunner(store)
    runner.run("prj-bundle", ScriptedProvider(responses()))
    scripted = responses()
    scripted["draft:ch03"] = branch_chapter()
    runner.revise("prj-bundle", ScriptedProvider(scripted), chapters=("ch03",))
    runner.branch(
        "prj-bundle", ScriptedProvider(responses()),
        child_node_id="node-side", link_id="link-side",
    )
    before = store.status("prj-bundle")
    revised_revision = before["current_revision_id"]
    revised_hashes = text_hashes(store, "prj-bundle", created.root_node.id)

    bundle_dir = tmp_path / "external" / "prj-bundle.bundle"
    ReplayBundle(store).export("prj-bundle", bundle_dir)
    restored_root = tmp_path / "restored"
    ReplayBundle.restore(bundle_dir, restored_root)

    restored = ProjectStore(restored_root)
    report = inspect_project(restored, "prj-bundle")
    assert report.ok is True
    assert report.findings == ()
    after = restored.status("prj-bundle")
    assert after["current_revision_id"] == revised_revision
    assert after["derived"]["chapters"] == ["ch03"]
    assert text_hashes(restored, "prj-bundle", created.root_node.id) == revised_hashes
    side = restored.status("prj-bundle", "node-side", include_descendants=False)
    assert side["derived"]["kind"] == "branch"
    assert side["state"] == "complete"
    # The revise did not inherit the source binding, so the root has no packet.
    view = build_context_view(restored, "prj-bundle", created.root_node.id)
    assert view.packet is None
    assert view.summary["kind"] is None
    # The world records themselves survive the bundle unchanged.
    records = WorldStore(restored).validate("prj-bundle")
    assert [entry.id for entry in records.canon_entries] == ["canon-shared"]
    assert [binding.id for binding in records.bindings] == ["binding-tide"]


def test_revise_and_branch_cli(tmp_path: Path):
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("CLI"), project_id="prj-cli")
    ProjectRunner(store).run("prj-cli", ScriptedProvider(responses()))
    source_revision = store.status("prj-cli")["current_revision_id"]
    script_path = tmp_path / "script.json"
    scripted = responses()
    scripted["draft:ch02"] = branch_chapter()
    script_path.write_text(
        json.dumps({"responses": scripted}, ensure_ascii=False), encoding="utf-8",
    )

    revised = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "revise", "prj-cli",
         "--chapter", "ch02", "--provider", "scripted", "--script", str(script_path),
         "--json"],
        capture_output=True, text=True, check=False,
    )
    assert revised.returncode == 0, revised.stderr
    payload = json.loads(revised.stdout)
    assert payload["derived"]["chapters"] == ["ch02"]
    assert payload["derived"]["source_revision_id"] == source_revision
    assert payload["state"] == "complete"

    branch = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "branch", "prj-cli",
         "--node-id", "node-cli-side", "--link-id", "link-cli-side",
         "--from-revision", source_revision, "--provider", "scripted",
         "--script", str(script_path), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert branch.returncode == 0, branch.stderr
    payload = json.loads(branch.stdout)
    assert payload["node_id"] == "node-cli-side"
    assert payload["derived"]["kind"] == "branch"
    parent = store.status("prj-cli")
    assert any(row["node_id"] == "node-cli-side" for row in parent["children"])

    bad = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "revise", "prj-cli",
         "--chapter", "ch99", "--provider", "scripted", "--script", str(script_path)],
        capture_output=True, text=True, check=False,
    )
    assert bad.returncode == 2
    assert "unknown chapter" in bad.stderr

    # Regenerating something needs a provider; a pure copy does not.
    missing_provider = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "revise", "prj-cli",
         "--chapter", "ch01"],
        capture_output=True, text=True, check=False,
    )
    assert missing_provider.returncode == 2
    assert "pass --provider" in missing_provider.stderr
    copied = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "revise", "prj-cli"],
        capture_output=True, text=True, check=False,
    )
    assert copied.returncode == 0, copied.stderr
    payload = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "status", "prj-cli", "--json"],
        capture_output=True, text=True, check=True,
    ).stdout)
    assert payload["derived"]["chapters"] == []
    assert payload["state"] == "complete"


def test_branch_links_are_appendable_and_stay_independent(tmp_path: Path):
    """Two branches of one revision do not share runs or artifacts."""
    store = ProjectStore(tmp_path)
    created = store.create_project(spec("二股"), project_id="prj-two")
    runner = ProjectRunner(store)
    runner.run("prj-two", ScriptedProvider(responses()))
    left = runner.branch(
        "prj-two", ScriptedProvider(responses()),
        child_node_id="node-left", link_id="link-left",
    )
    right = runner.branch(
        "prj-two", ScriptedProvider(responses()),
        child_node_id="node-right", link_id="link-right",
    )
    assert left.status["checkpoints"]["draft"]["run_id"] != (
        right.status["checkpoints"]["draft"]["run_id"]
    )
    assert text_hashes(store, "prj-two", "node-left").keys() == (
        text_hashes(store, "prj-two", "node-right").keys()
    )
    hashes = text_hashes(store, "prj-two", "node-left")
    other = text_hashes(store, "prj-two", "node-right")
    assert hashes == other  # identical scripted text, distinct artifacts
    project_dir = store.project_dir("prj-two")
    left_path = project_dir / "runs" / left.status["checkpoints"]["draft"]["run_id"] / "text/ch01.md"
    right_path = project_dir / "runs" / right.status["checkpoints"]["draft"]["run_id"] / "text/ch01.md"
    assert left_path != right_path
    assert hashlib.sha256(left_path.read_bytes()).hexdigest() == hashlib.sha256(
        right_path.read_bytes()
    ).hexdigest()
