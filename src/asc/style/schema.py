"""The voice specification: viewpoint, knowledge range, sample, banned list.

A voice file (``voice.yaml`` or ``voice.json``) declares how a work is told.
The checker compares the manuscript against this declaration; it never infers
quality from the numbers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PERSONS = {"first", "third"}
FIRST_PRONOUNS = {"私", "僕", "俺", "あたし", "わたくし", "わたし", "ぼく", "おれ"}


class VoiceError(ValueError):
    """Raised when the voice file is missing or malformed."""


@dataclass(frozen=True)
class BannedPhrase:
    id: str
    pattern: str
    message_ja: str


@dataclass(frozen=True)
class Voice:
    path: Path
    person: str
    character: str
    aliases: tuple[str, ...]
    pronouns: tuple[str, ...]
    narrator_knows_ja: str
    sample: str
    banned: tuple[BannedPhrase, ...] = ()
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "person": self.person, "character": self.character,
            "aliases": list(self.aliases), "pronouns": list(self.pronouns),
            "narrator_knows_ja": self.narrator_knows_ja,
            "sample_chars": len(self.sample),
            "banned": [b.__dict__ for b in self.banned],
        }


def _read_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
            raise VoiceError(f"{path.name}: loading YAML requires PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise VoiceError(f"{path.name}: the top level must be a mapping")
    return data


def load_voice(path: str | Path) -> Voice:
    path = Path(path)
    if path.is_dir():
        for name in ("voice.yaml", "voice.yml", "voice.json"):
            if (path / name).is_file():
                path = path / name
                break
        else:
            raise VoiceError(f"no voice file in {path}")
    if not path.is_file():
        raise VoiceError(f"voice file not found: {path}")
    data = _read_mapping(path)

    viewpoint = data.get("viewpoint") or {}
    if not isinstance(viewpoint, dict):
        raise VoiceError(f"{path.name}: 'viewpoint' must be a mapping")
    person = str(viewpoint.get("person", "") or "").strip()
    if person not in PERSONS:
        raise VoiceError(f"{path.name}: 'viewpoint.person' must be first or third")
    character = str(viewpoint.get("character", "") or "").strip()
    if not character:
        raise VoiceError(f"{path.name}: 'viewpoint.character' must be named")
    aliases = tuple(str(a) for a in (viewpoint.get("aliases") or []) if str(a).strip())
    pronouns = tuple(str(p) for p in (viewpoint.get("pronouns") or []) if str(p).strip())

    narrator = data.get("narrator") or {}
    if not isinstance(narrator, dict):
        raise VoiceError(f"{path.name}: 'narrator' must be a mapping")
    knows = str(narrator.get("knows_ja", "") or "").strip()
    if not knows:
        raise VoiceError(f"{path.name}: 'narrator.knows_ja' must be written")

    sample = str(data.get("sample", "") or "")
    banned: list[BannedPhrase] = []
    for row in data.get("banned") or []:
        if not isinstance(row, dict) or not row.get("id") or not row.get("pattern"):
            raise VoiceError(f"{path.name}: each 'banned' entry needs id and pattern")
        banned.append(BannedPhrase(
            id=str(row["id"]), pattern=str(row["pattern"]),
            message_ja=str(row.get("message_ja", "") or "")))
    return Voice(path=path, person=person, character=character, aliases=aliases,
                 pronouns=pronouns, narrator_knows_ja=knows,
                 sample=sample.strip(), banned=tuple(banned),
                 notes=str(data.get("notes", "") or "").strip())
