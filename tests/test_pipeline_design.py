"""The Design step must validate each document and fail open, not open-ended.

The provider is scripted or stubbed: these tests check the wiring (prompts,
repair rounds, reports, the draft/voice connections), not the quality of any
model.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    RunLedger, ScriptedProvider, build_design, build_plan, build_story,
    design_notes_for_chapter, load_tasks,
)
from asc.pipeline.design import DOCS  # noqa: E402
from asc.pipeline.llm import GenerationRequest, GenerationResult  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402

TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
FIXTURE = REPO_ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"
PROMPTS = REPO_ROOT / "prompts"


@pytest.fixture(scope="module")
def tasks():
    return load_tasks(TASKS)


@pytest.fixture()
def task(tasks):
    return tasks.get("t01")


@pytest.fixture()
def responses():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"]


def make_ledger(tmp_path: Path, system: str = "s1") -> RunLedger:
    return RunLedger.create(tmp_path / "runs", task_id="t01", system=system, seed=0,
                            protocol_version="protocol-v1")


def plan_canon(task, responses, ledger):
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    return load_canon(ledger.path / "canon")


class StubProvider:
    """Returns canned texts per purpose, then repeats the last one."""

    name = "stub"
    model = "stub"
    model_version = "v1"

    def __init__(self, texts: dict[str, list[str]]):
        self.texts = texts
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        options = self.texts.get(request.purpose, ["{}"])
        text = options[min(len(self.calls) - 1, len(options) - 1)]
        return GenerationResult(text=text, provider=self.name, model=self.model,
                                model_version=self.model_version)


# -- the happy path ---------------------------------------------------------

def test_scripted_design_run_is_clean(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design = build_design(task, ScriptedProvider(responses), ledger, canon,
                          prompt_dir=PROMPTS)
    assert design.as_dict()["unresolved"] == []
    assert design.as_dict()["missing"] == []
    assert design.as_dict()["findings"] == 0
    for name in DOCS:
        assert (ledger.path / "design" / f"{name}.json").is_file()
        assert (ledger.path / "design" / f"{name}.report.json").is_file()
    assert (ledger.path / "design.json").is_file()


def test_each_document_reports_attempts_and_status(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design = build_design(task, ScriptedProvider(responses), ledger, canon,
                          prompt_dir=PROMPTS, docs=("brief", "voice"))
    docs = design.as_dict()["docs"]
    assert set(docs) == {"brief", "voice"}
    assert docs["brief"]["status"] == "clean"
    assert docs["brief"]["attempts"] == 1


def test_brief_prompt_matches_the_mechanical_element_and_axis_checks(
        task, responses, tmp_path):
    provider = StubProvider({"design:brief": [responses["design:brief:t01"]]})
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    build_design(task, provider, ledger, canon, prompt_dir=PROMPTS, docs=("brief",))

    prompt = provider.calls[0].prompt
    assert "一字一句そのまま" in prompt
    assert "structure / character / world" in prompt
    assert "10 字以上" in prompt
    report = json.loads((ledger.path / "design" / "brief.report.json"
                         ).read_text(encoding="utf-8"))
    assert report["prompt"]["version"] == "1.1"


def test_unknown_document_is_a_programmer_error(task, responses, tmp_path):
    from asc.pipeline import DesignError
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    with pytest.raises(DesignError, match="unknown design document"):
        build_design(task, ScriptedProvider(responses), ledger, canon,
                     prompt_dir=PROMPTS, docs=("branch",))


# -- repair and fail-open ----------------------------------------------------

def test_repair_round_fixes_a_bad_first_attempt(task, responses, tmp_path):
    good = responses["design:brief:t01"]
    provider = StubProvider({"design:brief": ["not json at all", good],
                             "design:brief:repair": [good]})
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design = build_design(task, provider, ledger, canon, prompt_dir=PROMPTS,
                          docs=("brief",))
    assert design.as_dict()["docs"]["brief"]["status"] == "clean"
    assert design.as_dict()["docs"]["brief"]["attempts"] == 2
    assert (ledger.path / "design" / "brief.json").is_file()


def test_unresolved_documents_are_recorded_not_raised(task, responses, tmp_path):
    bad = json.dumps({"logline": "短い"}, ensure_ascii=False)
    provider = StubProvider({"design:brief": [bad], "design:brief:repair": [bad]})
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design = build_design(task, provider, ledger, canon, prompt_dir=PROMPTS,
                          docs=("brief",), max_attempts=2)
    doc = design.as_dict()["docs"]["brief"]
    assert doc["status"] == "unresolved"
    assert doc["attempts"] == 2
    assert doc["findings"] > 0
    report = json.loads((ledger.path / "design" / "brief.report.json"
                         ).read_text(encoding="utf-8"))
    assert report["status"] == "unresolved"
    assert report["findings"]


def test_unparseable_documents_are_missing_not_fatal(task, responses, tmp_path):
    good_voice = responses["design:voice:t01"]
    provider = StubProvider({"design:brief": ["{{{nope"], "design:brief:repair": ["{{{nope"],
                             "design:voice": [good_voice]})
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design = build_design(task, provider, ledger, canon, prompt_dir=PROMPTS,
                          docs=("brief", "voice"), max_attempts=2)
    summary = design.as_dict()
    assert summary["docs"]["brief"]["status"] == "missing"
    assert not (ledger.path / "design" / "brief.json").exists()
    # the run continues with the remaining documents
    assert summary["docs"]["voice"]["status"] == "clean"


# -- the draft connection -----------------------------------------------------

def test_design_notes_name_the_chapters_scenes(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    build_design(task, ScriptedProvider(responses), ledger, canon,
                 prompt_dir=PROMPTS)
    notes = design_notes_for_chapter(ledger.path / "design", "ch01")
    assert "s01" in notes
    assert "文体" in notes
    assert design_notes_for_chapter(None, "ch01") == "（設計メモなし）"
    assert design_notes_for_chapter(tmp_path, "ch01") == "（設計メモなし）"


def test_draft_prompt_carries_scene_notes_when_design_ran(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    build_design(task, ScriptedProvider(responses), ledger, canon,
                 prompt_dir=PROMPTS)
    provider = ScriptedProvider(responses)
    build_story(task, provider, ledger, canon=canon, prompt_dir=PROMPTS,
                design_dir=ledger.path / "design")
    first = provider.calls[0]
    assert "s01" in first.prompt
    assert "設計メモ" in first.prompt


def test_draft_prompt_says_so_when_no_design_ran(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    provider = ScriptedProvider(responses)
    build_story(task, provider, ledger, canon=canon, prompt_dir=PROMPTS)
    assert "（設計メモなし）" in provider.calls[0].prompt


# -- the pipeline and experiment wiring ----------------------------------------

def test_cli_design_stage_runs_from_an_existing_canon(tmp_path):
    planned = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--task", "t01",
         "--system", "s1", "--stage", "plan",
         "--out", str(tmp_path / "runs"), "--report-only", "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert planned.returncode == 0, planned.stderr
    canon_dir = next((tmp_path / "runs").iterdir()) / "canon"
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--task", "t01",
         "--system", "s1", "--stage", "design", "--canon", str(canon_dir),
         "--out", str(tmp_path / "runs"), "--report-only", "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    run_dirs = list((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 2
    designed = [d for d in run_dirs if (d / "design.json").is_file()]
    assert len(designed) == 1


def test_cli_no_design_skips_and_says_so(tmp_path):
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--task", "t01",
         "--system", "s1", "--no-design",
         "--out", str(tmp_path / "runs"), "--report-only", "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    run_dirs = list((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 1
    summary = json.loads((run_dirs[0] / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["design"]["status"] == "skipped"


def test_cli_s3_uses_the_designed_voice(tmp_path):
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--task", "t01",
         "--system", "s3",
         "--script", str(REPO_ROOT / "benchmarks/protocol-v1/fixtures"
                         / "pipeline-s2s3-demo.json"),
         "--out", str(tmp_path / "runs"), "--report-only", "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    run_dirs = list((tmp_path / "runs").iterdir())
    voice = json.loads((run_dirs[0] / "voice.json").read_text(encoding="utf-8"))
    assert voice["guide_from_spec"] is True


def test_experiment_cell_records_design_counts(task, responses, tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_experiment
    tasks = load_tasks(TASKS)
    cell = run_experiment.run_cell(
        task, "s1", 0, ScriptedProvider(responses), tasks,
        tmp_path / "runs", 0.8)
    assert cell["status"] == "ok"
    assert cell["design"] == "on"
    assert cell["design_findings"] == 0
    assert cell["design_unresolved"] == 0
    assert cell["provider_requests"] == 12
    assert cell["design_attempts"] == 8
    assert cell["design_repairs"] == 0
    assert cell["design_first_attempt_findings"] == 0
    assert cell["response_provenance"] == {
        "counts": {"scripted": 12}, "reused_source_run_ids": []}


def test_experiment_cell_aggregates_first_attempt_repairs_and_provenance(
        task, responses, tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_experiment
    tasks = load_tasks(TASKS)
    bad_brief = json.loads(responses["design:brief:t01"])
    bad_brief["logline"] = "短い"
    repaired = dict(responses)
    repaired["design:brief:t01"] = json.dumps(bad_brief, ensure_ascii=False)
    repaired["design:brief:repair:t01"] = responses["design:brief:t01"]

    cell = run_experiment.run_cell(
        task, "s1", 0, ScriptedProvider(repaired), tasks,
        tmp_path / "runs", 0.8)

    assert cell["status"] == "ok"
    assert cell["provider_requests"] == 13
    assert cell["design_attempts"] == 9
    assert cell["design_repairs"] == 1
    assert cell["design_first_attempt_findings"] > 0
    assert cell["design_findings"] == 0
    assert cell["response_provenance"]["counts"] == {"scripted": 13}
    run_dir = Path(cell["run_dir"])
    report = json.loads((run_dir / "design" / "brief.report.json"
                         ).read_text(encoding="utf-8"))
    assert report["attempts"] == 2
    assert report["repairs"] == 1
    assert report["first_attempt"]["findings"]
    assert report["findings"] == []

    aggregate = run_experiment.aggregate([cell])["by_system"]["s1"]
    assert aggregate["provider_requests"]["mean"] == 13
    assert aggregate["design_attempts"]["mean"] == 9
    assert aggregate["design_repairs"]["mean"] == 1
    assert aggregate["design_first_attempt_findings"]["mean"] > 0
    assert aggregate["response_provenance"] == {
        "counts": {"scripted": 13}, "reused_source_run_ids": []}
