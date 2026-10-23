"""L2/L3 calibration: kappa math, labels loading, judge-vs-majority."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.calibration import (  # noqa: E402
    CalibrationError, cohen_kappa, judge_agreement, load_judgements, majority,
    rater_agreement,
)

LABELS = REPO_ROOT / "harness" / "fixtures" / "labels-demo"
VERDICTS = REPO_ROOT / "harness" / "fixtures" / "verdicts-demo.json"


def test_kappa_is_one_for_perfect_agreement():
    result = cohen_kappa([("a", "a"), ("b", "b"), ("tie", "tie")])
    assert result["kappa"] == 1.0
    assert result["agreement"] == 1.0


def test_kappa_is_none_without_variance():
    result = cohen_kappa([("a", "a"), ("a", "a")])
    assert result["kappa"] is None
    assert result["agreement"] == 1.0


def test_demo_labels_give_kappa_half():
    """2 名×3 ペアの fixture は κ=0.5（2/3 一致、偶然一致 1/3）。"""
    report = rater_agreement(load_judgements(LABELS))
    assert report["status"] == "ok"
    assert report["raters"] == ["rater-a", "rater-b"]
    assert report["mean_kappa"] == 0.5


def test_single_rater_warns_instead_of_measuring(tmp_path):
    only = tmp_path / "judgements"
    only.mkdir()
    (only / "pair-001.json").write_text(
        json.dumps({"rater_id": "solo", "pair_id": "pair-001", "winner": "a"}),
        encoding="utf-8")
    report = rater_agreement(load_judgements(only))
    assert report["status"] == "single_rater"
    assert "1 名" in report["warning_ja"]


def test_bad_winner_is_rejected(tmp_path):
    bad = tmp_path / "judgements"
    bad.mkdir()
    (bad / "pair-001.json").write_text(
        json.dumps({"rater_id": "r", "pair_id": "pair-001", "winner": "A作"}),
        encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_judgements(bad)


def test_tied_vote_is_a_tie_not_a_guess():
    votes = [{"rater_id": "a", "pair_id": "p", "winner": "a"},
             {"rater_id": "b", "pair_id": "p", "winner": "tie"}]
    assert majority(votes) == {"p": "tie"}


def test_judge_vs_majority_rate():
    labels = load_judgements(LABELS)
    raw = json.loads(VERDICTS.read_text(encoding="utf-8"))
    verdicts = {k: v["winner"] for k, v in raw.items()}
    report = judge_agreement(labels, verdicts)
    assert report["rate"] == 0.667
    assert report["n"] == 3


def _stub_judge(path: Path, winner: str) -> Path:
    script = path / "judge.py"
    script.write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        f"print(json.dumps({{'winner': '{winner}', 'rationale_ja': 'stub'}}))\n",
        encoding="utf-8")
    return script


def test_judge_pairs_runs_every_pair_twice(tmp_path):
    pairs = tmp_path / "pairs"
    pairs.mkdir()
    (pairs / "pair-001.json").write_text(
        json.dumps({"pair_id": "pair-001", "a": "甲の本文。", "b": "乙の本文。"}),
        encoding="utf-8")
    stub = _stub_judge(tmp_path, "tie")
    out = tmp_path / "verdicts.json"
    completed = subprocess.run(
        [sys.executable, "scripts/judge_pairs.py", "--pairs", str(pairs),
         "--judge-command", f"{sys.executable} {stub}", "--out", str(out),
         "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    verdicts = json.loads(out.read_text(encoding="utf-8"))
    assert verdicts["pair-001"]["winner"] == "tie"


def test_judge_pairs_treats_position_bias_as_tie(tmp_path):
    """同じ位置を選び続けたら順序バイアスとして引き分けに倒す。"""
    pairs = tmp_path / "pairs"
    pairs.mkdir()
    (pairs / "pair-001.json").write_text(
        json.dumps({"pair_id": "pair-001", "a": "甲の本文。", "b": "乙の本文。"}),
        encoding="utf-8")
    stub = _stub_judge(tmp_path, "a")  # always picks the first side
    out = tmp_path / "verdicts.json"
    completed = subprocess.run(
        [sys.executable, "scripts/judge_pairs.py", "--pairs", str(pairs),
         "--judge-command", f"{sys.executable} {stub}", "--out", str(out),
         "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    verdicts = json.loads(out.read_text(encoding="utf-8"))
    assert verdicts["pair-001"]["winner"] == "tie"
    assert verdicts["pair-001"]["position_bias"] is True
