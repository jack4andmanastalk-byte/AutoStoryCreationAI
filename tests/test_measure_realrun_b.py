"""Batch B's measurement: the two counting modes, the arithmetic, the empty state.

The fixtures are (a) a scripted S1 run and (b) hand-built run directories. They
check that the script reads a run and applies the registered rules — they are
not evidence about prose, and none of them is a batch B sample.
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

import measure_realrun_b  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-b-t01"
DOCS = ["brief", "world", "history", "character", "relation", "plot", "scene", "voice"]


def registered() -> dict:
    return json.loads((BUNDLE / "preregistration.json").read_text(encoding="utf-8"))


def measure(tmp_path: Path, *extra: str) -> dict:
    out = tmp_path / "measured.json"
    assert measure_realrun_b.main(["--bundle", str(BUNDLE), "--out", str(out),
                                    *extra]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


# -- hand-built runs -------------------------------------------------------

def make_run(tmp_path: Path, name: str = "sample-1", *, chapters=None,
             design_findings: dict | None = None) -> Path:
    """A minimal S1 run directory with the artifacts the measurement reads."""
    run = tmp_path / name / "run"
    (run / "design").mkdir(parents=True)
    (run / "draft").mkdir()
    (run / "text").mkdir()

    digests = {prompt: spec["digest"] for prompt, spec in
               registered()["condition"]["prompts"].items()}
    (run / "manifest.json").write_text(json.dumps({
        "prompt_hashes": digests, "run_id": "run", "artifacts": [],
    }), encoding="utf-8")

    design_findings = design_findings or {}
    for doc in DOCS:
        first = design_findings.get(doc, [])
        (run / "design" / f"{doc}.report.json").write_text(json.dumps({
            "doc": doc, "status": "clean", "attempts": 2 if first else 1,
            "repairs": 1 if first else 0,
            "findings": [],
            "first_attempt": {"findings": first, "checks_failed": len(first)},
        }), encoding="utf-8")

    chapters = chapters or [
        {"id": "ch01", "chars": 1100, "day": 1, "location": "灯台",
         "injected": [], "body": "灯台の嵐の夜。鍵を数えた。"},
        {"id": "ch02", "chars": 1050, "day": 4, "location": "王都",
         "injected": [], "body": "王都で鍵屋に会った。"},
        {"id": "ch03", "chars": 1200, "day": 7, "location": "灯台",
         "injected": [], "body": "灯台に戻り、嵐は去った。"},
    ]
    draft_chapters = []
    hits = {"灯台": False, "鍵": False, "嵐": False}
    for chapter in chapters:
        body = chapter["body"]
        for term in hits:
            hits[term] = hits[term] or term in body
        text = (f"{{{{time: day={chapter['day']}}}}}"
                f"{{{{location: {chapter['location']}}}}}\n{body}\n")
        (run / "text" / f"{chapter['id']}.md").write_text(text, encoding="utf-8")
        (run / "draft" / f"{chapter['id']}-attempt-1.txt").write_text(
            body, encoding="utf-8")
        if chapter.get("attempt1_in_band") is False:
            (run / "draft" / f"{chapter['id']}-attempt-1.txt").write_text(
                "短い草稿。" * 300, encoding="utf-8")
        draft_chapters.append({
            "id": chapter["id"], "chars": chapter["chars"], "day": chapter["day"],
            "location": chapter["location"], "injected": chapter["injected"],
            "markers": 2,
        })
    (run / "draft.json").write_text(json.dumps({
        "task": {"id": "t01"}, "chapters": draft_chapters,
        "chars": sum(chapter["chars"] for chapter in chapters),
        "must_include": {"hits": hits,
                         "rate": round(sum(hits.values()) / len(hits), 3)},
        "warnings_ja": [],
    }), encoding="utf-8")
    (run / "audit.json").write_text(json.dumps({
        "summary": {"violations": 0, "by_severity": {}, "by_type": {},
                    "checks_run": 6, "checks_skipped": 0,
                    "ced_per_10k_chars": 0.0},
    }), encoding="utf-8")
    (run / "run-summary.json").write_text(json.dumps({
        "status": "pass", "gates": {}, "error": None,
    }), encoding="utf-8")
    (run / "responses.jsonl").write_text(
        json.dumps({"purpose": "draft:ch01",
                    "response": {"model": "arena-agent-mode",
                                 "model_version": "unversioned-test",
                                 "provenance": {"origin": "fresh"}}}) + "\n",
        encoding="utf-8")
    return run


# -- registration ----------------------------------------------------------

def test_the_registration_is_fixed_and_hashed(tmp_path):
    result = measure(tmp_path)
    prereg_path = BUNDLE / "preregistration.json"
    assert result["preregistration"]["sha256"] == \
        hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    prereg = registered()
    assert prereg["samples_planned"] == 1
    assert prereg["registered_before_any_sample"] is True
    assert set(prereg["rules"]) == {
        "B1_design_first_attempt", "B2_length", "B3_recurring_failure",
        "B4_must_include_exact", "B5_marker_declaration"}
    # The batch A ambiguity is answered by counting both ways, not by one reading.
    assert set(prereg["counting_rules"]["modes"]) == {
        "repair_erased_included", "final_only"}
    assert prereg["condition"]["plan"]["requested"] is False
    # The operating model: the harness runs, the reader runs nothing.
    assert prereg["operation"]["actors"]["reader"].startswith("人")
    assert "端末" in prereg["operation"]["user_actions"]
    assert result["condition"]["canon_matches_registration"] is True


def test_an_empty_batch_says_not_run(tmp_path):
    empty = tmp_path / "empty-bundle"
    empty.mkdir()
    (empty / "preregistration.json").write_text(
        (BUNDLE / "preregistration.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    out = tmp_path / "empty.json"
    assert measure_realrun_b.main([
        "--bundle", str(empty), "--out", str(out),
        "--canon", str(BUNDLE / "inputs" / "canon")]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["schema"] == "realrun-b-v1"
    assert result["samples"] == {}
    assert result["verdicts"]["B1_design_first_attempt"]["verdict"] == "not_run"
    assert result["verdicts"]["B2_length"]["verdict"] == "not_run"
    assert result["verdicts"]["B4_must_include_exact"]["verdict"] == "not_run"
    assert result["verdicts"]["B5_marker_declaration"]["verdict"] == "not_run"
    assert result["verdicts"]["B3_recurring_failure"]["verdict"] == {
        "repair_erased_included": "not_run", "final_only": "not_run"}


# -- the registered arithmetic ---------------------------------------------

def test_a_scripted_run_is_read_and_the_registered_rules_applied(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
         "--task", "t01", "--system", "s1", "--stage", "all",
         "--canon", str(BUNDLE / "inputs" / "canon"),
         "--out", str(tmp_path), "--run-id", "all", "--quiet", "--report-only"],
        capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    run = tmp_path / "all"
    assert (run / "canon" / "characters.json").is_file()

    result = measure(tmp_path, "--sample", f"sample-1={run}")
    sample = result["samples"]["sample-1"]
    assert sample["complete"] is True
    assert sample["design"]["docs_present"] == 8
    assert sample["draft"]["chapters_total"] == 3
    # The scripted fixture writes short chapters: out of band where it was written.
    assert sample["draft"]["chapters_in_length_band"] == 0
    assert {row["out_of_band_cause"]
            for row in sample["draft"]["chapters"].values()} == {"out_at_write"}
    verdicts = result["verdicts"]
    assert verdicts["B2_length"]["verdict"] == "length_out_at_write"
    assert verdicts["B1_design_first_attempt"]["verdict"] == \
        "design_clean_first_attempt"
    assert verdicts["B4_must_include_exact"]["verdict"] == "exact_match_ok"
    # The registration's prompt digests must be the ones the pipeline used.
    assert result["condition"]["prompt_hashes_match_registration"] is True
    assert result["condition"]["provenance_origins"] == {"scripted": 11}


def test_findings_are_counted_both_ways(tmp_path):
    """Batch A's open question: does an erased finding count? Both are reported."""
    finding = {"check": "act_coverage", "severity": "medium"}
    for name in ("sample-1", "sample-2"):
        make_run(tmp_path, name, design_findings={"plot": [finding]})
    result = measure(tmp_path,
                     "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}",
                     "--sample", f"sample-2={tmp_path / 'sample-2' / 'run'}")
    rule = result["verdicts"]["B3_recurring_failure"]
    assert rule["verdict"]["repair_erased_included"] == "recurring"
    assert rule["verdict"]["final_only"] == "no_recurring_failure"
    assert rule["by_check"]["repair_erased_included"]["design.act_coverage"] == \
        ["sample-1", "sample-2"]
    assert "design.act_coverage" not in rule["by_check"]["final_only"]


