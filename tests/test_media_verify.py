from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.config import NarouConfig, PathsConfig  # noqa: E402
from asc.fonts import build_font_set  # noqa: E402
from asc.render.pdf import BookPdfRenderer  # noqa: E402
from asc.schema import Author, Work  # noqa: E402
from asc.sources.media_verify import (  # noqa: E402
     extract_author_variants,
    extract_search_titles,
    parse_cinii_books_response,
    parse_wikipedia_page_media,
)
from asc.sources.narou import NarouSource, normalize_novel  # noqa: E402


def test_extract_search_titles_and_author_variants():
    titles = extract_search_titles(
        "【アニメ3期決定！】お気楽領主の楽しい領地防衛 ～生産系魔術で名もなき村を最強の城塞都市に～"
    )
    assert titles[0] == "お気楽領主の楽しい領地防衛"

    mushoku = extract_search_titles("無職転生　- 異世界行ったら本気だす -")
    assert mushoku[0] == "無職転生"

    dendro = extract_search_titles("＜Infinite Dendrogram＞-インフィニット・デンドログラム-")
    assert "インフィニット・デンドログラム" in dendro
    assert "Infinite Dendrogram" in dendro

    renamed = extract_search_titles(
        "隅でいいです。構わないでくださいよ。",
        "書籍版タイトル『聖女になるので二度目の人生は勝手にさせてもらいます』発売中",
    )
    assert renamed[0] == "聖女になるので二度目の人生は勝手にさせてもらいます"

    assert extract_author_variants("鼠色猫/長月達平") == ["鼠色猫", "長月達平"]
    assert extract_author_variants("江口　連") == ["江口連"]
    assert extract_author_variants("雨川 透子◆ルプななアニメ化") == ["雨川透子"]


def test_parse_cinii_books_verifies_books_and_manga_and_blocks_homonyms():
    kusuriya_json = {
        "@graph": [
            {
                "opensearch:totalResults": "32",
                "items": [
                    {
                        "title": "薬屋のひとりごと",
                        "dc:creator": "日向夏 [著]",
                        "dc:publisher": ["主婦の友インフォス", "主婦の友社(発売)"],
                        "dcterms:isPartOf": [{"dc:title": "ヒーロー文庫"}],
                        "dcterms:hasPart": [{"@id": "urn:isbn:9784074543793"}],
                        "cinii:ownerCount": "48",
                    },
                    {
                        "title": "薬屋のひとりごと",
                        "dc:creator": "日向夏原作 ; ねこクラゲ作画",
                        "dc:publisher": ["スクウェア・エニックス"],
                        "dcterms:isPartOf": [{"dc:title": "ビッグガンガンコミックス"}],
                        "dcterms:hasPart": [{"@id": "urn:isbn:9784757590274"}],
                        "cinii:ownerCount": "7",
                    },
                ],
            }
        ]
    }
    res = parse_cinii_books_response(
        kusuriya_json,
        search_titles=["薬屋のひとりごと"],
        author_variants=["日向夏"],
    )
    assert res["matched"] is True
    assert res["has_book"] is True
    assert res["has_manga"] is True
    assert res["publisher"] == "主婦の友インフォス"
    assert res["label"] == "ヒーロー文庫"
    assert res["isbn_sample"] == "9784074543793"
    assert res["manga_isbn_sample"] == "9784757590274"

    # Series title inside dcterms:isPartOf (e.g. 本好きの下剋上 "兵士の娘")
    honzuki_json = {
        "@graph": [
            {
                "opensearch:totalResults": "45",
                "items": [
                    {
                        "title": "兵士の娘",
                        "dc:creator": "香月美夜作 ; 椎名優絵",
                        "dc:publisher": ["TOブックス"],
                        "dcterms:isPartOf": [
                            {"dc:title": "TOジュニア文庫, [か-1-4] . 本好きの下剋上 / 香月美夜作"}
                        ],
                        "dcterms:hasPart": [{"@id": "urn:isbn:9784866990002"}],
                        "cinii:ownerCount": "1",
                    }
                ],
            }
        ]
    }
    res_h = parse_cinii_books_response(
        honzuki_json,
        search_titles=["本好きの下剋上"],
        author_variants=["香月美夜"],
    )
    assert res_h["matched"] is True
    assert res_h["has_book"] is True
    assert res_h["isbn_sample"] == "9784866990002"

    # Homonym by a different author must be rejected!
    homonym_json = {
        "@graph": [
            {
                "opensearch:totalResults": "5",
                "items": [
                    {
                        "title": "魔王",
                        "dc:creator": "伊坂幸太郎著",
                        "dc:publisher": ["講談社"],
                        "dcterms:hasPart": [{"@id": "urn:isbn:9784062760829"}],
                        "cinii:ownerCount": "120",
                    }
                ],
            }
        ]
    }
    res_bad = parse_cinii_books_response(
        homonym_json,
        search_titles=["魔王"],
        author_variants=["テスト太郎"],
    )
    assert res_bad["matched"] is False

    # Self-publishing (KDP) must be rejected!
    kdp_json = {
        "@graph": [
            {
                "opensearch:totalResults": "1",
                "items": [
                    {
                        "title": "俺の自費出版ファンタジー",
                        "dc:creator": "テスト太郎著",
                        "dc:publisher": ["Kindle Direct Publishing"],
                        "dcterms:hasPart": [{"@id": "urn:isbn:9798000000001"}],
                    }
                ],
            }
        ]
    }
    assert (
        parse_cinii_books_response(
            kdp_json,
            search_titles=["俺の自費出版ファンタジー"],
            author_variants=["テスト太郎"],
        )["matched"]
        is False
    )


