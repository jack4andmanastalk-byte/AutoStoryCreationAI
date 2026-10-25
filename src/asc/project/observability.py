"""One shared work summary and one shared set of next actions.

``status`` and ``doctor`` answer overlapping questions.  Before this module they
did it with separate code: ``status`` counted pending/stale items for one node
and ``doctor`` counted them for the whole project, with different wording and
different advice.  Operators had to decide which command to believe.

This module holds the two pieces both commands share:

``summarize``
    A node-scoped, JSON-stable summary of one work: state, stage statuses,
    pending responses, stale counts, run counts, and *which of those areas were
    actually inspected*.  An uninspected count is ``None``, never ``0``, so
    "nothing there" and "not looked at" cannot be confused.

``build_actions``
    The recovery/next-step hints derived from that state.  ``status`` prints
    them, and ``doctor`` uses the same strings in its finding messages so the
    two commands cannot drift apart.

Neither function reads or writes the store.  Callers pass what they inspected.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

WORK_SUMMARY_SCHEMA = "asc-project-work-summary-v1"

STAGE_ORDER = ("plan", "design", "draft")

#: World record types whose stored JSON carries no ``content_version`` field.
#: Their packet reference is a hash computed at read time, so a rewrite of the
#: stored record is only visible by comparing against a recorded packet.
UNVERSIONED_WORLD_TYPES = frozenset({
    "time_frame", "time_span", "time_conversion", "region", "spatial_relation",
    "culture", "culture_state_relation",
})


def _stage_order(stages: Iterable[str]) -> list[str]:
    known = [stage for stage in STAGE_ORDER if stage in stages]
    return known + sorted(set(stages) - set(STAGE_ORDER))


def summarize(
    *,
    state: str,
    stages: dict[str, str] | None = None,
    pending: Sequence[dict[str, Any]] = (),
    stale_links: int = 0,
    stale_canon: int | None = None,
    stale_bindings: int | None = None,
    run_count: int | None = None,
    interrupted_runs: int | None = None,
    scope: str = "node",
    node_id: str | None = None,
) -> dict[str, Any]:
    """Build the summary both ``status`` and ``doctor`` expose as ``work``."""
    inspected = ["checkpoints", "links", "pending"]
    if stale_canon is not None:
        inspected.append("world_canon")
    if stale_bindings is not None:
        inspected.append("world_bindings")
    if interrupted_runs is not None:
        inspected.append("runs")
    ordered_stages: dict[str, str] | None = None
    completed: list[str] = []
    failed: list[str] = []
    waiting: list[str] = []
    next_stage: str | None = None
    if stages is not None:
        ordered_stages = {stage: stages[stage] for stage in _stage_order(stages)}
        completed = [stage for stage, value in ordered_stages.items() if value == "done"]
        failed = [stage for stage, value in ordered_stages.items() if value == "failed"]
        waiting = [
            stage for stage, value in ordered_stages.items()
            if value == "waiting_response"
        ]
        next_stage = next(
            (stage for stage, value in ordered_stages.items() if value != "done"),
            None,
        )
    ready = sum(1 for row in pending if row.get("response_ready"))
    return {
        "schema": WORK_SUMMARY_SCHEMA,
        "scope": scope,
        "node_id": node_id,
        "state": state,
        "stages": ordered_stages,
        "completed_stages": completed,
        "failed_stages": failed,
        "waiting_stages": waiting,
        "next_stage": next_stage,
        "pending": {
            "count": len(pending),
            "ready": ready,
            "waiting_for_reply": len(pending) - ready,
        },
        "stale": {
            "links": stale_links,
            "canon": stale_canon,
            "bindings": stale_bindings,
        },
        "runs": {
            "count": run_count,
            "interrupted": interrupted_runs,
        },
        "inspected": inspected,
    }


def _action(
    command: str, reason: str, *, name: str, **targets: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {"action": name, "command": command, "reason": reason}
    for key, value in targets.items():
        if value is not None:
            data[key] = value
    return data


def build_actions(
    *,
    project_id: str,
    state: str,
    failed_stages: Sequence[str] = (),
    waiting_stages: Sequence[str] = (),
    pending_ready: int = 0,
    stale_links: int = 0,
    stale_canon: int = 0,
    stale_bindings: int = 0,
    interrupted_runs: int = 0,
    record_changes: Sequence[dict[str, Any]] = (),
    link_id: str | None = None,
    binding_node_id: str | None = None,
    canon_entry_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return the next operator actions, most important first.

    Each entry carries a ready-to-run ``command`` (the same CLI a human would
    type) and a ``reason``.  Only existing commands appear here; this module
    never invents a repair path, and nothing is executed automatically.
    """
    base = "python3 scripts/story_project.py"
    actions: list[dict[str, Any]] = []
    for stage in failed_stages:
        actions.append(_action(
            f"{base} resume {project_id} --retry-failed",
            f"stage {stage} is failed; retry it as a new run",
            name="resume --retry-failed", stage=stage,
        ))
    if interrupted_runs:
        actions.append(_action(
            f"{base} resume {project_id}",
            f"{interrupted_runs} run(s) never recorded a finish",
            name="resume",
        ))
    if waiting_stages:
        if pending_ready:
            actions.append(_action(
                f"{base} resume {project_id}",
                "a response file exists; resume to continue",
                name="resume", stage=waiting_stages[0],
            ))
        else:
            actions.append(_action(
                f"{base} pending {project_id}",
                "write the pending response file, then resume",
                name="pending", stage=waiting_stages[0],
            ))
    if stale_bindings:
        command = f"{base} world bind {project_id}"
        if binding_node_id:
            command += f" --node {binding_node_id}"
        actions.append(_action(
            command,
            f"{stale_bindings} binding(s) point at an older revision",
            name="world bind", node_id=binding_node_id,
        ))
    if stale_canon:
        command = f"{base} world adopt-canon {project_id}"
        if canon_entry_id:
            command += f" --supersedes {canon_entry_id}"
        actions.append(_action(
            command,
            f"{stale_canon} adopted canon entry(ies) have a newer source revision",
            name="world adopt-canon", entry_id=canon_entry_id,
        ))
    if stale_links:
        command = f"{base} adopt-child {project_id}"
        if link_id:
            command += f" {link_id}"
        actions.append(_action(
            command,
            f"{stale_links} pinned child link(s) differ from the child revision",
            name="adopt-child", link_id=link_id,
        ))
    if record_changes:
        total = sum(int(entry.get("count", 1)) for entry in record_changes)
        for entry in record_changes:
            command = f"{base} diff {project_id}"
            if entry.get("node_id"):
                command += f" --node {entry['node_id']}"
            command += f" --left run:{entry['run_id']} --right current"
            actions.append(_action(
                command,
                f"{total} world record(s) differ from the recorded version",
                name="diff", run_id=entry.get("run_id"),
                node_id=entry.get("node_id"),
            ))
    if state == "not_started":
        actions.append(_action(
            f"{base} run {project_id} --provider command --command <provider command>",
            "no stage has started yet",
            name="run",
        ))
    return actions


def actions_from_record_changes(
    changes: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group world-record version changes into one ``diff`` hint per run."""
    by_run: dict[tuple[str, str], int] = {}
    for change in changes:
        key = (str(change.get("node_id")), str(change.get("run_id")))
        by_run[key] = by_run.get(key, 0) + 1
    return [
        {"run_id": run_id, "node_id": node_id, "count": count}
        for (node_id, run_id), count in sorted(by_run.items())
    ]


__all__ = [
    "STAGE_ORDER",
    "UNVERSIONED_WORLD_TYPES",
    "WORK_SUMMARY_SCHEMA",
    "actions_from_record_changes",
    "build_actions",
    "summarize",
]
