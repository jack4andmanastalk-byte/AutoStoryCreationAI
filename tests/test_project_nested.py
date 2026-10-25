from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
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
    ProjectComposer,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    ProjectValidationError,
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
    for doc in ("brief", "world", "history", "character", "relation", "plot", "scene", "voice"):
        responses[f"design:{doc}:repair"] = responses[f"design:{doc}"]
    return responses


def spec(title: str, premise: str | None = None) -> WorkSpec:
    return WorkSpec(
        title=title,
        premise=premise or f"{title}の独立した物語。",
        chapter_count=3,
        target_chars_per_chapter=1200,
    )


def family(store: ProjectStore):
    root = store.create_project(spec("親作品"), project_id="prj-nested")
    first = store.create_child(
        root.project.id, spec("子作品一"), order=2, child_node_id="node-child-one",
    )
    second = store.create_child(
        root.project.id, spec("子作品二"), order=1, child_node_id="node-child-two",
    )
    return root, first, second


def run_node(store: ProjectStore, project_id: str, node_id: str, responses=None):
    return ProjectRunner(store).run(
        project_id, ScriptedProvider(responses or project_responses()), node_id=node_id,
    )


class PendingAt:
    name = "pending-nested"
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


def test_two_children_have_independent_runs_and_depth_one_links(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, first, second = family(store)
    initial = store.status(root.project.id)
    assert initial["state"] == "not_started"
    assert initial["runs"] == []
    assert [link["child_node_id"] for link in initial["links"]] == [
        second.child_node_id, first.child_node_id,
    ]

    first_result = run_node(store, root.project.id, first.child_node_id)
    assert first_result.status["node_id"] == first.child_node_id
    assert first_result.status["state"] == "complete"
    assert store.status(root.project.id, second.child_node_id)["state"] == "not_started"
    root_after_child = store.status(root.project.id)
    assert root_after_child["state"] == "not_started"
    assert root_after_child["runs"] == []
    links = {link["id"]: link for link in root_after_child["links"]}
    assert links[first.id]["ready"] is True
    assert links[second.id]["ready"] is False

    run_node(store, root.project.id, root.root_node.id)
    assert store.status(root.project.id)["state"] == "complete"
    assert store.status(root.project.id, second.child_node_id)["state"] == "not_started"
    grandchild = store.create_child(
        root.project.id, spec("孫作品"), parent_node_id=first.child_node_id,
        child_node_id="node-grandchild",
    )
    assert store.node_depth(root.project.id, grandchild.child_node_id) == 2
    child = store.load_node(root.project.id, first.child_node_id)
    with pytest.raises(ProjectValidationError, match="immutable"):
        store.save_node(replace(child, parent_id=child.id))


def test_child_resume_leaves_sibling_and_parent_link_untouched(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, first, second = family(store)
    run_node(store, root.project.id, first.child_node_id)
    before_first = store.status(root.project.id, first.child_node_id)
    before_link = store.load_link(root.project.id, root.root_node.id, first.id)
    pending_path = tmp_path / "operator" / "responses" / "design-world.json"
    pending_provider = PendingAt(
        ScriptedProvider(project_responses()), "design:world", pending_path,
    )
    with pytest.raises(ProjectRunPending) as caught:
        ProjectRunner(store).run(
            root.project.id, pending_provider, node_id=second.child_node_id,
        )
    waiting = caught.value.status
    assert waiting["node_id"] == second.child_node_id
    assert waiting["state"] == "waiting_response"
    assert store.status(root.project.id)["pending"][0]["node_id"] == second.child_node_id
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(
        json.dumps({"text": project_responses()["design:world"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = ProjectRunner(store).resume(
        root.project.id, ScriptedProvider(project_responses()), node_id=second.child_node_id,
    )
    assert result.status["state"] == "complete"
    after_first = store.status(root.project.id, first.child_node_id)
    assert after_first["current_revision_id"] == before_first["current_revision_id"]
    assert after_first["runs"] == before_first["runs"]
    assert store.load_link(root.project.id, root.root_node.id, first.id) == before_link
    assert store.status(root.project.id, second.child_node_id)["state"] == "complete"


def test_composition_is_pinned_until_explicit_adopt_and_bundle_restores(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    root, first, second = family(store)
    for node_id in (root.root_node.id, first.child_node_id, second.child_node_id):
        run_node(store, root.project.id, node_id)
    composer = ProjectComposer(store)
    single = composer.render(root.project.id, first.child_node_id)
    assert single.path is None
    assert "# 子作品一" in single.text
    assert "# 親作品" not in single.text

    before = composer.compose(root.project.id)
    assert before.path is not None
    assert before.text.index("## 子作品二") < before.text.index("## 子作品一")
    old_output = before.path.read_bytes()
    old_manifest = before.path.with_suffix(".json").read_bytes()
    old_second = store.status(root.project.id, second.child_node_id)
    first_link_before = store.load_link(root.project.id, root.root_node.id, first.id)
    assert first_link_before.artifacts
    assert "追加の章の本文です" not in json.dumps(
        first_link_before.to_dict(), ensure_ascii=False,
    )
    # Re-syncing the same completed revision changes bookkeeping time only;
    # it must not create a new compilation identity.
    store.sync_child_links(
        root.project.id, first.child_node_id, first_link_before.child_revision_id,
    )
    assert composer.compose(root.project.id).text == before.text

    continued = ProjectRunner(store).continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=first.child_node_id,
    )
    assert continued.status["state"] == "complete"
    assert continued.status["current_revision_id"] != first_link_before.child_revision_id
    assert store.status(root.project.id, second.child_node_id)["runs"] == old_second["runs"]
    root_status = store.status(root.project.id)
    link_states = {link["id"]: link for link in root_status["links"]}
    assert link_states[first.id]["stale"] is True
    assert link_states[second.id]["stale"] is False

    still_pinned = composer.compose(root.project.id)
    assert still_pinned.text == before.text
    assert still_pinned.path == before.path
    assert still_pinned.path.read_bytes() == old_output
    assert still_pinned.path.with_suffix(".json").read_bytes() == old_manifest
    assert "追加の章の本文です" not in still_pinned.text

    adopted_link = store.adopt_child(root.project.id, first.id)
    assert adopted_link.child_revision_id == continued.status["current_revision_id"]
    adopted = composer.compose(root.project.id)
    assert adopted.text != before.text
    assert adopted.path != before.path
    assert "追加の章の本文です" in adopted.text
    assert before.path.read_bytes() == old_output
    assert before.path.with_suffix(".json").read_bytes() == old_manifest
    assert composer.compose(root.project.id).text == adopted.text

    bundle_dir = tmp_path / "external" / "nested-bundle"
    ReplayBundle(store).export(root.project.id, bundle_dir)
    restored_root = tmp_path / "restored"
    restored = ReplayBundle.restore(bundle_dir, restored_root)
    assert restored["status"]["state"] == "complete"
    restored_composer = ProjectComposer(ProjectStore(restored_root))
    assert restored_composer.compose(root.project.id).text == adopted.text


def test_nested_cli_add_run_pending_status_and_compose(tmp_path: Path):
    root = tmp_path / "projects"
    base_script = tmp_path / "base.json"
    continuation_script = tmp_path / "continuation.json"
    base_script.write_text(
        json.dumps({"responses": project_responses()}, ensure_ascii=False), encoding="utf-8",
    )
    continuation_script.write_text(
        json.dumps({"responses": continuation_responses()}, ensure_ascii=False),
        encoding="utf-8",
    )
    command = [sys.executable, str(SCRIPT), "--root", str(root)]

    def call(*args: str) -> dict:
        result = subprocess.run(
            command + list(args), check=False, capture_output=True, text=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        return json.loads(result.stdout)

    call(
        "init", "--project-id", "prj-nested-cli", "--title", "CLI親",
        "--premise", "CLIの親作品。", "--chapters", "3", "--target-chars", "1200", "--json",
    )
    first = call(
        "add-child", "prj-nested-cli", "--node-id", "node-cli-one",
        "--title", "CLI子一", "--premise", "一つ目の子。", "--order", "1",
        "--chapters", "3", "--target-chars", "1200", "--json",
    )["link"]
    second = call(
        "add-child", "prj-nested-cli", "--node-id", "node-cli-two",
        "--title", "CLI子二", "--premise", "二つ目の子。", "--order", "2",
        "--chapters", "3", "--target-chars", "1200", "--json",
    )["link"]
    root_status = call("status", "prj-nested-cli", "--json")
    root_node = root_status["root_node_id"]
    for node_id in (root_node, first["child_node_id"], second["child_node_id"]):
        call(
            "run", "prj-nested-cli", "--node", node_id, "--provider", "scripted",
            "--script", str(base_script), "--json",
        )
    composed = call("compose", "prj-nested-cli", "--json")
    assert "CLI子一" in composed["text"] and "CLI子二" in composed["text"]
    continued = call(
        "continue", "prj-nested-cli", "--node", first["child_node_id"],
        "--add-chapters", "1", "--provider", "scripted",
        "--script", str(continuation_script), "--json",
    )
    assert continued["state"] == "complete"
    stale = call("status", "prj-nested-cli", "--json")
    stale_link = next(link for link in stale["links"] if link["id"] == first["id"])
    assert stale_link["stale"] is True
    assert call("compose", "prj-nested-cli", "--json")["text"] == composed["text"]
    call("adopt-child", "prj-nested-cli", first["id"], "--json")
    adopted = call("compose", "prj-nested-cli", "--json")
    assert adopted["text"] != composed["text"]
    rendered = call(
        "render", "prj-nested-cli", "--node", second["child_node_id"], "--json",
    )
    assert "CLI子二" in rendered["text"]
    assert "CLI子一" not in rendered["text"]
