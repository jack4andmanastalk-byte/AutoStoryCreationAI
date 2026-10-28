"""The CI wiring is part of the design, so it gets tests.

These do not run GitHub Actions; they pin the properties that keep CI fast and
safe, which are exactly the properties that erode silently:

* CI must run on every push (no path filter that can be forgotten),
* the dataset publication path stays removed (2026-10-29): the former
  `dataset-refresh` workflow, the `datasets` branch and the body-text
  publication ended. Silently reintroducing a publishing workflow would
  expose copyrighted material again,
* no workflow may publish on a schedule.

The former dataset-build property tests (shard slot reservation, cancelled-run
publish guards, release upload hardening) left with `dataset-refresh.yml`; the
incidents they documented are preserved in docs/ci.md section 5.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI = WORKFLOWS / "research-check.yml"
# Removed 2026-10-29 together with body-text publication
# (see docs/maintenance_status.md). The name stays pinned so that a silent
# reintroduction fails a test instead of republishing copyrighted files.
DATASET = WORKFLOWS / "dataset-refresh.yml"
DEBUG_NAROU = WORKFLOWS / "debug-narou.yml"


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def test_every_workflow_is_valid_yaml_with_jobs():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert files, "no workflows found"
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path.name
        assert data.get("jobs"), path.name
        for job_id, job in data["jobs"].items():
            assert job.get("runs-on") or job.get("uses"), f"{path.name}:{job_id}"
            assert job.get("timeout-minutes"), f"{path.name}:{job_id} has no timeout"


# -- repository CI ---------------------------------------------------------
def test_ci_runs_on_every_push_and_pull_request(ci):
    triggers = ci[True] if True in ci else ci["on"]
    push = triggers["push"]
    # a path filter is exactly how a new test file ends up untested
    assert "paths" not in push and "paths-ignore" not in push
    assert push["branches"] == ["**", "!datasets"]
    assert "pull_request" in triggers


def test_ci_skips_the_generated_datasets_branch(ci):
    """Legacy guard: the publishing branch was deleted on 2026-10-29.

    Keep the negative pattern so a re-created branch cannot burn runner
    slots on commits that cannot change code.
    """
    triggers = ci[True] if True in ci else ci["on"]
    branches = triggers["push"]["branches"]
    assert branches[-1] == "!datasets", "negative patterns must come last"


def test_ci_cancels_superseded_runs(ci):
    concurrency = ci["concurrency"]
    assert "github.ref" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is True


def test_ci_can_move_to_another_runner_without_a_code_change(ci):
    runs_on = ci["jobs"]["check"]["runs-on"]
    assert "CI_RUNNER_LABEL" in runs_on
    assert "ubuntu-latest" in runs_on


def test_actions_use_current_majors(ci):
    """Node 20 deprecation warnings appeared on checkout@v4 / setup-python@v5."""
    uses = [step["uses"] for step in ci["jobs"]["check"]["steps"] if "uses" in step]
    checkout = next(u for u in uses if u.startswith("actions/checkout@"))
    setup = next(u for u in uses if u.startswith("actions/setup-python@"))
    assert int(checkout.split("@v")[1]) >= 5
    assert int(setup.split("@v")[1]) >= 6


def test_ci_runs_the_whole_test_suite(ci):
    steps = ci["jobs"]["check"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    # a hand-maintained list of test files drifts; run the directory
    assert "pytest tests" in commands
    assert "build_research_catalog.py --check" in commands
    assert "audit_continuity.py" in commands
    assert "run_evaluation.py" in commands


def test_ci_declares_minimal_permissions(ci):
    assert ci["permissions"] == {"contents": "read"}


# -- removed publication workflow ------------------------------------------
def test_dataset_refresh_workflow_stays_removed():
    """Narou/Aozora body publication ended; do not bring it back silently."""
    assert not DATASET.exists(), (
        "dataset-refresh.yml must stay removed "
        "(record: docs/maintenance_status.md, 2026-10-29)"
    )
    assert not DEBUG_NAROU.exists(), "the narou download debug workflow must stay gone"


def test_no_workflow_publishes_on_a_schedule():
    """Scheduled triggers are how copyrighted data reappeared before."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = data[True] if True in data else data["on"]
        assert "schedule" not in triggers, f"{path.name} must not run on a schedule"
        if path.name == "research-check.yml":
            continue  # ordinary git events are fine for repository CI
        # any future workflow must not react to git events either
        assert "push" not in triggers and "pull_request" not in triggers, path.name


def test_docs_describe_the_budget():
    text = (REPO_ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
    assert "DATASET_MAX_PARALLEL" in text
    assert "CI_RUNNER_LABEL" in text
    assert "DATASET_RUNNER_LABEL" in text
    assert "20" in text
    # the billing incident and the arithmetic behind the schedule change
    assert "2,000" in text
    assert "700" in text
    # and the resolution: the repository is public, so hosted minutes are free
    assert "公開" in text
    assert "17 秒" in text
