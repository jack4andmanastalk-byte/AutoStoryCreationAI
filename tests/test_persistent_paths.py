"""Versionable paths are checked before starting a resumable Arena run."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_persistent_paths.py"


def invoke(repo, *paths):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, paths)],
                          cwd=repo, text=True, capture_output=True)


def test_paths_must_be_inside_repo_unignored_and_snapshot_safe(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("/runs/\nsecret/\n*.key\n", encoding="utf-8")
    assert invoke(repo, "experiments/example/runs/run1", "experiments/example/relay/run1").returncode == 0
    for path in ("experiments/example/out/run1", "runs/run1", "secret/a",
                 "experiments/example/password.key", str(tmp_path / "outside")):
        result = invoke(repo, path)
        assert result.returncode == 2, (path, result.stdout, result.stderr)
    (repo / "link").symlink_to(tmp_path, target_is_directory=True)
    assert invoke(repo, "link/outside").returncode == 2


def test_detects_ignored_directory_and_checks_all_inputs(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("hidden/\n", encoding="utf-8")
    result = invoke(tmp_path, "safe", "hidden")
    assert result.returncode == 2
    assert "ignored by Git" in result.stderr


def test_refuses_when_git_ignore_cannot_be_checked(tmp_path):
    assert invoke(tmp_path, "safe").returncode == 2
