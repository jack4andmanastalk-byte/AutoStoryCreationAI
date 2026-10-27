"""Phase 2: scripted Stage A -> Stage B wiring and deterministic regression."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import check_rewrite, load_game_log  # noqa: E402
from asc.gamelog.markers import chapter_markers, normalise_marker  # noqa: E402
from asc.plot.schema import load_plot  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.story.text import parse_markers  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402
import run_twostage  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-trpg-slice-t01"
INPUTS = BUNDLE / "inputs"
SCRIPT = BUNDLE / "scripted.json"
RUNNER = REPO_ROOT / "scripts" / "run_twostage.py"


def run_cli(out: Path, *extra: str, script: Path | None = None,
            run_id: str = "fixed", provider: str = "scripted",
            canon: Path | None = None, design_dir: Path | None = None):
    args = [
        sys.executable, str(RUNNER), "--task", "t01",
        "--canon", str(canon or INPUTS / "canon"),
        "--design-dir", str(design_dir or INPUTS / "design"),
        "--provider", provider,
        "--out", str(out), "--run-id", run_id,
        "--allow-temp-out", "--quiet",
    ]
    if provider == "scripted":
        args += ["--script", str(script or SCRIPT)]
    args += list(extra)
    return subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_script(tmp_path: Path, responses: dict) -> Path:
    # $file entries are relative to the committed script; pin them to absolute
    # paths so a test script can live in its own temp directory.
    for key, value in list(responses.items()):
        if isinstance(value, dict) and "$file" in value:
            target = Path(value["$file"])
            if not target.is_absolute():
                responses[key] = {"$file": str((SCRIPT.parent / target).resolve())}
    path = tmp_path / "scripted.json"
    path.write_text(json.dumps({"_note": "test fixture", "responses": responses},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def base_responses() -> dict:
    return json.loads(SCRIPT.read_text(encoding="utf-8"))["responses"]


# -- happy path --------------------------------------------------------------
def test_scripted_two_stage_run_is_clean_and_self_contained(tmp_path):
    out = tmp_path / "bundle"
    results_path = tmp_path / "results.json"
    completed = run_cli(out, "--results", str(results_path))
    assert completed.returncode == 0, completed.stderr
    run = out / "fixed"
    for relative in ("inputs/canon/characters.json", "inputs/design/plot.json",
                     "inputs/design/scene.json", "inputs/design/voice.json",
                     "inputs/scripted.json", "manifest.json", "responses.jsonl",
                     "design.report.json", "game_log.json", "game_log.report.json",
                     "timeline.json", "rewrite.report.json", "audit.json",
                     "state.json",
                     "run-summary.json", "text/ch01.md", "text/ch02.md",
                     "text/ch03.md"):
        assert (run / relative).is_file(), relative

    a_report = read_json(run / "game_log.report.json")
    assert a_report["summary"]["status"] == "clean"
    assert a_report["attempts"] == 1 and a_report["repairs"] == 0
    assert len(a_report["markers"]) == 19
    assert len(a_report["allowed_dead_references"]) == 4
    b_report = read_json(run / "rewrite.report.json")
    assert b_report["status"] == "clean"
    assert set(b_report["chapters"]) == {"ch01", "ch02", "ch03"}

    log = load_game_log(run / "game_log.json")
    for chapter in log.chapters:
        text = (run / "text" / f"{chapter.id}.md").read_text(encoding="utf-8")
        found = [normalise_marker(m.raw) for m in parse_markers(text, chapter.id)]
        expected = [normalise_marker(m.text)
                    for m in chapter_markers(log, chapter.id)]
        assert found == expected
        assert found[0] == "{{time: day=%s}}" % int(chapter.day)

    summary = read_json(run / "run-summary.json")
    assert summary["status"] == "clean"
    assert summary["gates"] == {"stage_a_clean": True, "stage_b_clean": True}
    assert summary["l1_hygiene"]["must_include"]["rate"] == 1.0
    assert summary["l1_hygiene"]["continuity"]["checks_skipped"] == 0
    # The continuity audit now separates reference-context dead-name mentions
    # into observations; unclassified mentions would remain medium violations.
    assert summary["l1_hygiene"]["continuity"]["violations"] == 0
    assert summary["l1_hygiene"]["continuity"]["observations"] == 3
    assert summary["l1_hygiene"]["continuity"]["by_type"] == {}
    assert summary["l1_hygiene"]["continuity"]["by_severity"] == {}

    results = read_json(results_path)
    assert results["schema"] == "trpg-slice-wiring-v1"
    assert results["status"] == "clean"
    assert results["provider"]["name"] == "scripted"
    assert results["stage_a"]["markers"] == 19
    assert len(results["stage_b"]["chapters"]) == 3
    assert results["evaluation_scope"]["gate_status"]["G3"] == "frozen_not_measured"
    assert results["evaluation_scope"]["gate_status"]["G4"] == "frozen_not_measured"
    assert results["evaluation_scope"]["frozen_layers"] == ["L2", "L3"]
    assert results["evaluation_scope"]["claims"][
        "semantic_quality_or_human_preference"] == "not_evaluated"
    assert "not a model response" in results["claim"]


def test_committed_bundle_summary_is_reproducible(tmp_path):
    """The checked-in results.json must describe the current fixture exactly."""
    generated = tmp_path / "results.json"
    completed = run_cli(tmp_path / "bundle", "--results", str(generated))
    assert completed.returncode == 0, completed.stderr
    committed = BUNDLE / "results.json"
    assert generated.read_bytes() == committed.read_bytes(), (
        "experiments/2026-10-trpg-slice-t01/results.json is stale; "
        "regenerate it with `make two-stage`")


def test_fixed_script_is_byte_deterministic_across_bundles(tmp_path):
    deterministic = ("game_log.json", "game_log.report.json",
                     "rewrite.report.json", "design.report.json",
                     "text/ch01.md", "text/ch02.md", "text/ch03.md")
    runs = []
    for index, name in enumerate(("a", "b")):
        out = tmp_path / name
        results = tmp_path / f"results-{name}.json"
        completed = run_cli(out, "--results", str(results))
        assert completed.returncode == 0, completed.stderr
        runs.append((out / "fixed", results))
    first, second = runs
    for relative in deterministic:
        assert (first[0] / relative).read_bytes() == (second[0] / relative).read_bytes(), \
            relative
    assert first[1].read_bytes() == second[1].read_bytes()

    def request_fingerprint(run_dir: Path):
        return [(row["purpose"], row["prompt_hash"], row["response_sha256"])
                for row in (json.loads(line) for line in
                            (run_dir / "responses.jsonl").read_text(
                                encoding="utf-8").splitlines() if line.strip())]
    assert request_fingerprint(first[0]) == request_fingerprint(second[0])
    assert [row[0] for row in request_fingerprint(first[0])] == [
        "stage_a", "stage_b:ch01", "stage_b:ch02", "stage_b:ch03"]


# -- repair and fail-closed behaviour ---------------------------------------
def test_stage_a_repair_round_fixes_a_dead_actor(tmp_path):
    raw = json.loads((INPUTS / "game_log.json").read_text(encoding="utf-8"))
    raw["chapters"][0]["scenes"][0]["present_characters"].append("johan")
    responses = base_responses()
    responses["stage_a:t01"] = json.dumps(raw, ensure_ascii=False)
    responses["stage_a:repair:t01"] = {"$file": str(INPUTS / "game_log.json")}
    script = write_script(tmp_path, responses)
    out = tmp_path / "bundle"
    completed = run_cli(out, script=script)
    assert completed.returncode == 0, completed.stderr
    report = read_json(out / "fixed" / "game_log.report.json")
    assert report["attempts"] == 2 and report["repairs"] == 1
    assert report["first_attempt_findings"] > 0
    assert report["summary"]["status"] == "clean"
    assert read_json(out / "fixed" / "rewrite.report.json")["status"] == "clean"
    purposes = [json.loads(line)["purpose"] for line in
                (out / "fixed" / "responses.jsonl").read_text(
                    encoding="utf-8").splitlines() if line.strip()]
    assert purposes[:2] == ["stage_a", "stage_a:repair"]


def test_unresolved_stage_a_blocks_stage_b(tmp_path):
    raw = json.loads((INPUTS / "game_log.json").read_text(encoding="utf-8"))
    raw["chapters"][0]["scenes"][0]["actions"][0]["actor"] = "johan"
    broken = json.dumps(raw, ensure_ascii=False)
    responses = base_responses()
    responses["stage_a:t01"] = broken
    responses["stage_a:repair:t01"] = broken
    script = write_script(tmp_path, responses)
    out = tmp_path / "bundle"
    results = tmp_path / "results.json"
    report_only = run_cli(out, "--report-only", "--results", str(results),
                          script=script)
    assert report_only.returncode == 0, report_only.stderr
    run = out / "fixed"
    assert read_json(run / "run-summary.json")["status"] == "unresolved"
    assert read_json(run / "run-summary.json")["stage_b"]["status"] == "skipped"
    assert not (run / "rewrite.report.json").exists()
    assert not (run / "text").exists()
    assert read_json(results)["status"] == "unresolved"

    strict_out = tmp_path / "strict"
    strict = run_cli(strict_out, script=script)
    assert strict.returncode == 1


def test_stage_b_repair_restores_a_missing_marker(tmp_path):
    good = (INPUTS / "rewrite" / "ch02.md").read_text(encoding="utf-8")
    broken = good.replace("{{learn: aria fact=F-03}}", "")
    responses = base_responses()
    responses["stage_b:ch02:t01"] = broken
    responses["stage_b:ch02:repair:t01"] = good
    script = write_script(tmp_path, responses)
    out = tmp_path / "bundle"
    completed = run_cli(out, script=script)
    assert completed.returncode == 0, completed.stderr
    report = read_json(out / "fixed" / "rewrite.report.json")
    assert report["status"] == "clean"
    assert report["chapters"]["ch02"]["attempts"] == 2
    assert "{{learn: aria fact=F-03}}" in (
        out / "fixed" / "text" / "ch02.md").read_text(encoding="utf-8")


def test_unresolved_stage_b_is_recorded_and_fails_the_gate(tmp_path):
    good = (INPUTS / "rewrite" / "ch03.md").read_text(encoding="utf-8")
    broken = good.replace("{{foreshadow: fs-003 payoff}}", "")
    responses = base_responses()
    responses["stage_b:ch03:t01"] = broken
    responses["stage_b:ch03:repair:t01"] = broken
    script = write_script(tmp_path, responses)
    out = tmp_path / "bundle"
    completed = run_cli(out, "--results", str(tmp_path / "results.json"),
                        script=script)
    assert completed.returncode == 1
    run = out / "fixed"
    report = read_json(run / "rewrite.report.json")
    assert report["status"] == "unresolved"
    assert any(item["check"] == "marker_sequence"
               for item in report["chapters"]["ch03"]["findings"])
    # The unverified chapter is still written, but never presented as clean.
    assert (run / "text" / "ch03.md").is_file()
    assert read_json(tmp_path / "results.json")["status"] == "unresolved"


# -- bundle boundaries and resume -------------------------------------------
def test_scratch_output_paths_are_rejected(tmp_path):
    build = REPO_ROOT / "build" / "twostage-scratch"
    completed = run_cli(build)
    assert completed.returncode == 2
    assert "build/" in completed.stderr
    plain = subprocess.run(
        [sys.executable, str(RUNNER), "--task", "t01",
         "--canon", str(INPUTS / "canon"), "--design-dir", str(INPUTS / "design"),
         "--provider", "scripted", "--script", str(SCRIPT),
         "--out", str(tmp_path / "outside"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert plain.returncode == 2
    assert "experiments/" in plain.stderr


def test_resume_replays_recorded_responses_from_the_same_bundle(tmp_path):
    out = tmp_path / "bundle"
    assert run_cli(out, run_id="resume-me").returncode == 0
    run = out / "resume-me"
    before = {name: (run / name).read_bytes() for name in
              ("game_log.json", "game_log.report.json", "rewrite.report.json",
               "text/ch01.md", "text/ch02.md", "text/ch03.md")}
    resumed = run_cli(out, "--resume", run_id="resume-me")
    assert resumed.returncode == 0, resumed.stderr
    assert read_json(run / "run-summary.json")["status"] == "clean"
    for name, content in before.items():
        assert (run / name).read_bytes() == content, name
    lines = [json.loads(line) for line in
             (run / "responses.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]
    assert len(lines) == 4  # no duplicated requests after resume


def test_resume_refuses_changed_inputs(tmp_path):
    import shutil

    canon = tmp_path / "canon-copy"
    shutil.copytree(INPUTS / "canon", canon)
    out = tmp_path / "bundle"
    assert run_cli(out, run_id="resume-me", canon=canon).returncode == 0
    (canon / "facts.json").write_text("{}", encoding="utf-8")
    resumed = run_cli(out, "--resume", run_id="resume-me", canon=canon)
    assert resumed.returncode == 2
    assert "hash mismatch" in resumed.stderr


def test_pending_operator_response_exports_prompts_into_the_bundle(tmp_path):
    stub = tmp_path / "pending.py"
    stub.write_text(
        "import sys\n"
        "print('NEED RESPONSE key=stage-a-pending file=relay/responses/x.json',\n"
        "      file=sys.stderr)\n"
        "raise SystemExit(3)\n", encoding="utf-8")
    out = tmp_path / "bundle"
    command = f"{sys.executable} {stub}"
    completed = run_cli(out, "--command", command, provider="command",
                        run_id="pending", script=None)
    assert completed.returncode == 3, completed.stderr
    run = out / "pending"
    assert (run / "PROMPTS.md").is_file()
    assert (run / "state.json").is_file()
    state = read_json(run / "state.json")
    assert state["status"] == "pending"
    assert state["pending"]["key"] == "stage-a-pending"
    assert "--resume" in state["resume_command"]
    prompts = (run / "PROMPTS.md").read_text(encoding="utf-8")
    assert "stage_a" in prompts and "emitted_markers" in prompts
    assert not (tmp_path / "results.json").exists()


class _CountingProvider:
    name = "counting"
    model = "fake"
    model_version = "v1"

    def __init__(self):
        self.calls = 0

    def generate(self, request):
        from asc.pipeline import GenerationResult
        self.calls += 1
        return GenerationResult(text="{}", provider=self.name, model=self.model)


def test_bundle_provider_refuses_a_stale_recorded_response():
    from asc.pipeline import GenerationRequest
    context = {"attempt": 1, "chapter": None, "task_id": "t01"}
    request = GenerationRequest(purpose="stage_a", prompt="hello", seed=0,
                                context=context)
    entry = {"purpose": "stage_a", "context": context, "seed": 0,
             "prompt_hash": request.prompt_hash,
             "response": {"text": "recorded", "model": "fake"}}
    delegate = _CountingProvider()
    provider = run_twostage.BundleProvider(delegate, [entry])
    assert provider.generate(request).text == "recorded"
    assert delegate.calls == 0
    changed = GenerationRequest(purpose="stage_a", prompt="different", seed=0,
                                context=context)
    provider.generate(changed)
    assert delegate.calls == 1


# -- Stage B contract --------------------------------------------------------
def test_rewrite_check_flags_marker_loss_unlogged_names_and_dead_state_markers():
    log = load_game_log(INPUTS / "game_log.json")
    canon = load_canon(INPUTS / "canon")
    voice = load_voice(INPUTS / "design" / "voice.json")
    scenes = load_scenes(INPUTS / "design" / "scene.json")
    text = (INPUTS / "rewrite" / "ch01.md").read_text(encoding="utf-8")

    clean = check_rewrite(text, "ch01", log, canon, voice, scenes)
    assert clean["summary"]["status"] == "clean"
    assert clean["summary"]["allowed_dead_references"] == 2

    broken = (text.replace("{{foreshadow: fs-002 setup}}", "")
              .replace("風はまだ強かったが", "セリアが来た。風はまだ強かったが")
              + "\n{{state: johan alive=yes}}\n")
    report = check_rewrite(broken, "ch01", log, canon, voice, scenes)
    assert report["summary"]["status"] == "unresolved"
    checks = {item["check"] for item in report["findings"]}
    assert {"marker_sequence", "character_boundary", "fact_boundary"} <= checks
    assert any("死者 johan" in item["message_ja"]
               for item in report["findings"])


def test_rewrite_check_flags_banned_voice_and_premature_fact_terms():
    log = load_game_log(INPUTS / "game_log.json")
    canon = load_canon(INPUTS / "canon")
    voice = load_voice(INPUTS / "design" / "voice.json")
    scenes = load_scenes(INPUTS / "design" / "scene.json")
    text = (INPUTS / "rewrite" / "ch01.md").read_text(encoding="utf-8")
    broken = text.replace("風はまだ強かったが",
                          "選ばれし者が雷を呼んだ。書き換えられた頁。")
    report = check_rewrite(broken, "ch01", log, canon, voice, scenes,
                           avoid=("古代の予言",))
    checks = {item["check"] for item in report["findings"]}
    assert "voice_contract" in checks
    assert "fact_boundary" in checks
    assert any("F-04" in item["message_ja"] or "F-03" in item["message_ja"]
               for item in report["findings"])


# -- P0: resume, record integrity, Stage B only, dead mentions ---------------
def _stub_provider(tmp_path: Path, name: str, body: str) -> str:
    """A command provider whose behaviour is written in its own source."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return f"{sys.executable} {path}"


