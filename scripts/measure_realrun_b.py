#!/usr/bin/env python3
"""Measure batch B against the rules that were fixed before it ran.

The registration lives in ``experiments/2026-10-realrun-b-t01/preregistration.json``
and is hashed into the result, so the thresholds used here are the ones that were
recorded, not ones chosen after seeing the text.

What it reads: one ``sample-*/run`` directory per sample, written by
``run_pipeline.py --task t01 --system s1 --stage all --canon <pinned>`` (design
reports, ``draft.json``, ``text/``, ``audit.json``, ``manifest.json``,
``responses.jsonl``). What it writes: per-document and per-chapter numbers, the
two counting modes for findings, and a verdict for each pre-registered rule.

Two rules of the registration shape the arithmetic:

* **B3 is counted both ways.** ``repair_erased_included`` counts findings from the
  first attempt (design) or from the rejected draft attempts, so a finding that a
  repair erased still counts. ``final_only`` counts what the final report shows.
  Both verdicts are written; neither is primary. This is the ambiguity batch A
  left open (docs/two_stage_slice.md §21.1, §23).
* **B2 judges the delivered text** and uses the first attempt only to say *where*
  a chapter left the 1,000–1,400 band (written that way vs. lost in repair).

A sample whose run stopped early (``DraftError`` after two rejected attempts) has
no ``run-summary.json`` and no ``draft.json``. It is still discovered (by
``manifest.json``), reported as ``complete: false``, and rules that need chapters
return ``incomplete`` instead of inventing numbers. The registration says such a
run is kept, not rewritten.

    python3 scripts/measure_realrun_b.py
    python3 scripts/measure_realrun_b.py --bundle experiments/2026-10-realrun-b-t01

A sample's directory must be ``<bundle>/sample-N/run``; ``--sample NAME=PATH``
overrides discovery, which is how the script is tested (against a scripted run,
where it is a check of the arithmetic, not evidence about prose).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.story.canon import load_canon  # noqa: E402
from asc.story.text import parse_markers  # noqa: E402

DEFAULT_BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-b-t01"
MARKER = re.compile(r"\{\{([^{}]+)\}\}")


# -- small readers ---------------------------------------------------------

def chars_without_markers(text: str) -> int:
    """Characters the pipeline itself counts (markers and whitespace removed)."""
    return len(re.sub(r"\s", "", MARKER.sub("", text)))


def discover_samples(bundle: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for path in sorted(bundle.glob("sample-*/run")):
        if (path / "manifest.json").is_file() or (path / "run-summary.json").is_file():
            found.append((path.parent.name, path))
    return found


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _finding_row(item: dict) -> dict:
    return {"check": item.get("check"), "severity": item.get("severity")}


def _issue_key(line: str) -> str:
    """Give a rejected draft attempt's free-text problem a stable name."""
    if line.startswith("too short"):
        return "draft.too_short"
    if line.startswith("uses a forbidden cliché"):
        return "draft.forbidden_cliche"
    return "draft.other"


# -- one sample ------------------------------------------------------------

def summarise_design(run_dir: Path, docs: list[str]) -> dict:
    per_doc: dict[str, dict] = {}
    for name in docs:
        report = _read_json(run_dir / "design" / f"{name}.report.json")
        if report is None:
            per_doc[name] = {"present": False}
            continue
        first = (report.get("first_attempt") or {}).get("findings") or []
        final = report.get("findings") or []
        per_doc[name] = {
            "present": True,
            "status": report.get("status"),
            "attempts": report.get("attempts"),
            "repairs": report.get("repairs"),
            "first_attempt_findings": [_finding_row(item) for item in first],
            "findings": [_finding_row(item) for item in final],
        }
    first_checks: dict[str, int] = {}
    final_checks: dict[str, int] = {}
    for row in per_doc.values():
        for item in row.get("first_attempt_findings", []):
            first_checks[item["check"]] = first_checks.get(item["check"], 0) + 1
        for item in row.get("findings", []):
            final_checks[item["check"]] = final_checks.get(item["check"], 0) + 1
    return {
        "docs": per_doc,
        "docs_present": sum(1 for row in per_doc.values() if row["present"]),
        "unresolved": [name for name, row in per_doc.items()
                        if row.get("status") in {"unresolved", "missing"}],
        "docs_with_first_attempt_findings": [
            name for name, row in per_doc.items() if row.get("first_attempt_findings")],
        "docs_with_findings": [name for name, row in per_doc.items() if row.get("findings")],
        "first_attempt_findings_by_check": first_checks,
        "final_findings_by_check": final_checks,
        "attempts": sum(row.get("attempts") or 0 for row in per_doc.values()),
        "repairs": sum(row.get("repairs") or 0 for row in per_doc.values()),
    }


