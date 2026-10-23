"""The Plan step must be reproducible, reject bad canons, and leave a run ledger.

The provider is scripted: these tests check the wiring (prompt hashing, retries,
manifest, canon validation), not the quality of any model.
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
    CommandProvider, GenerationRequest, PlanError, ProviderError, RunLedger,
    ScriptedProvider, build_plan, canon_coverage, load_prompt, load_tasks,
    normalise_canon, parse_plan,
)
from asc.pipeline.plan import _write_payload  # noqa: E402
from asc.story.canon import CanonError, load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402

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


# -- prompts ---------------------------------------------------------------

def test_prompt_template_has_a_stable_digest():
    first = load_prompt("plan-canon", PROMPTS)
    second = load_prompt("plan-canon", PROMPTS)
    assert first.digest == second.digest
    assert len(first.digest) == 16
    other = load_prompt("plan-repair", PROMPTS)
    assert other.digest != first.digest


def test_prompt_requires_every_placeholder():
    template = load_prompt("plan-canon", PROMPTS)
    assert {"title", "logline", "must_include", "chapters", "schema"} <= template.placeholders
    with pytest.raises(Exception, match="missing placeholders"):
        template.render({"title": "x"})


def test_prompt_must_declare_name_and_version(tmp_path):
    (tmp_path / "bad.md").write_text("no frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        load_prompt("bad", tmp_path)


# -- providers -------------------------------------------------------------

def test_scripted_provider_is_deterministic(responses):
    provider = ScriptedProvider(responses)
    request = GenerationRequest(purpose="plan", prompt="p", context={"task_id": "t01"})
    first, second = provider.generate(request), provider.generate(request)
    assert first.text == second.text
    assert first.provider == "scripted"
    assert provider.calls == [request, request]


def test_scripted_provider_refuses_an_unknown_task(responses):
    provider = ScriptedProvider(responses)
    with pytest.raises(ProviderError, match="no scripted response"):
        provider.generate(GenerationRequest(purpose="plan", prompt="p",
                                            context={"task_id": "t99"}))


def test_command_provider_round_trip(tmp_path):
    script = tmp_path / "provider.py"
    script.write_text(
        "import json,sys\n"
        "req=json.load(sys.stdin)\n"
        "print(json.dumps({'text':'本文','model':'m','usage':{'out':3}}))\n"
        "sys.stderr.write('log ' + req['purpose'] + '\\n')\n", encoding="utf-8")
    provider = CommandProvider(f"{sys.executable} {script}", model="m")
    result = provider.generate(GenerationRequest(purpose="plan", prompt="p"))
    assert result.text == "本文"
    assert result.model == "m"
    assert result.usage == {"out": 3}


def test_command_provider_rejects_non_json(tmp_path):
    script = tmp_path / "noisy.py"
    script.write_text("print('I am a helpful assistant')\n", encoding="utf-8")
    with pytest.raises(ProviderError, match="did not return JSON"):
        CommandProvider(f"{sys.executable} {script}").generate(
            GenerationRequest(purpose="plan", prompt="p"))


def test_command_provider_reports_failure(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("import sys\nsys.stderr.write('boom\\n')\nraise SystemExit(3)\n",
                      encoding="utf-8")
    with pytest.raises(ProviderError, match="exited 3"):
        CommandProvider(f"{sys.executable} {script}").generate(
            GenerationRequest(purpose="plan", prompt="p"))


def test_command_provider_rejects_empty_text(tmp_path):
    script = tmp_path / "empty.py"
    script.write_text("import json\nprint(json.dumps({'text':'   '}))\n", encoding="utf-8")
    with pytest.raises(ProviderError, match="empty text"):
        CommandProvider(f"{sys.executable} {script}").generate(
            GenerationRequest(purpose="plan", prompt="p"))


# -- canon validation ------------------------------------------------------

def test_plan_payload_is_normalised(responses):
    payload = json.loads(responses["plan:t01"])
    canon = normalise_canon(dict(payload))
    assert [c["id"] for c in canon["timeline"]["chapters"]] == ["ch01", "ch02", "ch03"]
    assert all(entry["id"] for entry in canon["characters"])


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p.pop("characters"), "characters"),
    (lambda p: p.pop("locations"), "locations"),
    (lambda p: p["timeline"].update(chapters=[]), "timeline"),
    (lambda p: p["timeline"]["chapters"][1].pop("day"), "day"),
    (lambda p: p["timeline"]["chapters"][0].update(day=9), "backwards"),
    (lambda p: p["foreshadowing"][1].update(payoff="ch01"), "precedes setup"),
    (lambda p: p["characters"][0].update(status="sleeping"), "unknown status"),
])
def test_plan_payload_rejects_broken_canon(responses, mutate, message):
    payload = json.loads(responses["plan:t01"])
    mutate(payload)
    with pytest.raises(CanonError, match=message):
        parse_plan(json.dumps(payload, ensure_ascii=False))


def test_plan_payload_accepts_code_fences(responses):
    fenced = "```json\n" + responses["plan:t01"] + "\n```"
    canon = parse_plan(fenced)
    assert canon["characters"]


def test_plan_payload_rejects_non_json():
    with pytest.raises(CanonError, match="not valid JSON"):
        parse_plan("はい、わかりました。以下が台帳です。")


# -- planning --------------------------------------------------------------

def test_build_plan_writes_canon_and_manifest(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    plan = build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    assert plan.attempts == 1

    canon = load_canon(ledger.path / "canon")
    assert len(canon.characters) == 3
    assert canon.chapters["ch03"].day == 5

    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    for key in ("run_id", "task_id", "system", "seed", "model", "temperature",
                "prompt_hashes", "git_commit", "protocol_version", "started_at"):
        assert key in manifest, key
    assert manifest["status"] == "ok"
    assert manifest["prompt_hashes"]["plan-canon"]
    assert "canon/characters.json" in manifest["artifacts"]

    recorded = (ledger.path / "responses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(recorded) == 1
    entry = json.loads(recorded[0])
    assert entry["purpose"] == "plan"
    assert entry["prompt_hash"] == entry["response"]["text"][:0] + entry["prompt_hash"]


def test_plan_is_repaired_once(tmp_path, task, responses):
    broken = json.loads(responses["plan:t01"])
    broken["timeline"]["chapters"] = []
    provider = ScriptedProvider({"plan:t01": json.dumps(broken, ensure_ascii=False),
                                 "plan-repair:t01": responses["plan:t01"]})
    ledger = make_ledger(tmp_path)
    plan = build_plan(task, provider, ledger, prompt_dir=PROMPTS)
    assert plan.attempts == 2
    assert [call.purpose for call in provider.calls] == ["plan", "plan-repair"]
    assert "timeline" in provider.calls[1].prompt
    assert (ledger.path / "plan" / "attempt-1.error.txt").is_file()
    assert load_canon(ledger.path / "canon").characters


def test_plan_gives_up_after_max_attempts(tmp_path, task):
    provider = ScriptedProvider({"plan": "not json", "plan-repair": "still not json"})
    ledger = make_ledger(tmp_path)
    with pytest.raises(PlanError, match="no valid canon after 2 attempts"):
        build_plan(task, provider, ledger, prompt_dir=PROMPTS, max_attempts=2)
    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "not valid JSON" in manifest["error"]


def test_plan_records_provider_failure(tmp_path, task):
    class Broken:
        name = "broken"
        model = "broken"
        model_version = None

        def generate(self, request):
            raise ProviderError("upstream is down")

    ledger = make_ledger(tmp_path)
    with pytest.raises(PlanError, match="upstream is down"):
        build_plan(task, Broken(), ledger, prompt_dir=PROMPTS)
    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


# -- the acceptance criterion ---------------------------------------------

def test_plan_canon_lets_every_check_run(tmp_path, task, responses):
    """The whole point of Phase 2-A: a planned canon must leave nothing skipped."""
    ledger = make_ledger(tmp_path)
    plan = build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    canon = load_canon(ledger.path / "canon")
    coverage = canon_coverage(canon)
    assert coverage["missing"] == []
    assert len(coverage["met"]) == coverage["total"] == 6

    text = tmp_path / "text"
    text.mkdir()
    chapters = [
        ("ch01", "アリアは灯台にいた。{{time: day=1}}{{location: 灯台}}\n"
                 "{{learn: aria fact=F-01}}「灯りを消してはいけない」\n"),
        ("ch02", "アリアは王都に着いた。{{time: day=4}}{{location: 王都}}\n"
                 "ボリスは鍵を持っていた。{{foreshadow: fs-001 setup}}\n"),
        ("ch03", "灯台に戻った。{{time: day=5}}{{location: 灯台}}\n"
                 "{{foreshadow: fs-001 payoff}}「予備の鍵はどこだ」\n"),
    ]
    for name, body in chapters:
        (text / f"{name}.md").write_text(body, encoding="utf-8")

    report = audit_texts(ledger.path / "canon", text)
    assert report["summary"]["checks_skipped"] == 0


# -- CLI -------------------------------------------------------------------

def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_pipeline.py"), *argv],
        capture_output=True, text=True)


def test_cli_creates_a_run(tmp_path):
    completed = run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "r1")
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["run_id"] == "r1"
    assert summary["checks_covered"] == "6/6"
    assert (tmp_path / "r1" / "manifest.json").is_file()
    assert (tmp_path / "r1" / "canon" / "characters.json").is_file()


def test_cli_is_idempotent_for_the_same_script(tmp_path):
    run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "a", "--quiet")
    run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "b", "--quiet")
    first = (tmp_path / "a" / "plan.json").read_text(encoding="utf-8")
    second = (tmp_path / "b" / "plan.json").read_text(encoding="utf-8")
    assert first == second


def test_cli_rejects_an_unknown_task(tmp_path):
    completed = run_cli("--task", "zzz", "--out", str(tmp_path))
    assert completed.returncode == 2
    assert "unknown task" in completed.stderr


def test_cli_requires_a_command_for_the_command_provider(tmp_path):
    completed = run_cli("--task", "t01", "--provider", "command", "--out", str(tmp_path))
    assert completed.returncode == 2
    assert "--command" in completed.stderr


def test_cli_refuses_to_overwrite_a_run(tmp_path):
    run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "same", "--quiet")
    completed = run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "same", "--quiet")
    assert completed.returncode == 2


def test_cli_can_audit_a_text_directory(tmp_path):
    text = tmp_path / "text"
    text.mkdir()
    for name, body in [("ch01", "{{time: day=1}}{{location: 灯台}}\n"),
                       ("ch02", "{{time: day=4}}{{location: 王都}}\n"),
                       ("ch03", "{{time: day=5}}{{location: 灯台}}\n")]:
        (text / f"{name}.md").write_text(body, encoding="utf-8")
    completed = run_cli("--task", "t01", "--out", str(tmp_path / "runs"),
                        "--text", str(text), "--run-id", "audited")
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["audit"]["checks_skipped"] == 0


def test_write_payload_is_loadable(tmp_path, responses):
    payload = json.loads(responses["plan:t01"])
    _write_payload(payload, tmp_path)
    canon = load_canon(tmp_path)
    assert canon.characters["aria"].age_at_start == 24
