from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import (  # noqa: E402
    PROJECT_SUMMARY_SCHEMA,
    ProjectRunner,
    ProjectStore,
    ProjectSummary,
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


def make_project(store: ProjectStore, project_id: str = "prj-sum"):
    return store.create_project(
        WorkSpec(
            title="灯台の記録",
            premise="閉ざされた灯台の記録を調べる三章の物語。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        project_id=project_id,
    )


def test_summary_reports_info_canon_design_and_checks_without_opening_json(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store)
    ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(project_responses()))

    result = ProjectSummary(store).summarize(snapshot.project.id)
    payload = result.to_dict()

    assert payload["schema"] == PROJECT_SUMMARY_SCHEMA
    assert payload["project_id"] == snapshot.project.id
    assert payload["state"] == "complete"
    assert payload["info"]["chapter_count"] == 3
    assert len(payload["info"]["chapters"]) == 3
    assert payload["info"]["total_chars_body"] > 0
    assert payload["canon"]["source"] == "run"
    assert len(payload["canon"]["characters"]) >= 2
    assert len(payload["canon"]["facts"]) >= 2
    assert payload["design"]["source"] == "run"
    assert [doc["doc"] for doc in payload["design"]["documents"]] == [
        "brief", "world", "history", "character",
        "relation", "plot", "scene", "voice",
    ]
    assert all(doc["summary_lines"] for doc in payload["design"]["documents"])
    assert payload["checks"]["blocker_count"] == 0
    assert "## 1. 作品情報（Info）" in result.markdown
    assert "## 2. 設定台帳（Canon Summary" in result.markdown
    assert "## 3. 設計書 8 種の要約（Design Summary" in result.markdown
    assert "## 4. 検査・監査の編集支援要約（Editorial Checks）" in result.markdown


def test_summary_separates_blockers_warnings_observations_and_next_commands(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store)
    responses = project_responses()
    # Force design:scene to remain unresolved (fail-open) so a design warning is emitted.
    bad_scene = json.loads(responses["design:scene"])
    bad_scene["scenes"][0]["disclosure"]["disclosed"] = []
    responses["design:scene"] = json.dumps(bad_scene, ensure_ascii=False)
    responses["design:scene:repair"] = responses["design:scene"]
    ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(responses))

    # Add a child node and revise it so the parent link becomes stale.
    link = store.create_child(
        snapshot.project.id,
        WorkSpec(
            title="外伝",
            premise="外伝の記録。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        child_node_id="node-child",
        link_id="link-child",
    )
    ProjectRunner(store).run(
        snapshot.project.id, ScriptedProvider(project_responses()), node_id=link.child_node_id,
    )
    ProjectRunner(store).revise(
        snapshot.project.id, ScriptedProvider(project_responses()), node_id=link.child_node_id,
    )

    result = ProjectSummary(store).summarize(snapshot.project.id)
    checks = result.checks
    assert checks["blocker_count"] == 0
    assert checks["warning_count"] >= 2
    rules = {w["rule"] for w in checks["warnings"]}
    assert "knowledge_tracked" in rules
    assert "child_link_stale" in rules
    assert any("revise prj-sum --design scene" in cmd for cmd in checks["next_edit_commands"])
    assert any("adopt-child prj-sum link-child" in cmd for cmd in checks["next_edit_commands"])


def test_summary_falls_back_to_relay_responses_when_runs_are_absent(tmp_path: Path):
    dogfood_root = ROOT / "experiments" / "2026-10-dogfood-01" / "work"
    work_copy = tmp_path / "work"
    shutil.copytree(dogfood_root, work_copy)
    # Remove runs/ completely: summary must still read canon and all 8 design docs from relay/responses.
    shutil.rmtree(work_copy / "prj-mine" / "runs")

    store = ProjectStore(work_copy)
    result = ProjectSummary(store).summarize("prj-mine")
    assert result.canon["source"] == "relay"
    assert len(result.canon["characters"]) == 4
    assert result.design["source"] == "relay"
    assert all(doc["source"] == "relay" for doc in result.design["documents"])
    assert all(doc["summary_lines"] for doc in result.design["documents"])


def test_summary_cli_supports_section_out_and_json(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = make_project(store, project_id="prj-sum-cli")
    ProjectRunner(store).run(snapshot.project.id, ScriptedProvider(project_responses()))
    out_md = tmp_path / "summary.md"

    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(store.root),
            "summary", snapshot.project.id,
            "--section", "info", "--section", "checks",
            "--out", str(out_md), "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["sections"] == ["info", "checks"]
    assert "info" in payload and "checks" in payload
    assert "canon" not in payload and "design" not in payload
    assert out_md.is_file()
    text = out_md.read_text(encoding="utf-8")
    assert "## 1. 作品情報（Info）" in text
    assert "## 4. 検査・監査の編集支援要約（Editorial Checks）" in text
    assert "## 2. 設定台帳" not in text
