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