def test_parse_wikipedia_page_media_distinguishes_vr_theme_from_real_games():
    # Franchise with Novel + Manga + split Anime + Game section
    wiki_page = {
        "pageid": 1001,
        "ns": 0,
        "title": "無職転生 〜異世界行ったら本気だす〜",
        "categories": [
            {"title": "Category:小説家になろうの小説"},
            {"title": "Category:MFブックス"},
            {"title": "Category:2021年のテレビアニメ"},
        ],
        "revisions": [
            {
                "slots": {
                    "main": {
                        "*": """
{{Infobox animanga/Novel
| 著者 = [[理不尽な孫の手]]
| 出版社 = [[KADOKAWA]]
| レーベル = [[MFブックス]]
| 巻数 = 全26巻
}}
{{Infobox animanga/Manga
| 作者 = フジカワユカ
}}
=== スマートフォンゲーム ===
『無職転生 〜ゲームになっても本気だす〜』が配信された。
"""
                    }
                }
            }
        ],
    }
    parsed = parse_wikipedia_page_media(
        wiki_page,
        ncode="n9669bk",
        search_titles=["無職転生"],
        author_variants=["理不尽な孫の手"],
        matched_by_ncode=True,
    )
    assert parsed["matched"] is True
    assert parsed["has_book"] is True
    assert parsed["has_manga"] is True
    assert parsed["has_anime"] is True
    assert parsed["has_game"] is True
    assert parsed["volumes"] == 26

    # VRMMO theme category WITHOUT real game adaptation must have has_game=False
    vr_page = {
        "pageid": 1002,
        "ns": 0,
        "title": "VR冒険記",
        "categories": [
            {"title": "Category:小説家になろうの小説"},
            {"title": "Category:コンピュータゲームを題材とした小説"},
            {"title": "Category:カドカワBOOKS"},
        ],
        "revisions": [{"slots": {"main": {"*": "『VR冒険記』はテスト著者による小説。"}}}],
    }
    parsed_vr = parse_wikipedia_page_media(
        vr_page,
        ncode="n1111aa",
        search_titles=["VR冒険記"],
        author_variants=["テスト著者"],
        matched_by_ncode=True,
    )
    assert parsed_vr["matched"] is True
    assert parsed_vr["has_book"] is True
    assert parsed_vr["has_game"] is False

    # Person biography page must be rejected even if linked
    person_page = {
        "pageid": 1003,
        "ns": 0,
        "title": "三好基晴",
        "categories": [{"title": "Category:存命人物"}],
        "revisions": [{"slots": {"main": {"*": "日本の医師。"}}}],
    }
    assert (
        parse_wikipedia_page_media(
            person_page,
            ncode="n6757e",
            search_titles=["エッセイ"],
            author_variants=["三好"],
            matched_by_ncode=True,
        )["matched"]
        is False
    )


