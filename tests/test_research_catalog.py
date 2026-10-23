"""Structural tests for the curated research corpus and unified catalog.

These tests check referential integrity and provenance. They do NOT verify the
scholarly correctness of the cited sources.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "research" / "catalog"
CURATED = ROOT / "research" / "curated"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def catalog():
    return {
        "techniques": read_jsonl(CATALOG / "techniques.jsonl"),
        "taxonomies": read_jsonl(CATALOG / "taxonomies.jsonl"),
        "tools": read_jsonl(CATALOG / "tools.jsonl"),
        "sources": read_jsonl(CATALOG / "sources.jsonl"),
        "executability": read_jsonl(CATALOG / "executability.jsonl"),
        "manifest": json.loads((CATALOG / "manifest.json").read_text(encoding="utf-8")),
        "validation": json.loads((CATALOG / "validation_report.json").read_text(encoding="utf-8")),
    }


@pytest.fixture(scope="module")
def seeds():
    return read_jsonl(ROOT / "research" / "program" / "skill_seeds.jsonl")


@pytest.fixture(scope="module")
def inventory():
    return read_jsonl(ROOT / "research" / "inventory" / "artifacts.jsonl")


def test_counts_match_manifest(catalog):
    counts = catalog["manifest"]["counts"]
    assert counts["techniques"] == len(catalog["techniques"])
    assert counts["taxonomies"] == len(catalog["taxonomies"])
    assert counts["tools"] == len(catalog["tools"])
    assert counts["sources"] == len(catalog["sources"])


def test_validation_passed(catalog):
    assert catalog["validation"]["status"] == "passed"
    for name, ok in catalog["validation"]["checks"].items():
        assert ok, f"validation check failed: {name}"


def test_ids_are_unique(catalog):
    ids = [r["id"] for key in ("techniques", "taxonomies", "tools") for r in catalog[key]]
    assert len(ids) == len(set(ids))


def test_techniques_are_well_formed(catalog):
    valid_domains = {"story", "character", "world", "history", "production", "interaction", "style", "meta"}
    for rec in catalog["techniques"]:
        assert rec["title_ja"], rec["id"]
        assert rec["domains"], rec["id"]
        assert set(rec["domains"]) <= valid_domains, rec["id"]
        assert rec["language"] == "ja"
        assert rec["provenance"]["path"].startswith("research/curated/")
        assert rec["entry_type"] in {
            "technique", "paradigm", "practice", "concept", "workflow", "critical_principle"
        }
        assert rec["evidence"]["source_count"] == len(rec["source_ids"]), rec["id"]


def test_source_references_resolve(catalog):
    known = {s["id"] for s in catalog["sources"]}
    for key in ("techniques", "taxonomies", "tools"):
        for rec in catalog[key]:
            missing = [sid for sid in rec["source_ids"] if sid not in known]
            assert not missing, f"{rec['id']} -> {missing[:3]}"


def test_related_ids_resolve(catalog):
    known = {r["id"] for r in catalog["techniques"]}
    for rec in catalog["techniques"]:
        missing = [rid for rid in rec["related_ids"] if rid not in known]
        assert not missing, f"{rec['id']} -> {missing[:3]}"


def test_sources_are_citable(catalog):
    for rec in catalog["sources"]:
        assert rec["title"]
        if rec["source_type"] in {"web_search_query", "api_search_query"}:
            continue
        assert rec["url"] or rec["doi"], rec["id"]
        assert rec["artifacts"], rec["id"]


def test_every_normalized_artifact_has_curated_files(catalog):
    artifacts = {r["artifact"] for key in ("techniques", "taxonomies", "tools") for r in catalog[key]}
    for artifact in artifacts:
        assert (CURATED / artifact).is_dir(), artifact


def test_skill_seed_references_resolve(catalog, seeds):
    techniques = {r["id"] for r in catalog["techniques"]}
    tools = {r["id"] for r in catalog["tools"]}
    assert {s["kind"] for s in seeds} == {"skill_seed", "harness_seed"}
    assert len({s["id"] for s in seeds}) == len(seeds)
    for seed in seeds:
        assert seed["status"] in {"seed", "implemented"}, seed["id"]
        assert seed["steps"] and seed["checks"] and seed["outputs"], seed["id"]
        assert set(seed["technique_ids"]) <= techniques, seed["id"]
        assert set(seed.get("tool_ids", [])) <= tools, seed["id"]
        assert seed["technique_ids"], seed["id"]


def test_inventory_decisions(inventory):
    valid = {"adopt", "reference", "exclude"}
    assert {r["decision"] for r in inventory} <= valid
    assert len({r["id"] for r in inventory}) == len(inventory)
    for rec in inventory:
        assert 0 <= rec["utility_total"] <= 18, rec["id"]
        assert sum(rec["utility"].values()) == rec["utility_total"], rec["id"]
        if rec["decision"] in {"adopt", "reference"}:
            assert rec["destination"], rec["id"]
            assert (CURATED / rec["destination"]).is_dir(), rec["id"]
        else:
            assert rec["destination"] is None, rec["id"]
            assert rec["normalized_records"] == 0, rec["id"]


def test_adopted_artifacts_are_normalized(inventory, catalog):
    normalized = {
        r["artifact"] for key in ("techniques", "taxonomies", "tools") for r in catalog[key]
    }
    for rec in inventory:
        if rec["decision"] == "adopt":
            assert rec["destination"] in normalized, rec["id"]


def test_added_sources_are_well_formed():
    rows = read_jsonl(ROOT / "research" / "curation" / "added_sources.jsonl")
    assert len(rows) >= 20
    assert len({r["id"] for r in rows}) == len(rows)
    for rec in rows:
        assert rec["title"] and rec["url"], rec["id"]
        assert rec["key_finding_ja"] and rec["relevance_ja"], rec["id"]
        assert rec["verification"], rec["id"]


def test_schema_is_valid_json_and_versioned():
    schema = json.loads((CATALOG / "schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert {"technique", "taxonomy", "tool", "source", "skill_seed", "executability"} <= set(
        schema["$defs"])


def test_manifest_inputs_exist():
    manifest = json.loads((CATALOG / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs_sha256"], "manifest must record input hashes"
    for rel in manifest["inputs_sha256"]:
        assert (ROOT / rel).is_file(), rel


def test_curated_manifest_hashes_match_files():
    """Every curated file must be byte-identical to the archived original."""
    import hashlib

    manifest = json.loads((CURATED / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == len(manifest["files"]) == 88
    for rec in manifest["files"]:
        path = ROOT / rec["destination"]
        assert path.is_file(), rec["destination"]
        if path.is_symlink():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == rec["sha256"], rec["destination"]


def test_executability_covers_every_technique(catalog):
    ids = {r["id"] for r in catalog["techniques"]}
    exec_ids = [r["id"] for r in catalog["executability"]]
    assert len(exec_ids) == len(set(exec_ids)) == len(ids)
    assert set(exec_ids) == ids


def test_executability_is_internally_consistent(catalog):
    for rec in catalog["executability"]:
        criteria = rec["criteria"]
        assert set(criteria) == {"procedure", "acceptance", "failure_condition", "example"}
        assert rec["score"] == sum(criteria.values())
        assert set(rec["missing"]) == {k for k, ok in criteria.items() if not ok}
        assert list(rec["missing"]) == [k for k in ("procedure", "acceptance",
                                                   "failure_condition", "example")
                                       if not criteria[k]]
        assert rec["tier"] in {"executable", "partial", "reference_only"}
        if rec["tier"] == "executable":
            assert criteria["procedure"] and criteria["acceptance"], rec["id"]
        if rec["tier"] == "reference_only":
            assert rec["score"] <= 1, rec["id"]


def test_executability_tiers_match_manifest(catalog):
    rows = catalog["executability"]
    counts = catalog["manifest"]["executability"]["tier_counts"]
    for tier in ("executable", "partial", "reference_only"):
        assert counts.get(tier, 0) == sum(1 for r in rows if r["tier"] == tier)
    assert sum(counts.values()) == len(rows)


def test_executability_summary_matches_manifest(catalog):
    """The generated markdown must not drift from the machine-readable roll-up."""
    summary = (CATALOG / "executability_summary.md").read_text(encoding="utf-8")
    total = len(catalog["executability"])
    for tier, n in catalog["manifest"]["executability"]["tier_counts"].items():
        assert f"| `{tier}` | {n} |" in summary, tier
    assert f"対象: **{total} 件**" in summary


def test_derived_operations_are_flagged(catalog):
    """A record must say whether its procedure came from the source or a mapping."""
    for rec in catalog["techniques"]:
        assert rec["extra"]["operation_origin"] in {"stated", "mechanism_derived", "none"}
    china = [r for r in catalog["techniques"] if r["artifact"] == "narrative/china_2026"]
    assert china and all(r["extra"]["operation_origin"] == "mechanism_derived" for r in china)
    assert all(r["operation_ja"] == r["mechanism_ja"] for r in china)


def test_executability_summary_sections_are_present(catalog):
    summary = (CATALOG / "executability_summary.md").read_text(encoding="utf-8")
    for heading in (
        "# 実行可能度の集計（自動生成）",
        "## 判定基準（4 項目・各 1 点）",
        "## 成果物別",
        "## `partial` を `executable` にするために足すもの",
        "## スキル種（13 件）が参照する技法の内訳",
        "## この集計で分からないこと",
    ):
        assert heading in summary, heading
    coverage = catalog["manifest"]["executability"]["seed_coverage"]
    assert coverage and coverage["seeds"] == 13
    assert not coverage["unresolved_ids"]


def test_implemented_seeds_point_at_existing_files(seeds):
    """When a seed claims to be implemented, the files it names must exist."""
    implemented = [s for s in seeds if s["status"] == "implemented"]
    assert {s["id"] for s in implemented} == {
        "seed-08-continuity-ledger", "seed-13-evaluation-harness"}
    for seed in implemented:
        impl = seed["implementation"]
        assert seed["acceptance_written"], seed["id"]
        assert seed["design_change_ja"], seed["id"]
        for key in ("skill", "cli", "tests"):
            assert (ROOT / impl[key]).is_file(), f"{seed['id']}: {impl[key]}"
        for path in impl["library"]:
            assert (ROOT / path).is_file(), f"{seed['id']}: {path}"
    statuses = {s["id"]: s["status"] for s in seeds}
    assert all(v in {"seed", "implemented"} for v in statuses.values())
