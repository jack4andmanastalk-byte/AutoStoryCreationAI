from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.sources.aozora import parse_japanese_year  # noqa: E402
from asc.text.aozora_format import parse_aozora_text  # noqa: E402

SAMPLE = """はつ恋
ツルゲーネフ
神西清訳

-------------------------------------------------------
【テキスト中に現れる記号について】

《》：ルビ
（例）捧《ささ》げる
-------------------------------------------------------

［＃ページの左右中央］


　_age_^*_これは地文だ。

　十六｜歳《さい》で、犬が走った。

　「吾輩は猫である」［＃「吾輩」に傍点］と彼は言った。

［＃改ページ］

　あとの段落。
"""


def test_header_is_parsed():
    parsed = parse_aozora_text(SAMPLE)
    assert parsed.title == "はつ恋"
    assert parsed.author == "ツルゲーネフ"
    assert parsed.translator == "神西清訳"


def test_legend_block_is_removed():
    parsed = parse_aozora_text(SAMPLE)
    assert "テキスト中に現れる記号について" not in parsed.text
    assert "《》：ルビ" not in parsed.text


def test_ruby_is_flattened():
    parsed = parse_aozora_text(SAMPLE)
    assert "十六歳で、犬が走った。" in parsed.text
    ruby = [r for block in parsed.blocks for r in block.get("ruby", [])]
    assert {"base": "歳", "reading": "さい"} in ruby


def test_unprefixed_kanji_ruby_and_colophon_are_cleaned():
    raw = (
        "キャラメルと飴玉\n夢野久作\n\n"
        "キャラメルと飴玉《あめだま》とが喧嘩《けんか》をはじめました。\n\n"
        "底本：「夢野久作全集7」三一書房\n"
        "入力：川山隆\n校正：土屋隆\n"
        "青空文庫作成ファイル：\n"
        "このファイルは、インターネットの図書館、青空文庫で作られました。\n"
    )
    parsed = parse_aozora_text(raw)
    assert parsed.text == "キャラメルと飴玉とが喧嘩をはじめました。"
    assert "底本：" not in parsed.text
    assert "青空文庫作成ファイル" not in parsed.text
    ruby = [r for block in parsed.blocks for r in block.get("ruby", [])]
    assert {"base": "飴玉", "reading": "あめだま"} in ruby
    assert {"base": "喧嘩", "reading": "けんか"} in ruby


def test_emphasis_is_captured():
    parsed = parse_aozora_text(SAMPLE)
    emphasis = [e for block in parsed.blocks for e in block.get("emphasis", [])]
    assert "吾輩" in emphasis


def test_page_break_is_kept():
    parsed = parse_aozora_text(SAMPLE)
    assert any(block["type"] == "page_break" for block in parsed.blocks)


def test_char_count():
    parsed = parse_aozora_text(SAMPLE)
    assert parsed.char_count > 0
    assert len(parsed.text.split("\n\n")) == len(
        [b for b in parsed.blocks if b["type"] == "paragraph"]
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1970（昭和45）年6月15日", 1970),
        ("「新潮」1918（大正7）年3月号", 1918),
        ("「ホトトギス」1905（明治38）年1月", 1905),
        ("令和6年", 2024),
        (None, None),
    ],
)
def test_japanese_year(text, expected):
    assert parse_japanese_year(text) == expected
