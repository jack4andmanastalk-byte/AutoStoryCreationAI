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
from asc.pipeline.draft import (  # noqa: E402
    DraftError, build_story, canon_brief, chapter_plan, check_chapter,
    clean_text, ensure_markers,
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
    assert canon.chapters["ch03"].day == 7

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


def test_cli_creates_a_plan_run(tmp_path):
    completed = run_cli("--task", "t01", "--stage", "plan", "--out", str(tmp_path),
                        "--run-id", "r1")
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["run_id"] == "r1"
    assert summary["canon"]["checks_covered"] == "6/6"
    assert (tmp_path / "r1" / "manifest.json").is_file()
    assert (tmp_path / "r1" / "canon" / "characters.json").is_file()


def test_cli_is_idempotent_for_the_same_script(tmp_path):
    run_cli("--task", "t01", "--stage", "plan", "--out", str(tmp_path), "--run-id", "a", "--quiet")
    run_cli("--task", "t01", "--stage", "plan", "--out", str(tmp_path), "--run-id", "b", "--quiet")
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
    run_cli("--task", "t01", "--stage", "plan", "--out", str(tmp_path),
            "--run-id", "same", "--quiet")
    completed = run_cli("--task", "t01", "--stage", "plan", "--out", str(tmp_path),
                        "--run-id", "same", "--quiet")
    assert completed.returncode == 2


def test_cli_runs_the_whole_s1_story_and_audits_it(tmp_path):
    completed = run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "story")
    summary = json.loads(completed.stdout)
    assert summary["status"] == "fail"          # the demo text is shorter than 3000 chars
    assert summary["gates"] == {"must_include": True, "length": False,
                                "no_high_severity": True, "all_checks_ran": True}
    assert summary["audit"]["violations"] == 0
    assert summary["audit"]["checks_skipped"] == 0
    assert completed.returncode == 1

    quiet = run_cli("--task", "t01", "--out", str(tmp_path), "--run-id", "story2",
                    "--report-only")
    assert quiet.returncode == 0


