from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.config import AozoraConfig, PathsConfig  # noqa: E402
from asc.http import HttpClient  # noqa: E402
from asc.sources.aozora import (  # noqa: E402
    AozoraSource,
    enrich_ndc_genre,
    load_ndc_map,
    parse_nuxt_payload,
    parse_official_card_csv,
    parse_pages_mirror,
    sample_works,
)

PAYLOAD = (
    '__NUXT_JSONP__("/works/10", (function(a,b,c,d,e,f,g,h){'
    'f.bibclass="NDC 913";f.first_appearance="「新潮」1918（大正7）年3月号";'
    'f.kana_type="新字旧仮名";'
    'return {data:[{book:{title:{title:"秋は淋しい",title_kana:"あきはさびしい",'
    'author_id:a,work_id:10,person_id:a},work:f,'
    'author:[{role:"著者",author_name:"素木 しづ",author_id:a,born_on:"1895-03-26"}],'
    'original_book:[{publisher:"北書房",first_edition:"1970（昭和45）年6月15日",'
    'book_title:"作品集",booktype:"底本"}],'
    'download:[{filetype:"テキストファイル(ルビあり)",filename:"10_ruby_20387.zip",'
    'charset:b,encoding:c,created_on:d,updated_on:e}],copyright:false},'
    'workHTMLURL:"https://www.aozora.gr.jp/cards/000012/files/10_20388.html"}]}'
    '}(12,"JIS X 0208","ShiftJIS","1999-09-05","2005-11-14",{},"なし",true)))'
)


def test_parse_nuxt_payload():
    data = parse_nuxt_payload(PAYLOAD)
    entry = data["data"][0]
    book = entry["book"]
    assert book["title"]["title"] == "秋は淋しい"
    assert book["title"]["work_id"] == 10
    assert book["work"]["bibclass"] == "NDC 913"
    assert book["work"]["first_appearance"].startswith("「新潮」")
    assert book["author"][0]["author_name"] == "素木 しづ"
    assert book["original_book"][0]["first_edition"].startswith("1970")
    assert book["download"][0]["charset"] == "JIS X 0208"
    assert book["download"][0]["created_on"] == "1999-09-05"
    assert book["copyright"] is False
    assert entry["workHTMLURL"].endswith("10_20388.html")


def test_parse_pages_mirror(tmp_path: Path):
    works = tmp_path / "_nuxt" / "static" / "12345" / "works" / "10"
    works.mkdir(parents=True)
    (works / "payload.js").write_text(PAYLOAD, encoding="utf-8")
    card = parse_pages_mirror(tmp_path)
    assert len(card.works) == 1
    work = card.works[0]
    assert work.id == "aozora:000010"
    assert work.title == "秋は淋しい"
    assert work.published_year == 1970
    assert work.genre["code"] == "913"
    assert work.extra["text_filename"] == "10_ruby_20387.zip"
    assert work.rights["copyright_flag"] is False


def test_official_csv_deduplicates_translators_and_preserves_copyright(tmp_path: Path):
    csv_text = (
        "作品ID,作品名,副題,人物ID,姓,名,役割フラグ,分類番号,初出,作品著作権フラグ,人物著作権フラグ,テキストファイルURL\n"
        "57302,フランダースの犬,,001044,ウィーダ,,著者,NDC K933,1872年,なし,なし,https://www.aozora.gr.jp/cards/001044/files/57302_ruby.zip\n"
        "57302,フランダースの犬,,001500,山田,太郎,翻訳者,NDC K933,1872年,あり,あり,https://www.aozora.gr.jp/cards/001044/files/57302_ruby.zip\n"
        "000148,吾輩は猫である,,000148,夏目,漱石,著者,NDC 913,「ホトトギス」1905（明治38）年1月,なし,なし,https://www.aozora.gr.jp/cards/000148/files/789_ruby.zip\n"
    )
    card = parse_official_card_csv(csv_text.encode("utf-8"))
    assert len(card.works) == 2
    by_id = card.by_id()

    flanders = by_id["aozora:057302"]
    assert len(flanders.authors) == 2
    assert flanders.rights["copyright_flag"] is True

    cat = by_id["aozora:000148"]
    assert cat.rights["copyright_flag"] is False

    # NDC enrichment resolves both K933 and 913 without external JSON files
    ndc_map = load_ndc_map()
    enrich_ndc_genre(flanders, ndc_map)
    enrich_ndc_genre(cat, ndc_map)
    assert flanders.genre["label"] == "英米小説・物語（児童書）"
    assert flanders.genre["parent"]["label"] == "文学"
    assert cat.genre["label"] == "小説・物語（日本文学）"
    assert cat.genre["parent"]["label"] == "文学"

    # sample_works and fetch_text must strictly skip copyright_flag=True works
    sampled = sample_works(card.works, count=10)
    assert [w.id for w in sampled] == ["aozora:000148"]

    source = AozoraSource(AozoraConfig(), PathsConfig(cache_dir=tmp_path), HttpClient())
    assert source.fetch_text(flanders, index={57302: tmp_path / "dummy.txt"}) is None

