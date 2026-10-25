from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import (  # noqa: E402
    ProviderError,
    ResponsePendingError,
    ScriptedProvider,
    load_scripted_responses,
)
from asc.project import (  # noqa: E402
    MAX_NESTING_DEPTH,
    ProjectComposer,
    ProjectDependencyError,
    ProjectRunError,
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


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def three_levels(store: ProjectStore):
    root = store.create_project(spec("親"), project_id="prj-multilevel")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    grandchild = store.create_child(
        root.project.id, spec("孫"), parent_node_id=child.child_node_id,
        child_node_id="node-grandchild", link_id="link-grandchild",
    )
    return root, child, grandchild


class PendingNode:
    name = "pending-multilevel"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, node_id: str, response_path: Path):
        self.delegate = delegate
        self.node_id = node_id
        self.response_path = response_path

    def generate(self, request):
        if (
            request.context.get("task_id") == self.node_id
            and request.purpose == "design:world"
        ):
            raise ResponsePendingError(
                f"NEED RESPONSE key={request.purpose} file={self.response_path}",
                key=request.purpose, response_path=str(self.response_path), request=request,
            )
        return self.delegate.generate(request)


class FailNode:
    name = "fail-multilevel"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, node_id: str):
        self.delegate = delegate
        self.node_id = node_id

    def generate(self, request):
        if request.context.get("task_id") == self.node_id and request.purpose == "plan":
            raise ProviderError("intentional dependency failure")
        return self.delegate.generate(request)


def test_depth_limit_cycle_rejection_and_stable_topological_order(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec("root"), project_id="prj-depth")
    parent_id = root.root_node.id
    for depth in range(1, MAX_NESTING_DEPTH + 1):
        link = store.create_child(
            root.project.id, spec(f"depth-{depth}"), parent_node_id=parent_id,
            child_node_id=f"node-depth-{depth}", link_id=f"link-depth-{depth}",
        )
        parent_id = link.child_node_id
        assert store.node_depth(root.project.id, parent_id) == depth
    with pytest.raises(ProjectValidationError, match="depth exceeds"):
        store.create_child(
            root.project.id, spec("too-deep"), parent_node_id=parent_id,
            child_node_id="node-too-deep",
        )

    runner = ProjectRunner(store)
    assert runner.dependency_order(root.project.id) == [
        root.root_node.id,
        *[f"node-depth-{depth}" for depth in range(1, MAX_NESTING_DEPTH + 1)]
    ]

    # Public mutation keeps parent_id immutable.  Simulate a damaged hand-edited
    # record to verify that readers still reject an actual containment cycle.
    cycle_path = store.node_dir(root.project.id, "node-depth-2") / "current.json"
    damaged = json.loads(cycle_path.read_text(encoding="utf-8"))
    damaged["parent_id"] = "node-depth-3"
    cycle_path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="cycle"):
        store.node_depth(root.project.id, "node-depth-2")
    with pytest.raises(ProjectValidationError, match="cycle"):
        runner.dependency_order(root.project.id)


