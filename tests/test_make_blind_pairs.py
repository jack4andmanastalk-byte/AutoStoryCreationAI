"""Blind packets are the only way L3 means anything, so blindness gets tested.

The properties pinned here are the ones that silently fail:

* a packet must not leak provenance (run id, system, seed, task, markers),
* a dropped pair must be dropped for a recorded reason, not quietly skipped,
* the same seed must produce byte-identical packets (someone will ask how the
  assignment was made),
* "a" must not mean "S1" — sides are balanced by construction.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "make_blind_pairs.py"

CHAPTER = "{{time: day=1}}{{location: 灯台}}\n嵐の夜、灯台の灯りを確かめた。{tail}"
SYSTEM_TEXT = {
    "s0": "本文だけの稿。" * 60,
    "s1": "{{time: day=1}}{{location: 灯台}}\n台帳から書いた稿。" * 40,
}


def make_run(root: Path, run_id: str, system: str, seed: int, text: str,
             status: str = "ok", task: str = "t01", started: str = "2026-10-23T12:00:00Z") -> Path:
    directory = root / run_id
    (directory / "text").mkdir(parents=True)
    (directory / "text" / "ch01.md").write_text(text, encoding="utf-8")
    manifest = {"run_id": run_id, "task_id": task, "system": system, "seed": seed,
                "status": status, "started_at": started, "model": "stub",
                "model_version": "v1", "protocol_version": "protocol-v1"}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def run(root: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--runs-root", str(root), "--out", str(out), *extra],
        capture_output=True, text=True)


def test_packets_carry_no_provenance(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "20261023T120000Z-t01-s0-s0-aaaa1111", "s0", 0, SYSTEM_TEXT["s0"])
    make_run(runs, "20261023T120100Z-t01-s1-s0-bbbb2222", "s1", 0, SYSTEM_TEXT["s1"])
    out = tmp_path / "pairs"
    result = run(runs, out)
    assert result.returncode == 0, result.stderr

    packet = json.loads((out / "pairs" / "pair-001.json").read_text(encoding="utf-8"))
    assert set(packet) == {"pair_id", "a", "b"}, "a packet may only carry the texts"
    blob = json.dumps(packet, ensure_ascii=False)
    for leak in ("s0", "s1", "t01", "20261023T", "{{", "}}", "run_id", "seed", "system"):
        assert leak not in blob, f"leaked {leak!r} into the packet"
    assert "ch01" not in blob

    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    entry = key["pairs"]["pair-001"]
    assert {entry["a"]["system"], entry["b"]["system"]} == {"s0", "s1"}
    assert key["dropped"] == []


def test_the_assignment_is_reproducible_and_balanced(tmp_path):
    runs = tmp_path / "runs"
    for seed in range(4):
        make_run(runs, f"a-{seed}", "s0", seed, SYSTEM_TEXT["s0"] + str(seed))
        make_run(runs, f"b-{seed}", "s1", seed, SYSTEM_TEXT["s1"] + str(seed))
    first, second = tmp_path / "one", tmp_path / "two"
    assert run(runs, first, "--seed", "7").returncode == 0
    assert run(runs, second, "--seed", "7").returncode == 0

    files = sorted(p.name for p in (first / "pairs").glob("*.json"))
    assert files == sorted(p.name for p in (second / "pairs").glob("*.json"))
    for name in files:
        assert (first / "pairs" / name).read_bytes() == (second / "pairs" / name).read_bytes()

    key = json.loads((first / "key.json").read_text(encoding="utf-8"))
    sides = [entry["a"]["system"] for entry in key["pairs"].values()]
    assert abs(sides.count("s1") - sides.count("s0")) <= 1, \
        "'a' must not systematically be the candidate"


def test_a_large_length_gap_is_dropped_with_a_reason(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "a-0", "s0", 0, "短い稿。" * 30)
    make_run(runs, "b-0", "s1", 0, "長い稿。" * 400)
    out = tmp_path / "pairs"
    result = run(runs, out)
    assert result.returncode == 2, "no usable pair means exit 2, not an empty packet"
    assert "no usable pair" in result.stderr
    assert not (out / "pairs").exists()


def test_unfinished_runs_and_missing_sides_are_counted(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "a-0", "s0", 0, SYSTEM_TEXT["s0"])
    make_run(runs, "b-0", "s1", 0, SYSTEM_TEXT["s1"])
    make_run(runs, "a-1", "s0", 1, SYSTEM_TEXT["s0"])          # no counterpart
    make_run(runs, "b-2", "s1", 2, SYSTEM_TEXT["s1"], status="failed")
    make_run(runs, "a-2", "s0", 2, SYSTEM_TEXT["s0"])
    out = tmp_path / "pairs"
    assert run(runs, out).returncode == 0
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    reasons = sorted(drop["reason"] for drop in key["dropped"])
    assert reasons == ["missing_side", "missing_side"]
    assert len(key["pairs"]) == 1


def test_the_newest_run_wins_a_duplicate(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "old", "s0", 0, SYSTEM_TEXT["s0"], started="2026-10-23T10:00:00Z")
    make_run(runs, "new", "s0", 0, SYSTEM_TEXT["s0"], started="2026-10-23T11:00:00Z")
    make_run(runs, "cand", "s1", 0, SYSTEM_TEXT["s1"])
    out = tmp_path / "pairs"
    assert run(runs, out).returncode == 0
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    systems = {key["pairs"]["pair-001"]["a"]["run_id"], key["pairs"]["pair-001"]["b"]["run_id"]}
    assert "new" in systems and "old" not in systems


def test_the_judge_prompt_tells_the_rater_not_to_open_the_key(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "a", "s0", 0, SYSTEM_TEXT["s0"])
    make_run(runs, "b", "s1", 0, SYSTEM_TEXT["s1"])
    out = tmp_path / "pairs"
    assert run(runs, out).returncode == 0
    prompt = (out / "judge_prompt.md").read_text(encoding="utf-8")
    assert "key.json" in prompt and "開かない" in prompt
    assert "文字数" in prompt, "§4 forbids preferring the longer text"
    assert "tie" in prompt
