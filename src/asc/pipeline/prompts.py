"""Prompt templates with a version and a content hash.

Prompts live in ``prompts/*.md`` as files so that a change is visible in git and
its hash can be recorded in the run manifest. Rendering uses ``$placeholder``
syntax (``string.Template``), because prompts contain literal JSON braces.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

from .llm import digest

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_DIR = REPO_ROOT / "prompts"

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


class PromptError(ValueError):
    """Raised when a prompt file is malformed or a placeholder is missing."""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    text: str
    path: Path | None = None

    @property
    def digest(self) -> str:
        return digest(f"{self.name}@{self.version}\n{self.text}")

    @property
    def placeholders(self) -> set[str]:
        return set(Template(self.text).get_identifiers())

    def render(self, values: dict) -> str:
        missing = self.placeholders - set(values)
        if missing:
            raise PromptError(f"{self.name}: missing placeholders: {sorted(missing)}")
        return Template(self.text).substitute(values)


def load_prompt(name: str, root: Path | None = None) -> PromptTemplate:
    directory = Path(root) if root else PROMPT_DIR
    path = directory / f"{name}.md"
    if not path.is_file():
        raise PromptError(f"prompt not found: {path}")
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(raw)
    if not match:
        raise PromptError(f"{path.name}: missing YAML frontmatter (name, version)")
    header, body = match.group(1), raw[match.end():]
    meta: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    if not meta.get("name") or not meta.get("version"):
        raise PromptError(f"{path.name}: frontmatter needs name and version")
    if meta["name"] != name:
        raise PromptError(f"{path.name}: name {meta['name']!r} != {name!r}")
    if not body.strip():
        raise PromptError(f"{path.name}: empty body")
    return PromptTemplate(name=name, version=meta["version"], text=body, path=path)
