from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.text.narou_html import parse_chapter, parse_novel_index  # noqa: E402

CHAPTER_HTML = """
<html><body>
<div class="chap_title">一、待てど来ぬ人</div>
<div class="novel_honbun" id="novel_honbun">
<p>ちりりんと澄んだ鈴の音が響く。</p>
<p>カナコは黒いノメリの下駄を白い裸足に突っかけた。</p>
</div>
<div id="footer">フッター</div>
</body></html>
"""

INDEX_HTML = """
<html><body>
<div class="index">
  <div class="chapter_title"><a href="/n3558ml/1/">一、待てど来ぬ人</a></div>
  <div class="chapter_title"><a href="/n3558ml/2/">二、来ぬ人を待つ</a></div>
  <div class="chapter_title"><a href="/n3558ml/10/">十、尾声</a></div>
</div>
</body></html>
"""


def test_chapter_paragraphs():
    chapter = parse_chapter(CHAPTER_HTML, index=1, url="https://ncode.syosetu.com/n3558ml/1/")
    assert chapter.paragraphs == [
        "ちりりんと澄んだ鈴の音が響く。",
        "カナコは黒いノメリの下駄を白い裸足に突っかけた。",
    ]
    assert chapter.char_count > 0
    assert chapter.title == "一、待てど来ぬ人"


def test_footer_is_not_part_of_the_body():
    chapter = parse_chapter(CHAPTER_HTML)
    assert all("フッター" not in p for p in chapter.paragraphs)


def test_index_is_parsed_and_sorted():
    entries = parse_novel_index(INDEX_HTML, "n3558ml")
    assert [entry[0] for entry in entries] == [1, 2, 10]
    assert entries[0][1] == "一、待てど来ぬ人"
    assert entries[0][2].endswith("/n3558ml/1/")