def test_strict_external_verification_filters_fake_and_captures_silent_r15():
    # Candidate 1: R15 silent masterpiece (isr15=1, NO "書籍化" keyword in Narou metadata!)
    silent_r15 = normalize_novel(
        {
            "title": "無職転生　- 異世界行ったら本気だす -",
            "ncode": "N9669BK",
            "userid": 288399,
            "writer": "理不尽な孫の手",
            "story": "３４歳職歴無し住所不定無職童貞のニートは、ある日家を追い出され…",
            "biggenre": 2,
            "genre": 201,
            "keyword": "R15 残酷な描写あり 異世界転生",
            "general_firstup": "2012-11-22 17:00:00",
            "general_all_no": 286,
            "length": 2820000,
            "isr15": 1,
            "fav_novel_cnt": 300000,
            "all_point": 500000,
            "global_point": 1100000,
        }
    )
    assert silent_r15.rights["commercialized"] is None
    assert "R15" in silent_r15.stats["elements"]

    # Candidate 2: Self-claimed "書籍化" in Narou metadata, but ZERO real external books/anime/games
    fake_claimed = normalize_novel(
        {
            "title": "【書籍化決定！】架空の未発売ウェブ小説",
            "ncode": "N0000ZZ",
            "userid": 999999,
            "writer": "架空作者",
            "story": "書籍化決定しました！（※実在しない自己申告）",
            "biggenre": 2,
            "genre": 201,
            "keyword": "異世界 書籍化",
            "general_firstup": "2025-01-01 00:00:00",
            "general_all_no": 50,
            "length": 150000,
            "isr15": 0,
            "fav_novel_cnt": 5000,
            "all_point": 10000,
            "global_point": 20000,
        }
    )
    assert fake_claimed.rights["commercialized"] is True

    class MockExternalClient:
        def get(self, url: str, **kwargs) -> bytes:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if "wikipedia.org" in parsed.netloc:
                if qs.get("list") == ["exturlusage"]:
                    if qs.get("euprotocol") == ["https"]:
                        return json.dumps(
                            {
                                "query": {
                                    "exturlusage": [
                                        {
                                            "pageid": 501,
                                            "ns": 0,
                                            "title": "無職転生",
                                            "url": "https://ncode.syosetu.com/n9669bk/",
                                        }
                                    ]
                                }
                            }
                        ).encode("utf-8")
                    return json.dumps({"query": {"exturlusage": []}}).encode("utf-8")
                if qs.get("list") == ["categorymembers"]:
                    return json.dumps({"query": {"categorymembers": []}}).encode("utf-8")
                if qs.get("list") == ["search"]:
                    return json.dumps({"query": {"search": []}}).encode("utf-8")
                if qs.get("prop") == ["categories|revisions"]:
                    return json.dumps(
                        {
                            "query": {
                                "pages": {
                                    "501": {
                                        "pageid": 501,
                                        "ns": 0,
                                        "title": "無職転生",
                                        "categories": [
                                            {"title": "Category:小説家になろうの小説"},
                                            {"title": "Category:MFブックス"},
                                            {"title": "Category:2021年のテレビアニメ"},
                                        ],
                                        "revisions": [
                                            {
                                                "slots": {
                                                    "main": {
                                                        "*": "{{Infobox animanga/Novel | 著者 = 理不尽な孫の手 | 出版社 = KADOKAWA | レーベル = MFブックス | 巻数 = 全26巻}}\n{{Infobox animanga/Manga}}\n=== ゲーム ==="
                                                    }
                                                }
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    ).encode("utf-8")
            if "ci.nii.ac.jp" in parsed.netloc:
                title_q = (qs.get("title") or [""])[0]
                if "無職転生" in title_q:
                    return json.dumps(
                        {
                            "@graph": [
                                {
                                    "opensearch:totalResults": "26",
                                    "items": [
                                        {
                                            "title": "無職転生 : 異世界行ったら本気だす",
                                            "dc:creator": "理不尽な孫の手著",
                                            "dc:publisher": ["KADOKAWA"],
                                            "dcterms:isPartOf": [{"dc:title": "MFブックス"}],
                                            "dcterms:hasPart": [{"@id": "urn:isbn:9784040662206"}],
                                            "cinii:ownerCount": "15",
                                        }
                                    ],
                                }
                            ]
                        }
                    ).encode("utf-8")
                return json.dumps({"@graph": [{"opensearch:totalResults": "0"}]}).encode("utf-8")
            raise AssertionError(f"unexpected URL {url}")

    cfg = NarouConfig(include_r15=True, strict_external_verification=True)
    src = NarouSource(cfg, PathsConfig(), MockExternalClient())  # type: ignore[arg-type]
    accepted = src.verify_candidates_external([silent_r15, fake_claimed], strict=True)

    assert [w.id for w in accepted] == ["narou:N9669BK"]
    assert silent_r15.rights["commercialized"] is True
    assert silent_r15.rights["external_verified"] is True
    assert silent_r15.extra["ranking"]["verified_media"] == ["book", "manga", "anime", "game"]
    assert silent_r15.extra["ranking"]["isbn_sample"] == "9784040662206"
    assert fake_claimed.rights["commercialized"] is False
    assert fake_claimed.rights["external_verified"] is False


def test_refresh_cover_preserves_body_pages(tmp_path: Path):
    from pypdf import PdfReader

    font_dir = Path(__file__).resolve().parents[1] / "data" / "cache" / "fonts"
    try:
        fonts = build_font_set(
            body_font="ZenOldMincho-Regular.ttf",
            heading_font="ZenKakuGothicNew-Bold.ttf",
            body_bold_font=None,
            cache_dir=font_dir,
        )
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"fonts unavailable: {exc}")

    renderer = BookPdfRenderer(fonts=fonts)
    work = Work(
        id="narou:N9669BK",
        source="syosetsuka_ni_narou",
        title="無職転生",
        url="https://ncode.syosetu.com/n9669bk/",
        authors=[Author(name="理不尽な孫の手", role="author")],
        genre={"label": "ハイファンタジー", "parent": {"label": "ファンタジー"}},
        stats={"char_count": 5000, "episodes": 2, "elements": ["R15"], "global_point": 1100000, "fav_novel_cnt": 300000},
        extra={"ranking": {"rank": 1, "is_book": True, "is_comic": True, "is_anime": True, "is_game": True, "isbn_sample": "9784040662206", "publisher": "KADOKAWA", "label": "MFブックス"}},
    )
    blocks = [{"type": "paragraph", "text": "本文テキストです。" * 40} for _ in range(15)]
    pdf_path = tmp_path / "N9669BK.pdf"
    renderer.render(work, blocks, pdf_path, note="テスト注記")
    orig_pages = len(PdfReader(str(pdf_path)).pages)
    assert orig_pages >= 2

    work.extra["ranking"]["rank"] = 2
    renderer.refresh_cover(work, pdf_path, pdf_path, note="更新注記")
    updated_reader = PdfReader(str(pdf_path))
    assert len(updated_reader.pages) == orig_pages
    cover_txt = updated_reader.pages[0].extract_text()
    assert "第2位" in cover_txt
    assert "9784040662206" in cover_txt


def test_parse_apple_books_response_verifies_imprint_and_rejects_unrelated():
    from asc.sources.media_verify import parse_apple_books_response

    apple_payload = {
        "resultCount": 4,
        "results": [
            {
                "kind": "ebook",
                "trackId": 1001,
                "trackName": "異世界迷宮でハーレムを(1)",
                "artistName": "氷樹一世, 蘇我捨恥(ヒーロー文庫/イマジカインフォス) & 四季童子",
                "genres": ["マンガ", "ブック"],
            },
            {
                "kind": "ebook",
                "trackId": 1002,
                "trackName": "異世界迷宮でハーレムを 1",
                "artistName": "蘇我捨恥(ヒーロー文庫/イマジカインフォス) & 四季童子",
                "genres": ["ライトノベル", "ブック"],
            },
            {
                "kind": "ebook",
                "trackId": 1003,
                "trackName": "【期間限定無料】異世界迷宮でハーレムを(1)",
                "artistName": "氷樹一世, 蘇我捨恥",
                "genres": ["マンガ", "ブック"],
            },
            {
                "kind": "ebook",
                "trackId": 1004,
                "trackName": "異世界迷宮でハーレムを 自費出版",
                "artistName": "蘇我捨恥 / Kindle Direct Publishing",
                "genres": ["ライトノベル"],
            },
        ],
    }

    parsed = parse_apple_books_response(
        apple_payload,
        search_titles=["異世界迷宮でハーレムを"],
        author_variants=extract_author_variants("蘇我捨恥"),
    )
    assert parsed["matched"] is True
    assert parsed["has_book"] is True
    assert parsed["has_manga"] is True
    assert parsed["label"] == "ヒーロー文庫"
    assert parsed["publisher"] == "イマジカインフォス"
    assert parsed["book_hits"] == 1
    assert parsed["manga_hits"] == 1

    # Uncommercialized work ("謙虚、堅実をモットーに生きております！") must NOT match unrelated books
    unrelated_payload = {
        "resultCount": 1,
        "results": [
            {
                "kind": "ebook",
                "trackId": 9999,
                "trackName": "謙虚なるコントラリアン",
                "artistName": "アンソニー・ボルトン",
                "genres": ["ビジネス／マネー", "ブック"],
            }
        ],
    }
    rejected = parse_apple_books_response(
        unrelated_payload,
        search_titles=["謙虚、堅実をモットーに生きております！"],
        author_variants=extract_author_variants("ひよこのケーキ"),
    )
    assert rejected["matched"] is False


def test_write_ranked_catalogs_emits_rank201_300_slice(tmp_path: Path):
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root / "scripts") not in sys.path:
        sys.path.insert(0, str(repo_root / "scripts"))
    import setup_dataset
    from asc.config import Config

    cfg = Config()
    cfg.paths.dataset_dir = tmp_path
    works = [
        Work(
            id=f"narou:N{idx:04d}AA",
            source="syosetsuka_ni_narou",
            title=f"作品{idx}",
            url=f"https://ncode.syosetu.com/n{idx:04d}aa/",
            authors=[Author(name=f"作者{idx}", role="author")],
            genre={"label": "ハイファンタジー"},
            stats={"char_count": 50000, "episodes": 25, "elements": ["R15"], "global_point": 100000 - idx, "fav_novel_cnt": 20000},
            pdf_path=f"data/pdf/narou/N{idx:04d}AA.pdf",
            extra={"pdf_bytes": 1048576, "ranking": {"rank": idx, "is_book": True, "is_comic": True}},
        )
        for idx in range(1, 301)
    ]
    setup_dataset._write_ranked_catalogs(cfg, works)

    assert (tmp_path / "narou_commercialized_ranked.jsonl").is_file()
    assert (tmp_path / "narou_commercialized_top100.jsonl").is_file()
    assert (tmp_path / "narou_commercialized_rank101_200.jsonl").is_file()
    assert (tmp_path / "narou_commercialized_rank201_300.jsonl").is_file()
    md_201_300 = (tmp_path / "narou_rank201_300_ranking.md").read_text(encoding="utf-8")
    assert "第201位〜第300位" in md_201_300
    assert "`N0201AA`" in md_201_300
    assert "`N0300AA`" in md_201_300

