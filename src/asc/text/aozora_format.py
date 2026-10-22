"""Parser for the Aozora Bunko plain text format.

Aozora distributes every work as a ZIP containing a ``.txt`` file written in
the *Aozora Bunko notation*:

* the first lines are the header (title / author / translator),
* a legend block delimited by ``-----`` lines explains the special characters,
* ruby is written as ``｜base《reading》``,
* editorial annotations are written as ``［＃...］`` (e.g. ``［＃改ページ］``,
  ``［＃「吾輩」に傍点］``).

The parser turns such a file into a list of blocks that can be rendered or fed
to a language model:

``{"type": "paragraph", "text": str, "ruby": [...], "emphasis": [...]}``
``{"type": "page_break"}``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SEPARATOR_RE = re.compile(r"^-{10,}\s*$")
ANNOTATION_RE = re.compile(r"［＃(.*?)］")
RUBY_RE = re.compile(r"｜([^《\n]{1,40})《([^》\n]{1,60})》")
LOOSE_RUBY_RE = re.compile(r"《([^》\n]{1,60})》")
EMPHASIS_RE = re.compile(r"「(.+?)」に傍点")
PAGE_BREAK_TOKENS = ("改ページ",)
IGNORE_ANNOTATIONS = (
    "改丁",
    "字下げ",
    "地の文",
    "ルビ",
    "外字",
    "圏点",
    "改行",
    "見出し",
    "中見出し",
    "小見出し",
)


@dataclass
class ParsedAozora:
    """Result of parsing an Aozora Bunko text file."""

    title: Optional[str] = None
    author: Optional[str] = None
    translator: Optional[str] = None
    blocks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Plain text reconstruction (paragraphs separated by a blank line)."""
        chunks: List[str] = []
        for block in self.blocks:
            if block["type"] == "paragraph":
                chunks.append(block["text"])
        return "\n\n".join(chunks)

    @property
    def char_count(self) -> int:
        return len("".join(b["text"] for b in self.blocks if b["type"] == "paragraph"))


def _strip_legend(lines: List[str]) -> Tuple[List[str], List[str]]:
    """Split the file into ``(header_lines, body_lines)``."""
    header: List[str] = []
    body: List[str] = []
    index = 0
    seen_separator = False
    for index, line in enumerate(lines):
        if not seen_separator:
            if SEPARATOR_RE.match(line.strip()):
                seen_separator = True
                # skip the legend block: it ends with the next separator line
                continue
            header.append(line)
            continue
        # inside the body: skip the legend block (ends at the 2nd separator)
        if SEPARATOR_RE.match(line.strip()):
            body = lines[index + 1 :]
            break
    else:
        body = lines[len(header) :]
    return header, body


def _clean_header(header: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    names = [line.strip() for line in header if line.strip()]
    if not names:
        return None, None, None
    title = names[0]
    author = names[1] if len(names) > 1 else None
    translator = names[2] if len(names) > 2 else None
    return title, author, translator


def _apply_annotations(line: str) -> Tuple[str, List[str], List[str], bool]:
    """Remove annotations, returning ``(text, ruby, emphasis, page_break)``."""
    ruby: List[Tuple[str, str]] = []
    emphasis: List[str] = []
    page_break = False

    def _ruby_sub(match: re.Match[str]) -> str:
        base, reading = match.group(1), match.group(2)
        ruby.append((base, reading))
        return base

    line = RUBY_RE.sub(_ruby_sub, line)

    def _annotation_sub(match: re.Match[str]) -> str:
        nonlocal page_break
        payload = match.group(1)
        if any(token in payload for token in PAGE_BREAK_TOKENS):
            page_break = True
            return ""
        found = EMPHASIS_RE.search(payload)
        if found:
            emphasis.append(found.group(1))
        return ""

    line = ANNOTATION_RE.sub(_annotation_sub, line)

    # loose ruby (no ｜ marker) - keep the base text, drop the reading
    line = LOOSE_RUBY_RE.sub(r"\1", line)
    return line, ruby, emphasis, page_break


def parse_aozora_text(raw: str) -> ParsedAozora:
    """Parse the content of an Aozora Bunko ``.txt`` file."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = text.split("\n")
    header, body = _strip_legend(lines)
    title, author, translator = _clean_header(header)

    blocks: List[Dict[str, Any]] = []
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        cleaned, ruby, emphasis, page_break = _apply_annotations(stripped)
        cleaned = cleaned.strip()
        if page_break:
            blocks.append({"type": "page_break"})
        if cleaned:
            blocks.append(
                {
                    "type": "paragraph",
                    "text": cleaned,
                    "ruby": [{"base": b, "reading": r} for b, r in ruby],
                    "emphasis": emphasis,
                }
            )
    return ParsedAozora(
        title=title, author=author, translator=translator, blocks=blocks
    )


def parse_aozora_file(path: str) -> ParsedAozora:
    """Parse an Aozora Bunko text file (Shift_JIS or UTF-8)."""
    with open(path, "rb") as fh:
        payload = fh.read()
    for encoding in ("utf-8", "cp932", "shift_jis", "euc_jp"):
        try:
            return parse_aozora_text(payload.decode(encoding))
        except UnicodeDecodeError:
            continue
    return parse_aozora_text(payload.decode("utf-8", errors="replace"))
