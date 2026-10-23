from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.harness import evaluate, load_patterns, render_markdown  # noqa: E402
from asc.evaluation.judge import (  # noqa: E402
    CommandJudge, FixtureJudge, JudgeError, compare_pairwise,
)
from asc.evaluation.metrics import load_documents, measure  # noqa: E402
from asc.evaluation.rubric import RubricError, load_rubric  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "demo"
BASELINE = REPO_ROOT / "harness" / "cases" / "demo-baseline"
RUBRIC = REPO_ROOT / "harness" / "rubrics" / "story-quality-v0.yaml"
PATTERNS = REPO_ROOT / "harness" / "patterns.yaml"
FIXTURE = REPO_ROOT / "harness" / "fixtures" / "judgements-demo.json"


@pytest.fixture(scope="module")
def rubric():
    return load_rubric(RUBRIC)


@pytest.fixture(scope="module")
def l1_only(tmp_path_factory):
    out = tmp_path_factory.mktemp("eval")
    return evaluate(DEMO / "text", canon_dir=DEMO / "canon", patterns_path=PATTERNS,
                    out_dir=out)


@pytest.fixture(scope="module")
def judge_out(tmp_path_factory):
    return tmp_path_factory.mktemp("eval-judge")


@pytest.fixture(scope="module")
def with_judge(judge_out):
    return evaluate(DEMO / "text", baseline_dir=BASELINE / "text", canon_dir=DEMO / "canon",
                    rubric_path=RUBRIC, patterns_path=PATTERNS,
                    judge=FixtureJudge(FIXTURE), out_dir=judge_out, label="demo")


def test_rubric_dimensions_and_scale(rubric):
    assert rubric.scale_min == 1 and rubric.scale_max == 5
    assert "coherence" in rubric.dimension_ids
    assert len(rubric.dimension_ids) == 6
    for dimension in rubric.dimensions:
        assert dimension.question_ja
        assert 1 in dimension.anchors and 5 in dimension.anchors


def test_invalid_rubric_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("id: x\ndimensions:\n  - id: a\n    anchors: {9: 'out of scale'}\n",
                    encoding="utf-8")
    with pytest.raises(RubricError):
        load_rubric(path)


def test_l1_runs_without_a_judge(l1_only):
    assert l1_only["l2"]["status"] == "skipped"
    assert l1_only["l1"]["metrics"]["chars"] > 0
    assert l1_only["l1"]["continuity"] is not None
    assert l1_only["l1"]["continuity"]["summary"]["by_severity"]["high"] >= 1
    gates = {g["id"]: g["status"] for g in l1_only["gates"]}
    assert gates["no_high_severity_continuity"] == "fail"
    assert gates["all_verdicts_evidenced"] == "skipped"
    assert gates["no_regression"] == "skipped"
    assert l1_only["status"] == "fail"


def test_tickets_are_assigned_to_an_owner(l1_only):
    assert l1_only["tickets"]
    for ticket in l1_only["tickets"]:
        assert ticket["owner"].startswith("skills/")
        assert ticket["action_ja"]
        assert ticket["category"]
    owners = set(l1_only["tickets_by_owner"])
    assert "skills/continuity-ledger" in owners


def test_l2_scores_are_evidence_backed(with_judge):
    assert with_judge["l2"]["status"] == "ok"
    verdicts = with_judge["l2"]["verdicts"]
    assert len(verdicts) == 6
    # prose_control is the only dimension where evidence is optional
    assert not [v for v in verdicts if v["unevidenced"]]
    gates = {g["id"]: g["status"] for g in with_judge["gates"]}
    assert gates["all_verdicts_evidenced"] == "pass"


def test_comparison_separates_defects_from_descriptive_metrics(with_judge):
    comparison = with_judge["comparison"]
    assert "ced_per_10k_chars" in comparison["defects"]
    assert "dialogue_ratio" in comparison["descriptive"]
    assert "dialogue_ratio" not in comparison["defects"]
    # a lower dialogue ratio is not a regression
    assert "dialogue_ratio" not in comparison["regressions"]


def test_ced_is_not_compared_across_audit_coverage(with_judge):
    ced = with_judge["comparison"]["defects"]["ced_per_10k_chars"]
    assert ced["comparable"] is False  # the baseline draft has no markers
    assert ced["coverage"]["baseline"] == 0.0
    assert "ced_per_10k_chars" not in with_judge["comparison"]["regressions"]
    assert with_judge["comparison"]["warnings_ja"]


def test_length_gap_skips_pairwise(with_judge):
    comparison = with_judge["comparison"]
    assert comparison["length_confound"] is True
    assert comparison["pairwise"] is None
    assert "25%" in comparison["pairwise_skipped_ja"]


def test_dimension_deltas_are_reported(with_judge):
    dimensions = with_judge["comparison"]["dimensions"]
    assert dimensions["coherence"]["delta"] == pytest.approx(1.0)
    assert "dimension:coherence" not in with_judge["comparison"]["regressions"]


def test_fixture_judge_requires_a_known_story(rubric):
    judge = FixtureJudge(FIXTURE)
    with pytest.raises(JudgeError):
        judge.score_story("text", rubric, {"story": "unknown"})


