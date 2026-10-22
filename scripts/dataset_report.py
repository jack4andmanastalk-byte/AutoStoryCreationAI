#!/usr/bin/env python3
"""Print statistics about the datasets stored in ``data/datasets``.

Usage::

    python scripts/dataset_report.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.config import load_config  # noqa: E402
from asc.report import DatasetReport  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--json", action="store_true", help="machine readable output")
    args = parser.parse_args()

    cfg = load_config(args.config)
    report = DatasetReport(cfg.paths.dataset_dir).build()
    if args.json:
        payload = {
            name: {
                "records": stats.works,
                "with_text": stats.with_text,
                "with_pdf": stats.with_pdf,
                "total_chars": stats.total_chars,
                "years": dict(stats.years),
                "genres": dict(stats.genres),
                "big_genres": dict(stats.big_genres),
            }
            for name, stats in report.stats.items()
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
