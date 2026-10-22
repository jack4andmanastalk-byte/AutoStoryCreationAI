"""Helpers to read and write JSON Lines files.

Every dataset in this repository is stored as JSONL: one JSON object per line,
UTF-8 encoded, keys are sorted so that diffs stay reviewable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


def write_jsonl(path: str | os.PathLike[str], records: Iterable[Dict[str, Any]]) -> int:
    """Write ``records`` to ``path`` and return the number of written rows."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
            count += 1
    return count


def append_jsonl(path: str | os.PathLike[str], record: Dict[str, Any]) -> None:
    """Append a single record to ``path`` (creating parent directories)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        fh.write("\n")


def read_jsonl(path: str | os.PathLike[str]) -> Iterator[Dict[str, Any]]:
    """Yield every record stored in ``path``.

    Blank lines are ignored, malformed lines raise a ``ValueError`` that
    mentions the offending line number.
    """
    target = Path(path)
    if not target.exists():
        return
    with target.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"{target}:{lineno}: invalid JSON ({exc})") from exc


def load_jsonl(path: str | os.PathLike[str]) -> List[Dict[str, Any]]:
    """Eager version of :func:`read_jsonl`."""
    return list(read_jsonl(path))
