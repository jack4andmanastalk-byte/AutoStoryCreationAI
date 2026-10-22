#!/usr/bin/env python3
"""Create the small sample files that are stored in the repository.

The full datasets are too large for git, therefore ``samples/`` contains

* ``*.sample.jsonl``  a deterministic subset of the metadata,
* ``pdf/``            a few rendered PDF files (with their metadata record).

Usage::

    python scripts/make_samples.py [--records 200] [--pdfs 4]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--records", type=int, default=200)
    parser.add_argument("--pdfs", type=int, default=4)
    args = parser.parse_args()

    cfg = load_config(args.config)
    sample_dir = REPO_ROOT / "samples"
    (sample_dir / "pdf").mkdir(parents=True, exist_ok=True)

    for source, target in SAMPLE_FILES.items():
        path = cfg.paths.dataset_dir / source
        if not path.exists():
            print(f"skip {source} (not built yet)")
            continue
        rows = list(read_jsonl(path))
        step = max(1, len(rows) // args.records)
        subset = rows[::step][: args.records]
        write_jsonl(sample_dir / target, subset)
        print(f"{target}: {len(subset)} records")

    # a couple of PDF files together with their metadata
    for source, prefix in (("aozora_works.jsonl", "aozora"), ("narou_novels.jsonl", "narou")):
        path = cfg.paths.dataset_dir / source
        if not path.exists():
            continue
        pdf_dir = cfg.paths.pdf_dir / prefix
        copied = 0
        for row in read_jsonl(path):
            if copied >= args.pdfs:
                break
            pdf_path = row.get("pdf_path")
            if not pdf_path:
                continue
            source_pdf = REPO_ROOT / pdf_path
            if not source_pdf.exists():
                continue
            shutil.copy2(source_pdf, sample_dir / "pdf" / source_pdf.name)
            copied += 1
        print(f"pdf/{prefix}: {copied} files")

    manifest = {
        "note": "Sample subset of the datasets, see docs/data_setup.md for the full pipeline.",
        "generated_by": "scripts/make_samples.py",
    }
    (sample_dir / "README.md").write_text(
        "# samples\n\n"
        "このディレクトリはリポジトリに同梱する小さなサンプルです。\n"
        "全文データは `make data` で `data/` 配下に生成されます（Git には含めません）。\n\n"
        "* `*.sample.jsonl` … メタデータの部分集合\n"
        "* `pdf/` … レンダリングした PDF のサンプル\n",
        encoding="utf-8",
    )
    (sample_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
