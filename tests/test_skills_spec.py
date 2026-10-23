"""Validate skills/*/SKILL.md against the Agent Skills specification.

Checked constraints (agentskills.io/specification, ADD-09):

* ``name`` — 1-64 characters, lowercase letters, digits and hyphens only, no
  leading/trailing hyphen, no consecutive hyphens, and equal to the directory name.
* ``description`` — 1-1024 characters.
* optional ``license`` (string) and ``compatibility`` (<= 500 characters).
* the body stays under 500 lines, so that the whole file can be loaded on demand.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def split_frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    _, frontmatter, body = text.split("---\n", 2)
    import yaml

    data = yaml.safe_load(frontmatter)
    assert isinstance(data, dict)
    return data, body


#: The implemented skills. Adding a skill means adding it here, with its
#: SKILL.md, references/, demo case and tests — never the name alone.
EXPECTED_SKILLS = [
    "continuity-ledger",
    "evaluation-harness",
    "history-timeline",
    "premise-brief",
    "revision-loop",
    "voice-style",
    "world-rules",
]


def test_expected_skills_exist():
    assert [p.parent.name for p in SKILLS] == EXPECTED_SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_frontmatter(path: Path):
    data, body = split_frontmatter(path.read_text(encoding="utf-8"))
    name = data["name"]
    assert 1 <= len(name) <= 64
    assert NAME_RE.match(name), name
    assert name == path.parent.name
    description = data["description"]
    assert 1 <= len(description) <= 1024
    assert data.get("license")
    assert len(str(data.get("compatibility", ""))) <= 500
    assert data["metadata"]["seed"].startswith("seed-")
    assert body.strip()
    assert len(body.splitlines()) < 500


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_has_references_and_acceptance(path: Path):
    skill_dir = path.parent
    references = sorted((skill_dir / "references").glob("*.md"))
    assert references, "each skill keeps its detail in references/"
    for reference in references:
        assert reference.read_text(encoding="utf-8").strip()
    text = path.read_text(encoding="utf-8")
    assert "## 合格条件" in text
    assert "## しないこと" in text
    assert "## 参照" in text


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_links_resolve(path: Path):
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http", "#")):
            continue
        assert (path.parent / target.split("#")[0]).exists(), f"{path.parent.name}: {target}"
