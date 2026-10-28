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
    assert report["prompt"]["version"] == "1.2"


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

def test_design_notes_name_only_the_chapters_plot_scenes_and_voice(
        task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    build_design(task, ScriptedProvider(responses), ledger, canon,
                 prompt_dir=PROMPTS)
    notes = design_notes_for_chapter(ledger.path / "design", "ch01", canon)
    assert "幕 setup／問い: 鍵を追う資格は誰の手にあるか" in notes
    assert "転換点 t1／選択: アリアは父の命令に背き" in notes
    assert "s01" in notes
    assert "文体" in notes
    assert "記録と情のどちらを取るか" not in notes  # ch02's act
    assert "転換点 t2" not in notes
    assert "鍵は返るが借り手の死の真相は残る" not in notes  # full ending
    assert design_notes_for_chapter(None, "ch01", canon) == "（設計メモなし）"
    assert design_notes_for_chapter(tmp_path, "ch01", canon) == "（設計メモなし）"


def test_draft_prompt_carries_checked_plot_per_chapter(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    build_design(task, ScriptedProvider(responses), ledger, canon,
                 prompt_dir=PROMPTS)
    provider = ScriptedProvider(responses)
    build_story(task, provider, ledger, canon=canon, prompt_dir=PROMPTS,
                design_dir=ledger.path / "design")
    assert [call.purpose for call in provider.calls] == [
        "draft:ch01", "draft:ch02", "draft:ch03"]
    questions = ["鍵を追う資格は誰の手にあるか", "記録と情のどちらを取るか",
                 "自分の選択で灯りを守れるか"]
    for index, call in enumerate(provider.calls):
        assert "設計メモ" in call.prompt
        assert "設定台帳と矛盾しない範囲で" in call.prompt
        assert "幕 " in call.prompt
        assert "転換点 t" + str(index + 1) in call.prompt
        assert questions[index] in call.prompt
        for other in questions[:index] + questions[index + 1:]:
            assert other not in call.prompt
    assert "s01" in provider.calls[0].prompt  # scene and voice still flow
    assert "文体" in provider.calls[0].prompt
    recorded = [json.loads(line) for line in (ledger.path / "responses.jsonl")
                .read_text(encoding="utf-8").splitlines()]
    recorded = [row for row in recorded if row["purpose"].startswith("draft:")]
    assert [row["prompt_hash"] for row in recorded] == [
        call.prompt_hash for call in provider.calls]
    assert "幕" in recorded[0]["prompt"]
    assert "draft-chapter" in json.loads((ledger.path / "manifest.json")
                                         .read_text(encoding="utf-8"))["prompt_hashes"]


def test_plot_memo_ablation_changes_only_plot_lines_in_draft_prompts(
        task, responses, tmp_path):
    """A paired prompt ablation keeps canon, scene, voice and prior text fixed."""
    source = make_ledger(tmp_path / "source")
    canon = plan_canon(task, responses, source)
    build_design(task, ScriptedProvider(responses), source, canon,
                 prompt_dir=PROMPTS)
    shared_design = source.path / "design"

    with_plot = ScriptedProvider(responses)
    build_story(task, with_plot, make_ledger(tmp_path / "with"), canon=canon,
                prompt_dir=PROMPTS, design_dir=shared_design)
    without_plot = ScriptedProvider(responses)
    build_story(task, without_plot, make_ledger(tmp_path / "without"), canon=canon,
                prompt_dir=PROMPTS, design_dir=shared_design,
                include_plot_memos=False)

    assert len(with_plot.calls) == len(without_plot.calls) == 3
    for included, omitted in zip(with_plot.calls, without_plot.calls):
        assert included.purpose == omitted.purpose
        assert included.temperature == omitted.temperature
        assert included.seed == omitted.seed
        assert "- 幕 " in included.prompt and "- 転換点 " in included.prompt
        assert "- 幕 " not in omitted.prompt and "- 転換点 " not in omitted.prompt
        assert "対立:" in included.prompt and "対立:" in omitted.prompt
        assert "文体" in included.prompt and "文体" in omitted.prompt
        # Once the designated chapter-local Plot memo lines are removed, the
        # complete request is byte-identical, including canon/prior context.
        without_plot_lines = "\n".join(
            line for line in included.prompt.split("\n")
            if not line.startswith("- 幕 ") and not line.startswith("- 転換点 "))
        assert without_plot_lines == omitted.prompt


def test_run_pipeline_draft_ablation_reuses_shared_inputs(task, responses, tmp_path):
    source = make_ledger(tmp_path / "source")
    canon = plan_canon(task, responses, source)
    build_design(task, ScriptedProvider(responses), source, canon,
                 prompt_dir=PROMPTS)
    shared_design = source.path / "design"
    shared_canon = source.path / "canon"

    outputs = {}
    for arm, extra in (("without-plot", ["--no-plot-memos"]), ("with-plot", [])):
        run_root = tmp_path / arm
        command = [
            sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"),
            "--task", "t01", "--system", "s1", "--stage", "draft",
            "--provider", "scripted", "--script", str(FIXTURE),
            "--canon", str(shared_canon), "--design-dir", str(shared_design),
            "--out", str(run_root), "--run-id", arm,
            "--report-only", "--quiet", *extra,
        ]
        subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        run_dir = run_root / arm
        outputs[arm] = {
            "summary": json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8")),
            "prompts": [json.loads(row)["prompt"] for row in
                        (run_dir / "responses.jsonl").read_text(encoding="utf-8").splitlines()],
        }

    base = outputs["without-plot"]
    treatment = outputs["with-plot"]
    assert base["summary"]["draft_condition"]["plot_memos"] is False
    assert treatment["summary"]["draft_condition"]["plot_memos"] is True
    assert base["summary"]["draft_condition"]["canon_source"] == \
        treatment["summary"]["draft_condition"]["canon_source"]
    assert base["summary"]["draft_condition"]["design_source"] == \
        treatment["summary"]["draft_condition"]["design_source"]
    assert base["summary"]["draft_condition"]["canon_files_sha256"] == \
        treatment["summary"]["draft_condition"]["canon_files_sha256"]
    assert base["summary"]["draft_condition"]["design_files_sha256"] == \
        treatment["summary"]["draft_condition"]["design_files_sha256"]
    assert len(base["prompts"]) == len(treatment["prompts"]) == 3
    for prompt_with, prompt_without in zip(treatment["prompts"], base["prompts"]):
        scrubbed = "\n".join(
            line for line in prompt_with.split("\n")
            if not line.startswith("- 幕 ") and not line.startswith("- 転換点 "))
        assert scrubbed == prompt_without


def test_unresolved_plot_is_omitted_from_the_draft_prompt(
        task, responses, tmp_path):
    bad = json.loads(responses["design:plot:t01"])
    bad["acts"][0]["chapters"] = ["ch99"]  # fail the acts_cover check
    bad["turns"][0]["choice_ja"] = "未検証の転換点を本文に渡さない"
    text = json.dumps(bad, ensure_ascii=False)
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    result = build_design(task, StubProvider({
        "design:plot": [text], "design:plot:repair": [text],
    }), ledger, canon, prompt_dir=PROMPTS, docs=("plot",))
    assert result.as_dict()["docs"]["plot"]["status"] == "unresolved"
    assert (ledger.path / "design" / "plot.json").is_file()  # fail-open
    notes = design_notes_for_chapter(ledger.path / "design", "ch01", canon)
    assert "未解決" in notes
    assert "未検証の転換点" not in notes
    provider = ScriptedProvider(responses)
    build_story(task, provider, ledger, canon=canon, prompt_dir=PROMPTS,
                design_dir=ledger.path / "design")
    assert "未解決" in provider.calls[0].prompt
    assert "未検証の転換点" not in provider.calls[0].prompt


def test_missing_plot_is_not_used_and_the_draft_explains_why(
        task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    result = build_design(task, StubProvider({
        "design:plot": ["not json"], "design:plot:repair": ["still not json"],
    }), ledger, canon, prompt_dir=PROMPTS, docs=("plot",))
    assert result.as_dict()["docs"]["plot"]["status"] == "missing"
    assert not (ledger.path / "design" / "plot.json").exists()
    assert (ledger.path / "design" / "plot.report.json").is_file()
    notes = design_notes_for_chapter(ledger.path / "design", "ch01", canon)
    assert "設計書が欠損" in notes
    provider = ScriptedProvider(responses)
    build_story(task, provider, ledger, canon=canon, prompt_dir=PROMPTS,
                design_dir=ledger.path / "design")
    assert "設計書が欠損" in provider.calls[0].prompt
    assert "- 幕 " not in provider.calls[0].prompt


def test_carried_plot_is_rechecked_and_stale_or_unreadable_plot_is_omitted(
        task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design_dir = tmp_path / "carried"
    design_dir.mkdir()
    plot_path = design_dir / "plot.json"
    report_path = design_dir / "plot.report.json"
    plot_path.write_text(responses["design:plot:t01"], encoding="utf-8")

    # Carried project revisions have no per-document report, but a fresh
    # check against the current canon authorizes the note.
    assert "検査記録と canon がない" in design_notes_for_chapter(design_dir, "ch01")
    assert "幕 setup" in design_notes_for_chapter(design_dir, "ch01", canon)

    stale = json.loads(responses["design:plot:t01"])
    stale["acts"][0]["chapters"] = ["ch99"]
    plot_path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
    assert "現在の canon で未解決" in design_notes_for_chapter(
        design_dir, "ch01", canon)  # inherited without report, but still invalid
    report_path.write_text('{"status": "clean"}', encoding="utf-8")
    assert "現在の canon で未解決" in design_notes_for_chapter(
        design_dir, "ch01", canon)
    assert "幕 setup" not in design_notes_for_chapter(design_dir, "ch01", canon)

    plot_path.write_text(responses["design:plot:t01"], encoding="utf-8")
    report_path.write_text('{"status": "unresolved"}', encoding="utf-8")
    assert "幕メモを省略" in design_notes_for_chapter(design_dir, "ch01", canon)
    report_path.write_text("{bad report", encoding="utf-8")
    assert "読取不可" in design_notes_for_chapter(design_dir, "ch01", canon)
    report_path.write_text('{"status": "clean"}', encoding="utf-8")
    plot_path.write_text("{bad plot", encoding="utf-8")
    assert "読めない" in design_notes_for_chapter(design_dir, "ch01", canon)


def test_plot_note_matches_chapter_alias_and_flattens_multiline_fields(
        task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design_dir = tmp_path / "design"
    design_dir.mkdir()
    plot = json.loads(responses["design:plot:t01"])
    plot["acts"][0]["chapters"] = ["第1章"]
    plot["turns"][0]["chapter"] = "第1章"
    plot["acts"][0]["question"] = "鍵を追う資格は\n誰の手にあるか"
    (design_dir / "plot.json").write_text(
        json.dumps(plot, ensure_ascii=False), encoding="utf-8")
    (design_dir / "plot.report.json").write_text(
        '{"status": "clean"}', encoding="utf-8")
    notes = design_notes_for_chapter(design_dir, "ch01", canon)
    assert "幕 setup／問い: 鍵を追う資格は 誰の手にあるか" in notes
    assert "転換点 t1" in notes
    assert "第1章" not in notes  # code and checker normalize the same way


def test_plot_handoff_does_not_require_three_acts(task, responses, tmp_path):
    ledger = make_ledger(tmp_path)
    canon = plan_canon(task, responses, ledger)
    design_dir = tmp_path / "two-acts"
    design_dir.mkdir()
    plot = json.loads(responses["design:plot:t01"])
    plot["acts"] = [
        {"id": "opening", "chapters": ["ch01", "ch02"], "question": "誰が鍵を守るか"},
        {"id": "closing", "chapters": ["ch03"], "question": "灯りを守れるか"},
    ]
    (design_dir / "plot.json").write_text(
        json.dumps(plot, ensure_ascii=False), encoding="utf-8")
    (design_dir / "plot.report.json").write_text(
        '{"status": "clean"}', encoding="utf-8")
    assert "幕 opening／問い: 誰が鍵を守るか" in design_notes_for_chapter(
        design_dir, "ch02", canon)
    assert "幕 closing" not in design_notes_for_chapter(design_dir, "ch02", canon)


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
    recorded = [json.loads(line) for line in (
        run_dirs[0] / "responses.jsonl"
    ).read_text(encoding="utf-8").splitlines()]
    drafts = [row["prompt"] for row in recorded if row["purpose"].startswith("draft:")]
    assert drafts and all("（設計メモなし）" in prompt and "- 幕 " not in prompt
                          for prompt in drafts)


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
    recorded = [json.loads(line) for line in (
        Path(cell["run_dir"]) / "responses.jsonl"
    ).read_text(encoding="utf-8").splitlines()]
    draft = next(row for row in recorded if row["purpose"] == "draft:ch01")
    assert "幕 setup／問い" in draft["prompt"]
    assert "転換点 t1／選択" in draft["prompt"]
    assert "転換点 t2／選択" not in draft["prompt"]


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
