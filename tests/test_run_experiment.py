"""The experiment record has to name the thing that wrote the text.

``--provider command`` used to record ``model=external`` no matter which model
answered, which would have flattened the chat-operator pilot into an anonymous
run. These tests keep the name and version on the command path.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_experiment.py"


def write_provider(tmp_path: Path) -> Path:
    path = tmp_path / "provider.py"
    path.write_text(
        "import json\n"
        "import sys\n"
        "json.load(sys.stdin)\n"
        'print(json.dumps({"text": "あ" * 450}, ensure_ascii=False))\n',
        encoding="utf-8")
    return path


def run(tmp_path: Path, *extra: str) -> dict:
    provider = write_provider(tmp_path)
    out = tmp_path / "out"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--id", "t", "--tasks", "t01",
         "--systems", "s0", "--seeds", "0", "--provider", "command",
         "--command", f"{sys.executable} {provider}",
         "--runs", str(tmp_path / "runs"), "--out", str(out), "--quiet", *extra],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads((out / "results.json").read_text(encoding="utf-8"))


def test_model_name_and_version_are_recorded(tmp_path):
    results = run(tmp_path, "--model", "arena-agent-mode",
                  "--model-version", "unversioned-2026-10-23")
    experiment = results["experiment"]
    assert experiment["model"] == "arena-agent-mode"
    assert experiment["model_version"] == "unversioned-2026-10-23"


def test_model_defaults_are_unchanged_without_the_flag(tmp_path):
    results = run(tmp_path)
    assert results["experiment"]["model"] == "external"
    assert results["experiment"]["model_version"] is None