FAIL_AT_CH02 = """
import json, sys
req = json.load(sys.stdin)
if req["purpose"].startswith("stage_b:ch02"):
    sys.stderr.write("boom\\n")
    sys.exit(1)
base = "%s/"
name = "game_log.json" if not req["purpose"].startswith("stage_b") else \\
    "rewrite/" + req["purpose"].split(":")[1] + ".md"
print(json.dumps({"text": open(base + name, encoding="utf-8").read()}))
""" % (INPUTS,)

STAGE_B_ONLY = """
import json, sys
req = json.load(sys.stdin)
if not req["purpose"].startswith("stage_b"):
    sys.stderr.write("stage A must not be requested in --stage b\\n")
    sys.exit(9)
print(json.dumps({"text": open("%s/rewrite/" + req["purpose"].split(":")[1]
                               + ".md", encoding="utf-8").read()}))
""" % (INPUTS,)


def test_resume_command_is_complete_and_executable(tmp_path):
    import shlex

    out = tmp_path / "bundle"
    assert run_cli(out, "--seed", "3", run_id="cmd").returncode == 0
    state = read_json(out / "cmd" / "state.json")
    command = state["resume_command"]
    for flag in ("--script", "--seed 3", "--allow-temp-out", "--resume", "--task t01"):
        assert flag in command, (flag, command)
    assert state["argv"] and state["resume_count"] == 0
    completed = subprocess.run(shlex.split(command), cwd=REPO_ROOT,
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert read_json(out / "cmd" / "state.json")["resume_count"] == 1


def test_resume_keeps_the_record_and_replays_without_duplicating(tmp_path):
    out = tmp_path / "bundle"
    assert run_cli(out, run_id="replay").returncode == 0
    path = out / "replay" / "responses.jsonl"
    before = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    assert len(before) == 4
    completed = run_cli(out, "--resume", run_id="replay")
    assert completed.returncode == 0, completed.stderr
    after = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    assert len(after) == 4, "a replayed answer must not be appended twice"
    assert [row["ts"] for row in after] == [row["ts"] for row in before], \
        "resume must not rewrite the recorded timestamps"
    replay = read_json(out / "replay" / "replay.report.json")
    assert replay["counts"] == {"replayed": 4}
    assert replay["duplicate_record_keys"] == []


def test_resume_with_a_different_seed_is_refused_and_can_be_allowed(tmp_path):
    out = tmp_path / "bundle"
    assert run_cli(out, run_id="seeded").returncode == 0
    refused = run_cli(out, "--resume", "--seed", "7", run_id="seeded")
    assert refused.returncode == 2
    assert "config mismatch on resume: seed" in refused.stderr
    assert read_json(out / "seeded" / "state.json")["config"]["seed"] == 0
    allowed = run_cli(out, "--resume", "--seed", "7", "--allow-config-change",
                      run_id="seeded")
    assert allowed.returncode == 0, allowed.stderr
    state = read_json(out / "seeded" / "state.json")
    assert state["config"]["seed"] == 7
    assert "seed" in state["config_changes"]
    replay = read_json(out / "seeded" / "replay.report.json")
    assert replay["counts"].get("missing") == 4  # no answer matches this seed


def test_a_provider_failure_still_writes_resumable_state(tmp_path):
    out = tmp_path / "bundle"
    command = _stub_provider(tmp_path, "fail.py", FAIL_AT_CH02)
    failed = run_cli(out, "--command", command, provider="command", run_id="half")
    assert failed.returncode == 2
    run = out / "half"
    state = read_json(run / "state.json")
    assert state["status"] == "failed"
    assert "boom" in state["error"]
    assert "--resume" in state["resume_command"]
    entries = [json.loads(line) for line in
               (run / "responses.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    assert [row["purpose"] for row in entries] == ["stage_a", "stage_b:ch01"]

    # The same failing provider is usable again: the record is kept and replayed.
    again = run_cli(out, "--resume", "--command", command, provider="command",
                    run_id="half")
    assert again.returncode == 2
    entries = [json.loads(line) for line in
               (run / "responses.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    assert [row["purpose"] for row in entries] == ["stage_a", "stage_b:ch01"], \
        "an interrupted resume must not drop the earlier records"
    assert read_json(run / "state.json")["resume_count"] == 1


def test_a_modified_recorded_response_is_refused(tmp_path):
    out = tmp_path / "bundle"
    assert run_cli(out, run_id="tamper").returncode == 0
    path = out / "tamper" / "responses.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    entries[0]["response"]["text"] = entries[0]["response"]["text"].replace("嵐", "霧")
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
                    encoding="utf-8")
    completed = run_cli(out, "--resume", run_id="tamper")
    assert completed.returncode == 2
    assert "response_sha256" in completed.stderr
    assert read_json(out / "tamper" / "state.json")["status"] == "failed"


def test_stage_b_only_rewrites_a_verified_log_without_calling_stage_a(tmp_path):
    out = tmp_path / "bundle"
    command = _stub_provider(tmp_path, "stageb.py", STAGE_B_ONLY)
    completed = run_cli(out, "--stage", "b", "--game-log",
                        str(INPUTS / "game_log.json"), "--command", command,
                        provider="command", run_id="b-only")
    assert completed.returncode == 0, completed.stderr
    run = out / "b-only"
    summary = read_json(run / "run-summary.json")
    assert summary["stage"] == "b"
    assert summary["stage_a"]["source"] == "provided"
    assert summary["stage_a"]["attempts"] == 0
    assert summary["stage_b"]["status"] == "clean"
    purposes = [json.loads(line)["purpose"] for line in
                (run / "responses.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
    assert purposes == ["stage_b:ch01", "stage_b:ch02", "stage_b:ch03"]
    assert (run / "inputs" / "game_log.input.json").is_file()
    assert any("入力ログ" in limit for limit in summary["limits"])


def test_stage_b_only_refuses_a_log_that_fails_its_checks(tmp_path):
    raw = json.loads((INPUTS / "game_log.json").read_text(encoding="utf-8"))
    raw["chapters"][0]["scenes"][0]["present_characters"].append("johan")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "bundle"
    command = _stub_provider(tmp_path, "stageb2.py", STAGE_B_ONLY)
    refused = run_cli(out, "--stage", "b", "--game-log", str(broken),
                      "--command", command, provider="command", run_id="b-broken")
    assert refused.returncode == 2
    assert "fail-closed" in refused.stderr
    state = read_json(out / "b-broken" / "state.json")
    assert state["status"] == "unresolved"
    assert "fail-closed" in state["error"]

    # The refused run left a resumable state; the override continues it.
    allowed = run_cli(out, "--stage", "b", "--game-log", str(broken),
                      "--allow-unverified-log", "--command", command, "--resume",
                      "--report-only", provider="command", run_id="b-broken")
    assert allowed.returncode == 0, allowed.stderr
    summary = read_json(out / "b-broken" / "run-summary.json")
    assert summary["stage_a"]["unverified"] is True
    # Stage B was attempted from the overriding log, so text exists even if the
    # rewrite checks are not clean.
    assert (out / "b-broken" / "text" / "ch01.md").is_file()


def test_stage_selection_rejects_contradictory_arguments(tmp_path):
    out = tmp_path / "bundle"
    missing = run_cli(out, "--stage", "b", run_id="x")
    assert missing.returncode == 2 and "--game-log" in missing.stderr
    extra = run_cli(out, "--game-log", str(INPUTS / "game_log.json"), run_id="x")
    assert extra.returncode == 2 and "--stage b" in extra.stderr
    stage_a = run_cli(out, "--stage", "a", run_id="a-only")
    assert stage_a.returncode == 0, stage_a.stderr
    summary = read_json(out / "a-only" / "run-summary.json")
    assert summary["stage_a"]["status"] == "clean"
    assert summary["stage_b"]["status"] == "skipped"
    assert not (out / "a-only" / "text").exists()


def test_dead_mention_needs_its_medium_in_the_same_sentence():
    """A chapter-level record reference does not cover a present-time act."""
    log = load_game_log(INPUTS / "game_log.json")
    canon = load_canon(INPUTS / "canon")
    voice = load_voice(INPUTS / "design" / "voice.json")
    scenes = load_scenes(INPUTS / "design" / "scene.json")
    text = (INPUTS / "rewrite" / "ch01.md").read_text(encoding="utf-8")

    def check(body: str) -> dict:
        return check_rewrite(body, "ch01", log, canon, voice, scenes,
                             avoid=(), min_chars=200)

    declared = check(text)
    assert declared["summary"]["status"] == "clean"
    assert declared["summary"]["allowed_dead_references"] == 2

    acts = check(text.replace(
        "潮札を革袋に入れ、",
        "ヨハンが戸口から入ってきてアリアの肩を叩いた。潮札を革袋に入れ、"))
    assert acts["summary"]["status"] == "unresolved"
    hit = [f for f in acts["findings"] if f["check"] == "character_boundary"]
    assert hit and hit[0]["severity"] == "high"
    assert "同じ文にない" in hit[0]["message_ja"]

    speaks = check(text.replace(
        "潮札を革袋に入れ、", "「まだ灯りは消すな」とヨハンが言った。潮札を革袋に入れ、"))
    assert speaks["summary"]["status"] == "unresolved"

    # Legitimate recollection still passes: the cue is in the naming sentence.
    recalled = check(text.replace(
        "兄の名を父が口にしなかった理由を、アリアは聞いたことがなかった。",
        "あの嵐の夜、ヨハンは港町を守ろうとしていた。"))
    assert recalled["summary"]["status"] == "clean"


def test_results_claim_matches_the_provider(tmp_path):
    """A relay run must not be summarised with the scripted wording."""
    stage_a = {key: None for key in
               ("status", "attempts", "repairs", "first_attempt_findings",
                "findings", "checks", "markers", "marker_counts")}
    stage_a["allowed_dead_references"] = []
    summary = {
        "provider": {"name": "scripted", "model": "scripted-fixture"},
        "stage": "both",
        "evaluation_scope": {}, "inputs": {}, "stage_a": stage_a,
        "stage_b": {}, "l1_hygiene": {}, "status": "clean", "limits": [],
    }
    class _Prompt:
        digest = "0000000000000000"

    prompts = {name: _Prompt() for name in run_twostage.PROMPT_NAMES}
    out = tmp_path / "scripted.json"
    run_twostage._write_results(out, summary, prompts)
    scripted = json.loads(out.read_text(encoding="utf-8"))["claim"]
    assert "not a model response" in scripted

    summary["provider"] = {"name": "command", "model": "external"}
    summary["stage"] = "b"
    out = tmp_path / "relay.json"
    run_twostage._write_results(out, summary, prompts)
    relay = json.loads(out.read_text(encoding="utf-8"))["claim"]
    assert "not a model response" not in relay
    assert "not a reproducible model" in relay
    assert "supplied input" in relay


def test_a_missing_required_word_fails_the_work_not_the_chapter(tmp_path):
    """The required word is a work-level L1 metric (B-06)."""
    out = tmp_path / "bundle"
    provider = _stub_provider(tmp_path, "nokey.py", STAGE_B_ONLY.replace(
        ".read()", ".read().replace('鍵', '錠')"))

    completed = run_cli(out, "--stage", "b", "--game-log",
                        str(INPUTS / "game_log.json"), "--command", provider,
                        provider="command", run_id="no-key")
    assert completed.returncode == 1
    summary = read_json(out / "no-key" / "run-summary.json")
    assert summary["stage_b"]["status"] == "unresolved"
    assert summary["stage_b"]["missing_must_include"] == ["鍵"]
    # Every chapter's own checks still pass: only the work-level gate failed.
    assert all(chapter["status"] == "clean"
               for chapter in summary["stage_b"]["chapters"])


def test_prompts_md_lists_only_the_unanswered_request(tmp_path):
    """Answered prompts are collapsed so the operator answers the open one (R-08)."""
    relay = tmp_path / "relay"
    command = f"{sys.executable} {REPO_ROOT / 'scripts' / 'chat_operator.py'} --dir {relay}"
    out = tmp_path / "bundle"

    first = run_cli(out, "--command", command, provider="command", run_id="pending")
    assert first.returncode == 3, first.stderr
    request_path = next((relay / "requests").glob("*.json"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    (relay / "responses").mkdir(parents=True, exist_ok=True)
    (relay / "responses" / request_path.name).write_text(json.dumps({
        "text": (INPUTS / "game_log.json").read_text(encoding="utf-8"),
        "prompt_hash": request["prompt_hash"],
        "model": "test-stub", "provenance": {"origin": "fresh"},
    }, ensure_ascii=False), encoding="utf-8")

    second = run_cli(out, "--resume", "--command", command, provider="command",
                     run_id="pending")
    assert second.returncode == 3, second.stderr
    prompts = (out / "pending" / "PROMPTS.md").read_text(encoding="utf-8")
    assert prompts.count("```text") == 1
    assert "stage_b/ch01" in prompts
    assert "stage_b/ch02" not in prompts
    assert "回答済みのプロンプト" in prompts


# -- deterministic time authority -------------------------------------------
def test_the_run_writes_a_derived_timeline_and_hands_it_to_stage_b(tmp_path):
    out = tmp_path / "bundle"
    results_path = tmp_path / "results.json"
    completed = run_cli(out, "--results", str(results_path))
    assert completed.returncode == 0, completed.stderr
    run = out / "fixed"

    timeline = read_json(run / "timeline.json")
    assert timeline["schema"] == "trpg-timeline-v1"
    assert timeline["mode"] == "deterministic"
    assert [row["day"] for row in timeline["chapters"]] == [1.0, 4.0, 7.0]
    assert [row["location"] for row in timeline["chapters"]] == [
        "灯台", "王都", "灯台"]
    # The number the prose must not have to compute itself.
    aria = timeline["chapters"][2]["characters"][0]
    assert aria["days_since_leaving_here"] == 6.0

    # It is a derived artifact: reproducible from the log plus canon alone.
    from asc.gamelog.world import derive_timeline
    canon = load_canon(run / "inputs" / "canon")
    again = derive_timeline(load_game_log(run / "game_log.json"), canon)
    assert json.dumps(again, ensure_ascii=False, sort_keys=True) == json.dumps(
        timeline, ensure_ascii=False, sort_keys=True)

    # The settled table reaches the prompt, so the model reads it, not derives it.
    prompt = (run / "stage_b" / "ch03-attempt-1.prompt.txt").read_text(
        encoding="utf-8")
    assert "この章の日: 7日目" in prompt
    assert "この場所を離れてから 6日" in prompt

    summary = read_json(run / "run-summary.json")
    assert summary["timeline"]["chapters"][2]["days"]["aria"]["leaving"] == 6.0
    assert read_json(results_path)["timeline"]["schema"] == "trpg-timeline-v1"


def _ch03_with_wrong_day(tmp_path):
    good = (INPUTS / "rewrite" / "ch03.md").read_text(encoding="utf-8")
    wrong = good.replace("灯台に戻ると、", "四日ぶりの灯台だった。灯台に戻ると、")
    assert "四日ぶり" in wrong
    responses = base_responses()
    responses["stage_b:ch03:t01"] = wrong
    responses["stage_b:ch03:repair:t01"] = wrong
    return write_script(tmp_path, responses)


def test_a_wrong_explicit_day_count_warns_but_does_not_repair(tmp_path):
    script = _ch03_with_wrong_day(tmp_path)
    out = tmp_path / "bundle"
    completed = run_cli(out, "--results", str(tmp_path / "results.json"),
                        script=script)
    assert completed.returncode == 0, completed.stderr
    run = out / "fixed"
    report = read_json(run / "rewrite.report.json")
    assert report["status"] == "clean"
    chapter = report["chapters"]["ch03"]
    assert chapter["attempts"] == 1          # no repair round was spent
    findings = [item for item in chapter["findings"]
                if item["check"] == "timeline_consistency"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert findings[0]["blocks_repair"] is False
    assert read_json(run / "run-summary.json")["timeline"]["strict"] is False


def test_strict_timeline_makes_the_same_chapter_a_repair(tmp_path):
    script = _ch03_with_wrong_day(tmp_path)
    out = tmp_path / "bundle"
    completed = run_cli(out, "--strict-timeline",
                        "--results", str(tmp_path / "results.json"),
                        script=script)
    assert completed.returncode == 1
    run = out / "fixed"
    report = read_json(run / "rewrite.report.json")
    assert report["status"] == "unresolved"
    assert report["chapters"]["ch03"]["attempts"] == 2
    assert read_json(run / "run-summary.json")["timeline"]["strict"] is True
    assert read_json(tmp_path / "results.json")["timeline"]["strict"] is True
