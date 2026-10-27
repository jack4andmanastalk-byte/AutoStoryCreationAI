#!/usr/bin/env python3
"""Measure batch B against the rules that were fixed before it ran.

The registration lives in
``experiments/2026-10-realrun-b-t01/preregistration.json`` and is hashed into
the result. Thresholds and prompt-template digests are read from that file,
not chosen after seeing a run.

What it reads: one ``run_pipeline.py --system s1 --stage all`` run directory
per sample. What it writes: condition checks, per-stage counts, and a verdict
for each pre-registered rule. Prompt and response bodies are deliberately not
copied into the result.

The central B2 counting rule is explicit: design findings are counted from
``first_attempt.findings`` even when a repair removes them from the final
report. Final findings are recorded separately.

    python3 scripts/measure_realrun_b.py
    python3 scripts/measure_realrun_b.py --bundle experiments/2026-10-realrun-b-t01

A sample's directory must be ``<bundle>/sample-N/run``; ``--sample NAME=PATH``
overrides discovery, which is also how the script is tested against scripted
runs. A scripted run checks the arithmetic only; it is not evidence about a
real model's prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-b-t01"
REPAIR_SEVERITIES = {"high", "medium"}
ATTEMPT_FILE_RE = re.compile(r"-attempt-(\d+)\.txt$")
ISSUE_FILE_RE = re.compile(r"-attempt-(\d+)\.issues\.txt$")


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _sorted_counter(counter: Counter) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter, key=lambda item: str(item))}


def _count_values(items: list[dict], *keys: str) -> dict[str, int]:
    counter: Counter = Counter()
    for item in items:
        if not isinstance(item, dict):
            counter["unknown"] += 1
            continue
        value = next((item.get(key) for key in keys if item.get(key) not in (None, "")), "unknown")
        counter[str(value)] += 1
    return _sorted_counter(counter)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, violations: list[dict], label: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        violations.append({
            "code": f"artifact_malformed:{label}",
            "detail": f"{path.name}: {exc}",
        })
        return None
    if not isinstance(value, dict):
        violations.append({
            "code": f"artifact_malformed:{label}",
            "detail": f"{path.name}: expected a JSON object",
        })
        return None
    return value


def _add_violation(violations: list[dict], code: str, detail: str) -> None:
    item = {"code": code, "detail": detail}
    if item not in violations:
        violations.append(item)


def discover_samples(bundle: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for path in sorted(bundle.glob("sample-*/run")):
        if (path / "run-summary.json").is_file() or (path / "manifest.json").is_file():
            found.append((path.parent.name, path))
    return found


def _finding_identity(item: Any) -> tuple[str, str, str]:
    if not isinstance(item, dict):
        return ("unknown", "unknown", str(item))
    check = item.get("check") or item.get("id") or item.get("type") or "unknown"
    severity = item.get("severity") or "unknown"
    message = item.get("message_ja") or item.get("message") or ""
    return (str(check), str(severity), str(message))


def _summarise_findings(items: Any) -> dict:
    rows = [item for item in _as_list(items) if isinstance(item, dict)]
    # Malformed non-object entries still count as reported findings, but the
    # checkers in this repository emit objects. Keep the total based on the
    # source list rather than silently dropping anything unusual.
    raw_items = _as_list(items)
    return {
        "count": len(raw_items),
        "by_check": _count_values(raw_items, "check", "id", "type"),
        "by_severity": _count_values(raw_items, "severity"),
        "findings": [
            {
                "check": str(item.get("check") or item.get("id") or item.get("type") or "unknown"),
                "severity": str(item.get("severity") or "unknown"),
            }
            for item in rows
        ],
    }


def _findings_from_counts(count: Any, by_severity: Any) -> dict:
    severity_counts = {
        str(key): int(value)
        for key, value in _as_dict(by_severity).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    return {
        "count": _as_int(count) or 0,
        "by_check": {},
        "by_severity": dict(sorted(severity_counts.items())),
        "findings": [],
    }


def _repair_count(findings_summary: dict) -> int:
    by_severity = _as_dict(findings_summary.get("by_severity"))
    return sum(int(by_severity.get(name) or 0) for name in REPAIR_SEVERITIES)


def _read_responses(path: Path, violations: list[dict]) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    malformed = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _add_violation(violations, "artifact_malformed:responses.jsonl", str(exc))
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed = True
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            malformed = True
    if malformed:
        _add_violation(
            violations,
            "artifact_malformed:responses.jsonl",
            "one or more ledger lines are not JSON objects",
        )
    return rows


def _max_response_attempt(rows: list[dict], purposes: set[str]) -> int | None:
    attempts: list[int] = []
    for row in rows:
        if row.get("purpose") not in purposes:
            continue
        attempt = _as_int(_as_dict(row.get("context")).get("attempt"))
        if attempt is not None:
            attempts.append(attempt)
    return max(attempts) if attempts else None


def _attempt_numbers_from_files(directory: Path, chapter_id: str) -> tuple[list[int], dict[int, list[str]]]:
    attempts: set[int] = set()
    issues: dict[int, list[str]] = {}
    if not directory.is_dir():
        return [], issues
    for path in sorted(directory.glob(f"{chapter_id}-attempt-*")):
        issue_match = ISSUE_FILE_RE.search(path.name)
        if issue_match:
            attempt = int(issue_match.group(1))
            attempts.add(attempt)
            try:
                lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
            except OSError:
                lines = []
            issues[attempt] = [line for line in lines if line]
            continue
        attempt_match = ATTEMPT_FILE_RE.search(path.name)
        if attempt_match:
            attempts.add(int(attempt_match.group(1)))
    return sorted(attempts), issues


def _summarise_design_doc(
    run_dir: Path,
    doc_name: str,
    summary_design: dict,
    violations: list[dict],
) -> dict:
    report_path = run_dir / "design" / f"{doc_name}.report.json"
    json_path = run_dir / "design" / f"{doc_name}.json"
    report = _load_json(report_path, violations, f"design/{doc_name}.report.json")
    summary_docs = _as_dict(summary_design.get("docs"))
    summary_doc = _as_dict(summary_docs.get(doc_name))

    if report is not None:
        first_block = _as_dict(report.get("first_attempt"))
        first_items = _as_list(first_block.get("findings"))
        final_items = _as_list(report.get("findings"))
        first = _summarise_findings(first_items)
        final = _summarise_findings(final_items)
        first_counter = Counter(_finding_identity(item) for item in first_items)
        final_counter = Counter(_finding_identity(item) for item in final_items)
        disappeared_exact = sum((first_counter - final_counter).values())
        new_exact = sum((final_counter - first_counter).values())
        status = str(report.get("status") or summary_doc.get("status") or "unknown")
        attempts = _as_int(report.get("attempts"))
        if attempts is None:
            attempts = _as_int(summary_doc.get("attempts")) or 0
        repairs = _as_int(report.get("repairs"))
        if repairs is None:
            repairs = _as_int(summary_doc.get("repairs"))
        if repairs is None:
            repairs = max(0, attempts - 1)
        checks_failed = _as_int(report.get("checks_failed"))
        first_checks_failed = _as_int(first_block.get("checks_failed"))
        prompt = _as_dict(report.get("prompt"))
    else:
        first = _findings_from_counts(
            summary_doc.get("first_attempt_findings"),
            summary_doc.get("first_attempt_by_severity"),
        )
        final = _findings_from_counts(
            summary_doc.get("findings"), summary_doc.get("by_severity")
        )
        disappeared_exact = 0
        new_exact = 0
        if summary_doc.get("status"):
            status = str(summary_doc["status"])
        elif json_path.is_file():
            status = "present_without_report"
        else:
            status = "not_reached"
        attempts = _as_int(summary_doc.get("attempts")) or 0
        repairs = _as_int(summary_doc.get("repairs"))
        if repairs is None:
            repairs = max(0, attempts - 1)
        checks_failed = _as_int(summary_doc.get("checks_failed"))
        first_checks_failed = _as_int(summary_doc.get("first_attempt_checks_failed"))
        prompt = {}

    first["checks_failed"] = first_checks_failed
    final["checks_failed"] = checks_failed
    return {
        "status": status,
        "attempts": attempts,
        "repairs": repairs,
        "report_present": report is not None,
        "json_present": json_path.is_file(),
        "first_attempt": first,
        "final": final,
        "first_repair_findings": _repair_count(first),
        "final_repair_findings": _repair_count(final),
        "disappeared_exact": disappeared_exact,
        "new_in_final_exact": new_exact,
        "prompt": {
            key: prompt.get(key)
            for key in ("name", "version", "digest")
            if prompt.get(key) is not None
        },
    }


def _summarise_design(
    run_dir: Path,
    expected_docs: list[str],
    summary_design: dict,
    violations: list[dict],
) -> dict:
    docs = {
        name: _summarise_design_doc(run_dir, name, summary_design, violations)
        for name in expected_docs
    }
    unresolved = [
        name for name in expected_docs if docs[name]["status"] == "unresolved"
    ]
    missing = [name for name in expected_docs if docs[name]["status"] == "missing"]
    for name in _as_list(summary_design.get("unresolved")):
        if str(name) in expected_docs and str(name) not in unresolved:
            unresolved.append(str(name))
    for name in _as_list(summary_design.get("missing")):
        if str(name) in expected_docs and str(name) not in missing:
            missing.append(str(name))
    unresolved = [name for name in expected_docs if name in set(unresolved)]
    missing = [name for name in expected_docs if name in set(missing)]

    def total(section: str, key: str = "count") -> int:
        return sum(int(_as_dict(doc.get(section)).get(key) or 0) for doc in docs.values())

    def merge_counts(section: str, key: str) -> dict[str, int]:
        counter: Counter = Counter()
        for doc in docs.values():
            values = _as_dict(_as_dict(doc.get(section)).get(key))
            for name, value in values.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    counter[str(name)] += int(value)
        return _sorted_counter(counter)

    return {
        "docs": docs,
        "docs_expected": len(expected_docs),
        "reports_present": sum(1 for doc in docs.values() if doc["report_present"]),
        "missing_reports": [
            name for name in expected_docs if not docs[name]["report_present"]
        ],
        "docs_not_reached": [
            name
            for name in expected_docs
            if docs[name]["status"] in {"not_reached", "present_without_report"}
        ],
        "unresolved": unresolved,
        "missing": missing,
        "attempts": sum(int(doc.get("attempts") or 0) for doc in docs.values()),
        "repairs": sum(int(doc.get("repairs") or 0) for doc in docs.values()),
        "first_attempt_findings": total("first_attempt"),
        "final_findings": total("final"),
        "first_repair_findings": sum(
            int(doc.get("first_repair_findings") or 0) for doc in docs.values()
        ),
        "final_repair_findings": sum(
            int(doc.get("final_repair_findings") or 0) for doc in docs.values()
        ),
        "disappeared_exact": sum(
            int(doc.get("disappeared_exact") or 0) for doc in docs.values()
        ),
        "new_in_final_exact": sum(
            int(doc.get("new_in_final_exact") or 0) for doc in docs.values()
        ),
        "docs_with_first_findings": [
            name
            for name in expected_docs
            if int(_as_dict(docs[name].get("first_attempt")).get("count") or 0) > 0
        ],
        "docs_with_multiple_attempts": [
            name for name in expected_docs if int(docs[name].get("attempts") or 0) > 1
        ],
        "first_by_check": merge_counts("first_attempt", "by_check"),
        "final_by_check": merge_counts("final", "by_check"),
        "first_by_severity": merge_counts("first_attempt", "by_severity"),
        "final_by_severity": merge_counts("final", "by_severity"),
    }


def _summarise_draft(
    run_dir: Path,
    summary: dict | None,
    draft_data: dict | None,
    responses: list[dict],
    length_band: tuple[int, int],
) -> dict:
    draft_block = _as_dict((summary or {}).get("draft")) or _as_dict(draft_data)
    chapter_rows: dict[str, dict] = {}
    ordered_ids: list[str] = []
    for row in _as_list(draft_block.get("chapters")):
        if not isinstance(row, dict) or not row.get("id"):
            continue
        chapter_id = str(row["id"])
        chapter_rows[chapter_id] = row
        if chapter_id not in ordered_ids:
            ordered_ids.append(chapter_id)

    discovered: set[str] = set(ordered_ids)
    text_dir = run_dir / "text"
    if text_dir.is_dir():
        discovered.update(path.stem for path in text_dir.glob("*.md"))
    draft_dir = run_dir / "draft"
    if draft_dir.is_dir():
        for path in draft_dir.glob("*-attempt-*"):
            prefix = path.name.split("-attempt-", 1)[0]
            if prefix:
                discovered.add(prefix)
    response_attempts: dict[str, list[int]] = {}
    for row in responses:
        purpose = str(row.get("purpose") or "")
        if not purpose.startswith("draft:"):
            continue
        chapter_id = str(_as_dict(row.get("context")).get("chapter") or purpose.split(":", 1)[1])
        discovered.add(chapter_id)
        attempt = _as_int(_as_dict(row.get("context")).get("attempt"))
        if attempt is not None:
            response_attempts.setdefault(chapter_id, []).append(attempt)
    for chapter_id in sorted(discovered):
        if chapter_id not in ordered_ids:
            ordered_ids.append(chapter_id)

    chapters: dict[str, dict] = {}
    for chapter_id in ordered_ids:
        row = chapter_rows.get(chapter_id, {})
        file_attempts, issues = _attempt_numbers_from_files(draft_dir, chapter_id)
        attempts_observed = max(
            file_attempts + response_attempts.get(chapter_id, []) + list(issues),
            default=0,
        )
        if row and attempts_observed == 0:
            attempts_observed = 1
        first_issues = issues.get(1, [])
        injected_value = row.get("injected", [])
        if isinstance(injected_value, list):
            injected = [str(item) for item in injected_value]
            injected_count = len(injected)
        elif isinstance(injected_value, (int, float)) and not isinstance(injected_value, bool):
            injected = []
            injected_count = int(injected_value)
        else:
            injected = []
            injected_count = 0
        markers_value = row.get("markers", 0)
        markers = (
            len(markers_value)
            if isinstance(markers_value, list)
            else (_as_int(markers_value) or 0)
        )
        chars = _as_int(row.get("chars"))
        chapters[chapter_id] = {
            "chars": chars,
            "in_length_band": (
                length_band[0] <= chars <= length_band[1] if chars is not None else False
            ),
            "day": row.get("day"),
            "location": row.get("location"),
            "attempts_observed": attempts_observed,
            "first_attempt_failed": bool(first_issues or attempts_observed > 1),
            "first_issues": first_issues,
            "issues_by_attempt": {
                str(attempt): values for attempt, values in sorted(issues.items())
            },
            "injected": injected,
            "injected_count": injected_count,
            "markers": markers,
        }

    known_chars = [
        int(row["chars"]) for row in chapters.values() if row.get("chars") is not None
    ]
    chars_total = _as_int(draft_block.get("chars"))
    if chars_total is None:
        chars_total = _as_int((summary or {}).get("chars"))
    if chars_total is None and known_chars:
        chars_total = sum(known_chars)
    return {
        "chapters": chapters,
        "chapters_total": len(chapters),
        "chars_total": chars_total,
        "chapters_in_length_band": sum(
            1 for row in chapters.values() if row["in_length_band"]
        ),
        "first_failed_chapters": [
            chapter_id
            for chapter_id in ordered_ids
            if chapters[chapter_id]["first_attempt_failed"]
        ],
        "injected_markers_total": sum(
            int(row.get("injected_count") or 0) for row in chapters.values()
        ),
        "must_include": draft_block.get("must_include"),
        "warnings_count": len(_as_list(draft_block.get("warnings_ja"))),
    }


def _summarise_audit(
    run_dir: Path, summary: dict | None, violations: list[dict]
) -> dict:
    report = _load_json(run_dir / "audit.json", violations, "audit.json")
    summary_audit = _as_dict((summary or {}).get("audit"))
    report_summary = _as_dict((report or {}).get("summary"))
    base = report_summary or summary_audit
    present = bool(base)
    report_violations = [
        item for item in _as_list((report or {}).get("violations")) if isinstance(item, dict)
    ]
    by_severity = _as_dict(base.get("by_severity"))
    if not by_severity and report_violations:
        by_severity = _count_values(report_violations, "severity")
    by_type = _as_dict(base.get("by_type"))
    if not by_type and report_violations:
        by_type = _count_values(report_violations, "type", "check", "id")
    return {
        "present": present,
        "source": "audit.json" if report_summary else ("run-summary.json" if summary_audit else None),
        "violations": _as_int(base.get("violations"))
        if base.get("violations") is not None
        else (len(report_violations) if report is not None else None),
        "by_severity": {
            str(key): int(value)
            for key, value in sorted(by_severity.items())
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
        "by_type": {
            str(key): int(value)
            for key, value in sorted(by_type.items())
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
        "high": int(by_severity.get("high") or 0),
        "checks_run": _as_int(base.get("checks_run")),
        "checks_skipped": _as_int(base.get("checks_skipped")),
        "ced_per_10k_chars": base.get("ced_per_10k_chars"),
        "chars": _as_int(base.get("chars")),
        "violation_details": [
            {
                "type": str(item.get("type") or item.get("check") or item.get("id") or "unknown"),
                "severity": str(item.get("severity") or "unknown"),
                "chapter": item.get("chapter"),
            }
            for item in report_violations
        ],
    }


def _prompt_pin_digest(pin: Any) -> str | None:
    if isinstance(pin, str):
        return pin
    if isinstance(pin, dict):
        value = pin.get("digest")
        return str(value) if value else None
    return None


def _check_condition(
    *,
    run_dir: Path,
    complete: bool,
    summary: dict | None,
    manifest: dict | None,
    plan_data: dict | None,
    plan_attempts: int | None,
    design: dict,
    draft: dict,
    canon_missing: list[str],
    prereg: dict,
    violations: list[dict],
) -> None:
    condition = _as_dict(prereg.get("condition"))
    if not run_dir.is_dir() or (summary is None and manifest is None):
        _add_violation(
            violations,
            "run_artifacts_missing",
            "neither run-summary.json nor manifest.json is present",
        )
        return

    if manifest is not None:
        checks = (
            ("task_id", condition.get("task"), "task_mismatch:manifest"),
            ("system", condition.get("system"), "system_mismatch:manifest"),
            ("seed", condition.get("seed"), "seed_mismatch"),
            ("temperature", condition.get("temperature"), "temperature_mismatch"),
        )
        for key, expected, code in checks:
            if expected is not None and manifest.get(key) != expected:
                _add_violation(
                    violations,
                    code,
                    f"manifest {key}={manifest.get(key)!r}, expected {expected!r}",
                )
    elif complete:
        _add_violation(violations, "artifact_missing:manifest.json", "manifest is missing")

    if summary is not None:
        summary_checks = (
            ("task", condition.get("task"), "task_mismatch:run-summary"),
            ("system", condition.get("system"), "system_mismatch:run-summary"),
            ("stage", condition.get("stage"), "stage_mismatch"),
        )
        for key, expected, code in summary_checks:
            if expected is not None and summary.get(key) != expected:
                _add_violation(
                    violations,
                    code,
                    f"run-summary {key}={summary.get(key)!r}, expected {expected!r}",
                )
        if not isinstance(summary.get("plan"), dict) or not (
            (_as_int(_as_dict(summary.get("plan")).get("attempts")) or 0) > 0
        ):
            _add_violation(
                violations,
                "canon_not_plan_generated",
                "run-summary.json has no positive plan.attempts",
            )
        if "draft_condition" in summary:
            _add_violation(
                violations,
                "external_canon_or_design_reused",
                "run-summary.json contains draft_condition from a shared-input draft run",
            )
        summary_design = _as_dict(summary.get("design"))
        if complete and (not summary_design or summary_design.get("status") == "skipped"):
            _add_violation(violations, "design_not_run", "the design stage did not run")
        summary_docs = _as_dict(summary_design.get("docs"))
        expected_docs = [
            str(name) for name in _as_list(condition.get("design_docs"))
        ]
        if summary_docs and set(summary_docs) != set(expected_docs):
            _add_violation(
                violations,
                "design_docs_mismatch",
                f"summary docs={sorted(summary_docs)!r}, expected={expected_docs!r}",
            )
        if complete and design.get("missing_reports"):
            _add_violation(
                violations,
                "design_reports_missing",
                f"missing reports for {design['missing_reports']!r}",
            )
        expected_chapters = _as_int(condition.get("chapters"))
        if (
            expected_chapters is not None
            and draft.get("chapters_total") not in (None, 0)
            and int(draft["chapters_total"]) != expected_chapters
        ):
            _add_violation(
                violations,
                "chapters_mismatch",
                f"draft chapters={draft['chapters_total']!r}, expected {expected_chapters!r}",
            )
        if complete and canon_missing:
            _add_violation(
                violations,
                "canon_files_missing",
                f"missing generated canon files: {canon_missing!r}",
            )

    # Prompt template pins. The manifest stores both template names and
    # per-purpose rendered-prompt hashes; only template-name entries are
    # compared here.
    pins = _as_dict(_as_dict(condition.get("prompt_set")).get("pins"))
    prompt_hashes = _as_dict((manifest or {}).get("prompt_hashes"))
    for name, pin in pins.items():
        expected_digest = _prompt_pin_digest(pin)
        if not expected_digest:
            continue
        actual = prompt_hashes.get(str(name))
        source = "manifest"
        if str(name) == "plan-repair" and plan_attempts and plan_attempts > 1:
            plan_prompt = _as_dict((plan_data or {}).get("prompt"))
            if plan_prompt.get("name") == "plan-repair":
                # After a repair attempt, the ledger's plan-repair entry is
                # the rendered prompt hash (purpose key), while plan.json
                # retains the repair template digest.
                actual = plan_prompt.get("digest")
                source = "plan.json"
            else:
                actual = None
        if actual is not None and str(actual) != expected_digest:
            _add_violation(
                violations,
                f"prompt_digest_mismatch:{name}",
                f"{source} digest={actual!r}, expected {expected_digest!r}",
            )
        elif complete and actual is None:
            _add_violation(
                violations,
                f"prompt_digest_missing:{name}",
                "the completed run has no comparable template digest",
            )

    plan_prompt = _as_dict((plan_data or {}).get("prompt"))
    if plan_prompt.get("name") and str(plan_prompt["name"]) in pins:
        expected_digest = _prompt_pin_digest(pins[str(plan_prompt["name"])])
        if expected_digest and plan_prompt.get("digest") != expected_digest:
            _add_violation(
                violations,
                f"prompt_digest_mismatch:plan.json:{plan_prompt['name']}",
                f"plan.json digest={plan_prompt.get('digest')!r}, expected {expected_digest!r}",
            )
    for doc_name, doc in _as_dict(design.get("docs")).items():
        prompt = _as_dict(_as_dict(doc).get("prompt"))
        prompt_name = prompt.get("name")
        if prompt_name and str(prompt_name) in pins:
            expected_digest = _prompt_pin_digest(pins[str(prompt_name)])
            if expected_digest and prompt.get("digest") != expected_digest:
                _add_violation(
                    violations,
                    f"prompt_digest_mismatch:design-report:{doc_name}",
                    f"report digest={prompt.get('digest')!r}, expected {expected_digest!r}",
                )


def summarise_sample(name: str, run_dir: Path, prereg: dict) -> dict:
    violations: list[dict] = []
    condition = _as_dict(prereg.get("condition"))
    summary = _load_json(run_dir / "run-summary.json", violations, "run-summary.json")
    manifest = _load_json(run_dir / "manifest.json", violations, "manifest.json")
    plan_data = _load_json(run_dir / "plan.json", violations, "plan.json")
    draft_data = _load_json(run_dir / "draft.json", violations, "draft.json")
    responses = _read_responses(run_dir / "responses.jsonl", violations)
    complete = summary is not None

    plan_attempts = _as_int(_as_dict((summary or {}).get("plan")).get("attempts"))
    if plan_attempts is None:
        plan_attempts = _as_int((plan_data or {}).get("attempts"))
    if plan_attempts is None:
        plan_attempts = _max_response_attempt(responses, {"plan", "plan-repair"})
    plan_first_error_present = (run_dir / "plan" / "attempt-1.error.txt").is_file()
    plan_first_failed = bool(
        plan_first_error_present or (plan_attempts is not None and plan_attempts > 1)
    )

    expected_canon_files = [
        str(item)
        for item in _as_list(
            _as_dict(condition.get("canon_policy")).get("expected_canon_files")
        )
    ]
    canon_hashes: dict[str, str] = {}
    canon_missing: list[str] = []
    for filename in expected_canon_files:
        path = run_dir / "canon" / filename
        if path.is_file():
            try:
                canon_hashes[filename] = _sha256_file(path)
            except OSError as exc:
                _add_violation(
                    violations,
                    f"artifact_unreadable:canon/{filename}",
                    str(exc),
                )
                canon_missing.append(filename)
        else:
            canon_missing.append(filename)

    expected_docs = [str(item) for item in _as_list(condition.get("design_docs"))]
    summary_design = _as_dict((summary or {}).get("design"))
    design = _summarise_design(run_dir, expected_docs, summary_design, violations)

    length_band_values = _as_list(prereg.get("length_band"))
    length_band = (
        int(length_band_values[0]),
        int(length_band_values[1]),
    ) if len(length_band_values) == 2 else (1000, 1400)
    draft = _summarise_draft(run_dir, summary, draft_data, responses, length_band)
    total_band_values = _as_list(prereg.get("total_length_band"))
    if len(total_band_values) == 2 and draft.get("chars_total") is not None:
        draft["total_in_length_band"] = bool(
            int(total_band_values[0])
            <= int(draft["chars_total"])
            <= int(total_band_values[1])
        )
    else:
        draft["total_in_length_band"] = False

    audit = _summarise_audit(run_dir, summary, violations)

    _check_condition(
        run_dir=run_dir,
        complete=complete,
        summary=summary,
        manifest=manifest,
        plan_data=plan_data,
        plan_attempts=plan_attempts,
        design=design,
        draft=draft,
        canon_missing=canon_missing,
        prereg=prereg,
        violations=violations,
    )

    provenance_counter: Counter = Counter()
    purpose_counter: Counter = Counter()
    for row in responses:
        purpose_counter[str(row.get("purpose") or "unknown")] += 1
        response = _as_dict(row.get("response"))
        provenance = _as_dict(response.get("provenance"))
        provenance_counter[str(provenance.get("origin") or "unspecified")] += 1

    status = (summary or {}).get("status") or (manifest or {}).get("status") or "incomplete"
    manifest_subset = {
        key: (manifest or {}).get(key)
        for key in (
            "run_id",
            "task_id",
            "system",
            "seed",
            "model",
            "model_version",
            "provider",
            "temperature",
            "response_count",
            "responses_sha256",
            "git_commit",
            "protocol_version",
            "status",
            "error",
        )
        if manifest is not None and key in manifest
    }
    plan_prompt = _as_dict((plan_data or {}).get("prompt"))
    return {
        "name": name,
        "run_dir": str(run_dir),
        "status": status,
        "complete": complete,
        "eligible": not violations,
        "condition_violations": violations,
        "manifest": manifest_subset,
        "plan": {
            "attempts": plan_attempts,
            "first_attempt_failed": plan_first_failed,
            "first_attempt_error_file_present": plan_first_error_present,
            "prompt": {
                key: plan_prompt.get(key)
                for key in ("name", "version", "digest")
                if plan_prompt.get(key) is not None
            },
        },
        "canon": {
            "summary": (summary or {}).get("canon"),
            "files_sha256": canon_hashes,
            "missing_files": canon_missing,
        },
        "design": design,
        "draft": draft,
        "audit": audit,
        "gates": (summary or {}).get("gates"),
        "responses": {
            "ledger_entries": len(responses),
            "manifest_response_count": _as_int((manifest or {}).get("response_count")),
            "by_purpose": _sorted_counter(purpose_counter),
            "provenance_counts": _sorted_counter(provenance_counter),
        },
    }


def _completion_label(sample: dict) -> str:
    if _as_list(sample.get("condition_violations")):
        return "condition_violation"
    if not sample.get("complete"):
        return "incomplete"
    design = _as_dict(sample.get("design"))
    if _as_list(design.get("unresolved")) or _as_list(design.get("missing")):
        return "complete_with_unresolved_design"
    if sample.get("status") != "pass":
        return "complete_but_gate_fail"
    return "complete_pass"


def _first_attempt_label(sample: dict) -> str:
    if _as_list(sample.get("condition_violations")):
        return "condition_violation"
    if not sample.get("complete"):
        return "incomplete"
    design = _as_dict(sample.get("design"))
    draft = _as_dict(sample.get("draft"))
    plan = _as_dict(sample.get("plan"))
    plan_first_failed = bool(plan.get("first_attempt_failed"))
    design_first_total = int(design.get("first_attempt_findings") or 0)
    draft_first_failed = bool(_as_list(draft.get("first_failed_chapters")))
    first_any = plan_first_failed or design_first_total > 0 or draft_first_failed
    final_unresolved = bool(
        _as_list(design.get("unresolved"))
        or _as_list(design.get("missing"))
        or int(design.get("final_repair_findings") or 0) > 0
    )
    if not first_any:
        return "first_attempt_clean"
    if final_unresolved:
        return "first_attempt_findings_unresolved"
    repaired_indicator = bool(
        plan_first_failed
        or draft_first_failed
        or int(design.get("first_repair_findings") or 0) > 0
        or _as_list(design.get("docs_with_multiple_attempts"))
        or int(design.get("disappeared_exact") or 0) > 0
    )
    if repaired_indicator:
        return "first_attempt_findings_repaired"
    return "first_attempt_findings_remain_nonblocking"


def _length_label(sample: dict, prereg: dict) -> str:
    if _as_list(sample.get("condition_violations")):
        return "condition_violation"
    if not sample.get("complete"):
        return "not_enough_data"
    draft = _as_dict(sample.get("draft"))
    need = int(_as_dict(_as_dict(prereg.get("rules")).get("B3_length")).get(
        "min_chapters_in_band", 2
    ))
    chapter_ok = int(draft.get("chapters_in_length_band") or 0) >= need
    total_ok = bool(draft.get("total_in_length_band"))
    if chapter_ok and total_ok:
        return "length_ok"
    if chapter_ok or total_ok:
        return "length_mixed"
    return "length_outside"


def _audit_label(sample: dict) -> str:
    if _as_list(sample.get("condition_violations")):
        return "condition_violation"
    if not sample.get("complete"):
        return "not_measured"
    audit = _as_dict(sample.get("audit"))
    if not audit.get("present"):
        return "not_measured"
    if int(audit.get("high") or 0) > 0:
        return "audit_high_present"
    if int(audit.get("checks_skipped") or 0) > 0:
        return "audit_incomplete_coverage"
    return "audit_no_high_all_checks_ran"


def _aggregate(labels: list[str], priority: list[str]) -> str:
    for label in priority:
        if label in labels:
            return label
    return labels[0] if labels else "not_enough_data"


def verdicts(samples: dict[str, dict], prereg: dict) -> dict:
    planned = int(prereg.get("samples_planned") or 0)
    enough = len(samples) >= planned if planned else bool(samples)
    if not samples:
        return {
            "samples_present": 0,
            "samples_planned": planned,
            "enough_samples": False,
            "B0_condition": {"verdict": "not_run", "violations_by_sample": {}},
            "B1_completion": {"verdict": "not_run", "by_sample": {}},
            "B2_first_attempt": {"verdict": "not_enough_data", "by_sample": {}},
            "B3_length": {"verdict": "not_enough_data", "by_sample": {}},
            "B4_audit": {"verdict": "not_enough_data", "by_sample": {}},
        }

    completion = {name: _completion_label(row) for name, row in samples.items()}
    first_attempt = {
        name: _first_attempt_label(row) for name, row in samples.items()
    }
    length = {name: _length_label(row, prereg) for name, row in samples.items()}
    audit = {name: _audit_label(row) for name, row in samples.items()}
    violations_by_sample = {
        name: [
            str(item.get("code") or "unknown")
            for item in _as_list(row.get("condition_violations"))
            if isinstance(item, dict)
        ]
        for name, row in samples.items()
        if _as_list(row.get("condition_violations"))
    }

    if violations_by_sample:
        condition_verdict = "condition_violation"
        completion_verdict = "condition_violation"
        first_verdict = "condition_violation"
        length_verdict = "condition_violation"
        audit_verdict = "condition_violation"
    elif not enough:
        condition_verdict = "not_enough_data"
        completion_verdict = "not_enough_data"
        first_verdict = "not_enough_data"
        length_verdict = "not_enough_data"
        audit_verdict = "not_enough_data"
    else:
        condition_verdict = "condition_ok"
        completion_verdict = _aggregate(
            list(completion.values()),
            [
                "incomplete",
                "complete_with_unresolved_design",
                "complete_but_gate_fail",
                "complete_pass",
            ],
        )
        first_verdict = _aggregate(
            list(first_attempt.values()),
            [
                "incomplete",
                "first_attempt_findings_unresolved",
                "first_attempt_findings_repaired",
                "first_attempt_findings_remain_nonblocking",
                "first_attempt_clean",
            ],
        )
        length_labels = list(length.values())
        if all(label == "length_ok" for label in length_labels):
            length_verdict = "length_ok"
        elif all(label == "length_outside" for label in length_labels):
            length_verdict = "length_outside"
        elif "not_enough_data" in length_labels:
            length_verdict = "not_enough_data"
        else:
            length_verdict = "length_mixed"
        audit_verdict = _aggregate(
            list(audit.values()),
            [
                "audit_high_present",
                "audit_incomplete_coverage",
                "not_measured",
                "audit_no_high_all_checks_ran",
            ],
        )

    first_details = {}
    for name, row in samples.items():
        design = _as_dict(row.get("design"))
        draft = _as_dict(row.get("draft"))
        plan = _as_dict(row.get("plan"))
        first_details[name] = {
            "plan_first_attempt_failed": bool(plan.get("first_attempt_failed")),
            "design_first_attempt_findings": int(
                design.get("first_attempt_findings") or 0
            ),
            "design_final_findings": int(design.get("final_findings") or 0),
            "design_disappeared_exact": int(design.get("disappeared_exact") or 0),
            "design_docs_with_first_findings": _as_list(
                design.get("docs_with_first_findings")
            ),
            "design_first_by_check": _as_dict(design.get("first_by_check")),
            "draft_first_failed_chapters": _as_list(
                draft.get("first_failed_chapters")
            ),
        }

    return {
        "samples_present": len(samples),
        "samples_planned": planned,
        "enough_samples": enough,
        "B0_condition": {
            "verdict": condition_verdict,
            "violations_by_sample": violations_by_sample,
        },
        "B1_completion": {"verdict": completion_verdict, "by_sample": completion},
        "B2_first_attempt": {
            "verdict": first_verdict,
            "by_sample": first_attempt,
            "counting_rule": _as_dict(
                _as_dict(_as_dict(prereg.get("rules")).get("B2_first_attempt")).get(
                    "counting_rule"
                )
            ).get("primary"),
            "details": first_details,
        },
        "B3_length": {
            "verdict": length_verdict,
            "by_sample": length,
            "details": {
                name: {
                    "chapters_in_length_band": _as_dict(row.get("draft")).get(
                        "chapters_in_length_band"
                    ),
                    "chars_total": _as_dict(row.get("draft")).get("chars_total"),
                    "total_in_length_band": _as_dict(row.get("draft")).get(
                        "total_in_length_band"
                    ),
                }
                for name, row in samples.items()
            },
        },
        "B4_audit": {
            "verdict": audit_verdict,
            "by_sample": audit,
            "details": {
                name: {
                    "present": bool(_as_dict(row.get("audit")).get("present")),
                    "violations": _as_dict(row.get("audit")).get("violations"),
                    "high": _as_dict(row.get("audit")).get("high"),
                    "checks_skipped": _as_dict(row.get("audit")).get(
                        "checks_skipped"
                    ),
                    "ced_per_10k_chars": _as_dict(row.get("audit")).get(
                        "ced_per_10k_chars"
                    ),
                }
                for name, row in samples.items()
            },
        },
    }


def _registration_checks(prereg: dict) -> dict:
    tasks_file = _as_dict(_as_dict(prereg.get("condition")).get("tasks_file"))
    relative_path = str(tasks_file.get("path") or "")
    registered_sha = tasks_file.get("sha256")
    current_sha = None
    if relative_path:
        path = Path(relative_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_file():
            current_sha = _sha256_file(path)
    return {
        "tasks_file": {
            "path": relative_path or None,
            "registered_sha256": registered_sha,
            "current_sha256": current_sha,
            "matches": bool(registered_sha and current_sha == registered_sha),
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument(
        "--preregistration", default=None, help="default: <bundle>/preregistration.json"
    )
    parser.add_argument(
        "--sample",
        action="append",
        default=None,
        metavar="NAME=RUN_DIR",
        help="override discovery (repeatable)",
    )
    parser.add_argument("--out", default=None, help="default: <bundle>/results.json")
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    prereg_path = Path(args.preregistration or bundle / "preregistration.json")
    prereg_bytes = prereg_path.read_bytes()
    prereg = json.loads(prereg_bytes.decode("utf-8"))

    if args.sample:
        pairs: list[tuple[str, Path]] = []
        for entry in args.sample:
            name, separator, path = entry.partition("=")
            if not separator or not name or not path:
                raise SystemExit(f"--sample needs NAME=PATH, got {entry!r}")
            pairs.append((name, Path(path)))
    else:
        pairs = discover_samples(bundle)

    samples = {
        name: summarise_sample(name, path, prereg) for name, path in pairs
    }
    result = {
        "schema": "realrun-b-v1",
        "experiment": prereg.get("experiment"),
        "preregistration": {
            "path": str(prereg_path.relative_to(REPO_ROOT))
            if prereg_path.is_absolute() and REPO_ROOT in prereg_path.parents
            else str(prereg_path),
            "sha256": hashlib.sha256(prereg_bytes).hexdigest(),
        },
        "registration_checks": _registration_checks(prereg),
        "samples": samples,
        "verdicts": verdicts(samples, prereg),
        "not_claimed": prereg.get("not_claimed", []),
        "limits": [
            "One sample is an existence check, not a rate: no recurrence or "
            "compliance rate is claimed from this batch.",
            "The canon in this batch is generated by its own plan stage, so "
            "this is not a paired comparison against batch A's fixed canon.",
            "First-attempt findings are counted even when a repair removes "
            "them; final findings are recorded separately.",
            "Length, gates, markers, and the continuity audit are L1 "
            "quantities; L2/L3 remain frozen_not_measured and say nothing "
            "about literary quality.",
            "The operator cannot be seeded, so the text is not reproducible "
            "(G5 stays unmet); provenance is recorded, not assumed fresh.",
        ],
    }

    if not samples:
        print(
            "no samples yet: nothing measured "
            f"(expected {prereg.get('samples_planned')} under {bundle})"
        )
    for name, row in samples.items():
        design = _as_dict(row.get("design"))
        draft = _as_dict(row.get("draft"))
        audit = _as_dict(row.get("audit"))
        plan = _as_dict(row.get("plan"))
        print(
            f"## {name}: status={row.get('status')} complete={row.get('complete')} "
            f"eligible={row.get('eligible')} plan_attempts={plan.get('attempts')} "
            f"design_first={design.get('first_attempt_findings')} "
            f"design_final={design.get('final_findings')} "
            f"design_repairs={design.get('repairs')} "
            f"chars={draft.get('chars_total')} "
            f"in_band={draft.get('chapters_in_length_band')}/"
            f"{draft.get('chapters_total')} "
            f"audit_violations={audit.get('violations')} "
            f"audit_high={audit.get('high')} "
            f"checks_skipped={audit.get('checks_skipped')}"
        )
    print("## verdicts")
    for key, value in result["verdicts"].items():
        if isinstance(value, dict) and "verdict" in value:
            print(f"  {key}: {value['verdict']}")

    out = Path(args.out or bundle / "results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
