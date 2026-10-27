#!/usr/bin/env python3
"""Create the small sample files that are stored in the repository.

The full datasets are too large for git, therefore ``samples/`` contains

* ``*.sample.jsonl``  a deterministic subset of the bibliographic metadata

Note: Full texts of Syosetsuka ni Narou works remain the copyright of
their respective authors and are therefore kept in git-ignored ``data/`` only
(see ``docs/legal_and_ethics.md``).

Usage::

    python scripts/make_samples.py [--records 200]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.config import load_config  # noqa: E402
from asc.jsonl import read_jsonl, write_jsonl  # noqa: E402

SAMPLE_FILES = {
    "aozora_works.jsonl": "aozora_works.sample.jsonl",
    "aozora_authors.jsonl": "aozora_authors.sample.jsonl",
    "narou_novels.jsonl": "narou_novels.sample.jsonl",
}


def _select_subset(
    rows: List[Dict[str, Any]],
    count: int,
    priority_ids: set[str],
) -> List[Dict[str, Any]]:
    chosen: List[Dict[str, Any]] = [r for r in rows if r.get("id") in priority_ids]
    seen = {r.get("id") for r in chosen}
    remaining = [r for r in rows if r.get("id") not in seen]
    needed = max(0, count - len(chosen))
    if needed and remaining:
        step = max(1, len(remaining) // needed)
        chosen.extend(remaining[::step][:needed])
    return chosen[:count]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--records", type=int, default=200)
    args = parser.parse_args()

    cfg = load_config(args.config)
    sample_dir = REPO_ROOT / "samples"

    for source, target in SAMPLE_FILES.items():
        path = cfg.paths.dataset_dir / source
        if not path.exists():
            print(f"skip {source} (not built yet)")
            continue
        rows = list(read_jsonl(path))
        priority: set[str] = set()
        if source == "narou_novels.jsonl":
            comm_rows = [
                r for r in rows if (r.get("rights") or {}).get("commercialized") is True
            ]
            comm_step = max(1, len(comm_rows) // min(100, args.records // 2 or 1)) if comm_rows else 1
            priority = {
                r["id"] for r in comm_rows[::comm_step][: min(100, args.records // 2)]
            }
        subset = _select_subset(rows, args.records, priority)
        write_jsonl(sample_dir / target, subset)
        print(f"{target}: {len(subset)} records")

    manifest = {
        "note": "Sample subset of the datasets.",
        "generated_by": "scripts/make_samples.py",
    }
    (sample_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (sample_dir / "README.md").write_text(
        "# samples\n\n"
        "このディレクトリはリポジトリに同梱する小さなサンプルです。\n"
        "全件データ・本文は `make data`（または `make pull-datasets`）で `data/` 配下に生成されます（Git には含めません）。\n\n"
        "* `aozora_works.sample.jsonl` / `aozora_authors.sample.jsonl` … 青空文庫メタデータの部分集合\n"
        "* `narou_novels.sample.jsonl` … 小説家になろうメタデータ（商業化フラグ付き作品を含む）の部分集合\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
