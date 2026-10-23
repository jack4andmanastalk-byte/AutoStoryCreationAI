#!/usr/bin/env python3
"""Download raw responses of the official Syosetsuka ni Narou novel API.

The responses are stored as JSON files below ``data/cache/narou_api`` and can
be imported later with ``python scripts/setup_dataset.py narou-metadata``
(see ``narou.api_response_files`` in ``configs/dataset.yaml``).  Keeping the
raw responses makes the dataset reproducible without hammering the API.

Usage::

    python scripts/fetch_narou_api.py --per-query 500 --order-pages 2
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

#: Short codes of the official API (see https://dev.syosetu.com/man/api/).
#: The long field names are rejected by the API for some queries, the short
#: codes always work and the answer uses the long names as keys.
FIELDS = [
    "t",  # title
    "n",  # ncode
    "u",  # userid
    "w",  # writer
    "s",  # story
    "k",  # keyword
    "bg",  # big genre
    "g",  # genre
    "gf",  # first posted
    "gl",  # last updated
    "nt",  # novel type
    "e",  # completed
    "ga",  # number of episodes
    "l",  # character count
    "ti",  # reading time
    "ir",  # R15
    "ibl",  # boys love
    "igl",  # girls love
    "izk",  # cruel description
    "its",  # isekai reincarnation
    "iti",  # isekai transfer
    "f",  # bookmarks (fav_novel_cnt)
    "i",  # impressions (impression_cnt)
    "r",  # reviews (review_cnt)
    "a",  # evaluation points (all_point)
    "ah",  # evaluation count (all_hyoka_cnt)
    "gp",  # global point (fav_novel_cnt * 2 + all_point)
    "sa",  # illustrations
    "ka",  # conversation rate
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--genres", type=int, nargs="*", default=None)
    parser.add_argument(
        "--orders",
        nargs="*",
        default=["hyoka", "favnovelcnt", "impressioncnt", "reviewcnt", "lengthdesc", "generalfirstup"],
    )
    parser.add_argument("--per-query", type=int, default=500)
    parser.add_argument(
        "--order-pages",
        type=int,
        default=4,
        help="number of 500-record pages to fetch per top ordering query (max st=2000)",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=["書籍化", "コミカライズ", "アニメ化", "ゲーム化"],
        help="commercialisation search terms harvested via order=hyoka (R15 included)",
    )
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

    limit = min(args.per_query, 500)
    queries: list[tuple[str, dict]] = []
    major_genres = {101, 102, 201, 202, 302, 401}
    for genre in args.genres if args.genres is not None else cfg.narou.genres:
        g_pages = 2 if genre in major_genres and args.order_pages >= 2 else 1
        for page_idx in range(g_pages):
            st = 1 + page_idx * limit
            if st > 2000:
                break
            suffix = "" if page_idx == 0 else f"_p{page_idx + 1}"
            # Note: notr15 is intentionally omitted so R15-flagged general works are included.
            queries.append((f"genre_{genre}{suffix}", {"genre": genre, "order": "hyoka", "st": st}))

    for order in args.orders or []:
        if order in {"hyoka", "favnovelcnt"}:
            pages = max(1, args.order_pages)
        elif order in {"impressioncnt", "reviewcnt"}:
            pages = min(2, max(1, args.order_pages))
        else:
            pages = 1
        for page_idx in range(pages):
            st = 1 + page_idx * limit
            if st > 2000:
                break
            suffix = "" if page_idx == 0 else f"_p{page_idx + 1}"
            queries.append((f"order_{order}{suffix}", {"order": order, "st": st}))

    for idx, kw in enumerate(args.keywords or []):
        kw_pages = 2 if kw == "書籍化" and args.order_pages >= 2 else 1
        for page_idx in range(kw_pages):
            st = 1 + page_idx * limit
            if st > 2000:
                break
            suffix = "" if page_idx == 0 else f"_p{page_idx + 1}"
            queries.append((f"kw_{idx}_{kw}{suffix}", {"word": kw, "order": "hyoka", "st": st}))

    for name, query in queries:
        params: dict = {"out": "json", "lim": limit}
        if not args.no_fields:
            params["of"] = "-".join(FIELDS)
        params.update(query)
        url = cfg.narou.api_base + "?" + urlencode(params)
        LOGGER.info("GET %s", url)
        payload = client.get(url)
        data = json.loads(payload.decode("utf-8"))
        target = out_dir / f"{name}.json"
        target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("stored %s records in %s", max(0, len(data) - 1), target)
        time.sleep(min(cfg.http.request_interval_seconds, 0.5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
