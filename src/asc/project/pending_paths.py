"""Resolve project-owned pending relay paths after a checkout is relocated.

External operator paths are deliberately left untouched. Older checkpoints did
not record relative paths, so only the unmistakable default project relay layout
is mapped for backwards compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def record_project_paths(project_dir: Path, pending: dict[str, Any]) -> dict[str, Any]:
    result = dict(pending)
    base = project_dir.resolve()
    for field in ("response_path", "request_path"):
        value = result.get(field)
        if not value:
            continue
        try:
            relative = Path(value).resolve().relative_to(base)
        except ValueError:
            continue
        result[field + "_relative"] = relative.as_posix()
    return result


def resolve_project_paths(
    project_dir: Path, pending: dict[str, Any], run_id: str | None = None,
) -> dict[str, Any]:
    result = dict(pending)
    base = project_dir.resolve()
    key = result.get("key")
    legacy_arena = False
    if run_id:
        try:
            manifest = json.loads((base / "runs" / run_id / "manifest.json").read_text(encoding="utf-8"))
            legacy_arena = manifest.get("provider") == "arena-relay"
        except (OSError, ValueError, AttributeError):
            pass
    for field, directory in (("response_path", "responses"), ("request_path", "requests")):
        value = result.get(field)
        if not value:
            continue
        relative = result.get(field + "_relative")
        if relative:
            candidate = (base / relative).resolve()
            # Never let a forged relative path escape the current project.
            if not candidate.is_relative_to(base):
                raise ValueError(f"pending {field} escapes project directory")
            result[field] = str(candidate)
            continue
        # Old default Arena relay checkpoints store absolute paths. Do not infer
        # a new location for arbitrary external command providers or custom dirs.
        old = Path(value)
        if (legacy_arena and isinstance(key, str) and old.name == key + ".json"
                and old.parent.name == directory and old.parent.parent.name == "relay"
                and old.parent.parent.parent.name == base.name):
            result[field] = str(base / "relay" / directory / old.name)
    return result