def test_one_sample_does_not_answer_the_recurrence_rule(tmp_path):
    make_run(tmp_path)
    result = measure(tmp_path, "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    assert result["verdicts"]["B3_recurring_failure"]["verdict"] == {
        "repair_erased_included": "not_evaluable_at_n1",
        "final_only": "not_evaluable_at_n1"}


def test_a_chapter_that_lost_its_length_in_repair_is_named(tmp_path):
    chapters = [
        {"id": "ch01", "chars": 820, "day": 1, "location": "灯台", "injected": [],
         "body": "灯台の嵐の夜。鍵を数えた。", "attempt1_in_band": True},
        {"id": "ch02", "chars": 860, "day": 4, "location": "王都", "injected": [],
         "body": "王都で鍵屋に会った。"},
        {"id": "ch03", "chars": 1200, "day": 7, "location": "灯台", "injected": [],
         "body": "灯台に戻り、嵐は去った。"},
    ]
    make_run(tmp_path, chapters=chapters)
    # Both short chapters were in band on attempt 1 and lost the length in a
    # repair: 1/3 of the delivered chapters is inside the band.
    for chapter_id in ("ch01", "ch02"):
        (tmp_path / "sample-1" / "run" / "draft" /
         f"{chapter_id}-attempt-1.txt").write_text("鍵" * 1200, encoding="utf-8")
    (tmp_path / "sample-1" / "run" / "draft" / "ch01-attempt-1.issues.txt").write_text(
        "uses a forbidden cliché: 選ばれし者\n", encoding="utf-8")
    result = measure(tmp_path, "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    chapter = result["samples"]["sample-1"]["draft"]["chapters"]["ch01"]
    assert chapter["first_attempt_in_length_band"] is True
    assert chapter["out_of_band_cause"] == "lost_in_repair"
    assert result["verdicts"]["B2_length"]["verdict"] == "length_lost_in_repair"
    # A rejected attempt is visible in the inclusive mode only.
    assert result["verdicts"]["B3_recurring_failure"]["by_check"][
        "repair_erased_included"]["draft.forbidden_cliche"] == ["sample-1"]


def test_a_marker_that_disagrees_with_canon_is_reported(tmp_path):
    chapters = [
        {"id": "ch01", "chars": 1100, "day": 2, "location": "港", "injected": [],
         "body": "灯台の嵐の夜。鍵を数えた。"},
        {"id": "ch02", "chars": 1050, "day": 4, "location": "王都", "injected": [],
         "body": "王都で鍵屋に会った。"},
        {"id": "ch03", "chars": 1200, "day": 7, "location": "灯台", "injected": [],
         "body": "灯台に戻り、嵐は去った。"},
    ]
    make_run(tmp_path, chapters=chapters)
    result = measure(tmp_path, "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    rule = result["verdicts"]["B5_marker_declaration"]
    assert rule["verdict"] == "markers_disagree"
    assert rule["marker_mismatches"]["sample-1"][0] == {
        "chapter": "ch01", "kind": "time", "declared": "2", "canon": "1"}


def test_a_marker_supplied_from_canon_is_not_a_pass(tmp_path):
    chapters = [
        {"id": "ch01", "chars": 1100, "day": 1, "location": "灯台",
         "injected": ["{{time: day=1}}"], "body": "嵐の夜。鍵を数えた。"},
        {"id": "ch02", "chars": 1050, "day": 4, "location": "王都", "injected": [],
         "body": "王都で鍵屋に会った。"},
        {"id": "ch03", "chars": 1200, "day": 7, "location": "灯台", "injected": [],
         "body": "灯台に戻り、嵐は去った。"},
    ]
    make_run(tmp_path, chapters=chapters)
    result = measure(tmp_path, "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    assert result["verdicts"]["B5_marker_declaration"]["verdict"] == "markers_repaired"
    assert result["verdicts"]["B5_marker_declaration"]["injected_markers"] == \
        {"sample-1": 1}


def test_a_run_that_stopped_early_is_incomplete_not_invented(tmp_path):
    run = make_run(tmp_path)
    (run / "draft.json").unlink()
    (run / "run-summary.json").unlink()
    (run / "draft" / "ch02-attempt-1.issues.txt").write_text(
        "too short (120 chars, minimum 200)\n", encoding="utf-8")
    (run / "draft" / "ch02-attempt-2.issues.txt").write_text(
        "too short (140 chars, minimum 200)\n", encoding="utf-8")
    result = measure(tmp_path, "--sample", f"sample-1={run}")
    sample = result["samples"]["sample-1"]
    assert sample["complete"] is False
    assert result["verdicts"]["B2_length"]["verdict"] == "incomplete"
    assert result["verdicts"]["B4_must_include_exact"]["verdict"] == "incomplete"
    # The design stage still ran, so B1 is answerable.
    assert result["verdicts"]["B1_design_first_attempt"]["verdict"] == \
        "design_clean_first_attempt"


def test_a_missing_required_word_is_a_gap(tmp_path):
    chapters = [
        {"id": "ch01", "chars": 1100, "day": 1, "location": "灯台", "injected": [],
         "body": "灯台の夜。鍵を数えた。"},          # 嵐 is replaced by a synonym
        {"id": "ch02", "chars": 1050, "day": 4, "location": "王都", "injected": [],
         "body": "大風のなか王都で鍵屋に会った。"},
        {"id": "ch03", "chars": 1200, "day": 7, "location": "灯台", "injected": [],
         "body": "灯台に戻った。"},
    ]
    make_run(tmp_path, chapters=chapters)
    result = measure(tmp_path, "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    rule = result["verdicts"]["B4_must_include_exact"]
    assert rule["verdict"] == "exact_match_gap"
    assert rule["missing_terms"] == {"sample-1": ["嵐"]}


def test_a_stale_prompt_digest_is_reported(tmp_path):
    run = make_run(tmp_path)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["prompt_hashes"]["draft-chapter"] = "0000000000000000"
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = measure(tmp_path, "--sample", f"sample-1={run}")
    assert result["condition"]["prompt_hashes_match_registration"] is False
    assert result["condition"]["prompt_mismatches"][0]["prompt"] == "draft-chapter"


def test_a_changed_canon_is_detected(tmp_path):
    canon = tmp_path / "canon"
    canon.mkdir()
    for path in (BUNDLE / "inputs" / "canon").glob("*.json"):
        (canon / path.name).write_text(path.read_text(encoding="utf-8"),
                                       encoding="utf-8")
    (canon / "facts.json").write_text('{"facts": []}', encoding="utf-8")
    make_run(tmp_path)
    result = measure(tmp_path, "--canon", str(canon),
                     "--sample", f"sample-1={tmp_path / 'sample-1' / 'run'}")
    assert result["condition"]["canon_matches_registration"] is False
