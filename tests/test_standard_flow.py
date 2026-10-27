"""The standard flow: premise -> three inspected chapters, in one Arena session.

These tests pin the contract of [`docs/standard_flow.md`](../docs/standard_flow.md)
and the commands printed by [`docs/quickstart.md`](../docs/quickstart.md):

* ``story_project.py`` is the single standard entry point;
* generation defaults to the project relay (``<project>/relay``), so a missing
  answer stops the run instead of inventing text;
* ``relay export`` / ``relay ingest`` are the only handoff an operator needs;
* a finished work says where the manuscript is.

The answers used here are the repository's scripted fixture
(``benchmarks/protocol-v1/fixtures/project-demo.json``). They prove the wiring;
they are **not** model output and nothing here is a claim about quality.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "story_project.py"
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "project-demo.json"
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT / "src"))

from asc.pipeline import load_scripted_responses  # noqa: E402


def answers_by_purpose() -> dict[str, str]:
    responses = load_scripted_responses(FIXTURE)
    return {key: text for key, text in responses.items()}


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
    )


def init_project(root: Path, project_id: str = "prj-flow") -> Path:
    result = cli(
        "--root", str(root), "init",
        "--project-id", project_id,
        "--title", "潮の記録者",
        "--premise", "港町で失われた潮位記録を追う。",
        "--chapters", "3",
        "--target-chars", "1200",
    )
    assert result.returncode == 0, result.stderr
    return root / project_id


def export(root: Path, project_id: str) -> dict:
    result = cli("--root", str(root), "relay", "export", project_id, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def answer_pending(root: Path, project_id: str, answers: dict[str, str]) -> int:
    """Write the fixture text for every unanswered request; return how many."""
    summary = export(root, project_id)
    if not summary["pending"]:
        return 0
    index = json.loads(
        (Path(summary["out"]) / "index.json").read_text(encoding="utf-8")
    )
    blocks = []
    for row in index["pending"]:
        text = answers.get(row["purpose"])
        assert text is not None, f"no fixture answer for purpose {row['purpose']}"
        blocks.append(
            f"<<<ANSWER {row['tag']}>>>\n{text.rstrip()}\n<<<END {row['tag']}>>>"
        )
    answer_file = root / "answers.txt"
    answer_file.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    result = cli(
        "--root", str(root), "relay", "ingest", project_id,
        "--file", str(answer_file), "--json",
    )
    assert result.returncode == 0, result.stderr
    ingested = json.loads(result.stdout)
    assert not ingested["rejected"], ingested["rejected"]
    return len(ingested["written"])


def run_until_complete(root: Path, project_id: str, answers: dict[str, str]) -> list[int]:
    """Run, answer, resume - the loop an Arena session performs."""
    codes = []
    result = cli("--root", str(root), "run", project_id)
    codes.append(result.returncode)
    for _ in range(20):
        if result.returncode == 0:
            break
        assert result.returncode == 3, result.stderr
        assert answer_pending(root, project_id, answers) == 1
        result = cli("--root", str(root), "resume", project_id)
        codes.append(result.returncode)
    assert result.returncode == 0, result.stderr
    return codes


def test_the_default_provider_records_the_prompt_in_the_project_relay(tmp_path: Path):
    directory = init_project(tmp_path)
    result = cli("--root", str(tmp_path), "run", "prj-flow")
    assert result.returncode == 3
    assert "pending: plan" in result.stderr
    assert "PROMPTS.md" in result.stderr
    relay = directory / "relay"
    assert (relay / "requests").is_dir()
    assert (relay / "PROMPTS.md").is_file()
    # The response file named on stderr is the one the operator has to write.
    response = re.search(r"response: (\S+)", result.stderr).group(1)
    assert Path(response).parent == relay / "responses"
    assert not Path(response).exists()


def test_export_ingest_resume_reaches_three_chapters(tmp_path: Path):
    directory = init_project(tmp_path)
    codes = run_until_complete(tmp_path, "prj-flow", answers_by_purpose())
    assert codes[0] == 3 and codes[-1] == 0
    assert codes.count(3) == len(codes) - 1

    status = cli("--root", str(tmp_path), "status", "prj-flow", "--json")
    payload = json.loads(status.stdout)
    assert payload["state"] == "complete"
    assert payload["work"]["stages"] == {"plan": "done", "design": "done", "draft": "done"}
    assert payload["work"]["pending"]["count"] == 0
    # Each run recorded the relay provider, not an external model command.
    for run_id in payload["runs"]:
        manifest = json.loads(
            (directory / "runs" / run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["provider"] == "arena-relay"
        assert manifest["model"] == "arena-agent-mode"

    out = directory / "manuscript.md"
    render = cli(
        "--root", str(tmp_path), "render", "prj-flow", "--out", str(out),
    )
    assert render.returncode == 0, render.stderr
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 潮の記録者")
    assert len(re.findall(r"\{\{time: day=", text)) == 3
    assert "{{location:" in text


def test_status_reports_the_manuscript_of_a_finished_work(tmp_path: Path):
    directory = init_project(tmp_path)
    run_until_complete(tmp_path, "prj-flow", answers_by_purpose())
    status = cli("--root", str(tmp_path), "status", "prj-flow")
    assert status.returncode == 0
    # The finished work says where the manuscript goes before it is written,
    # and shows the file once it exists.
    assert "Manuscript: not written yet" in status.stdout
    assert "render prj-flow" in status.stdout
    out = directory / "manuscript.md"
    assert cli(
        "--root", str(tmp_path), "render", "prj-flow", "--out", str(out),
    ).returncode == 0
    status = cli("--root", str(tmp_path), "status", "prj-flow")
    assert f"Manuscript: {out}" in status.stdout


def test_a_script_still_selects_the_scripted_provider_on_its_own(tmp_path: Path):
    """``--script`` predates the relay default and must keep selecting it."""
    init_project(tmp_path)
    result = cli("--root", str(tmp_path), "run", "prj-flow", "--script", str(FIXTURE))
    assert result.returncode == 0, result.stderr
    assert "State: complete" in result.stdout
    assert not (tmp_path / "prj-flow" / "relay" / "requests").exists()


def test_relay_ingest_rejects_an_unknown_tag(tmp_path: Path):
    init_project(tmp_path)
    result = cli("--root", str(tmp_path), "run", "prj-flow")
    assert result.returncode == 3
    answer_file = tmp_path / "answers.txt"
    answer_file.write_text(
        "<<<ANSWER ZZZZ>>>\n本文\n<<<END ZZZZ>>>\n", encoding="utf-8",
    )
    result = cli(
        "--root", str(tmp_path), "relay", "ingest", "prj-flow",
        "--file", str(answer_file), "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["written"] == []
    assert payload["rejected"][0]["reason"] == "unknown tag"
    assert payload["still_pending"] == 1


def test_relay_status_before_any_request_points_at_the_first_run(tmp_path: Path):
    init_project(tmp_path)
    result = cli("--root", str(tmp_path), "relay", "status", "prj-flow", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["requests"] == 0
    assert payload["pending"] == []


@pytest.mark.parametrize("name", ["standard_flow.md", "quickstart.md"])
def test_the_standard_documents_exist_and_name_the_entry_point(name: str):
    path = DOCS / name
    assert path.is_file(), f"missing {path}"
    text = path.read_text(encoding="utf-8")
    assert "scripts/story_project.py" in text
    assert "run_pipeline" in text or "run_twostage" in text


def test_quickstart_commands_name_existing_scripts_and_subcommands():
    """A quickstart that drifts from the CLI is worse than no quickstart."""
    text = (DOCS / "quickstart.md").read_text(encoding="utf-8")
    commands = re.findall(
        r"(?:\.venv/bin/)?python3? (scripts/[A-Za-z_]+\.py)([^\n`]*)", text,
    )
    assert commands, "the quickstart should show runnable commands"
    help_output = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
    )
    assert help_output.returncode == 0
    subcommands = set(re.findall(r"^    ([a-z][\w-]*)", help_output.stdout, re.M))
    assert {"run", "resume", "render", "relay"} <= subcommands

    takes_value = {"--root", "--node", "--file", "--out", "--script", "--command",
                   "--relay-dir", "--model", "--provider"}
    for script, rest in commands:
        assert (ROOT / script).is_file(), f"quickstart names a missing script: {script}"
        if script != "scripts/story_project.py":
            continue
        tokens, skip, subcommand = rest.split(), False, None
        for token in tokens:
            if skip:
                skip = False
                continue
            if token in takes_value:
                skip = True
                continue
            if token.startswith("-"):
                continue
            subcommand = token
            break
        if subcommand is None:
            continue  # e.g. `--help` only
        assert subcommand in subcommands or subcommand.startswith("<"), (
            f"quickstart uses an unknown subcommand: {subcommand!r}"
        )
