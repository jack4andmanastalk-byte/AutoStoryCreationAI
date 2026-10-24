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


def test_l1_scope_and_arena_limits_are_recorded(tmp_path):
    results = run(tmp_path, "--model", "arena-agent-mode",
                  "--model-version", "unversioned-2026-10-24")
    scope = results["evaluation_scope"]
    assert scope["mode"] == "l1-only"
    assert scope["active_layers"] == ["L1"]
    assert set(scope["frozen_layers"]) == {"L2", "L3"}
    note = (tmp_path / "out" / "note.md").read_text(encoding="utf-8")
    assert "評価範囲は L1-only" in note
    assert "G3/G4 は未測定" in note
    assert "G5 を主張しません" in note
    assert "探索的な参考値" in note


def test_response_origins_are_counted_without_guessing(tmp_path):
    import importlib.util
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from asc.pipeline import GenerationRequest, RunLedger
    from asc.pipeline.llm import GenerationResult

    spec = importlib.util.spec_from_file_location("run_experiment", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger = RunLedger.create(tmp_path / "runs", task_id="t01", system="s1",
                              seed=0, protocol_version="protocol-v1")
    for purpose, provenance in (
            ("plan", {"origin": "fresh"}),
            ("design:brief", {"origin": "reused", "source_run_id": "run-old"}),
            ("draft:ch01", {})):
        request = GenerationRequest(purpose=purpose, prompt=purpose)
        ledger.record(request, GenerationResult(
            text="応答", provider="command", model="m", provenance=provenance))

    requests, provenance = module._response_metrics(ledger)
    assert requests == 3
    assert provenance == {
        "counts": {"fresh": 1, "reused": 1, "unspecified": 1},
        "reused_source_run_ids": ["run-old"],
    }
    row = {"system": "s1", "status": "ok", "provider_requests": requests,
           "response_provenance": provenance}
    aggregate = module.aggregate([row])["by_system"]["s1"]
    assert aggregate["response_provenance"] == provenance
