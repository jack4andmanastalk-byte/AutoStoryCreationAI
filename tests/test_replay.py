"""Recorded-response replay is exact, offline and auditable.

These tests exercise pipeline wiring only. A successful replay is not fresh
model generation and does not establish G5 model reproducibility.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_experiment  # noqa: E402
from asc.pipeline import (  # noqa: E402
    GenerationRequest, ReplayError, ReplayProvider, ScriptedProvider, load_tasks,
)

TASKS_FILE = REPO_ROOT / "benchmarks/protocol-v1/tasks.yaml"
FIXTURE = REPO_ROOT / "benchmarks/protocol-v1/fixtures/plan-demo.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def responses() -> dict[str, str]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"]


def make_source(tmp_path: Path, answer_map: dict[str, str] | None = None) -> dict:
    tasks = load_tasks(TASKS_FILE)
    cell = run_experiment.run_cell(
        tasks.get("t01"), "s1", 0, ScriptedProvider(answer_map or responses()),
        tasks, tmp_path / "source-runs", 0.8)
    assert cell["status"] == "ok", cell.get("error")
    return cell


def replay_source(tmp_path: Path, source: dict, name: str = "replay-runs") -> dict:
    tasks = load_tasks(TASKS_FILE)
    provider = ReplayProvider(source["run_dir"])
    return run_experiment.run_cell(
        tasks.get("t01"), "s1", 0, provider, tasks, tmp_path / name, 0.8)


def test_clean_replay_matches_artifacts_and_preserves_source(tmp_path):
    source = make_source(tmp_path)
    source_dir = Path(source["run_dir"])
    manifest_before = sha256(source_dir / "manifest.json")
    responses_before = sha256(source_dir / "responses.jsonl")
    source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    assert source_manifest["responses_sha256"] == responses_before
    assert source_manifest["response_count"] == 12

    replay = replay_source(tmp_path, source)

    assert replay["status"] == "ok", replay.get("error")
    assert replay["provider_requests"] == 12
    assert replay["response_provenance"]["counts"] == {"replay": 12}
    assert replay["replay"]["ok"] is True
    assert replay["replay"]["replayed_responses"] == 12
    assert replay["replay"]["artifacts_match"] is True
    assert replay["replay"]["manifest_prompt_hashes_match"] is True
    assert sha256(source_dir / "manifest.json") == manifest_before
    assert sha256(source_dir / "responses.jsonl") == responses_before

    replay_dir = Path(replay["run_dir"])
    for chapter in ("ch01.md", "ch02.md", "ch03.md"):
        assert (replay_dir / "text" / chapter).read_bytes() == \
            (source_dir / "text" / chapter).read_bytes()
    audit = json.loads((replay_dir / "replay-audit.json").read_text(encoding="utf-8"))
    assert audit["source"]["run_id"] == source["run_id"]
    assert audit["source"]["responses_pinned_by_source_manifest"] is True
    assert len(audit["requests"]) == 12
    assert all(row["full_prompt_match"] for row in audit["requests"])
    replay_manifest = json.loads((replay_dir / "manifest.json").read_text(encoding="utf-8"))
    assert replay_manifest["provider"] == "replay"
    assert replay_manifest["response_count"] == 12
    assert replay_manifest["usage"] == {"replay": 12}


def test_replay_supports_design_repair_attempt_keys(tmp_path):
    repaired = responses()
    bad_brief = json.loads(repaired["design:brief:t01"])
    bad_brief["logline"] = "短い"
    repaired["design:brief:t01"] = json.dumps(bad_brief, ensure_ascii=False)
    repaired["design:brief:repair:t01"] = responses()["design:brief:t01"]
    source = make_source(tmp_path, repaired)
    assert source["design_repairs"] == 1
    assert source["provider_requests"] == 13

    replay = replay_source(tmp_path, source)

    assert replay["status"] == "ok", replay.get("error")
    assert replay["design_repairs"] == 1
    assert replay["provider_requests"] == 13
    audit = json.loads((Path(replay["run_dir"]) / "replay-audit.json"
                        ).read_text(encoding="utf-8"))
    keys = {row["request_key"] for row in audit["requests"]}
    assert "s1-t01-s0-design-brief-a1" in keys
    assert "s1-t01-s0-design-brief-repair-a2" in keys
    assert replay["replay"]["all_source_responses_consumed"] is True


def test_replay_rejects_changed_prompt_and_unknown_request_key(tmp_path):
    source = make_source(tmp_path)
    provider = ReplayProvider(source["run_dir"])
    first = json.loads((Path(source["run_dir"]) / "responses.jsonl"
                        ).read_text(encoding="utf-8").splitlines()[0])
    request = GenerationRequest(
        purpose=first["purpose"], prompt=first["prompt"] + "\n変更",
        temperature=first["temperature"], seed=first["seed"],
        context={"task_id": "t01", "system": "s1", "attempt": 1})
    with pytest.raises(ReplayError, match="prompt hash mismatch"):
        provider.generate(request)

    other_task = GenerationRequest(
        purpose=first["purpose"], prompt=first["prompt"],
        temperature=first["temperature"], seed=first["seed"],
        context={"task_id": "t02", "system": "s1", "attempt": 1})
    with pytest.raises(ReplayError, match="no recorded response"):
        provider.generate(other_task)


def test_replay_rejects_a_response_log_that_differs_from_manifest(tmp_path):
    source = make_source(tmp_path)
    path = Path(source["run_dir"]) / "responses.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    entries[0]["response"]["text"] = "改変された応答"
    path.write_text("".join(json.dumps(entry, ensure_ascii=False) + "\n"
                            for entry in entries), encoding="utf-8")

    with pytest.raises(ReplayError, match="responses.jsonl differs"):
        ReplayProvider(source["run_dir"])


def test_replay_fails_when_a_final_artifact_differs(tmp_path):
    source = make_source(tmp_path)
    provider = ReplayProvider(source["run_dir"])
    # Change only the final artifact after the provider has pinned the source
    # manifest/log. The recorded answers remain valid, but exact replay must fail.
    (Path(source["run_dir"]) / "text" / "ch01.md").write_text(
        "成果物だけを変更\n", encoding="utf-8")
    tasks = load_tasks(TASKS_FILE)
    replay = run_experiment.run_cell(
        tasks.get("t01"), "s1", 0, provider, tasks, tmp_path / "replay-runs", 0.8)

    assert replay["status"] == "failed"
    assert replay["replay"]["source_unchanged"] is True
    assert replay["replay"]["artifacts_match"] is False
    audit = json.loads((Path(replay["run_dir"]) / "replay-audit.json"
                        ).read_text(encoding="utf-8"))
    assert any(row["path"] == "text/ch01.md" and not row["match"]
               for row in audit["artifacts"])


def test_replay_cli_writes_source_pins_and_does_not_claim_g5(tmp_path):
    source = make_source(tmp_path)
    source_dir = Path(source["run_dir"])
    out = tmp_path / "replay-experiment"
    completed = subprocess.run(
        [sys.executable, "scripts/run_experiment.py", "--id", "replay-test",
         "--tasks", "t01", "--systems", "s1", "--seeds", "0",
         "--provider", "replay", "--replay-from", str(source_dir),
         "--replay-manifest-sha256", sha256(source_dir / "manifest.json"),
         "--replay-responses-sha256", sha256(source_dir / "responses.jsonl"),
         "--runs", str(tmp_path / "cli-runs"), "--out", str(out), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["experiment"]["provider"] == "replay"
    assert results["replay"]["source"]["manifest_pin_provided"] is True
    assert results["replay"]["source"]["responses_pin_provided"] is True
    assert results["replay"]["cells"][0]["status"] == "ok"
    assert results["replay"]["cells"][0]["verification"]["ok"] is True
    assert results["by_system"]["s1"]["response_provenance"]["counts"] == {"replay": 12}
    note = (out / "note.md").read_text(encoding="utf-8")
    assert "offline replay" in note
    assert "新規生成ではありません" in note
    assert "G5" in note