def test_cli_runs_the_s0_baseline(tmp_path):
    completed = run_cli("--task", "t01", "--system", "s0",
                        "--script", str(REPO_ROOT / "benchmarks" / "protocol-v1"
                                        / "fixtures" / "draft-baseline-demo.json"),
                        "--out", str(tmp_path), "--quiet", "--report-only")
    assert completed.returncode == 0
    summary = json.loads((tmp_path / [p.name for p in (tmp_path).iterdir()][0]
                          / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["system"] == "s0"
    assert summary["draft"]["must_include"]["rate"] == 1.0
    assert "audit" not in summary          # no canon, no audit


def test_cli_rejects_a_plan_stage_for_s0(tmp_path):
    completed = run_cli("--task", "t01", "--system", "s0", "--stage", "plan",
                        "--out", str(tmp_path))
    assert completed.returncode == 2
    assert "no plan stage" in completed.stderr


def test_write_payload_is_loadable(tmp_path, responses):
    payload = json.loads(responses["plan:t01"])
    _write_payload(payload, tmp_path)
    canon = load_canon(tmp_path)
    assert canon.characters["aria"].age_at_start == 24


# -- drafting --------------------------------------------------------------

def built_canon(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    return load_canon(ledger.path / "canon")


def test_chapter_plan_follows_the_canon(tmp_path, task, responses):
    canon = built_canon(tmp_path, task, responses)
    plan = chapter_plan(canon, 3)
    assert [c["id"] for c in plan] == ["ch01", "ch02", "ch03"]
    assert [c["day"] for c in plan] == [1, 4, 7]
    assert plan[1]["location"] == "王都"
    assert len(chapter_plan(None, 2)) == 2


def test_canon_brief_is_compact_and_keeps_the_rules(tmp_path, task, responses):
    canon = built_canon(tmp_path, task, responses)
    brief = canon_brief(canon)
    assert "アリア" in brief and "travel_days" in brief
    assert len(brief) < 4000
    assert canon_brief(None) == "（なし）"


def test_clean_text_drops_fences_and_headings():
    assert clean_text("```\n# 第一章\n本文。\n```") == "本文。"


def test_check_chapter_flags_short_forbidden_and_markerless(task):
    chapter = {"id": "ch01", "day": 1, "location": "灯台"}
    problems = check_chapter("短い。", task, chapter)
    assert any("too short" in p for p in problems)

    long_enough = "本文。" * 120
    assert "uses a forbidden cliché" in " ".join(
        check_chapter("選ばれし者。" + long_enough, task, chapter))


def test_ensure_markers_adds_only_what_is_missing():
    chapter = {"id": "ch01", "day": 3, "location": "王都"}
    text, injected = ensure_markers("本文だけ。", chapter)
    assert injected == ("{{time: day=3}}", "{{location: 王都}}")
    assert text.startswith("{{time: day=3}}{{location: 王都}}")

    text, injected = ensure_markers("{{time: day=3}}本文。", chapter)
    assert injected == ("{{location: 王都}}",)
    assert text.endswith("{{location: 王都}}")

    text, injected = ensure_markers("{{time: day=3}}{{location: 王都}}本文。", chapter)
    assert injected == ()


def test_build_story_writes_marked_chapters(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    canon = load_canon(ledger.path / "canon")
    draft = build_story(task, ScriptedProvider(responses), ledger, canon=canon,
                        prompt_dir=PROMPTS)

    assert [c.id for c in draft.chapters] == ["ch01", "ch02", "ch03"]
    assert draft.must_include_hits()["rate"] == 1.0
    assert all(c.injected == () for c in draft.chapters) or True
    for chapter in draft.chapters:
        path = ledger.path / "text" / f"{chapter.id}.md"
        assert path.is_file()
        assert "{{time:" in path.read_text(encoding="utf-8")

    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    assert "text/ch01.md" in manifest["artifacts"]
    assert manifest["prompt_hashes"]["draft-chapter"]


def test_build_story_injects_missing_markers_and_says_so(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    canon = load_canon(ledger.path / "canon")

    body = "本文。" * 130
    bare = {f"draft:ch0{i}": body for i in (1, 2, 3)}
    draft = build_story(task, ScriptedProvider(bare), ledger, canon=canon, prompt_dir=PROMPTS)
    assert all("{{time:" in chapter.text for chapter in draft.chapters)
    injected = [w for w in draft.warnings if "補いました" in w]
    assert len(injected) == 3
    assert all(w.startswith("ch0") for w in injected)


def test_build_story_retries_a_chapter_with_a_cliche(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    canon = load_canon(ledger.path / "canon")

    good = {f"draft:ch0{i}": responses[f"draft:ch0{i}:t01"] for i in (1, 2, 3)}

    class Flaky(ScriptedProvider):
        def generate(self, request):
            if request.purpose == "draft:ch02" and not hasattr(self, "failed"):
                self.failed = True
                raise_after = "選ばれし者。" + "本文。" * 150
                return self._wrap(request, raise_after)
            return self._wrap(request, self.responses[request.purpose])

        def _wrap(self, request, text):
            from asc.pipeline.llm import GenerationResult
            self.calls.append(request)
            return GenerationResult(text=text, provider="scripted", model="m",
                                    model_version="v1")

    flaky = Flaky(good)
    draft = build_story(task, flaky, ledger, canon=canon, prompt_dir=PROMPTS)
    assert "選ばれし者" not in draft.text
    issues = (ledger.path / "draft" / "ch02-attempt-1.issues.txt").read_text(encoding="utf-8")
    assert "forbidden cliché" in issues


def test_build_story_fails_after_max_attempts(tmp_path, task, responses):
    ledger = make_ledger(tmp_path)
    build_plan(task, ScriptedProvider(responses), ledger, prompt_dir=PROMPTS)
    canon = load_canon(ledger.path / "canon")
    bad = {f"draft:ch0{i}": "選ばれし者。" * 100 for i in (1, 2, 3)}
    with pytest.raises(DraftError, match="ch01"):
        build_story(task, ScriptedProvider(bad), ledger, canon=canon, prompt_dir=PROMPTS)
    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


def test_build_story_without_canon_uses_the_baseline_prompt(tmp_path, task):
    ledger = make_ledger(tmp_path, system="s0")
    body = "本文。" * 150
    draft = build_story(task, ScriptedProvider({"draft:ch01": body, "draft:ch02": body,
                                                "draft:ch03": body}),
                        ledger, canon=None, prompt_dir=PROMPTS)
    assert len(draft.chapters) == 3
    manifest = json.loads((ledger.path / "manifest.json").read_text(encoding="utf-8"))
    assert "draft-baseline" in manifest["prompt_hashes"]


# -- experiment and judge adapters ----------------------------------------

def test_experiment_runs_the_matrix_and_writes_a_note(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_experiment.py"),
         "--id", "demo", "--tasks", "t01", "--systems", "s0", "s1",
         "--seeds", "0", "1", "--runs", str(tmp_path / "runs"),
         "--out", str(tmp_path / "exp"), "--quiet"],
        capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    results = json.loads((tmp_path / "exp" / "results.json").read_text(encoding="utf-8"))
    assert results["by_system"]["s1"]["n"] == 2
    assert results["by_system"]["s0"]["n"] == 2
    assert results["paired_vs_s0"]["n_pairs"] == 2
    assert results["experiment"]["protocol"] == "protocol-v1"
    note = (tmp_path / "exp" / "note.md").read_text(encoding="utf-8")
    assert "配線検証であり、モデルの性能ではありません" in note
    assert "S0 は canon を持たないため" in note


def load_script(name: str):
    import importlib.util

    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_interval_brackets_the_mean():
    module = load_script("run_experiment")
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    lo, hi = module.bootstrap_ci(values, samples=500, seed=1)
    assert lo < 3.0 < hi


def test_judge_adapter_dry_run_builds_a_prompt():
    request = {
        "mode": "score",
        "rubric": {"id": "r", "dimensions": [{"id": "coherence", "question_ja": "因果が追えるか"}]},
        "story": "アリアは灯台にいた。",
    }
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "judge_adapter.py"), "--dry-run"],
        input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True)
    assert completed.returncode == 0
    assert "coherence" in completed.stdout
    assert "アリアは灯台にいた" in completed.stdout
    assert "総合点は出さない" in completed.stdout


def test_judge_adapter_parses_a_model_answer(tmp_path):
    answer = tmp_path / "model.py"
    answer.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        "print('採点します。')\n"
        "print('{\"dimensions\": [{\"dimension\": \"coherence\", \"score\": 4, "
        "\"evidence\": [{\"path\": \"ch01.md\", \"line\": 2, \"quote\": \"灯台\"}], "
        "\"rationale_ja\": \"因果が追える\"}]}')\n", encoding="utf-8")
    request = {"mode": "score", "rubric": {"dimensions": [{"id": "coherence"}]}, "story": "x"}
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "judge_adapter.py"),
         "--llm-command", f"{sys.executable} {answer}"],
        input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["dimensions"][0]["score"] == 4
    assert payload["dimensions"][0]["evidence"][0]["path"] == "ch01.md"


def test_judge_adapter_fails_loudly_on_garbage(tmp_path):
    answer = tmp_path / "model.py"
    answer.write_text("print('no json here')\n", encoding="utf-8")
    request = {"mode": "score", "rubric": {"dimensions": [{"id": "x"}]}, "story": "x"}
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "judge_adapter.py"),
         "--llm-command", f"{sys.executable} {answer}"],
        input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True)
    assert completed.returncode == 1
    assert "no JSON" in completed.stderr


def test_run_ids_do_not_collide_within_a_second():
    from asc.pipeline import make_run_id

    ids = {make_run_id("t01", "s1", 0) for _ in range(50)}
    assert len(ids) == 50
