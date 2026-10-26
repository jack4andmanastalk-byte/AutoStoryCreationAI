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
                     "rewrite.report.json", "audit.json", "state.json",
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
    # The legacy string-based audit still reports dead-name mentions as medium.
    # This is not claimed as an improvement; Stage B classifies them explicitly.
    assert summary["l1_hygiene"]["continuity"]["by_type"] == {
        "dead_character_reappears": 3}
    assert summary["l1_hygiene"]["continuity"]["by_severity"] == {"medium": 3}

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
