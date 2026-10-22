"""Extract readable text from Syosetsuka ni Narou web pages.

Only the standard library is used: :mod:`html.parser` is enough to pull the
``#novel_honbun`` container out of a chapter page.

A chapter page looks like::

    <div class="novel_honbun" id="novel_honbun">
      <p>first paragraph</p>
      <p>second paragraph</p>
    </div>

The website was redesigned in 2025; the current markup is::

    <div class="p-novel__body">
      <div class="js-novel-text p-novel__text">
        <p id="L1">first paragraph</p>
      </div>
    </div>

Both variants are supported.

The parser is intentionally forgiving: if the container cannot be located the
largest text block of the document is used instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

_BLOCK_TAGS = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4"}

#: Classes / ids that mark the container of the novel text.  The first entry
#: is the old layout, the others belong to the current design.
BODY_MARKERS = ("novel_honbun", "js-novel-text", "p-novel__text")

#: Classes that mark the title of an episode.
TITLE_MARKERS = ("chap_title", "p-novel__title")
#: ASCII blanks are collapsed; the ideographic space (U+3000) is kept because
#: it is used as a meaningful separator inside Japanese sentences.
_WS_RE = re.compile(r"[ \t]+")


@dataclass
class Chapter:
    """One episode of a web novel."""

    index: int
    title: Optional[str] = None
    url: Optional[str] = None
    paragraphs: List[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(p) for p in self.paragraphs)

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


class _NarouParser(HTMLParser):
    """Collects the body text of a chapter page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._body_depth = 0
        self._in_body = False
        self._chunks: List[str] = []
        self._pending_break = 0
        self.chapter_title: Optional[str] = None
        self._in_title = False
        self._title_chunks: List[str] = []
        self._seen_body = False

    # -- helpers ------------------------------------------------------
    @staticmethod
    def _has_class(attrs: Dict[str, Optional[str]], name: str) -> bool:
        value = attrs.get("class") or ""
        return name in value.split()

    def _flush_break(self, count: int = 1) -> None:
        if count:
            self._pending_break = max(self._pending_break, count)

    # -- HTMLParser API ------------------------------------------------
    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = dict(attrs_list)
        if not self._in_body:
            if attrs.get("id") == "novel_honbun" or any(
                self._has_class(attrs, marker) for marker in BODY_MARKERS
            ):
                self._in_body = True
                self._body_depth = 1
                self._seen_body = True
                return
            if any(self._has_class(attrs, marker) for marker in TITLE_MARKERS):
                self._in_title = True
                self._title_chunks = []
                return
            if tag in {"h1", "h2"} and self.chapter_title is None:
                self._in_title = True
                self._title_chunks = []
            return

        self._body_depth += 1
        if tag == "br":
            self._flush_break(1)
        elif tag in _BLOCK_TAGS:
            self._flush_break(2)

    def handle_endtag(self, tag: str) -> None:
        if self._in_title and tag in {"div", "h1", "h2", "span", "p"}:
            text = "".join(self._title_chunks).strip()
            if text:
                self.chapter_title = text
            self._in_title = False
            return
        if not self._in_body:
            return
        if tag in _BLOCK_TAGS:
            self._flush_break(2)
        self._body_depth -= 1
        if self._body_depth <= 0:
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_chunks.append(data)
            return
        if not self._in_body:
            return
        if not data.strip():
            if data:
                self._chunks.append(" ")
            return
        if self._pending_break:
            self._chunks.append("\n" * self._pending_break)
            self._pending_break = 0
        self._chunks.append(data)

    # -- result --------------------------------------------------------
    def paragraphs(self) -> List[str]:
        raw = "".join(self._chunks)
        raw = unescape(raw).replace("\r\n", "\n").replace("\r", "\n")
        paragraphs: List[str] = []
        for chunk in raw.split("\n"):
            line = _WS_RE.sub(" ", chunk).strip()
            if line:
                paragraphs.append(line)
        return paragraphs


def parse_chapter(html: str, index: int = 1, url: Optional[str] = None) -> Chapter:
    """Extract ``(title, paragraphs)`` from a chapter page."""
    parser = _NarouParser()
    parser.feed(html)
    parser.close()
    paragraphs = parser.paragraphs()
    return Chapter(index=index, title=parser.chapter_title, url=url, paragraphs=paragraphs)


class _IndexParser(HTMLParser):
    """Collects the episode list of a novel index page."""

    def __init__(self, ncode: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ncode = ncode.lower()
        self.entries: List[Tuple[int, str, str]] = []  # (index, title, url)
        self._href: Optional[str] = None
        self._chunks: List[str] = []
        self._in_entry = False

    def handle_starttag(self, tag: str, attrs_list) -> None:
        if tag != "a":
            return
        attrs = dict(attrs_list)
        href = attrs.get("href") or ""
        match = re.search(rf"/{re.escape(self.ncode)}/(\d+)/?", href)
        if not match:
            return
        self._in_entry = True
        self._chunks = []
        self._href = f"https://ncode.syosetu.com/{self.ncode}/{match.group(1)}/"

    def handle_data(self, data: str) -> None:
        if self._in_entry:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_entry:
            title = "".join(self._chunks).strip()
            index = int(re.search(r"/(\d+)/?$", self._href or "").group(1))
            self.entries.append((index, title, self._href or ""))
            self._in_entry = False
            self._chunks = []
            self._href = None


def parse_novel_index(html: str, ncode: str) -> List[Tuple[int, str, str]]:
    """Return ``[(index, title, url), ...]`` for a novel index page."""
    parser = _IndexParser(ncode)
    parser.feed(html)
    parser.close()
    seen = {}
    for index, title, url in parser.entries:
        seen.setdefault(index, (index, title, url))
    return [seen[key] for key in sorted(seen)]
