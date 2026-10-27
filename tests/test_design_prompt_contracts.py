"""Contract tests for the seven non-brief design prompts.

The standalone skill tests already cover their YAML demos. These tests cover
the generation boundary instead: the prompt states the contract, valid JSON is
accepted, semantic/schema failures become recorded repair attempts, and the
fail-open design stage does not turn malformed model output into a crashed run.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    RunLedger, build_design, build_plan, load_tasks,
)
from asc.pipeline.llm import GenerationRequest, GenerationResult  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402

TASKS_FILE = REPO_ROOT / "benchmarks/protocol-v1/tasks.yaml"
FIXTURE = REPO_ROOT / "benchmarks/protocol-v1/fixtures/plan-demo.json"
PROMPTS = REPO_ROOT / "prompts"
DOC_NAMES = ("world", "history", "character", "relation", "plot", "scene", "voice")


class StubProvider:
    name = "stub"
    model = "stub"
    model_version = "v1"

    def __init__(self, texts: dict[str, str]):
        self.texts = texts
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        return GenerationResult(
            text=self.texts[request.purpose], provider=self.name,
            model=self.model, model_version=self.model_version)


@pytest.fixture(scope="module")
def task():
    return load_tasks(TASKS_FILE).get("t01")


@pytest.fixture(scope="module")
def responses():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"]


@pytest.fixture(scope="module")
def canon(task, responses, tmp_path_factory):
    ledger = RunLedger.create(
        tmp_path_factory.mktemp("design-contract-plan"), task_id="t01",
        system="s1", seed=0, protocol_version="protocol-v1")
    from asc.pipeline import ScriptedProvider
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    return load_canon(ledger.path / "canon")


def valid_doc(name: str, responses) -> dict:
    return json.loads(responses[f"design:{name}:t01"])


def run_doc(name: str, payload: dict | str, task, canon, tmp_path: Path,
            *, max_attempts: int = 2):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    provider = StubProvider({
        f"design:{name}": text,
        f"design:{name}:repair": text,
    })
    ledger = RunLedger.create(
        tmp_path / "runs", task_id="t01", system="s1", seed=0,
        protocol_version="protocol-v1")
    design = build_design(
        task, provider, ledger, canon, prompt_dir=PROMPTS,
        docs=(name,), max_attempts=max_attempts)
    report = json.loads((ledger.path / "design" / f"{name}.report.json"
                         ).read_text(encoding="utf-8"))
    return design.as_dict()["docs"][name], report, provider


@pytest.mark.parametrize(("name", "required", "version"), [
    ("world", "地名は設定台帳の場所 ID と一致させる", "1.0"),
    ("history", "出来事は年代順に並べ", "1.1"),
    ("character", "主要人物は全員書く", "1.0"),
    ("relation", "設定台帳で既知の事実を unknown と主張しない", "1.0"),
    ("plot", "転換点を 3〜5 件置き", "1.0"),
    ("scene", "開示か保留のどちらかに置く", "1.0"),
    ("voice", "一人称なら自称を宣言する", "1.0"),
])
def test_prompt_states_the_mechanical_contract(
        name, required, version, task, canon, responses, tmp_path):
    result, report, provider = run_doc(
        name, valid_doc(name, responses), task, canon, tmp_path, max_attempts=1)
    assert result["status"] == "clean"
    prompt = provider.calls[0].prompt
    assert required in prompt
    assert "設定台帳" in prompt
    assert "先行する設計書" in prompt
    assert "JSON のみを返してください" in prompt
    assert report["prompt"]["name"] == f"design-{name}"
    assert report["prompt"]["version"] == version


@pytest.mark.parametrize("name", DOC_NAMES)
def test_valid_json_is_clean_for_each_design_document(
        name, task, canon, responses, tmp_path):
    result, report, provider = run_doc(
        name, valid_doc(name, responses), task, canon, tmp_path, max_attempts=1)
    assert result["status"] == "clean"
    assert result["attempts"] == 1
    assert result["findings"] == 0
    assert report["findings"] == []
    assert len(provider.calls) == 1


def bad_world(doc):
    doc["geography"] = ["雲の都"]
    doc["disclosure"][0]["chapter"] = "ch09"


def bad_history(doc):
    doc["events"] = list(reversed(doc["events"]))
    doc["events"][0]["cause"] = "ev-missing"
    doc["knowledge"]["zorro"] = {"knows": ["ev-missing"], "unknown": []}


def bad_character(doc):
    char = doc["characters"][0]
    char["id"] = "zorro"
    char["want"] = char["need"]
    char["predictions"] = char["predictions"][:1]


def bad_relation(doc):
    doc["knowledge"][0]["state"] = "unknown"  # aria knows F-01 in canon
    doc["changes"][0]["pair"] = ["aria", "celia"]  # not a declared pair


def bad_plot(doc):
    doc["acts"][0]["chapters"] = ["ch99"]
    doc["turns"] = doc["turns"][:1]
    doc["unresolved"][0]["foreshadowing"] = "fs-999"


def bad_scene(doc):
    # F-03 is gained but neither disclosed nor withheld.
    doc["scenes"][0]["disclosure"]["disclosed"] = []
    doc["scenes"][1]["foreshadows"]["planted"] = [
        {"id": "fs-late", "payoff": "ch01"}]
    doc["scenes"][2]["foreshadows"]["paid"] = ["fs-999"]


def bad_voice(doc):
    doc["viewpoint"]["person"] = "first"
    doc["viewpoint"]["pronouns"] = []
    doc["sample"] = ""
    doc["banned"][0]["message_ja"] = ""


@pytest.mark.parametrize(("name", "mutate", "expected"), [
    ("world", bad_world, {"geography_grounded", "disclosure_ordered"}),
    ("history", bad_history, {"chronology_ordered", "causality_linked", "knowledge_consistent"}),
    ("character", bad_character, {"core_declared", "choices_predicted", "canon_grounded"}),
    ("relation", bad_relation, {"knowledge_matches_canon", "change_staged"}),
    ("plot", bad_plot, {"acts_cover", "turns_placed", "debts_listed"}),
    ("scene", bad_scene, {"knowledge_tracked", "foreshadow_tagged"}),
    ("voice", bad_voice, {"viewpoint_declared", "sample_declared", "banned_reason"}),
])
def test_semantic_failures_are_recorded_and_sent_to_repair(
        name, mutate, expected, task, canon, responses, tmp_path):
    payload = copy.deepcopy(valid_doc(name, responses))
    mutate(payload)
    result, report, provider = run_doc(name, payload, task, canon, tmp_path)

    assert result["status"] == "unresolved"
    assert result["attempts"] == 2
    assert result["first_attempt_findings"] > 0
    assert expected <= {item["check"] for item in report["findings"]}
    assert expected <= {item["check"] for item in report["first_attempt"]["findings"]}
    assert [call.purpose for call in provider.calls] == [
        f"design:{name}", f"design:{name}:repair"]
    repair_prompt = provider.calls[1].prompt
    for check in expected:
        assert check in repair_prompt
    assert json.dumps(payload, ensure_ascii=False) in repair_prompt


def wrong_world_type(doc):
    doc["rules"] = "rule-light"


def wrong_history_type(doc):
    doc["events"][0]["year"] = "百年前"


def wrong_character_type(doc):
    doc["characters"][0]["speech"] = "三十字以上のサンプル"


def wrong_relation_type(doc):
    doc["changes"][0]["pair"] = "aria-boris"


def wrong_plot_type(doc):
    doc["ending"] = "happy"


def wrong_scene_type(doc):
    doc["scenes"][0]["disclosure"] = "伏せる"


def wrong_voice_type(doc):
    doc["viewpoint"] = "third"


@pytest.mark.parametrize(("name", "mutate"), [
    ("world", wrong_world_type),
    ("history", wrong_history_type),
    ("character", wrong_character_type),
    ("relation", wrong_relation_type),
    ("plot", wrong_plot_type),
    ("scene", wrong_scene_type),
    ("voice", wrong_voice_type),
])
def test_wrong_nested_json_types_become_schema_findings_not_crashes(
        name, mutate, task, canon, responses, tmp_path):
    payload = copy.deepcopy(valid_doc(name, responses))
    mutate(payload)
    result, report, provider = run_doc(name, payload, task, canon, tmp_path)

    assert result["status"] == "unresolved"
    assert result["attempts"] == 2
    assert [item["check"] for item in report["findings"]] == ["schema"]
    assert report["findings"][0]["severity"] == "high"
    assert len(provider.calls) == 2


def test_scene_gained_fact_may_be_withheld_with_a_reason(
        task, canon, responses, tmp_path):
    payload = copy.deepcopy(valid_doc("scene", responses))
    disclosure = payload["scenes"][0]["disclosure"]
    disclosure["disclosed"] = []
    disclosure["withheld"].append(
        {"fact": "F-03", "reason": "帳面を調べるch02まで伏せる"})

    result, report, provider = run_doc(
        "scene", payload, task, canon, tmp_path, max_attempts=1)

    assert result["status"] == "clean"
    assert report["findings"] == []
    assert len(provider.calls) == 1