def test_command_judge_round_trip(tmp_path, rubric):
    script = tmp_path / "judge.py"
    script.write_text(
        "import json,sys\n"
        "req=json.load(sys.stdin)\n"
        "dims=[{'dimension':d['id'],'score':4,'evidence':[{'path':'ch01.md','line':1}],"
        "'rationale_ja':'ok'} for d in req['rubric']['dimensions']]\n"
        "print(json.dumps({'dimensions':dims}))\n", encoding="utf-8")
    judge = CommandJudge(f"{sys.executable} {script}")
    verdicts = judge.score_story("story", rubric, {"story": "x"})
    assert len(verdicts) == 6
    assert all(v.score == 4 for v in verdicts)


def test_command_judge_rejects_malformed_output(tmp_path, rubric):
    script = tmp_path / "bad.py"
    script.write_text("print('not json')\n", encoding="utf-8")
    judge = CommandJudge(f"{sys.executable} {script}")
    with pytest.raises(JudgeError, match="did not return JSON"):
        judge.score_story("story", rubric, {"story": "x"})


def test_pairwise_detects_position_bias(rubric):
    class BiasJudge(CommandJudge):
        name = "biased"

        def pairwise(self, a, b, rubric, context=None):
            return {"winner": "a", "rationale_ja": "first wins"}

    result = compare_pairwise(BiasJudge("true"), "A", "B", rubric, {})
    assert result["position_bias"] is True
    assert result["winner"] == "tie"


def test_human_labels_calibrate_the_judge(tmp_path, rubric):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"items": [
        {"rater": "r1", "winner": "a"}, {"rater": "r2", "winner": "a"},
        {"rater": "r1", "winner": "tie"}]}, ensure_ascii=False), encoding="utf-8")
    comparison = {"pairwise": {"winner": "a"}}
    from asc.evaluation.harness import _calibrate

    result = _calibrate(labels, comparison)
    assert result["n"] == 3
    assert result["agreement_with_judge"] == pytest.approx(0.667, abs=0.001)
    assert len(result["raters"]) == 2


def test_single_rater_cannot_measure_human_agreement(tmp_path):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"items": [{"rater": "r1", "winner": "a"}]}), encoding="utf-8")
    from asc.evaluation.harness import _calibrate

    result = _calibrate(labels, {"pairwise": {"winner": "a"}})
    assert "warning_ja" in result


def test_metrics_are_deterministic_and_label_proxies():
    documents = load_documents(DEMO / "text")
    first = measure(documents)
    second = measure(load_documents(DEMO / "text"))
    assert first == second
    assert first["style"]["kind"] == "proxy"
    assert first["style"]["sentence_length_cv"] is not None
    assert 0 <= first["dialogue_ratio"] <= 1


def test_forbidden_patterns_report_positions(tmp_path):
    text = tmp_path / "ch01.md"
    text.write_text("とてもとても長い夜だった。\nつまり、そういうことだ。\n", encoding="utf-8")
    from asc.evaluation.metrics import find_forbidden

    hits = find_forbidden(load_documents(tmp_path), load_patterns(PATTERNS))
    ids = {h["id"] for h in hits}
    assert {"doubled_adverb", "meta_summary"} <= ids
    assert all("line" in h["evidence"] for h in hits)


def test_report_renders_all_three_layers(with_judge):
    markdown = render_markdown(with_judge)
    assert "L1 決定論的検査" in markdown
    assert "L2 モデル判定" in markdown
    assert "L3 人間評価" in markdown
    assert "改善チケット" in markdown
    assert "この評価で分からないこと" in markdown


def test_outputs_are_written(with_judge, judge_out):
    evaluation = json.loads((judge_out / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["candidate_label"] == "demo"
    assert (judge_out / "report.md").is_file()
    assert (judge_out / "continuity.json").is_file()


def test_unevidenced_verdict_fails_the_gate(tmp_path):
    """A judge that returns scores without evidence must not be able to pass."""
    script = tmp_path / "judge.py"
    script.write_text(
        "import json,sys\n"
        "req=json.load(sys.stdin)\n"
        "dims=[{'dimension':d['id'],'score':4,'evidence':[],'rationale_ja':'trust me'}"
        " for d in req['rubric']['dimensions']]\n"
        "print(json.dumps({'dimensions':dims}))\n", encoding="utf-8")
    results = evaluate(DEMO / "text",
                       rubric_path=RUBRIC,
                       judge=CommandJudge(f"{sys.executable} {script}"))
    gates = {g["id"]: g["status"] for g in results["gates"]}
    assert gates["all_verdicts_evidenced"] == "fail"
    assert all(v["unevidenced"] for v in results["l2"]["verdicts"]
               if v["dimension"] != "prose_control")


def test_cli_writes_outputs_and_returns_status(tmp_path):
    script = str(REPO_ROOT / "scripts" / "run_evaluation.py")
    completed = subprocess.run(
        [sys.executable, script, "--candidate", str(DEMO / "text"),
         "--baseline", str(BASELINE / "text"), "--canon", str(DEMO / "canon"),
         "--rubric", str(RUBRIC), "--patterns", str(PATTERNS),
         "--judge-fixture", str(FIXTURE), "--out", str(tmp_path / "out")],
        capture_output=True, text=True)
    assert completed.returncode == 1  # high severity continuity violation
    assert (tmp_path / "out" / "evaluation.json").is_file()
    assert (tmp_path / "out" / "report.md").is_file()
    summary = json.loads(completed.stdout)
    assert summary["gates"]["all_verdicts_evidenced"] == "pass"


def test_cli_returns_2_on_bad_input(tmp_path):
    script = str(REPO_ROOT / "scripts" / "run_evaluation.py")
    completed = subprocess.run(
        [sys.executable, script, "--candidate", str(tmp_path / "missing")],
        capture_output=True, text=True)
    assert completed.returncode == 2
