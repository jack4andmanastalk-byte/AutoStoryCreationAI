"""U-02: one relay round, one work unit.

The operator's question in a long session is never "which file is next?" but
"where does this work stand, and what is the one thing I do now?".  These tests
pin the answer:

* ``relay status`` reports state, answered/pending counts, the request that is
  waiting, and the single next command;
* ``relay submit`` is that next command: ingest the answers and continue;
* a finished work says so and points at the manuscript, and submitting again
  changes nothing (no request is re-asked, no stored answer is overwritten);
* a failed stage points at ``--retry-failed`` instead of collecting answers that
  a retry would not reuse;
* the same handoff is what ``status`` / ``doctor`` suggest as the next action.

The answers are the repository's scripted fixture
(``benchmarks/protocol-v1/fixtures/project-demo.json``): a wiring check, not
model output, and no claim about quality.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "story_project.py"
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "project-demo.json"

sys.path.insert(0, str(ROOT / "src"))

from asc.pipeline import load_scripted_responses  # noqa: E402


def answers_by_purpose() -> dict[str, str]:
    return load_scripted_responses(FIXTURE)


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
    )


def init_project(root: Path, project_id: str = "prj-round", chapters: int = 3) -> Path:
    result = cli(
        "--root", str(root), "init",
        "--project-id", project_id,
        "--title", "潮の記録者",
        "--premise", "港町で失われた潮位記録を追う。",
        "--chapters", str(chapters),
        "--target-chars", "1200",
    )
    assert result.returncode == 0, result.stderr
    return root / project_id


def round_status(root: Path, project_id: str) -> dict:
    result = cli("--root", str(root), "relay", "status", project_id, "--json")
    assert result.returncode in {0, 2, 3}, result.stderr
    return json.loads(result.stdout)


def write_answers(root: Path, tag: str, purpose: str, answers: dict[str, str]) -> Path:
    path = root / "answers.txt"
    text = answers[purpose]
    path.write_text(
        f"<<<ANSWER {tag}>>>\n{text.rstrip()}\n<<<END {tag}>>>\n", encoding="utf-8",
    )
    return path


def submit(root: Path, project_id: str, file: Path) -> subprocess.CompletedProcess:
    return cli(
        "--root", str(root), "relay", "submit", project_id, "--file", str(file),
        "--json",
    )


def drive(root: Path, project_id: str, answers: dict[str, str]) -> list[dict]:
    """Run once, then one submit per round; return every round report."""
    first = cli("--root", str(root), "run", project_id)
    assert first.returncode == 3, first.stderr
    rounds = []
    for _ in range(30):
        status = round_status(root, project_id)
        if status["next"] is None:
            break
        row = status["next"]
        file = write_answers(root, row["tag"], row["purpose"], answers)
        result = submit(root, project_id, file)
        payload = json.loads(result.stdout)
        assert result.returncode in {0, 3}, (result.returncode, payload)
        rounds.append(payload["round"])
    return rounds


def test_one_submit_advances_exactly_one_request(tmp_path: Path):
    directory = init_project(tmp_path)
    answers = answers_by_purpose()
    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3

    before = round_status(tmp_path, "prj-round")
    assert before["next"]["purpose"] == "plan"
    assert before["next_command"].endswith("relay submit prj-round --file <answers.txt>")

    file = write_answers(tmp_path, before["next"]["tag"], "plan", answers)
    result = submit(tmp_path, "prj-round", file)
    payload = json.loads(result.stdout)
    assert result.returncode == 3, payload
    assert payload["ingest"]["written"] == [
        key for key in payload["ingest"]["written"]
    ]
    after = payload["round"]
    assert after["answered"] == 1
    assert after["next"]["purpose"] == "design:brief"
    # The plan answer is stored once and is not asked for again.
    requests = sorted((directory / "relay" / "requests").glob("*.json"))
    assert len(requests) == 2
    plan_requests = [path for path in requests if path.stem.endswith("-plan-a1")]
    assert len(plan_requests) == 1


def test_the_whole_work_drives_to_completion_and_reports_the_manuscript(tmp_path: Path):
    directory = init_project(tmp_path)
    rounds = drive(tmp_path, "prj-round", answers_by_purpose())

    # 12 requests: plan 1, design 8, draft 3. One round per request, no repeats.
    assert len(rounds) == 12
    assert [row["answered"] for row in rounds] == list(range(1, 13))
    final = rounds[-1]
    assert final["state"] == "complete"
    assert final["pending_count"] == 0
    assert final["next"] is None
    assert final["manuscript"]["path"] == str(directory / "manuscript.md")
    assert final["next_command"].endswith(
        f"render prj-round --out {directory / 'manuscript.md'}"
    )

    # One request per answered response: nothing was recorded twice.
    assert len(list((directory / "relay" / "requests").glob("*.json"))) == 12
    assert len(list((directory / "relay" / "responses").glob("*.json"))) == 12


def test_a_finished_round_reports_the_warnings_the_draft_stage_recorded(tmp_path: Path):
    """The draft warns about chapter length; a round is where a person reads it.

    The warnings used to live only in the run's ``draft.json``, so a completed
    work looked clean even when every chapter was far from the target.  They are
    warnings, not failures: the work still completes.
    """
    init_project(tmp_path, chapters=3)
    rounds = drive(tmp_path, "prj-round", answers_by_purpose())
    final = rounds[-1]
    assert final["state"] == "complete"
    assert final["warnings"], "the scripted chapters are far below 1200 chars"
    assert any("目安" in item for item in final["warnings"])

    human = cli("--root", str(tmp_path), "relay", "status", "prj-round")
    assert human.returncode == 0
    assert "Warnings:" in human.stdout
    assert "（目安 1140〜1260 字の外）" in human.stdout
    # The exit code still says "done", because a warning is not a failure.
    assert "complete" in human.stdout


def test_a_round_before_any_draft_reports_no_warnings(tmp_path: Path):
    init_project(tmp_path)
    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3
    status = round_status(tmp_path, "prj-round")
    assert status["warnings"] == []


def test_submitting_again_changes_nothing(tmp_path: Path):
    directory = init_project(tmp_path)
    drive(tmp_path, "prj-round", answers_by_purpose())
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (directory / "relay" / "responses").glob("*.json")
    }
    last_tag = round_status(tmp_path, "prj-round")["next"]
    assert last_tag is None
    # The operator re-submits the last file out of habit.
    file = tmp_path / "answers.txt"
    result = submit(tmp_path, "prj-round", file)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert "already complete" in payload["skipped"]
    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (directory / "relay" / "responses").glob("*.json")
    }
    assert after == before


def test_a_failed_stage_points_at_the_retry_not_at_more_answers(tmp_path: Path):
    # The fixture plan always has three chapters, so a two-chapter spec fails.
    init_project(tmp_path, chapters=2)
    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3
    status = round_status(tmp_path, "prj-round")
    file = write_answers(tmp_path, status["next"]["tag"], "plan", answers_by_purpose())
    first = submit(tmp_path, "prj-round", file)
    assert first.returncode == 2
    payload = json.loads(first.stdout)
    assert payload["round"]["state"] == "failed"
    assert payload["round"]["next_command"].endswith("resume prj-round --retry-failed")
    assert "plan stage failed" in payload["error"]

    # Another submit without --retry-failed collects nothing.
    second = submit(tmp_path, "prj-round", file)
    assert second.returncode == 2
    skipped = json.loads(second.stdout)["skipped"]
    assert "retrying it makes a new attempt" in skipped
    assert "--retry-failed" in skipped


def test_status_and_doctor_share_the_relay_next_action(tmp_path: Path):
    init_project(tmp_path)
    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3
    status = json.loads(
        cli("--root", str(tmp_path), "status", "prj-round", "--json").stdout
    )
    doctor = json.loads(
        cli("--root", str(tmp_path), "doctor", "prj-round", "--json").stdout
    )
    assert status["next_actions"] == doctor["next_actions"]
    action = status["next_actions"][0]
    assert action["action"] == "relay export"
    assert action["command"].endswith("relay export prj-round")

    human = cli("--root", str(tmp_path), "status", "prj-round")
    assert "Relay: 0 answered / 1 pending" in human.stdout
    assert "relay submit prj-round" in human.stdout


def test_relay_status_exit_codes_describe_the_round(tmp_path: Path):
    init_project(tmp_path)
    # Nothing recorded yet: not started, nothing pending.
    result = cli("--root", str(tmp_path), "relay", "status", "prj-round")
    assert result.returncode == 0
    assert "not_started" in result.stdout

    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3
    result = cli("--root", str(tmp_path), "relay", "status", "prj-round")
    assert result.returncode == 3
    assert "Next request: tag" in result.stdout
    # The stage prefix must not repeat itself ("draft: draft:ch02").
    assert "draft: draft:" not in result.stdout
    assert "design: design:" not in result.stdout

    drive_answers = answers_by_purpose()
    status = round_status(tmp_path, "prj-round")
    file = write_answers(tmp_path, status["next"]["tag"], "plan", drive_answers)
    submit(tmp_path, "prj-round", file)
    # Still waiting on the next request, so the exit code stays 3.
    assert cli("--root", str(tmp_path), "relay", "status", "prj-round").returncode == 3


def test_a_paste_with_no_matching_block_does_not_advance(tmp_path: Path):
    directory = init_project(tmp_path)
    assert cli("--root", str(tmp_path), "run", "prj-round").returncode == 3
    file = tmp_path / "answers.txt"
    file.write_text("本文だけ。タグが無い。\n", encoding="utf-8")
    result = submit(tmp_path, "prj-round", file)
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["ingest"]["written"] == []
    assert payload["round"]["answered"] == 0
    assert payload["round"]["next"]["purpose"] == "plan"
    # No response was invented and no new request was recorded.
    assert len(list((directory / "relay" / "requests").glob("*.json"))) == 1
    assert not (directory / "relay" / "responses").exists()


def test_revise_and_branch_use_the_relay_by_default_and_recover_one_chapter(tmp_path: Path):
    """U-04: regenerating one chapter or one design doc is one relay round.

    ``revise --chapter ch01`` and ``branch --design scene`` used to refuse an
    omitted ``--provider`` even though ``quickstart.md`` documented them without
    one.  They now take the same relay default as ``run`` / ``continue``: copy
    everything else byte for byte, ask only for the selected item, and finish in
    one ``relay submit``.
    """
    init_project(tmp_path)
    answers = answers_by_purpose()
    drive(tmp_path, "prj-round", answers)

    before_rendered = cli("--root", str(tmp_path), "render", "prj-round").stdout
    revised = cli("--root", str(tmp_path), "revise", "prj-round", "--chapter", "ch01")
    assert revised.returncode == 3, revised.stderr

    status = round_status(tmp_path, "prj-round")
    # Plan and design are carried over; only draft:ch01 is asked for.
    assert status["stages"] == {"plan": "done", "design": "done", "draft": "waiting_response"}
    assert status["pending_count"] == 1
    assert status["next"]["purpose"] == "draft:ch01"

    new_ch01 = "{{time: day=1}}{{location: 灯台}}\n" + "改訂した第一章の本文です。" * 25
    updated = dict(answers, **{"draft:ch01": new_ch01})
    file = write_answers(tmp_path, status["next"]["tag"], "draft:ch01", updated)
    done = submit(tmp_path, "prj-round", file)
    assert done.returncode == 0, done.stdout
    after = json.loads(done.stdout)["round"]
    assert after["state"] == "complete"
    assert after["answered"] == 13  # 12 from the first revision + 1 revised chapter

    after_rendered = cli("--root", str(tmp_path), "render", "prj-round").stdout
    assert "改訂した第一章の本文です。" in after_rendered
    assert after_rendered != before_rendered


def test_an_unresolved_design_doc_is_reported_and_points_at_revise_design(tmp_path: Path):
    """Fail-open design keeps going, so the round must say which doc needs revise.

    In the U-05 continuation dogfood, ``design:scene`` stayed ``unresolved`` and
    only ``doctor`` noticed.  The round report now names the doc and the exact
    ``revise --design <doc>`` command that regenerates just that document.
    """
    init_project(tmp_path)
    answers = answers_by_purpose()
    broken_scene = json.loads(answers["design:scene"])
    # Put a canon foreshadow ID in `planted`: the scene checker rejects it, and
    # repeating the same answer on the repair round leaves scene `unresolved`.
    broken_scene["scenes"][0]["foreshadows"]["planted"] = [
        {"id": "fs-001", "payoff": "ch03"}
    ]
    bad = dict(
        answers,
        **{
            "design:scene": json.dumps(broken_scene, ensure_ascii=False),
            "design:scene:repair": json.dumps(broken_scene, ensure_ascii=False),
        },
    )
    rounds = drive(tmp_path, "prj-round", bad)
    # 13 rounds: the 12 normal requests + 1 repair round for design:scene.
    assert len(rounds) == 13
    final = rounds[-1]
    assert final["state"] == "complete"
    assert any(
        "design (scene)" in item and "revise prj-round --design scene" in item
        for item in final["warnings"]
    )


def test_a_child_node_can_be_inspected_and_driven_and_reminds_about_adopt_child(tmp_path: Path):
    """U-06: ``relay status --node <child>`` and the ``adopt-child`` reminder."""
    init_project(tmp_path)
    answers = answers_by_purpose()
    drive(tmp_path, "prj-round", answers)

    added = cli(
        "--root", str(tmp_path), "add-child", "prj-round",
        "--node-id", "node-sub", "--link-id", "link-sub",
        "--title", "外伝", "--premise", "外伝の記録。",
        "--chapters", "3", "--target-chars", "1200",
    )
    assert added.returncode == 0, added.stderr

    # Root is still complete; `--node node-sub` inspects the child, not the root.
    assert round_status(tmp_path, "prj-round")["state"] == "complete"
    child_before = json.loads(
        cli("--root", str(tmp_path), "relay", "status", "prj-round", "--node", "node-sub", "--json").stdout
    )
    assert child_before["node_id"] == "node-sub"
    assert child_before["state"] == "not_started"

    assert cli("--root", str(tmp_path), "run", "prj-round", "--node", "node-sub").returncode == 3
    for _ in range(20):
        st = json.loads(
            cli("--root", str(tmp_path), "relay", "status", "prj-round", "--node", "node-sub", "--json").stdout
        )
        if st["next"] is None:
            break
        file = write_answers(tmp_path, st["next"]["tag"], st["next"]["purpose"], answers)
        res = cli(
            "--root", str(tmp_path), "relay", "submit", "prj-round",
            "--node", "node-sub", "--file", str(file), "--json",
        )
        assert res.returncode in {0, 3}, res.stdout

    child_done = json.loads(
        cli("--root", str(tmp_path), "relay", "status", "prj-round", "--node", "node-sub", "--json").stdout
    )
    assert child_done["state"] == "complete"
    # The initial revision is synced into link-sub automatically; a Pure copy
    # revise makes a newer child revision, so the link is now stale and the
    # round names `adopt-child` before `compose`.
    assert cli("--root", str(tmp_path), "revise", "prj-round", "--node", "node-sub").returncode == 0
    stale = json.loads(
        cli("--root", str(tmp_path), "relay", "status", "prj-round", "--node", "node-sub", "--json").stdout
    )
    assert any("adopt-child prj-round link-sub" in w for w in stale["warnings"])

    assert cli("--root", str(tmp_path), "adopt-child", "prj-round", "link-sub").returncode == 0
    after_adopt = json.loads(
        cli("--root", str(tmp_path), "relay", "status", "prj-round", "--node", "node-sub", "--json").stdout
    )
    assert not any("adopt-child" in w for w in after_adopt["warnings"])


def test_render_out_records_custom_manuscript_path_and_revision_for_relay_status(tmp_path: Path):
    """F-25: ``render --out`` is remembered per node/revision by ``relay status`` and ``status``."""
    init_project(tmp_path)
    answers = answers_by_purpose()
    drive(tmp_path, "prj-round", answers)

    before = round_status(tmp_path, "prj-round")
    assert before["manuscript"]["written"] is False
    assert before["manuscript"]["path"] == str(tmp_path / "prj-round" / "manuscript.md")

    custom_out = tmp_path / "exports" / "manuscript-v1.md"
    reader_out = tmp_path / "exports" / "manuscript-v1.reader.md"
    explicit_out = tmp_path / "exports" / "manuscript-v2.md"

    explicit_before = json.loads(
        cli(
            "--root", str(tmp_path), "relay", "status", "prj-round",
            "--out", str(custom_out), "--json",
        ).stdout
    )
    assert explicit_before["manuscript"]["path"] == str(custom_out)
    assert explicit_before["manuscript"]["written"] is False

    rendered = cli(
        "--root", str(tmp_path), "render", "prj-round", "--out", str(custom_out),
    )
    assert rendered.returncode == 0, rendered.stderr
    assert custom_out.is_file()

    rendered_reader = cli(
        "--root", str(tmp_path), "render", "prj-round",
        "--reader", "--out", str(reader_out),
    )
    assert rendered_reader.returncode == 0, rendered_reader.stderr
    assert reader_out.is_file()

    after = round_status(tmp_path, "prj-round")
    assert after["manuscript"]["path"] == str(custom_out)
    assert after["manuscript"]["written"] is True
    assert after["manuscript"]["reader_path"] == str(reader_out)

    human_relay = cli("--root", str(tmp_path), "relay", "status", "prj-round").stdout
    assert f"Manuscript: {custom_out}" in human_relay
    assert "(not written yet)" not in human_relay

    human_status = cli("--root", str(tmp_path), "status", "prj-round").stdout
    assert f"Manuscript: {custom_out}" in human_status
    assert "Manuscript: not written yet" not in human_status

    # Creating a newer revision marks the prior revision's custom file as not yet written
    # for the current revision until rendered again.
    assert cli("--root", str(tmp_path), "revise", "prj-round").returncode == 0
    revised = round_status(tmp_path, "prj-round")
    assert revised["manuscript"]["path"] == str(custom_out)
    assert revised["manuscript"]["written"] is False

    explicit_next = json.loads(
        cli(
            "--root", str(tmp_path), "relay", "status", "prj-round",
            "--out", str(explicit_out), "--json",
        ).stdout
    )
    assert explicit_next["manuscript"]["path"] == str(explicit_out)
    assert explicit_next["manuscript"]["written"] is False




@pytest.mark.parametrize("legacy", [False, True])
def test_pending_project_restores_from_git_checkpoint_in_another_directory(tmp_path: Path, legacy: bool):
    """A Git checkpoint must resume without relying on the old checkout's paths."""
    import shutil

    original = tmp_path / "original"
    original.mkdir()
    subprocess.run(["git", "init", "-q", str(original)], check=True)
    subprocess.run(["git", "-C", str(original), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(original), "config", "user.email", "test@example.invalid"], check=True)
    (original / ".gitignore").write_text("/runs/\n", encoding="utf-8")
    root = original / "works"
    project = init_project(root)
    assert cli("--root", str(root), "run", "prj-round").returncode == 3
    plan = round_status(root, "prj-round")["next"]
    assert submit(root, "prj-round", write_answers(root, plan["tag"], plan["purpose"], answers_by_purpose())).returncode == 3
    brief = round_status(root, "prj-round")["next"]
    assert brief["purpose"] == "design:brief"
    # Store the answer before checkpointing, but do not resume yet.
    answer = write_answers(root, brief["tag"], brief["purpose"], answers_by_purpose())
    result = cli("--root", str(root), "relay", "ingest", "prj-round", "--file", str(answer), "--json")
    assert result.returncode == 0, result.stderr
    saved = {p.name: p.read_bytes() for p in (project / "relay" / "responses").glob("*.json")}
    assert len(saved) == 2
    if legacy:
        # Checkpoints written before project-relative paths existed.
        checkpoint = next(p for p in project.glob("nodes/*/checkpoints/design.json"))
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        data["pending"].pop("request_path_relative", None)
        data["pending"].pop("response_path_relative", None)
        checkpoint.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["git", "-C", str(original), "add", ".gitignore", "works/prj-round"], check=True)
    subprocess.run(["git", "-C", str(original), "commit", "-qm", "pending project"], check=True)
    restored = tmp_path / "restored"
    subprocess.run(["git", "clone", "-q", str(original), str(restored)], check=True)
    shutil.rmtree(original)
    newroot = restored / "works"
    status = cli("--root", str(newroot), "status", "prj-round", "--json")
    assert status.returncode == 0, status.stderr
    pending = json.loads(status.stdout)["pending"][0]
    assert pending["response_ready"] is True
    assert str(newroot) in pending["response_path"]
    doctor = cli("--root", str(newroot), "doctor", "prj-round", "--json")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert json.loads(doctor.stdout)["pending"][0]["response_ready"] is True
    resumed = cli("--root", str(newroot), "resume", "prj-round", "--json")
    assert resumed.returncode == 3, resumed.stdout + resumed.stderr
    assert round_status(newroot, "prj-round")["next"]["purpose"] == "design:world"
    assert {p.name: p.read_bytes() for p in (newroot / "prj-round" / "relay" / "responses").glob("*.json")} == saved
    for _ in range(20):
        row = round_status(newroot, "prj-round")["next"]
        if row is None:
            break
        result = submit(newroot, "prj-round", write_answers(newroot, row["tag"], row["purpose"], answers_by_purpose()))
        assert result.returncode in (0, 3), result.stdout + result.stderr
    else:
        pytest.fail("restored project did not complete")
    assert round_status(newroot, "prj-round")["state"] == "complete"
    responses = newroot / "prj-round" / "relay" / "responses"
    assert len(list(responses.glob("*.json"))) == 12
    assert all((responses / name).read_bytes() == data for name, data in saved.items())
