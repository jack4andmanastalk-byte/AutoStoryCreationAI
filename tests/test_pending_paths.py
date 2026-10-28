"""Project-owned relay paths relocate; external operators must not be rewritten."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from asc.project.pending_paths import record_project_paths, resolve_project_paths


def test_relative_project_relay_and_external_paths(tmp_path):
    old = tmp_path / "old" / "work"
    new = tmp_path / "new" / "work"
    inside = old / "custom-relay" / "responses" / "k.json"
    pending = {"key": "k", "response_path": str(inside), "request_path": None}
    saved = record_project_paths(old, pending)
    assert saved["response_path_relative"] == "custom-relay/responses/k.json"
    assert resolve_project_paths(new, saved)["response_path"] == str(new / "custom-relay/responses/k.json")
    external = {"key": "k", "response_path": str(tmp_path / "external" / "k.json")}
    assert resolve_project_paths(new, record_project_paths(old, external)) == external


def test_legacy_default_layout_requires_arena_provider(tmp_path):
    project = tmp_path / "new" / "work"
    run = project / "runs" / "run1"
    run.mkdir(parents=True)
    manifest = run / "manifest.json"
    old = tmp_path / "old" / "work" / "relay" / "responses" / "k.json"
    pending = {"key": "k", "response_path": str(old)}
    manifest.write_text(json.dumps({"provider": "command"}), encoding="utf-8")
    assert resolve_project_paths(project, pending, "run1")["response_path"] == str(old)
    manifest.write_text(json.dumps({"provider": "arena-relay"}), encoding="utf-8")
    assert resolve_project_paths(project, pending, "run1")["response_path"] == str(project / "relay/responses/k.json")


def test_relative_path_cannot_escape_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    for rel in ("../outside", str(tmp_path / "outside")):
        with pytest.raises(ValueError, match="escapes"):
            resolve_project_paths(project, {"response_path": "/old", "response_path_relative": rel})
    (project / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        resolve_project_paths(project, {"response_path": "/old", "response_path_relative": "link/outside"})
