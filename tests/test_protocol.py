"""The frozen evaluation protocol (docs/protocol.md) must stay machine-checkable.

If the task set drifts without a version bump, comparisons across experiments stop
meaning anything. These tests pin the shape of v1, not its content.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_MD = REPO_ROOT / "docs" / "protocol.md"
TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"

REQUIRED_SECTIONS = [
    "## 1. 問い",
    "## 2. タスクセット",
    "## 3. 生成条件",
    "## 4. 測定",
    "## 5. 合格閾値（事前登録）",
    "## 6. 対照群",
    "## 7. 手続き",
    "## 8. 報告規則",
    "## 9. 版の上げ方",
]


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(TASKS.read_text(encoding="utf-8"))


def test_task_set_is_frozen_at_ten(spec):
    assert spec["protocol"] == "protocol-v1"
    assert len(spec["tasks"]) == 10
    ids = [task["id"] for task in spec["tasks"]]
    assert ids == sorted(ids)
    assert len(set(ids)) == 10


def test_every_task_is_measurable(spec):
    for task in spec["tasks"]:
        assert task["genre"] in spec["genres"], task["id"]
        assert task["control"] in spec["controls"], task["id"]
        assert task["title_ja"]
        assert 40 <= len(task["logline"]) <= 220, task["id"]
        assert 2 <= len(task["must_include"]) <= 3, task["id"]
        assert task["must_include"] == list(dict.fromkeys(task["must_include"]))
        assert 1 <= len(task["avoid"]) <= 2, task["id"]
        # an avoid term must not be a required word, or the task contradicts itself
        assert not set(task["avoid"]) & set(task["must_include"]), task["id"]


def test_genre_distribution_matches_the_protocol(spec):
    counts: dict[str, int] = {}
    for task in spec["tasks"]:
        counts[task["genre"]] = counts.get(task["genre"], 0) + 1
    assert counts == {"fantasy": 4, "contemporary": 3, "history": 3}


def test_scale_is_three_chapters(spec):
    assert spec["chapters"] == 3
    low, high = spec["target_chars"]
    assert 3000 <= low < high <= 4500
    assert high / spec["chapters"] >= 1000


def test_protocol_document_has_the_required_sections():
    text = PROTOCOL_MD.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, section
    assert "protocol-v1" in text


def test_protocol_states_gates_and_their_thresholds():
    text = PROTOCOL_MD.read_text(encoding="utf-8")
    for gate in ("G1", "G2", "G3", "G4", "G5"):
        assert re.search(rf"\| {gate} \|", text), gate
    # the thresholds are pre-registered numbers, not adjectives
    assert "80%" in text and "0.40" in text and "0.70" in text


def test_protocol_forbids_aggregate_scores_and_requires_manifest_fields():
    text = PROTOCOL_MD.read_text(encoding="utf-8")
    assert "総合点を出さない" in text
    for field in ("run_id", "git_commit", "prompt_hashes", "protocol_version"):
        assert field in text, field


def test_protocol_links_resolve():
    text = PROTOCOL_MD.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http", "#")):
            continue
        assert (PROTOCOL_MD.parent / target.split("#")[0]).exists(), target
