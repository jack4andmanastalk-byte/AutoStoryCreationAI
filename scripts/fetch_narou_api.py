#!/usr/bin/env python3
"""Download raw responses of the official Syosetsuka ni Narou novel API.

The responses are stored as JSON files below ``data/cache/narou_api`` and can
be imported later with ``python scripts/setup_dataset.py narou-metadata``
(see ``narou.api_response_files`` in ``configs/dataset.yaml``).  Keeping the
raw responses makes the dataset reproducible without hammering the API.

Usage::

    python scripts/fetch_narou_api.py --genres 101 201 303 --per-query 300
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.config import load_config  # noqa: E402
from asc.http import HttpClient  # noqa: E402

LOGGER = logging.getLogger("fetch_narou_api")

#: fields that are stored for every novel
FIELDS = [
    "title",
    "ncode",
    "userid",
    "writer",
    "story",
    "keyword",
    "biggenre",
    "genre",
    "generalfirstup",
    "generallastup",
    "novel_type",
    "general_all_no",
    "length",
    "time",
    "isstop",
    "isr15",
    "isbl",
    "isgl",
    "iszankoku",
    "istensei",
    "istenni",
    "sasie_cnt",
    "kaiwaritu",
    "fav_novel_cnt",
    "impression_cnt",
    "review_cnt",
    "all_point",
    "all_hyoka_cnt",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--genres", type=int, nargs="*", default=None)
    parser.add_argument("--orders", nargs="*", default=["hyoka", "favnovelcnt"])
    parser.add_argument("--per-query", type=int, default=300)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-fields", action="store_true", help="store every field")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    cfg = load_config(args.config)
    client = HttpClient(
        user_agent=cfg.http.user_agent,
        timeout=cfg.http.timeout_seconds,
        max_retries=cfg.http.max_retries,
        backoff=cfg.http.backoff_seconds,
        request_interval=cfg.http.request_interval_seconds,
        cache_dir=cfg.http.cache_dir,
    )
    out_dir = Path(args.out_dir) if args.out_dir else cfg.paths.cache_dir / "narou_api"
    out_dir.mkdir(parents=True, exist_ok=True)

    queries: list[dict] = []
    for genre in args.genres if args.genres is not None else cfg.narou.genres:
        queries.append({"genre": genre})
    for order in args.orders or []:
        queries.append({"order": order})

    for query in queries:
        params = {"out": "json", "lim": min(args.per_query, 500)}
        if not args.no_fields:
            params["of"] = "-".join(FIELDS)
        params.update(query)
        url = cfg.narou.api_base + "?" + urlencode(params)
        LOGGER.info("GET %s", url)
        payload = client.get(url)
        data = json.loads(payload.decode("utf-8"))
        name = "_".join(f"{key}_{value}" for key, value in query.items())
        target = out_dir / f"{name}.json"
        target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("stored %s records in %s", len(data) - 1, target)
        time.sleep(cfg.http.request_interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