def test_run_tree_stops_at_pending_and_failed_dependencies(tmp_path: Path):
    store = ProjectStore(tmp_path / "pending")
    root, child, grandchild = three_levels(store)
    runner = ProjectRunner(store)
    response_path = tmp_path / "operator" / "responses" / "design-world.json"
    pending_provider = PendingNode(
        ScriptedProvider(project_responses()), child.child_node_id, response_path,
    )
    with pytest.raises(ProjectRunPending):
        runner.run_tree(root.project.id, pending_provider)
    assert store.status(root.project.id, root.root_node.id)["state"] == "complete"
    assert store.status(root.project.id, child.child_node_id)["state"] == "waiting_response"
    assert store.status(root.project.id, grandchild.child_node_id)["state"] == "not_started"
    assert store.status(root.project.id, grandchild.child_node_id)["runs"] == []

    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps({"text": project_responses()["design:world"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    resumed = runner.resume(
        root.project.id, ScriptedProvider(project_responses()), node_id=child.child_node_id,
    )
    assert resumed.status["state"] == "complete"
    finished = runner.run_tree(root.project.id, ScriptedProvider(project_responses()))
    assert [item.status["node_id"] for item in finished.results] == [grandchild.child_node_id]

    failed_store = ProjectStore(tmp_path / "failed")
    failed_root, failed_child, failed_grandchild = three_levels(failed_store)
    failed_runner = ProjectRunner(failed_store)
    # three_levels uses a fixed project id, so use a separate store but the same
    # stable IDs deliberately; each store is independent.
    with pytest.raises(ProjectRunError):
        failed_runner.run_tree(
            failed_root.project.id,
            FailNode(ScriptedProvider(project_responses()), failed_child.child_node_id),
        )
    assert failed_store.status(failed_root.project.id, failed_child.child_node_id)["state"] == "failed"
    assert failed_store.status(failed_root.project.id, failed_grandchild.child_node_id)["state"] == "not_started"
    with pytest.raises(ProjectDependencyError, match="failed"):
        failed_runner.run_tree(failed_root.project.id, ScriptedProvider(project_responses()))


def test_resume_keeps_the_original_packet_when_an_ancestor_completes(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec("親"), project_id="prj-resume-context")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    runner = ProjectRunner(store)
    response_path = tmp_path / "responses" / "design-world.json"
    with pytest.raises(ProjectRunPending):
        runner.run(
            root.project.id,
            PendingNode(ScriptedProvider(project_responses()), child.child_node_id, response_path),
            node_id=child.child_node_id,
        )
    original = store.status(root.project.id, child.child_node_id)
    original_input = json.loads(
        (store.project_dir(root.project.id) / "runs"
         / original["checkpoints"]["design"]["run_id"] / "project-input.json")
        .read_text(encoding="utf-8")
    )
    assert original_input["context_packet"]["ancestors"][0]["state"] == "not_started"
    runner.run(root.project.id, ScriptedProvider(project_responses()))
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps({"text": project_responses()["design:world"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    resumed = runner.resume(
        root.project.id, ScriptedProvider(project_responses()), node_id=child.child_node_id,
    )
    assert resumed.status["state"] == "complete"
    resumed_input = json.loads(
        (store.project_dir(root.project.id) / "runs" / resumed.stage_runs["design"]
         / "project-input.json").read_text(encoding="utf-8")
    )
    assert resumed_input["context_packet"] == original_input["context_packet"]


def test_recursive_compose_is_pinned_at_every_level_and_bundle_safe(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    root, child, grandchild = three_levels(store)
    runner = ProjectRunner(store)
    provider = ScriptedProvider(project_responses())
    tree = runner.run_tree(root.project.id, provider)
    assert list(tree.order) == [root.root_node.id, child.child_node_id, grandchild.child_node_id]
    composer = ProjectComposer(store)
    before = composer.compose(root.project.id)
    assert before.text.index("# 親") < before.text.index("## 子") < before.text.index("### 孫")
    assert before.path is not None
    old_bytes = before.path.read_bytes()
    old_manifest = before.path.with_suffix(".json").read_bytes()
    assert before.links[0]["children"][0]["id"] == grandchild.id

    # Re-sync changes only bookkeeping time, not recursive composition identity.
    grand_link = store.load_link(root.project.id, child.child_node_id, grandchild.id)
    store.sync_child_links(root.project.id, grandchild.child_node_id, grand_link.child_revision_id)
    assert composer.compose(root.project.id).text == before.text
    assert composer.compose(root.project.id).path == before.path

    continued = runner.continue_project(
        root.project.id, ScriptedProvider(continuation_responses()),
        additional_chapters=1, node_id=grandchild.child_node_id,
    )
    assert continued.status["state"] == "complete"
    assert store.status(root.project.id, child.child_node_id)["links"][0]["stale"] is True
    assert composer.compose(root.project.id).text == before.text
    assert before.path.read_bytes() == old_bytes
    assert before.path.with_suffix(".json").read_bytes() == old_manifest

    store.adopt_child(root.project.id, grandchild.id)
    adopted = composer.compose(root.project.id)
    assert adopted.text != before.text
    assert "追加の章の本文です" in adopted.text
    assert before.path.read_bytes() == old_bytes
    child_composed = composer.compose(root.project.id, child.child_node_id)
    assert "# 子" in child_composed.text and "## 孫" in child_composed.text
    rendered = composer.render(root.project.id, grandchild.child_node_id)
    assert "# 孫" in rendered.text and "# 親" not in rendered.text

    bundle_dir = tmp_path / "bundle"
    ReplayBundle(store).export(root.project.id, bundle_dir)
    restored_root = tmp_path / "restored"
    ReplayBundle.restore(bundle_dir, restored_root)
    restored = ProjectComposer(ProjectStore(restored_root)).compose(root.project.id)
    assert restored.text == adopted.text


def test_context_packet_is_structured_recorded_and_excludes_parent_prose(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root, child, grandchild = three_levels(store)
    provider = ScriptedProvider(project_responses())
    result = ProjectRunner(store).run_tree(root.project.id, provider)
    by_node = {item.status["node_id"]: item for item in result.results}
    project_dir = store.project_dir(root.project.id)
    child_input = json.loads(
        (project_dir / "runs" / by_node[child.child_node_id].stage_runs["plan"]
         / "project-input.json").read_text(encoding="utf-8")
    )
    grand_input = json.loads(
        (project_dir / "runs" / by_node[grandchild.child_node_id].stage_runs["plan"]
         / "project-input.json").read_text(encoding="utf-8")
    )
    child_packet = child_input["context_packet"]
    grand_packet = grand_input["context_packet"]
    assert child_packet["selection"]["prose"] == "excluded"
    assert len(child_packet["ancestors"]) == 1
    assert len(grand_packet["ancestors"]) == 2
    assert grand_packet["ancestors"][0]["node_id"] == root.root_node.id
    assert grand_packet["ancestors"][1]["node_id"] == child.child_node_id
    assert all(
        "text" not in chapter
        for ancestor in grand_packet["ancestors"] for chapter in ancestor["chapters"]
    )
    parent_text = (project_dir / "runs" / by_node[root.root_node.id].stage_runs["draft"]
                   / "text" / "ch01.md").read_text(encoding="utf-8")
    assert parent_text not in json.dumps(grand_packet, ensure_ascii=False)
    child_plan_request = next(
        request for request in provider.calls
        if request.purpose == "plan" and request.context.get("task_id") == child.child_node_id
    )
    assert "asc-context-packet-pre1" in child_plan_request.prompt
    assert parent_text not in child_plan_request.prompt
    child_design_request = next(
        request for request in provider.calls
        if request.purpose == "design:brief"
        and request.context.get("task_id") == child.child_node_id
    )
    assert "asc-context-packet-pre1" in child_design_request.prompt
    root_plan_request = next(
        request for request in provider.calls
        if request.purpose == "plan" and request.context.get("task_id") == root.root_node.id
    )
    assert "asc-context-packet-pre1" not in root_plan_request.prompt


def test_run_tree_cli_and_recursive_compose(tmp_path: Path):
    root_dir = tmp_path / "projects"
    script = tmp_path / "responses.json"
    script.write_text(json.dumps({"responses": project_responses()}, ensure_ascii=False), encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--root", str(root_dir)]

    def call(*args: str) -> dict:
        completed = subprocess.run(command + list(args), check=False, capture_output=True, text=True)
        assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
        return json.loads(completed.stdout)

    call(
        "init", "--project-id", "prj-cli-tree", "--title", "CLI親",
        "--premise", "CLI親の物語", "--chapters", "3", "--target-chars", "1200", "--json",
    )
    root_status = call("status", "prj-cli-tree", "--json")
    child = call(
        "add-child", "prj-cli-tree", "--parent-node", root_status["root_node_id"],
        "--node-id", "cli-child", "--link-id", "cli-link-child", "--title", "CLI子",
        "--premise", "CLI子の物語", "--chapters", "3", "--target-chars", "1200", "--json",
    )["link"]
    grandchild = call(
        "add-child", "prj-cli-tree", "--parent-node", child["child_node_id"],
        "--node-id", "cli-grandchild", "--link-id", "cli-link-grandchild", "--title", "CLI孫",
        "--premise", "CLI孫の物語", "--chapters", "3", "--target-chars", "1200", "--json",
    )["link"]
    result = call(
        "run-tree", "prj-cli-tree", "--provider", "scripted", "--script", str(script), "--json",
    )
    assert result["order"] == [root_status["root_node_id"], child["child_node_id"], grandchild["child_node_id"]]
    assert len(result["tree_runs"]) == 3
    composed = call("compose", "prj-cli-tree", "--json")
    assert "### CLI孫" in composed["text"]
