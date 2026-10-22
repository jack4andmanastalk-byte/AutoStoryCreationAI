from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.sources.narou import api_field, normalize_novel  # noqa: E402

# A record as it is returned by the official API when the short codes are
# requested (https://dev.syosetu.com/man/api/).
API_RECORD = {
    "title": "魔王だが、勇者（あいつら）は Applause",
    "ncode": "N6734MX",
    "userid": 3147212,
    "writer": "Mittsu",
    "story": "勇者の一行が最強の魔王に襲われる。",
    "biggenre": 2,
    "genre": 201,
    "keyword": "ASNE 大袋 15 秋の文芸 2026",
    "general_firstup": "2026-10-23 00:32:13",
    "general_lastup": "2026-10-23 00:32:13",
    "noveltype": 1,
    "end": 1,
    "general_all_no": 14,
    "length": 77644,
    "time": 156,
    "isr15": 0,
    "isbl": 0,
    "isgl": 0,
    "iszankoku": 0,
    "istensei": 0,
    "istenni": 0,
    "fav_novel_cnt": 12,
    "all_point": 345,
    "all_hyoka_cnt": 20,
    "sasie_cnt": 3,
    "kaiwaritu": 37,
}


def test_api_field_accepts_short_codes():
    short = {"gf": "2026-10-23 00:32:13", "l": 77644, "ga": 14, "e": 1}
    assert api_field(short, "generalfirstup") == "2026-10-23 00:32:13"
    assert api_field(short, "length") == 77644
    assert api_field(short, "general_all_no") == 14
    assert api_field(short, "end") == 1
    assert api_field(short, "missing", "fallback") == "fallback"


def test_normalize_novel_reads_the_publication_date():
    work = normalize_novel(API_RECORD)
    assert work.published_at == "2026-10-23"
    assert work.published_year == 2026
    assert work.title == "魔王だが、勇者（あいつら）は Applause"
    assert work.genre["code"] == 201
    assert work.genre["parent"]["code"] == 2
    assert work.stats["char_count"] == 77644
    assert work.stats["episodes"] == 14
    assert work.stats["is_completed"] is True
    assert work.extra["last_up"] == "2026-10-23 00:32:13"
    assert work.url == "https://ncode.syosetu.com/n6734mx/"


def test_normalize_novel_accepts_short_codes():
    record = {
        "t": "タイトル",
        "n": "N1234AB",
        "u": 42,
        "w": "作者",
        "s": "あらすじ",
        "bg": 1,
        "g": 101,
        "k": "異世界",
        "gf": "2024-05-06 07:08:09",
        "gl": "2024-06-07 08:09:10",
        "nt": 1,
        "e": 0,
        "ga": 3,
        "l": 1234,
        "ti": 5,
        "ir": 1,
    }
    work = normalize_novel(record)
    assert work.title == "タイトル"
    assert work.published_year == 2024
    assert work.stats["char_count"] == 1234
    assert work.stats["episodes"] == 3
    assert work.stats["is_completed"] is False
    assert "R15" in work.stats["elements"]
