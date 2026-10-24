"""S2 (revision) and S3 (voice) run end to end on the scripted fixture.

These tests verify the wiring only: critique -> revise -> re-audit records
its rounds, the voice pass rewrites every chapter, and the experiment runner
accepts s2/s3. Nothing here measures a model.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures"
           / "pipeline-s2s3-demo.json")
REVISE_FIXTURE = (REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures"
                  / "pipeline-s2s3-revise-demo.json")


def run_pipeline(tmp_path: Path, system: str, *extra: str) -> dict:
    out = tmp_path / "runs"
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--task", "t01",
         "--system", system, "--out", str(out), "--report-only", *extra],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    runs = list(out.iterdir())
    assert len(runs) == 1
    return json.loads((runs[0] / "run-summary.json").read_text(encoding="utf-8")), runs[0]


def test_s2_records_its_rounds(tmp_path):
    summary, run_dir = run_pipeline(tmp_path, "s2", "--script", str(FIXTURE))
    assert summary["system"] == "s2"
    assert summary["revision"]["converged"] is True
    assert (run_dir / "revision.json").is_file()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "revise-chapter" in manifest["prompt_hashes"]


def test_s2_revision_actually_fires_and_fixes(tmp_path):
    """ch03 の回収漏れが批評され、改稿で解消されること。"""
    summary, run_dir = run_pipeline(tmp_path, "s2", "--script", str(REVISE_FIXTURE))
    revision = summary["revision"]
    assert revision["rounds"] == 1
    assert revision["revised"] == ["ch03"]
    assert revision["comparisons"][0]["fixed"] == 2
    assert revision["comparisons"][0]["persisting"] == 0
    assert summary["audit"]["violations"] == 0
    critique = json.loads((run_dir / "critique-round-1.json").read_text(encoding="utf-8"))
    assert critique["summary"]["open"] == 2


def test_s3_applies_the_voice_pass(tmp_path):
    summary, run_dir = run_pipeline(tmp_path, "s3", "--script", str(FIXTURE))
    assert summary["system"] == "s3"
    assert summary["voice"]["chapters"] == ["ch01", "ch02", "ch03"]
    assert summary["voice"]["kept"] == []
    assert (run_dir / "voice.json").is_file()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "revise-chapter" in manifest["prompt_hashes"]
    assert "voice-pass" in manifest["prompt_hashes"]
    # the voice text landed in the chapters (the fixture appends a sentence)
    ch01 = (run_dir / "text" / "ch01.md").read_text(encoding="utf-8")
    assert "風の音だけが" in ch01


def test_s3_voice_text_keeps_markers_and_terms(tmp_path):
    summary, run_dir = run_pipeline(tmp_path, "s3", "--script", str(FIXTURE))
    assert summary["final"]["must_include"]["rate"] == 1.0
    ch01 = (run_dir / "text" / "ch01.md").read_text(encoding="utf-8")
    assert "{{time:" in ch01 and "{{location:" in ch01


def test_experiment_matrix_accepts_s2_and_s3(tmp_path):
    out = tmp_path / "exp"
    completed = subprocess.run(
        [sys.executable, "scripts/run_experiment.py", "--id", "s2s3",
         "--tasks", "t01", "--systems", "s0", "s1", "s2", "s3", "--seeds", "0",
         "--provider", "scripted", "--script", str(FIXTURE),
         "--runs", str(tmp_path / "runs"), "--out", str(out), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert set(results["by_system"]) == {"s0", "s1", "s2", "s3"}
    assert results["by_system"]["s2"]["revision_rounds"]["mean"] == 0
    assert "paired_vs_s0_s2" in results
    assert "paired_vs_s0_s3" in results
    note = (out / "note.md").read_text(encoding="utf-8")
    assert "(S2−S0)" in note and "(S3−S0)" in note


def test_prompts_render_without_missing_placeholders():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from asc.pipeline import load_prompt  # noqa: E402

    revise = load_prompt("revise-chapter")
    revise.render({"title": "t", "logline": "l", "chapter_id": "ch01",
                   "canon": "c", "findings": "f", "chapter_text": "x",
                   "must_include": "m", "avoid": "a"})
    voice = load_prompt("voice-pass")
    voice.render({"title": "t", "chapter_id": "ch01", "chapter_text": "x",
                  "voice_guide": "g", "must_include": "m", "avoid": "a"})
