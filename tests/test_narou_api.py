from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.sources.narou import (  # noqa: E402
    NarouSource,
    api_field,
    compute_popularity_ranking_score,
    detect_commercialized_from_metadata,
    estimate_volumes_from_text,
    extract_syuppan_search_word,
    normalize_novel,
    parse_anime_commercialization_html,
    parse_commercialized_info_html,
    parse_syuppan_list_html,
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


def test_syuppan_and_anime_parsers_and_ranking_score():
    assert extract_syuppan_search_word("【アニメ化決定！】お気楽領主の楽しい領地防衛 ～生産系魔術～") == "お気楽領主の楽しい領"
    assert extract_syuppan_search_word("Ｒｅ：ゼロから始める異世界生活") == "ゼロから始める異世界"
    assert extract_syuppan_search_word("無職転生　- 異世界行ったら本気だす -") == "無職転生"

    anime_html = """
    <a href="https://ncode.syosetu.com/n6316bn/">転生したらスライムだった件</a>
    <a href="https://ncode.syosetu.com/N9669BK/">無職転生</a>
    """
    assert parse_anime_commercialization_html(anime_html) == {"n6316bn", "n9669bk"}

    syuppan_html = """
    <div class="p-syuppan">
      <a href="/syuppan/view/bookid/9689/">無職転生 24</a>
      <a href="https://mypage.syosetu.com/288399/">理不尽な孫の手</a>
      <div>出版社KADOKAWA/メディアファクトリー</div>
      <div>レーベルMFブックス</div>
      <a href="/syuppan/view/bookid/9690/">無職転生 25</a>
      <a href="https://mypage.syosetu.com/288399/">理不尽な孫の手</a>
      <a href="/syuppan/view/bookid/9999/">別作者の無職転生パロディ</a>
      <a href="https://mypage.syosetu.com/111111/">別人</a>
    </div>
    <h3>書報を探す</h3>
    """
    parsed = parse_syuppan_list_html(syuppan_html, userid="288399")
    assert parsed["matched"] is True
    assert parsed["volumes"] == 2
    assert parsed["publisher"] == "KADOKAWA/メディアファクトリー"
    assert parsed["label"] == "MFブックス"

    assert estimate_volumes_from_text("オーバーラップノベルス様より書籍１７巻まで発売中！") == 17
    assert estimate_volumes_from_text("ヒーロー文庫さんで現在十五巻まででております。") == 15

    w1 = normalize_novel(
        dict(
            API_RECORD,
            ncode="N2710DB",
            title="とんでもスキルで異世界放浪メシ",
            story="オーバーラップノベルス様より書籍１７巻まで発売中！アニメ1期・2期放送済",
            fav_novel_cnt=275336,
            all_point=490936,
            global_point=1041608,
        )
    )
    w2 = normalize_novel(
        dict(
            API_RECORD,
            ncode="N0001AA",
            title="【書籍化】小規模作品",
            fav_novel_cnt=5000,
            all_point=10000,
            global_point=20000,
        )
    )
    s1 = compute_popularity_ranking_score(w1)
    s2 = compute_popularity_ranking_score(w2)
    assert s1["is_anime"] is True
    assert s1["estimated_volumes"] == 17
    assert s1["ranking_score"] > s2["ranking_score"]


def test_fetch_novel_text_paginates_all_toc_pages():
    from asc.config import NarouConfig, PathsConfig

    pages = {
        "https://ncode.syosetu.com/n9999zz/": """
            <a href="/n9999zz/1/">第1話</a>
            <a href="/n9999zz/2/">第2話</a>
            <a href="/n9999zz/?p=2">次へ</a>
            <a href="/n9999zz/?p=3">最後へ</a>
        """,
        "https://ncode.syosetu.com/n9999zz/?p=2": '<a href="/n9999zz/101/">第101話</a>',
        "https://ncode.syosetu.com/n9999zz/?p=3": '<a href="/n9999zz/201/">第201話</a>',
        "https://ncode.syosetu.com/n9999zz/1/": '<div class="p-novel__text"><p>一話本文。</p></div>',
        "https://ncode.syosetu.com/n9999zz/2/": '<div class="p-novel__text"><p>二話本文。</p></div>',
        "https://ncode.syosetu.com/n9999zz/101/": '<div class="p-novel__text"><p>百一話本文。</p></div>',
        "https://ncode.syosetu.com/n9999zz/201/": '<div class="p-novel__text"><p>二百一話本文。</p></div>',
    }

    class DummyClient:
        def get_text(self, url: str, **kwargs) -> str:
            return pages[url]

    cfg = NarouConfig(text_source="download", use_txtdownload=False)
    src = NarouSource(cfg, PathsConfig(), DummyClient())  # type: ignore[arg-type]
    novel = src.fetch_novel_text("N9999ZZ", max_episodes=0)
    assert [c["index"] for c in novel.chapters] == [1, 2, 101, 201]
    assert novel.char_count == len("一話本文。") + len("二話本文。") + len("百一話本文。") + len("二百一話本文。")



