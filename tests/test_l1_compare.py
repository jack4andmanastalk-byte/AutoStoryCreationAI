"""The L1 arm comparison: same measurements, two generation conditions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import compare_l1_arms  # noqa: E402

SLICE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
CANON = SLICE / "inputs" / "canon"
REWRITE = SLICE / "inputs" / "rewrite"


def run(tmp_path, *arms: str, task: str = "t01"):
    out = tmp_path / "results.json"
    completed = compare_l1_arms.main([
        "--task", task, "--canon", str(CANON),
        *[part for arm in arms for part in ("--arm", arm)],
        "--out", str(out),
    ])
    assert completed == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_two_chapter_directories_produce_a_comparable_profile(tmp_path):
    report = run(tmp_path, f"a={REWRITE}", f"b={REWRITE}")
    assert report["schema"] == "l1-arm-comparison-v1"
    assert report["provider"]["model"] == "arena-agent-mode"
    assert report["evaluation_scope"]["gate_status"]["G3"] == "frozen_not_measured"
    arm = report["arms"]["a"]
    assert arm["source"] == "chapter_files"
    assert arm["documents"] == 3
    assert arm["must_include"]["rate"] == 1.0
    assert arm["forbidden"]["hits"] == 0
    assert arm["audit"]["checks_skipped"] == 0
    assert arm["style"]["sentence_length_cv"] is not None
    assert set(arm["per_chapter_chars"]) == {"ch01", "ch02", "ch03"}
    # Comparing an arm with itself is the whole point of the delta: all zero.
    for row in report["delta"]["a"].values():
        assert row["difference"] == 0
    assert report["limits"]


def test_relay_responses_can_be_compared_as_an_arm(tmp_path):
    """A recorded run outlives the prompt, so its answers are an arm too."""
    relay = tmp_path / "relay"
    relay.mkdir()
    for index, chapter in enumerate(("ch01", "ch02"), start=1):
        (relay / f"s1-t01-s{index}-draft-{chapter}-a1.json").write_text(
            json.dumps({"text": f"{{{{time: day={index}}}}}本文{index}。",
                        "model": "arena-agent-mode"}, ensure_ascii=False),
            encoding="utf-8")
    # A Stage A response has no chapter in its key and must be ignored.
    (relay / "s1-t01-s0-stage_a-a1.json").write_text(
        json.dumps({"text": "{not prose}"}, ensure_ascii=False), encoding="utf-8")

    report = run(tmp_path, f"relay={relay}", f"text={REWRITE}")
    arm = report["arms"]["relay"]
    assert arm["source"] == "relay_responses"
    assert arm["documents"] == 2
    assert set(arm["per_chapter_chars"]) == {"ch01", "ch02"}
    assert arm["must_include"]["rate"] < 1.0


def test_a_directory_without_chapters_is_refused(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.txt.json").write_text(json.dumps({"no": "text"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        run(tmp_path, f"a={empty}", f"b={REWRITE}")


def test_exactly_two_arms_are_required(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path, f"only={REWRITE}")