def _marker_values(text: str, chapter_id: str) -> dict:
    days: list[str] = []
    locations: list[str] = []
    for marker in parse_markers(text, chapter_id):
        if marker.kind == "time":
            for arg in marker.args:
                if arg.startswith("day="):
                    days.append(arg.split("=", 1)[1].strip().rstrip("N"))
                    break
        elif marker.kind == "location":
            locations.append(" ".join(marker.args).strip())
    return {"days": days, "locations": locations}


def summarise_chapter(run_dir: Path, chapter: dict, canon, band: tuple[int, int]) -> dict:
    chapter_id = chapter["id"]
    text_path = run_dir / "text" / f"{chapter_id}.md"
    text = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
    first_path = run_dir / "draft" / f"{chapter_id}-attempt-1.txt"
    first_text = first_path.read_text(encoding="utf-8") if first_path.is_file() else None
    attempt_texts = sorted((run_dir / "draft").glob(f"{chapter_id}-attempt-*.txt"))
    issues: list[dict] = []
    for path in sorted((run_dir / "draft").glob(f"{chapter_id}-attempt-*.issues.txt")):
        attempt = path.name.split("-attempt-")[1].split(".")[0]
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                issues.append({"attempt": int(attempt), "problem": line.strip(),
                               "check": _issue_key(line.strip())})

    chars = chapter.get("chars")
    first_chars = chars_without_markers(first_text) if first_text is not None else None
    in_band = bool(chars is not None and band[0] <= chars <= band[1])
    first_in_band = (None if first_chars is None
                     else bool(band[0] <= first_chars <= band[1]))
    cause = None
    if chars is not None and not in_band:
        if first_in_band is None:
            cause = "unknown"
        elif first_in_band:
            cause = "lost_in_repair"
        else:
            cause = "out_at_write"

    canon_chapter = canon.chapters.get(chapter_id) if canon is not None else None
    declared = _marker_values(text, chapter_id)
    mismatches: list[dict] = []
    expected_day = (None if canon_chapter is None or canon_chapter.day is None
                    else str(canon_chapter.day))
    expected_location = None if canon_chapter is None else canon_chapter.location
    if expected_day is not None and declared["days"] and declared["days"][0] != expected_day:
        mismatches.append({"kind": "time", "declared": declared["days"][0],
                           "canon": expected_day})
    if expected_location and declared["locations"] \
            and declared["locations"][0] != expected_location:
        mismatches.append({"kind": "location", "declared": declared["locations"][0],
                           "canon": expected_location})

    return {
        "chars": chars,
        "in_length_band": in_band,
        "first_attempt_chars": first_chars,
        "first_attempt_in_length_band": first_in_band,
        "out_of_band_cause": cause,
        "attempts": len(attempt_texts) or None,
        "rejected_attempts": len(issues),
        "issues": issues,
        "day": chapter.get("day"),
        "location": chapter.get("location"),
        "injected": list(chapter.get("injected") or []),
        "declared_markers": declared,
        "marker_mismatches": mismatches,
    }


