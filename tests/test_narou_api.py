from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.sources.narou import (  # noqa: E402
    api_field,
    detect_commercialized_from_metadata,
    normalize_novel,
    parse_commercialized_info_html,
)

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


def test_commercialization_detected_from_metadata():
    comm, markers = detect_commercialized_from_metadata(
        "【アニメ化】ループ7回目の悪役令嬢",
        "女主人公 異世界 書籍化 アニメ化",
        "★TVアニメスタート！",
        genre_code=101,
        fav_novel_cnt=150000,
        all_point=320000,
    )
    assert comm is True
    assert "書籍化" in markers
    assert "アニメ化" in markers

    # Aspirational / self-published / 0-bookmark works must not be flagged
    comm_neg, _ = detect_commercialized_from_metadata(
        "面白くない僕と彼女が、書籍化を目指す話",
        "現代 青春",
        "書籍化を目指して頑張ります！",
        genre_code=302,
        fav_novel_cnt=500,
        all_point=1200,
    )
    assert comm_neg is None

    comm_spam, _ = detect_commercialized_from_metadata(
        "テスト書籍化",
        "書籍化",
        "テスト",
        genre_code=201,
        fav_novel_cnt=1,
        all_point=2,
    )
    assert comm_spam is None


def test_parse_commercialized_info_html_ignores_bookmark_modal_and_other_works():
    # Live Narou infotop pages contain a hidden bookmark modal with "エラーが発生しました"
    # and a "同一作者の作品" section at the bottom.
    comm_html = """
    <html><head><title>作品タイトル[作品情報]</title></head><body>
    <h1>【アニメ化】ループ7回目の悪役令嬢</h1>
    <div>キーワード：異世界 書籍化 アニメ化</div>
    <h2>同一作者の作品</h2>
    <div>別の作品</div>
    <div class="modal">設定を保存しました エラーが発生しました</div>
    </body></html>
    """
    assert parse_commercialized_info_html(comm_html) is True

    # Non-commercialized work whose author has OTHER commercialized works:
    non_comm_html = """
    <html><head><title>短編タイトル[作品情報]</title></head><body>
    <h1>静かな森の短編</h1>
    <div>キーワード：ほのぼの 日常</div>
    <h2>同一作者の作品</h2>
    <div>【書籍化・アニメ化】別の大人気作品</div>
    <div class="modal">エラーが発生しました</div>
    </body></html>
    """
    assert parse_commercialized_info_html(non_comm_html) is False

    # Actual error page:
    err_html = "<html><head><title>エラー</title></head><body>該当する小説が存在しません</body></html>"
    assert parse_commercialized_info_html(err_html) is None


def test_normalize_novel_unescapes_html_entities():
    rec = dict(API_RECORD, title="【書籍化&amp;コミカライズ】猫と&quot;魔法&quot;")
    work = normalize_novel(rec)
    assert work.title == '【書籍化&コミカライズ】猫と"魔法"'
    assert work.rights["commercialized"] is True


