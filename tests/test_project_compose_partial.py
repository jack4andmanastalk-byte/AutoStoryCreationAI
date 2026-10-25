"""Partial composition: an unfinished child is omitted explicitly, never silently."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    NestedError,
    ProjectComposer,
    ProjectRunner,
    ProjectStore,
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


def spec(title: str) -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の独立した物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def family(store: ProjectStore):
    root = store.create_project(spec("親作品"), project_id="prj-partial")
    first = store.create_child(
        root.project.id, spec("子作品一"), order=2, child_node_id="node-child-one",
    )
    second = store.create_child(
        root.project.id, spec("子作品二"), order=1, child_node_id="node-child-two",
    )
    return root, first, second


def run_node(store: ProjectStore, project_id: str, node_id: str) -> None:
    ProjectRunner(store).run(
        project_id, ScriptedProvider(project_responses()), node_id=node_id,
    )


def test_partial_compose_marks_the_omission_and_stays_deterministic(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    root, first, second = family(store)
    run_node(store, root.project.id, root.root_node.id)
    run_node(store, root.project.id, first.child_node_id)
    composer = ProjectComposer(store)

    with pytest.raises(NestedError) as excinfo:
        composer.compose(root.project.id)
    assert second.id in str(excinfo.value)
    assert "no pinned draft" in str(excinfo.value)

    partial = composer.compose(root.project.id, partial=True)
    # The unfinished child keeps its position and is visibly marked, not skipped.
    assert partial.text.index("## 子作品二") < partial.text.index("## 子作品一")
    assert "この作品は未収録" in partial.text
    assert f"<!-- asc-omitted: link={second.id} node={second.child_node_id}" in partial.text
    assert len(partial.omitted) == 1
    row = partial.omitted[0]
    assert row["link_id"] == second.id
    assert row["node_id"] == second.child_node_id
    assert row["title"] == "子作品二"
    assert row["reason"] == "no-pinned-draft"
    assert partial.to_dict()["omitted"] == [row]

    manifest = json.loads(partial.path.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["omitted"] == [row]
    assert [link["id"] for link in manifest["links"]] == [first.id]
    assert partial.path.read_text(encoding="utf-8") == partial.text

    again = composer.compose(root.project.id, partial=True)
    assert again.content_version == partial.content_version
    assert again.path == partial.path
    partial_bytes = partial.path.read_bytes()

    # Completing the child produces a different identity at a different path,
    # and the partial artifact is left untouched (write-once).
    run_node(store, root.project.id, second.child_node_id)
    full = composer.compose(root.project.id)
    assert full.omitted == ()
    assert "omitted" not in full.to_dict()
    full_manifest = json.loads(full.path.with_suffix(".json").read_text(encoding="utf-8"))
    assert "omitted" not in full_manifest
    assert full.content_version != partial.content_version
    assert full.path != partial.path
    assert "asc-omitted" not in full.text
    assert partial.path.read_bytes() == partial_bytes


def test_partial_compose_covers_nested_descendants(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    root, first, second = family(store)
    grandchild = store.create_child(
        root.project.id, spec("孫作品"), order=1,
        parent_node_id=first.child_node_id, child_node_id="node-grandchild",
    )
    for node_id in (root.root_node.id, first.child_node_id, second.child_node_id):
        run_node(store, root.project.id, node_id)
    composer = ProjectComposer(store)

    with pytest.raises(NestedError):
        composer.compose(root.project.id)
    partial = composer.compose(root.project.id, partial=True)
    assert [row["node_id"] for row in partial.omitted] == [grandchild.child_node_id]
    # The pinned sibling and parent prose are still included byte for byte.
    assert "## 子作品一" in partial.text and "### 孫作品" in partial.text
    assert "この作品は未収録" in partial.text
    assert "asc-embedded" in partial.text


def test_cli_compose_partial_flag(tmp_path: Path):
    root = tmp_path / "projects"
    script = tmp_path / "base.json"
    script.write_text(
        json.dumps({"responses": project_responses()}, ensure_ascii=False),
        encoding="utf-8",
    )
    command = [sys.executable, str(SCRIPT), "--root", str(root)]

    def call(*args: str):
        return subprocess.run(
            command + list(args), check=False, capture_output=True, text=True,
        )

    assert call(
        "init", "--project-id", "prj-cli-partial", "--title", "CLI親",
        "--premise", "CLIの親作品。", "--chapters", "3", "--target-chars", "1200", "--json",
    ).returncode == 0
    first = json.loads(call(
        "add-child", "prj-cli-partial", "--node-id", "node-cli-one",
        "--title", "CLI子一", "--premise", "一つ目の子。", "--order", "1",
        "--chapters", "3", "--target-chars", "1200", "--json",
    ).stdout)["link"]
    second = json.loads(call(
        "add-child", "prj-cli-partial", "--node-id", "node-cli-two",
        "--title", "CLI子二", "--premise", "二つ目の子。", "--order", "2",
        "--chapters", "3", "--target-chars", "1200", "--json",
    ).stdout)["link"]
    root_node = json.loads(call("status", "prj-cli-partial", "--json").stdout)["root_node_id"]
    for node_id in (root_node, first["child_node_id"]):
        assert call(
            "run", "prj-cli-partial", "--node", node_id, "--provider", "scripted",
            "--script", str(script), "--json",
        ).returncode == 0

    strict = call("compose", "prj-cli-partial", "--json")
    assert strict.returncode == 2
    assert "no pinned draft" in strict.stderr

    partial = call("compose", "prj-cli-partial", "--partial", "--json")
    assert partial.returncode == 0, partial.stderr
    report = json.loads(partial.stdout)
    assert [row["link_id"] for row in report["omitted"]] == [second["id"]]
    assert "この作品は未収録" in report["text"]
    assert "CLI子一" in report["text"]

    out = tmp_path / "external" / "partial.md"
    written = call(
        "compose", "prj-cli-partial", "--partial", "--out", str(out),
    )
    assert written.returncode == 0, written.stderr
    assert f"Omitted: {second['id']} ({second['child_node_id']})" in written.stdout
    assert "この作品は未収録" in out.read_text(encoding="utf-8")
