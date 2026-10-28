"""The CI wiring is part of the design, so it gets tests.

These do not run GitHub Actions; they pin the properties that keep CI fast and
safe, which are exactly the properties that erode silently:

* repository CI must not be blocked by the dataset build (slot reservation),
* a superseded run must cancel rather than queue,
* a cancelled dataset run must never publish,
* CI must run on every push (no path filter that can be forgotten).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import fnmatch
import re
import shutil
import subprocess

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI = WORKFLOWS / "research-check.yml"
DATASET = WORKFLOWS / "dataset-refresh.yml"

# GitHub-hosted concurrency for the Free plan. The dataset job must leave room.
CONCURRENCY_BUDGET = 20
MIN_FREE_SLOTS = 6


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dataset() -> dict:
    return yaml.safe_load(DATASET.read_text(encoding="utf-8"))


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
    """The dataset bot pushes that branch in batches; it cannot change code."""
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


def test_ci_does_not_depend_on_the_dataset_build(ci, dataset):
    assert not set(ci["jobs"]) & set(dataset["jobs"])
    assert "needs" not in ci["jobs"]["check"]


# -- dataset build ---------------------------------------------------------

def test_dataset_shards_reserve_slots_for_ci(dataset):
    job = dataset["jobs"]["render-narou"]
    matrix = job["strategy"]["matrix"]["shard"]
    assert len(matrix) == 20
    declared = job["strategy"]["max-parallel"]
    assert "DATASET_MAX_PARALLEL" in declared, "keep the override documented"
    default = 12  # the literal fallback in the workflow
    assert default < CONCURRENCY_BUDGET - MIN_FREE_SLOTS
    assert CONCURRENCY_BUDGET - default - 2 >= MIN_FREE_SLOTS


def test_dataset_jobs_cancel_superseded_builds(dataset):
    for job_id in ("prepare", "render-narou"):
        concurrency = dataset["jobs"][job_id]["concurrency"]
        assert concurrency["cancel-in-progress"] is True, job_id
        assert "github.ref" in concurrency["group"], job_id
    # matrix shards must include matrix.shard so shards do not cancel each other
    assert "matrix.shard" in dataset["jobs"]["render-narou"]["concurrency"]["group"]
    # publishing is serialised instead: two force-pushes must not interleave
    publish = dataset["jobs"]["publish"]["concurrency"]
    assert publish["cancel-in-progress"] is False


def test_a_cancelled_build_never_publishes(dataset):
    condition = " ".join(dataset["jobs"]["publish"]["if"].split())
    assert "!cancelled()" in condition      # backfill on partial failure, but obey UI Cancel
    assert "always()" not in condition      # `always()` blocks standard GitHub UI Cancel
    assert "needs.prepare.result == 'success'" in condition
    assert "needs.render-narou.result != 'cancelled'" in condition


def test_dataset_refresh_cannot_be_started_by_branch_push(dataset):
    triggers = dataset[True] if True in dataset else dataset["on"]
    assert "push" not in triggers and "pull_request" not in triggers
    assert "workflow_dispatch" in triggers and "schedule" in triggers


def test_dataset_publish_only_from_main(dataset):
    condition = " ".join(dataset["jobs"]["publish"]["if"].split())
    assert "github.ref == 'refs/heads/main'" in condition


# -- release publishing ----------------------------------------------------

def publish_script(dataset: dict) -> str:
    steps = dataset["jobs"]["publish"]["steps"]
    return next(step["run"] for step in steps if "Release" in step.get("name", ""))


def test_release_assets_cannot_be_added_twice(dataset):
    """The 2026-10-23 incident: a glob matched the full catalog as well.

    `gh release upload` aborts on a duplicate name with HTTP 422, and because
    --clobber deletes the old asset first, the release was left without its
    PDF bundles.
    """
    script = publish_script(dataset)
    globs = [p for p in
             re.findall(r"data/datasets/narou_commercialized_rank[^ ]*\.jsonl", script)
             if "[" in p]
    assert globs, "expected the slice glob in the publish step"
    for pattern in globs:
        # shell glob semantics, which is what bash applies here
        assert not fnmatch.fnmatch(
            "data/datasets/narou_commercialized_ranked.jsonl", pattern), pattern
        assert fnmatch.fnmatch(
            "data/datasets/narou_commercialized_rank201_300.jsonl", pattern), pattern
    # and the list is deduplicated defensively before it is used
    assert "!seen[$0]++" in script
    assert "mapfile -t ASSETS" in script


def test_release_uploads_are_one_asset_at_a_time_with_retries(dataset):
    script = publish_script(dataset)
    assert 'gh release upload "$TAG_MAIN" "${ASSETS[@]}"' not in script
    assert "${ASSETS[@]}" in script          # still iterated
    assert "upload_with_retry" in script
    assert script.count("upload_with_retry \"$TAG_MAIN\"") >= 1


def test_release_step_verifies_what_it_published(dataset):
    script = publish_script(dataset)
    assert "verify_release()" in script
    assert "releases/tags/" in script
    assert "::error::" in script
    # a truncated or oversized archive must fail before the old asset is deleted
    assert "gzip -t" in script
    assert "2147483648" in script


def test_publish_step_is_valid_bash(dataset):
    if not shutil.which("bash"):
        pytest.skip("bash is not available")
    completed = subprocess.run(["bash", "-n"], input=publish_script(dataset),
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_prepare_step_reuses_seed_artifacts_but_survives_their_expiry(dataset):
    steps = dataset["jobs"]["prepare"]["steps"]
    script = next(step["run"] for step in steps
                  if "run" in step and "Prepare or reuse" in step.get("name", ""))
    # a pinned run id expires after 7 days; fall back to the newest successes
    assert "gh run list --workflow dataset-refresh.yml --status success" in script
    assert "reused_prep=0" in script


def test_workflows_declare_minimal_permissions(ci, dataset):
    assert ci["permissions"] == {"contents": "read"}
    assert dataset["permissions"]["contents"] == "write"


def test_dataset_build_is_cheap_enough_to_leave_minutes_for_ci(dataset):
    """One build is ~700 minutes; a weekly schedule alone exceeds 2,000/month."""
    triggers = dataset[True] if True in dataset else dataset["on"]
    cron = triggers["schedule"][0]["cron"]
    fields = cron.split()
    assert len(fields) == 5
    minute, hour, day_of_month, month, day_of_week = fields
    monthly = day_of_month.isdigit() and day_of_week == "*"
    assert monthly, f"expected a monthly schedule, got {cron!r}"
    assert "workflow_dispatch" in triggers


def test_both_workflows_can_move_to_a_self_hosted_runner(ci, dataset):
    """Self-hosted runners do not consume hosted minutes (docs/ci.md section 4)."""
    assert "CI_RUNNER_LABEL" in ci["jobs"]["check"]["runs-on"]
    for job in dataset["jobs"].values():
        assert "DATASET_RUNNER_LABEL" in job["runs-on"]


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