def _count_checks(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = item.get("check") or "draft.other"
        counts[key] = counts.get(key, 0) + 1
    return counts


def summarise_draft(run_dir: Path, canon, band: tuple[int, int], task_terms,
                    avoid_terms) -> dict:
    draft = _read_json(run_dir / "draft.json")
    chapters: dict[str, dict] = {}
    if draft is None:
        # The run stopped before the draft was written; keep what the attempts left.
        rejected: list[dict] = []
        for path in sorted((run_dir / "draft").glob("*-attempt-*.issues.txt")):
            chapter_id = path.name.split("-attempt-")[0]
            attempt = path.name.split("-attempt-")[1].split(".")[0]
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rejected.append({"chapter": chapter_id, "attempt": int(attempt),
                                     "problem": line.strip(),
                                     "check": _issue_key(line.strip())})
        return {"draft_complete": False, "chapters": {}, "chapters_total": 0,
                "chapters_in_length_band": 0, "chars_total": None,
                "must_include": None, "avoid_hits": {},
                "warnings_ja": [], "injected_total": 0,
                "marker_mismatches": [], "rejected_attempts": rejected,
                "issues_by_check": _count_checks(rejected)}

    for chapter in draft.get("chapters") or []:
        chapters[chapter["id"]] = summarise_chapter(run_dir, chapter, canon, band)

    texts = [path.read_text(encoding="utf-8")
             for path in sorted((run_dir / "text").glob("*.md"))]
    joined = "\n\n".join(texts)
    must_include = draft.get("must_include") or {}
    hits = must_include.get("hits") or {}
    return {
        "draft_complete": True,
        "chapters": chapters,
        "chapters_total": len(chapters),
        "chapters_in_length_band": sum(
            1 for row in chapters.values() if row["in_length_band"]),
        "chars_total": draft.get("chars"),
        "must_include": {"hits": hits, "rate": must_include.get("rate"),
                         "missing": [term for term in task_terms if not hits.get(term)]},
        "avoid_hits": {term: joined.count(term) for term in avoid_terms
                       if term in joined},
        "warnings_ja": list(draft.get("warnings_ja") or []),
        "injected_total": sum(len(row["injected"]) for row in chapters.values()),
        "marker_mismatches": [
            {"chapter": chapter_id, **item}
            for chapter_id, row in chapters.items()
            for item in row["marker_mismatches"]
        ],
        "rejected_attempts": [
            {"chapter": chapter_id, **item}
            for chapter_id, row in chapters.items() for item in row["issues"]
        ],
        "issues_by_check": _count_checks(
            [item for row in chapters.values() for item in row["issues"]]),
    }


def summarise_audit(run_dir: Path) -> dict:
    audit = _read_json(run_dir / "audit.json")
    if audit is None:
        return {"present": False}
    summary = audit.get("summary") or {}
    return {
        "present": True,
        "violations": summary.get("violations"),
        "by_severity": summary.get("by_severity") or {},
        "by_type": summary.get("by_type") or {},
        "checks_run": summary.get("checks_run"),
        "checks_skipped": summary.get("checks_skipped"),
        "ced_per_10k_chars": summary.get("ced_per_10k_chars"),
    }


def summarise_provenance(run_dir: Path) -> dict:
    journal = run_dir / "responses.jsonl"
    origins: dict[str, int] = {}
    models: dict[str, int] = {}
    count = 0
    if journal.is_file():
        for line in journal.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            response = entry.get("response") or {}
            origin = (response.get("provenance") or {}).get("origin") or "unspecified"
            origins[origin] = origins.get(origin, 0) + 1
            label = (f"{response.get('model') or 'unknown'}"
                     f" / {response.get('model_version') or 'unversioned'}")
            models[label] = models.get(label, 0) + 1
    return {"responses": count, "origins": origins, "models": models}


def summarise_sample(name: str, run_dir: Path, canon, prereg: dict) -> dict:
    summary = _read_json(run_dir / "run-summary.json")
    manifest = _read_json(run_dir / "manifest.json") or {}
    rules = prereg["rules"]
    band = tuple(prereg["length_band"])
    task_terms = rules["B4_must_include_exact"]["terms"]
    avoid_terms = ["選ばれし者", "古代の予言"]
    design = summarise_design(run_dir, rules["B1_design_first_attempt"]["docs"])
    draft = summarise_draft(run_dir, canon, band, task_terms, avoid_terms)
    return {
        "run_dir": str(run_dir),
        "complete": bool(summary and draft["draft_complete"]),
        "status": (summary or {}).get("status"),
        "gates": (summary or {}).get("gates") or {},
        "design": design,
        "draft": draft,
        "audit": summarise_audit(run_dir),
        "provenance": summarise_provenance(run_dir),
        "prompt_hashes": manifest.get("prompt_hashes") or {},
        "error": (summary or {}).get("error") or manifest.get("error"),
    }


# -- registered verdicts ---------------------------------------------------

def _design_counts(samples: dict[str, dict], mode: str) -> dict[str, list[str]]:
    """``check -> samples`` for one counting mode (see the registration)."""
    hits: dict[str, list[str]] = {}
    for name, sample in samples.items():
        design = sample["design"]
        key = ("first_attempt_findings_by_check" if mode == "repair_erased_included"
               else "final_findings_by_check")
        for check, count in (design.get(key) or {}).items():
            if count:
                hits.setdefault(f"design.{check}", []).append(name)
    return hits


def _draft_counts(samples: dict[str, dict], mode: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    if mode != "repair_erased_included":
        # The pipeline keeps a chapter only after it passes, so the final report
        # of a delivered chapter carries no draft findings by construction.
        return hits
    for name, sample in samples.items():
        for check, count in (sample["draft"].get("issues_by_check") or {}).items():
            if count:
                hits.setdefault(check, []).append(name)
    return hits


def _audit_counts(samples: dict[str, dict]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for name, sample in samples.items():
        for kind, count in (sample["audit"].get("by_type") or {}).items():
            if count:
                hits.setdefault(f"audit.{kind}", []).append(name)
    return hits


def verdicts(samples: dict[str, dict], prereg: dict) -> dict:
    rules = prereg["rules"]
    planned = prereg["samples_planned"]
    present = len(samples)
    complete = {name: row for name, row in samples.items()
                if row["complete"] and row["draft"]["chapters_total"]}

    # B1: design, first attempt.
    if not samples:
        design_verdict = "not_run"
    elif not any(row["design"]["docs_present"] for row in samples.values()):
        design_verdict = "incomplete"
    else:
        unresolved = {name: row["design"]["unresolved"] for name, row in samples.items()
                      if row["design"]["unresolved"]}
        repaired = {name: row["design"]["docs_with_first_attempt_findings"]
                    for name, row in samples.items()
                    if row["design"]["docs_with_first_attempt_findings"]}
        if unresolved:
            design_verdict = "design_unresolved"
        elif repaired:
            design_verdict = "design_repaired"
        else:
            design_verdict = "design_clean_first_attempt"

    # B2: length of the delivered chapters, split by where they left the band.
    need = rules["B2_length"]["min_chapters_in_band"]
    if not complete:
        length_verdict = "not_run" if not samples else "incomplete"
        in_band: dict[str, int] = {}
        causes: dict[str, str] = {}
    else:
        in_band = {name: row["draft"]["chapters_in_length_band"]
                   for name, row in complete.items()}
        causes = {}
        for name, row in complete.items():
            for chapter_id, chapter in row["draft"]["chapters"].items():
                if chapter["out_of_band_cause"]:
                    causes[f"{name}/{chapter_id}"] = chapter["out_of_band_cause"]
        if all(count >= need for count in in_band.values()):
            length_verdict = "length_ok"
        elif not causes:
            length_verdict = "length_ok"
        elif set(causes.values()) == {"lost_in_repair"}:
            length_verdict = "length_lost_in_repair"
        elif set(causes.values()) == {"out_at_write"}:
            length_verdict = "length_out_at_write"
        elif set(causes.values()) == {"unknown"}:
            length_verdict = "length_cause_unknown"
        else:
            length_verdict = "length_mixed_causes"

    # B3: recurrence, counted both ways (the batch A ambiguity).
    threshold = rules["B3_recurring_failure"]["min_samples"]
    modes = rules["B3_recurring_failure"]["counting"]
    by_mode: dict[str, dict[str, list[str]]] = {}
    for mode in modes:
        hits = _design_counts(samples, mode)
        for check, names in _draft_counts(samples, mode).items():
            hits.setdefault(check, []).extend(names)
        for check, names in _audit_counts(samples).items():
            hits.setdefault(check, []).extend(names)
        by_mode[mode] = {check: sorted(set(names)) for check, names in hits.items()}
    if not samples:
        recurrence = {mode: "not_run" for mode in modes}
    elif present < threshold:
        recurrence = {mode: "not_evaluable_at_n1" if present == 1 else "not_enough_data"
                      for mode in modes}
    else:
        recurrence = {}
        for mode in modes:
            recurring = [check for check, names in by_mode[mode].items()
                         if len(names) >= threshold]
            recurrence[mode] = "recurring" if recurring else "no_recurring_failure"

    # B4: required words, exact match.
    if not complete:
        must_verdict = "not_run" if not samples else "incomplete"
        missing_terms: dict[str, list[str]] = {}
    else:
        missing_terms = {name: row["draft"]["must_include"]["missing"]
                         for name, row in complete.items()
                         if row["draft"]["must_include"]["missing"]}
        must_verdict = "exact_match_gap" if missing_terms else "exact_match_ok"

    # B5: markers the text declared vs. the ones canon had to supply.
    if not complete:
        marker_verdict = "not_run" if not samples else "incomplete"
        disagreements: dict[str, list[dict]] = {}
        injected: dict[str, int] = {}
    else:
        disagreements = {name: row["draft"]["marker_mismatches"]
                         for name, row in complete.items()
                         if row["draft"]["marker_mismatches"]}
        injected = {name: row["draft"]["injected_total"]
                    for name, row in complete.items() if row["draft"]["injected_total"]}
        if disagreements:
            marker_verdict = "markers_disagree"
        elif injected:
            marker_verdict = "markers_repaired"
        else:
            marker_verdict = "markers_declared"

    return {
        "samples_present": present,
        "samples_planned": planned,
        "samples_complete": sorted(complete),
        "B1_design_first_attempt": {
            "verdict": design_verdict,
            "docs": rules["B1_design_first_attempt"]["docs"],
            "by_doc": {name: row["design"]["docs"] for name, row in samples.items()},
            "first_attempt_findings_by_check": {
                name: row["design"]["first_attempt_findings_by_check"]
                for name, row in samples.items()},
            "final_findings_by_check": {
                name: row["design"]["final_findings_by_check"]
                for name, row in samples.items()},
            "unresolved": {name: row["design"]["unresolved"]
                           for name, row in samples.items()
                           if row["design"]["unresolved"]},
        },
        "B2_length": {
            "verdict": length_verdict,
            "chapters_in_band": in_band,
            "needed_per_sample": need,
            "band": list(prereg["length_band"]),
            "out_of_band_causes": causes,
        },
        "B3_recurring_failure": {
            "verdict": recurrence,
            "min_samples": threshold,
            "by_check": by_mode,
            "structural_note": rules["B3_recurring_failure"]["notes"],
        },
        "B4_must_include_exact": {
            "verdict": must_verdict,
            "terms": rules["B4_must_include_exact"]["terms"],
            "missing_terms": missing_terms,
            "rates": {name: row["draft"]["must_include"]["rate"]
                      for name, row in complete.items()},
        },
        "B5_marker_declaration": {
            "verdict": marker_verdict,
            "marker_mismatches": disagreements,
            "injected_markers": injected,
        },
    }


def condition_check(bundle: Path, canon_dir: Path, samples: dict[str, dict],
                    prereg: dict) -> dict:
    """Did the run keep the conditions that were registered?"""
    condition = prereg["condition"]
    digest = hashlib.sha256()
    files: dict[str, str] = {}
    for path in sorted(canon_dir.glob("*.json")):
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    canon_ok = digest.hexdigest() == condition["canon_tree_sha256"]
    registered = {name: spec["digest"] for name, spec in condition["prompts"].items()}
    prompt_mismatches: list[dict] = []
    for name, sample in samples.items():
        actual = sample["prompt_hashes"]
        for prompt, wanted in registered.items():
            got = actual.get(prompt)
            if got != wanted:
                prompt_mismatches.append({"sample": name, "prompt": prompt,
                                          "registered": wanted, "actual": got})
    origins: dict[str, int] = {}
    models: dict[str, int] = {}
    for sample in samples.values():
        for origin, count in sample["provenance"]["origins"].items():
            origins[origin] = origins.get(origin, 0) + count
        for label, count in sample["provenance"]["models"].items():
            models[label] = models.get(label, 0) + count
    resolved = canon_dir.resolve()
    source = (str(resolved.relative_to(REPO_ROOT)) if REPO_ROOT in resolved.parents
              else str(canon_dir))
    return {
        "canon_tree_sha256": digest.hexdigest(),
        "canon_matches_registration": canon_ok,
        "canon_files": files,
        "canon_source": source,
        "prompt_hashes_match_registration": not prompt_mismatches,
        "prompt_mismatches": prompt_mismatches,
        "provenance_origins": origins,
        "models": models,
        "plan_requested": condition["plan"]["requested"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--preregistration", default=None,
                        help="default: <bundle>/preregistration.json")
    parser.add_argument("--canon", default=None, help="default: <bundle>/inputs/canon")
    parser.add_argument("--sample", action="append", default=None,
                        metavar="NAME=RUN_DIR", help="override discovery (repeatable)")
    parser.add_argument("--out", default=None, help="default: <bundle>/results.json")
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    prereg_path = Path(args.preregistration or bundle / "preregistration.json")
    prereg_bytes = prereg_path.read_bytes()
    prereg = json.loads(prereg_bytes.decode("utf-8"))
    canon_dir = Path(args.canon or bundle / "inputs" / "canon")
    canon = load_canon(canon_dir)

    if args.sample:
        pairs: list[tuple[str, Path]] = []
        for entry in args.sample:
            name, _, path = entry.partition("=")
            if not name or not path:
                raise SystemExit(f"--sample needs NAME=PATH, got {entry!r}")
            pairs.append((name, Path(path)))
    else:
        pairs = discover_samples(bundle)

    samples = {name: summarise_sample(name, path, canon, prereg)
               for name, path in pairs}
    result = {
        "schema": "realrun-b-v1",
        "experiment": prereg["experiment"],
        "preregistration": {
            "path": str(prereg_path.relative_to(REPO_ROOT))
            if prereg_path.is_absolute() and REPO_ROOT in prereg_path.parents
            else str(prereg_path),
            "sha256": hashlib.sha256(prereg_bytes).hexdigest(),
        },
        "condition": condition_check(bundle, canon_dir, samples, prereg),
        "samples": samples,
        "verdicts": verdicts(samples, prereg),
        "not_claimed": prereg["not_claimed"],
        "limits": [
            "N=1: no rate, interval or significance claim is made from this batch.",
            "The plan stage was pinned, not run: this measures S1's design -> draft, "
            "not S1 end to end.",
            "The responder cannot be seeded, so the text is not reproducible (G5 stays "
            "unmet); provenance is recorded per response, not assumed fresh.",
            "Length and marker counts are L1 quantities; they say nothing about "
            "whether the chapters are any good.",
        ],
    }

    if not samples:
        print("no samples yet: nothing measured "
              f"(expected {prereg['samples_planned']} under {bundle})")
    for name, row in samples.items():
        draft = row["draft"]
        print(f"## {name}: complete={row['complete']} status={row['status']} "
              f"chars={draft['chars_total']} "
              f"in_band={draft['chapters_in_length_band']}/{draft['chapters_total']} "
              f"design_repairs={row['design']['repairs']} "
              f"draft_issues={len(draft['rejected_attempts'])}")
        for doc, doc_row in row["design"]["docs"].items():
            first = [item["check"] for item in doc_row.get("first_attempt_findings", [])]
            print(f"   design/{doc:9s} {str(doc_row.get('status')):10s} "
                  f"attempts={doc_row.get('attempts')} first={first or '—'}")
        for chapter_id, chapter in draft["chapters"].items():
            print(f"   {chapter_id}: {chapter['chars']}字 "
                  f"(attempt1 {chapter['first_attempt_chars']}字, "
                  f"cause {chapter['out_of_band_cause'] or '—'}) "
                  f"injected={chapter['injected'] or '—'} "
                  f"issues={[item['check'] for item in chapter['issues']] or '—'}")
    print("## verdicts")
    for key, value in result["verdicts"].items():
        if isinstance(value, dict) and "verdict" in value:
            print(f"  {key}: {value['verdict']}")

    out = Path(args.out or bundle / "results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
