from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.project import (  # noqa: E402
    ArtifactRef,
    ProjectCorruptError,
    ProjectExistsError,
    ProjectLockError,
    ProjectNotFoundError,
    ProjectStore,
    ProjectValidationError,
    WorkSpec,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "story_project.py"


def make_spec(**changes) -> WorkSpec:
    values = {
        "title": "潮の記録者",
        "premise": "港町で失われた潮位記録を追う。",
        "language": "ja",
        "chapter_count": 3,
        "target_chars_per_chapter": 1600,
        "form": "novel",
        "options": {"tone": "quiet"},
    }
    values.update(changes)
    return WorkSpec(**values)


def test_project_round_trip_and_initial_status(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    snapshot = store.create_project(make_spec(), project_id="prj-seaside")

    assert snapshot.root_node.parent_id is None
    assert snapshot.revision.parent_revision_id is None
    expected_hash = hashlib.sha256(json.dumps(
        snapshot.revision.spec.to_dict(), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    assert snapshot.revision.spec_sha256 == expected_hash
    assert store.load_snapshot("prj-seaside") == snapshot

    status = store.status("prj-seaside")
    assert status["state"] == "not_started"
    assert status["stages"] == {"plan": "pending", "design": "pending", "draft": "pending"}
    assert status["artifacts"] == []
    assert status["runs"] == []
    assert status["spec"]["premise"] == "港町で失われた潮位記録を追う。"
    assert not list(store.root.glob("*.tmp-*"))


def test_ids_are_stable_unique_and_path_safe(tmp_path: Path):
    store = ProjectStore(tmp_path)
    first = store.create_project(make_spec())
    second = store.create_project(make_spec())
    assert first.project.id != second.project.id
    assert first.root_node.id != second.root_node.id
    assert first.revision.id != second.revision.id

    with pytest.raises(ProjectExistsError):
        store.create_project(make_spec(), project_id=first.project.id)
    with pytest.raises(ProjectValidationError):
        store.create_project(make_spec(), project_id="../escape")
    with pytest.raises(ProjectNotFoundError):
        store.load_project("prj-missing")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "  "),
        ("premise", ""),
        ("language", ""),
        ("chapter_count", 0),
        ("target_chars_per_chapter", -1),
        ("options", {"not_finite": float("nan")}),
    ],
)
def test_invalid_work_spec_is_rejected(tmp_path: Path, field: str, value):
    with pytest.raises(ProjectValidationError):
        ProjectStore(tmp_path).create_project(make_spec(**{field: value}))


def test_schema_version_and_spec_hash_are_checked_on_load(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(make_spec(), project_id="prj-integrity")
    project_path = store.project_dir(snapshot.project.id) / "project.json"
    project_data = json.loads(project_path.read_text(encoding="utf-8"))
    project_data["schema_version"] = 999
    project_path.write_text(json.dumps(project_data), encoding="utf-8")
    with pytest.raises(ProjectCorruptError, match="schema_version"):
        store.load_project(snapshot.project.id)

    project_data["schema_version"] = 1
    project_path.write_text(json.dumps(project_data), encoding="utf-8")
    revision_path = store.revision_path(
        snapshot.project.id, snapshot.root_node.id, snapshot.revision.id,
    )
    revision_data = json.loads(revision_path.read_text(encoding="utf-8"))
    revision_data["spec"]["premise"] = "changed without a new revision"
    revision_path.write_text(json.dumps(revision_data), encoding="utf-8")
    with pytest.raises(ProjectCorruptError, match="spec_sha256"):
        store.load_snapshot(snapshot.project.id)


def test_current_state_update_is_atomic_and_single_writer(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(make_spec(), project_id="prj-lock")
    updated = replace(snapshot.root_node, updated_at="2026-10-25T00:00:00Z")
    store.save_node(updated)
    assert store.load_node(snapshot.project.id, snapshot.root_node.id) == updated

    with store.writer_lock(snapshot.project.id):
        with pytest.raises(ProjectLockError):
            ProjectStore(tmp_path).save_node(updated)

    missing_revision = replace(updated, current_revision_id="rev-missing")
    with pytest.raises(ProjectNotFoundError):
        store.save_node(missing_revision)
    assert store.load_node(snapshot.project.id, snapshot.root_node.id) == updated


def test_artifact_refs_are_content_addressed_and_relative():
    reference = ArtifactRef(
        artifact_id="draft",
        path="artifacts/draft.md",
        sha256="a" * 64,
        media_type="text/markdown",
        producer_run_id="run-001",
    )
    assert ArtifactRef.from_dict(reference.to_dict()) == reference
    with pytest.raises(ProjectValidationError, match="relative POSIX path|unsafe"):
        ArtifactRef.from_dict({**reference.to_dict(), "path": "../draft.md"})
    with pytest.raises(ProjectValidationError, match="sha256"):
        ArtifactRef.from_dict({**reference.to_dict(), "sha256": "not-a-hash"})


def test_cli_init_then_status_in_a_separate_process(tmp_path: Path):
    root = tmp_path / "projects"
    init = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(root), "init",
            "--project-id", "prj-cli", "--title", "別processの確認",
            "--premise", "任意のpremiseを保存する。", "--chapters", "5",
            "--target-chars", "1200", "--json",
        ],
        check=False, capture_output=True, text=True,
    )
    assert init.returncode == 0, init.stderr
    created = json.loads(init.stdout)

    loaded = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "status", "prj-cli", "--json"],
        check=False, capture_output=True, text=True,
    )
    assert loaded.returncode == 0, loaded.stderr
    assert json.loads(loaded.stdout) == created
    assert created["spec"]["chapter_count"] == 5
    assert created["spec"]["target_chars_per_chapter"] == 1200

    duplicate = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(root), "init",
            "--project-id", "prj-cli", "--title", "duplicate", "--premise", "duplicate",
        ],
        check=False, capture_output=True, text=True,
    )
    assert duplicate.returncode == 2
    assert "already exists" in duplicate.stderr
