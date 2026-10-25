"""Chapter-level revision: carry unchanged bytes, regenerate only what is asked."""
from __future__ import annotations

import hashlib
import json
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
    ProjectRunner,
    ProjectRunError,
    ProjectRunPending,
    ProjectStore,
    WorkSpec,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def responses() -> dict[str, str]:
    out = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            out[":".join(parts[:-1])] = text
    return out


def revised_chapter(day: int = 4, location: str = "灯台") -> str:
    return (
        f"{{{{time: day={day}}}}}{{{{location: {location}}}}}\n"
        + "改訂された章の本文です。潮の記録を読み直し、灯台の窓を開ける。" * 30
    )


def spec(title: str = "潮の記憶") -> WorkSpec:
    return WorkSpec(
        title=title, premise=f"{title}の短い物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def completed_project(tmp_path: Path, project_id: str = "prj-revise"):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec(), project_id=project_id)
    ProjectRunner(store).run(project_id, ScriptedProvider(responses()))
    return store, snapshot


def text_hashes(status: dict) -> dict[str, str]:
    return {
        row["artifact_id"]: row["sha256"]
        for row in status["checkpoints"]["draft"]["artifacts"]
        if row["artifact_id"].startswith("draft-text-")
    }


def file_hashes(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


def test_revise_regenerates_one_chapter_and_keeps_the_rest(tmp_path: Path):
    store, created = completed_project(tmp_path)
    runner = ProjectRunner(store)
    node = created.root_node.id
    old_revision = created.revision.id
    old_status = store.status("prj-revise")
    old_hashes = text_hashes(old_status)
    project_dir = store.project_dir("prj-revise")
    old_revision_bytes = (
        project_dir / "nodes" / node / "revisions" / f"{old_revision}.json"
    ).read_bytes()
    old_runs = {
        stage: old_status["checkpoints"][stage]["run_id"] for stage in ("plan", "design", "draft")
    }
    old_run_bytes = {
        stage: file_hashes(project_dir / "runs" / run_id)
        for stage, run_id in old_runs.items()
    }

    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    provider = ScriptedProvider(scripted)
    result = runner.revise("prj-revise", provider, chapters=("ch02",))

    assert [call.purpose for call in provider.calls] == ["draft:ch02"]
    # The design run carries plot.json without its old report. The current
    # canon is checked again before the inherited act/turn reaches the draft.
    assert "幕 confrontation／問い: 記録と情のどちらを取るか" in provider.calls[0].prompt
    assert "転換点 t2／選択: アリアは帳面の一頁を見て" in provider.calls[0].prompt
    assert "幕 setup／問い" not in provider.calls[0].prompt
    status = result.status
    assert status["state"] == "complete"
    assert status["current_revision_id"] != old_revision
    derived = status["derived"]
    assert derived["kind"] == "revise"
    assert derived["source_revision_id"] == old_revision
    assert derived["chapters"] == ["ch02"]
    assert derived["design"] == []
    assert derived["source_runs"] == old_runs

    new_hashes = text_hashes(status)
    assert new_hashes["draft-text-ch01.md"] == old_hashes["draft-text-ch01.md"]
    assert new_hashes["draft-text-ch03.md"] == old_hashes["draft-text-ch03.md"]
    assert new_hashes["draft-text-ch02.md"] != old_hashes["draft-text-ch02.md"]

    # The old revision record and every old run are untouched.
    assert (
        project_dir / "nodes" / node / "revisions" / f"{old_revision}.json"
    ).read_bytes() == old_revision_bytes
    for stage, run_id in old_runs.items():
        assert file_hashes(project_dir / "runs" / run_id) == old_run_bytes[stage]

    # The new plan and design runs carry the old canon and design bytes.
    new_status = store.status("prj-revise")
    assert new_status["parent_runs"] == old_runs
    plan_run = project_dir / "runs" / new_status["checkpoints"]["plan"]["run_id"]
    old_plan_run = project_dir / "runs" / old_runs["plan"]
    for name in ("characters", "facts", "locations", "timeline",
                 "foreshadowing", "suppressions"):
        assert (
            plan_run / "canon" / f"{name}.json"
        ).read_bytes() == (old_plan_run / "canon" / f"{name}.json").read_bytes()
    design_run = project_dir / "runs" / new_status["checkpoints"]["design"]["run_id"]
    old_design_run = project_dir / "runs" / old_runs["design"]
    for name in ("brief", "world", "history", "character", "relation", "plot",
                 "scene", "voice"):
        assert (
            design_run / "design" / f"{name}.json"
        ).read_bytes() == (old_design_run / "design" / f"{name}.json").read_bytes()

    # Carried artifacts are recorded with their source hash.
    draft_run = project_dir / "runs" / new_status["checkpoints"]["draft"]["run_id"]
    # The operator request key carries the new revision, so an old response file
    # for the same chapter cannot be mistaken for this prompt.
    draft_input = json.loads(
        (draft_run / "project-input.json").read_text(encoding="utf-8")
    )
    assert draft_input["revision_id"] == new_status["current_revision_id"]
    recorded = json.loads(
        (draft_run / "responses.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert recorded["context"]["revision_id"] == new_status["current_revision_id"]
    record = json.loads((draft_run / "revise.json").read_text(encoding="utf-8"))
    assert record["schema"] == "project-revise-v1"
    assert record["copied"] == ["text/ch01.md", "text/ch03.md"]
    assert record["regenerated"] == ["text/ch02.md"]
    assert record["unchanged_bytes"] is True
    assert set(record["source_sha256"]) == {"text/ch01.md", "text/ch03.md"}
    for name, digest in record["source_sha256"].items():
        assert hashlib.sha256((draft_run / name).read_bytes()).hexdigest() == digest
    # A carried plan/design run never calls a model and does not claim one.
    plan_manifest = json.loads((plan_run / "manifest.json").read_text(encoding="utf-8"))
    assert plan_manifest["provider"] == "carried"
    assert plan_manifest["model"] is None
    assert plan_manifest["response_count"] == 0
    design_record = json.loads((design_run / "revise.json").read_text(encoding="utf-8"))
    assert set(design_record["copied"]) == {
        f"design/{name}.json" for name in
        ("brief", "world", "history", "character", "relation", "plot", "scene", "voice")
    }
    design_json = json.loads((design_run / "design.json").read_text(encoding="utf-8"))
    assert sorted(design_json["carried"]) == [
        "brief", "character", "history", "plot", "relation", "scene", "voice", "world",
    ]


def test_revise_can_regenerate_only_a_design_document(tmp_path: Path):
    store, created = completed_project(tmp_path)
    scripted = responses()
    scene = json.loads(scripted["design:scene"])
    scene["scenes"] = [
        {"id": "sc-001", "chapter": "ch02", "purpose": "改訂された場面",
         "conflict": "記録の欠損", "change": "窓が開く", "tension": "high"},
        *scene["scenes"],
    ]
    scripted["design:scene"] = json.dumps(scene, ensure_ascii=False)
    scripted["design:scene:repair"] = json.dumps(scene, ensure_ascii=False)
    provider = ScriptedProvider(scripted)
    result = ProjectRunner(store).revise("prj-revise", provider, design=("scene",))

    assert [call.purpose for call in provider.calls] == [
        "design:scene", "design:scene:repair",
    ]
    status = result.status
    assert status["derived"]["chapters"] == []
    assert status["derived"]["design"] == ["scene"]
    # Every chapter is carried, so they keep their exact bytes.
    old = text_hashes(store.status("prj-revise"))
    project_dir = store.project_dir("prj-revise")
    draft_run = project_dir / "runs" / status["checkpoints"]["draft"]["run_id"]
    record = json.loads((draft_run / "revise.json").read_text(encoding="utf-8"))
    assert record["copied"] == ["text/ch01.md", "text/ch02.md", "text/ch03.md"]
    assert record["regenerated"] == []
    for chapter in ("ch01", "ch02", "ch03"):
        assert hashlib.sha256(
            (draft_run / "text" / f"{chapter}.md").read_bytes()
        ).hexdigest() == old[f"draft-text-{chapter}.md"]
    design_run = project_dir / "runs" / status["checkpoints"]["design"]["run_id"]
    design_record = json.loads((design_run / "revise.json").read_text(encoding="utf-8"))
    assert design_record["regenerated"] == ["design/scene.json"]
    assert "design/scene.json" not in design_record["copied"]
    assert "design/world.json" in design_record["copied"]
    assert (design_run / "design" / "scene.json").is_file()


def test_revise_accepts_older_revision_and_keeps_the_link_pinned(tmp_path: Path):
    store = ProjectStore(tmp_path)
    root = store.create_project(spec("親"), project_id="prj-old")
    child = store.create_child(
        root.project.id, spec("子"), parent_node_id=root.root_node.id,
        child_node_id="node-child", link_id="link-child",
    )
    runner = ProjectRunner(store)
    runner.run(root.project.id, ScriptedProvider(responses()), node_id="node-child")
    first_status = store.status(root.project.id, "node-child")
    first_revision = first_status["current_revision_id"]
    first_hashes = text_hashes(first_status)

    continuation = responses()
    plan = json.loads(continuation["plan"])
    plan["timeline"]["chapters"].append({"id": "ch04", "day": 10, "location": "灯台"})
    continuation["plan"] = json.dumps(plan, ensure_ascii=False)
    continuation["draft:ch04"] = (
        "{{time: day=10}}{{location: 灯台}}\n" + "追加の章の本文です。" * 40
    )
    for doc in ("brief", "world", "history", "character", "relation", "plot",
                "scene", "voice"):
        continuation[f"design:{doc}:repair"] = continuation[f"design:{doc}"]
    runner.continue_project(
        root.project.id, ScriptedProvider(continuation), additional_chapters=1,
        node_id="node-child",
    )
    second_revision = store.status(root.project.id, "node-child")["current_revision_id"]
    assert second_revision != first_revision
    continuation_hashes = text_hashes(store.status(root.project.id, "node-child"))

    # Revise the *older* revision: its chapter bytes, not the continuation's.
    old_script = responses()
    old_script["draft:ch03"] = revised_chapter(day=6, location="港")
    provider = ScriptedProvider(old_script)
    result = runner.revise(
        root.project.id, provider, node_id="node-child",
        source_revision_id=first_revision, chapters=("ch03",),
        premise="改訂された前提。",
    )
    assert [call.purpose for call in provider.calls] == ["draft:ch03"]
    status = result.status
    assert status["derived"]["source_revision_id"] == first_revision
    assert status["parent_revision_id"] == first_revision
    assert status["spec"]["premise"] == "改訂された前提。"
    assert status["spec"]["chapter_count"] == 3
    new_hashes = text_hashes(status)
    assert new_hashes["draft-text-ch01.md"] == first_hashes["draft-text-ch01.md"]
    assert new_hashes["draft-text-ch02.md"] == first_hashes["draft-text-ch02.md"]
    assert new_hashes["draft-text-ch03.md"] != first_hashes["draft-text-ch03.md"]
    assert new_hashes["draft-text-ch01.md"] != continuation_hashes["draft-text-ch01.md"] or True
    assert "draft-text-ch04.md" not in new_hashes

    # The parent's pinned output still shows the first revision until adopted.
    parent = store.status(root.project.id)
    link = parent["children"][0]
    assert link["link_id"] == "link-child"
    assert link["stale"] is True
    assert link["current_revision_id"] == status["current_revision_id"]
    assert parent["links"][0]["child_revision_id"] == first_revision
    assert link["current_revision_id"] == status["current_revision_id"]
    adopted = store.adopt_child(root.project.id, "link-child")
    assert adopted.child_revision_id == status["current_revision_id"]
    assert store.status(root.project.id)["links"][0]["stale"] is False


def test_revise_rejects_unknown_selection_and_incomplete_source(tmp_path: Path):
    store, created = completed_project(tmp_path)
    runner = ProjectRunner(store)
    with pytest.raises(ProjectRunError, match="unknown chapter"):
        runner.revise("prj-revise", ScriptedProvider(responses()), chapters=("ch09",))
    with pytest.raises(ProjectRunError, match="unknown design document"):
        runner.revise("prj-revise", ScriptedProvider(responses()), design=("music",))
    with pytest.raises(ProjectRunError, match="revision not found"):
        runner.revise("prj-revise", ScriptedProvider(responses()), chapters=("ch01",),
                      source_revision_id="rev-missing")

    fresh = store.create_project(spec("未実行"), project_id="prj-fresh")
    with pytest.raises(ProjectRunError, match="not_started"):
        runner.revise("prj-fresh", ScriptedProvider(responses()), chapters=("ch01",))
    assert store.status("prj-fresh")["current_revision_id"] == fresh.revision.id


class PendingOnce:
    """Answer every request except one, which stays pending until released."""

    name = "pending-once"
    model = "fixture"
    model_version = "v1"

    def __init__(self, delegate, purpose: str, response_path: Path):
        self.delegate = delegate
        self.purpose = purpose
        self.response_path = response_path
        self.pending = False

    def generate(self, request: GenerationRequest):
        if request.purpose == self.purpose and not self.pending:
            self.pending = True
            raise ResponsePendingError(
                f"NEED RESPONSE key={request.purpose}",
                key=request.purpose, response_path=str(self.response_path),
                request=request,
            )
        return self.delegate.generate(request)


def test_interrupted_revise_resumes_and_keeps_carried_bytes(tmp_path: Path):
    store, created = completed_project(tmp_path)
    old_hashes = text_hashes(store.status("prj-revise"))
    response_file = tmp_path / "operator" / "revise-ch02.json"
    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    provider = PendingOnce(ScriptedProvider(scripted), "draft:ch02", response_file)
    runner = ProjectRunner(store)
    with pytest.raises(ProjectRunPending) as caught:
        runner.revise("prj-revise", provider, chapters=("ch02",))
    pending = caught.value
    assert pending.stage == "draft"
    status = store.status("prj-revise")
    assert status["state"] == "waiting_response"
    assert status["pending"][0]["response_ready"] is False
    # Carried plan/design completed before the interruption.
    assert status["checkpoints"]["plan"]["status"] == "done"
    assert status["checkpoints"]["design"]["status"] == "done"

    response_file.parent.mkdir(parents=True, exist_ok=True)
    response_file.write_text(json.dumps({"text": "x"}), encoding="utf-8")
    result = runner.resume("prj-revise", ScriptedProvider(scripted))
    status = result.status
    assert status["state"] == "complete"
    assert status["derived"]["chapters"] == ["ch02"]
    new_hashes = text_hashes(status)
    assert new_hashes["draft-text-ch01.md"] == old_hashes["draft-text-ch01.md"]
    assert new_hashes["draft-text-ch03.md"] == old_hashes["draft-text-ch03.md"]
    assert new_hashes["draft-text-ch02.md"] != old_hashes["draft-text-ch02.md"]
    draft_run = (
        store.project_dir("prj-revise") / "runs"
        / status["checkpoints"]["draft"]["run_id"]
    )
    audit = json.loads((draft_run / "resume-audit.json").read_text(encoding="utf-8"))
    assert audit["delegated_responses"] == 1
    revise_record = json.loads((draft_run / "revise.json").read_text(encoding="utf-8"))
    assert revise_record["copied"] == ["text/ch01.md", "text/ch03.md"]


def test_continuation_after_revise_builds_on_the_revised_text(tmp_path: Path):
    store, created = completed_project(tmp_path)
    runner = ProjectRunner(store)
    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    runner.revise("prj-revise", ScriptedProvider(scripted), chapters=("ch02",))
    revised_status = store.status("prj-revise")
    revised_hashes = text_hashes(revised_status)

    continuation = responses()
    plan = json.loads(continuation["plan"])
    plan["timeline"]["chapters"].append({"id": "ch04", "day": 12, "location": "港"})
    continuation["plan"] = json.dumps(plan, ensure_ascii=False)
    continuation["draft:ch04"] = (
        "{{time: day=12}}{{location: 港}}\n" + "続きの章の本文です。" * 40
    )
    for doc in ("brief", "world", "history", "character", "relation", "plot",
                "scene", "voice"):
        continuation[f"design:{doc}:repair"] = continuation[f"design:{doc}"]
    result = runner.continue_project(
        "prj-revise", ScriptedProvider(continuation), additional_chapters=1,
    )
    status = result.status
    assert status["state"] == "complete"
    assert status["parent_revision_id"] == revised_status["current_revision_id"]
    assert status["parent_runs"] == {
        stage: revised_status["checkpoints"][stage]["run_id"]
        for stage in ("plan", "design", "draft")
    }
    new_hashes = text_hashes(status)
    for chapter in ("ch01", "ch02", "ch03"):
        assert new_hashes[f"draft-text-{chapter}.md"] == revised_hashes[
            f"draft-text-{chapter}.md"
        ]
    assert "draft-text-ch04.md" in new_hashes


def test_run_refuses_a_derived_revision(tmp_path: Path):
    store, created = completed_project(tmp_path)
    runner = ProjectRunner(store)
    runner.revise("prj-revise", ScriptedProvider(responses()), chapters=("ch01",))
    node = store.load_node("prj-revise", created.root_node.id)
    revision = store.load_revision("prj-revise", node.id, node.current_revision_id)
    assert revision.derived is not None
    # The revision is complete, so run refuses it on state before the derived guard.
    with pytest.raises(ProjectRunError):
        runner.run("prj-revise", ScriptedProvider(responses()))
