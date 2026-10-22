"""PDF rendering for the research corpus.

The renderer is intentionally simple but produces *readable* books:

* an A5 cover page with the bibliographic metadata of the work,
* the body text with Japanese line breaking (kinsoku shori),
* a running header with the work title and a page number footer,
* PDF metadata (title / author / subject / keywords) so that the files can be
  searched in a PDF reader.

The implementation uses `fpdf2 <https://pypi.org/project/fpdf2/>`_ and a
CJK font (see :mod:`asc.fonts`).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fpdf import FPDF

from ..fonts import FONT_LICENSE, FontSet
from ..schema import Work

LOGGER = logging.getLogger(__name__)

#: Characters that must not start a line (Japanese kinsoku shori).
NO_LINE_START = set("、。，．）」』】〕〉》”’ゝゞーァィゥェォッャュョヮヵヶぁぃぅぇぉっゃゅょゎ!?,.:;)]}」』")
#: Characters that must not end a line.
NO_LINE_END = set("（「『【〔〈《“‘([{")


def wrap_text(pdf: FPDF, text: str, width: float) -> List[str]:
    """Wrap ``text`` into lines of at most ``width`` millimetres.

    The function is character based (Japanese text has no spaces) and applies
    the basic kinsoku rules: closing punctuation never starts a line and
    opening punctuation never ends a line.
    """
    if not text:
        return []
    lines: List[str] = []
    current = ""
    current_width = 0.0
    for char in text:
        char_width = pdf.get_string_width(char)
        if current and current_width + char_width > width:
            if char in NO_LINE_START and len(current) > 1:
                # keep the closing punctuation on the current line
                current += char
                lines.append(current)
                current = ""
                current_width = 0.0
                continue
            if current[-1] in NO_LINE_END and len(current) > 1:
                # move the opening punctuation to the next line
                moved = current[-1]
                current = current[:-1]
                lines.append(current)
                current = moved
                current_width = pdf.get_string_width(current)
                current += char
                current_width += char_width
                continue
            lines.append(current)
            current = char
            current_width = char_width
        else:
            current += char
            current_width += char_width
    if current:
        lines.append(current)
    return lines


class _Book(FPDF):
    """FPDF subclass with a running header and a page number footer."""

    header_text: str = ""
    cover: bool = True

    def header(self) -> None:  # pragma: no cover - exercised through rendering
        if self.cover:
            return
        self.set_font("heading", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, self.header_text[:80], align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        y = self.get_y() + 1
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.set_y(y + 3)

    def footer(self) -> None:  # pragma: no cover - exercised through rendering
        self.set_y(-12)
        self.set_font("heading", size=8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 6, f"- {self.page_no() - 1} -", align="C")


class BookPdfRenderer:
    """Render works (Aozora / Narou) into readable PDF files."""

    def __init__(
        self,
        fonts: FontSet,
        page_size: str = "A5",
        font_size: float = 10.5,
        heading_font_size: float = 16.0,
        margin_mm: float = 18.0,
        line_height: float = 1.75,
        show_ruby: bool = False,
    ) -> None:
        self.fonts = fonts
        self.page_size = page_size
        self.font_size = font_size
        self.heading_font_size = heading_font_size
        self.margin_mm = margin_mm
        self.line_height = line_height
        self.show_ruby = show_ruby

    # ------------------------------------------------------------------
    def _new_document(self, work: Work) -> _Book:
        pdf = _Book(orientation="P", unit="mm", format=self.page_size)
        pdf.set_margins(self.margin_mm, self.margin_mm, self.margin_mm)
        pdf.set_auto_page_break(True, margin=self.margin_mm)
        pdf.add_font("body", "", str(self.fonts.body))
        if self.fonts.body_bold:
            pdf.add_font("body", "B", str(self.fonts.body_bold))
        pdf.add_font("heading", "", str(self.fonts.heading))
        pdf.set_title(work.title[:120])
        author = work.primary_author
        pdf.set_author(author.name if author else "")
        pdf.set_subject(work.url)
        pdf.set_creator("AutoStoryCreationAI dataset builder")
        pdf.set_keywords(
            ",".join(
                filter(
                    None,
                    [
                        work.source,
                        work.genre.get("label") if work.genre else None,
                        str(work.published_year or ""),
                        "日本語",
                    ],
                )
            )
        )
        pdf.header_text = work.title
        return pdf

    # ------------------------------------------------------------------
    def _render_cover(self, pdf: _Book, work: Work, note: str = "") -> None:
        pdf.cover = True
        pdf.add_page()
        width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.set_y(pdf.l_margin + 12)

        pdf.set_font("heading", size=self.heading_font_size)
        pdf.multi_cell(width, 9, work.title, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        author = work.primary_author
        if author:
            pdf.set_font("body", size=self.font_size + 1)
            pdf.multi_cell(width, 7, author.name, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(8)

        pdf.set_font("heading", size=9)
        pdf.set_text_color(90, 90, 90)
        rows = self._metadata_rows(work)
        for label, value in rows:
            if not value:
                continue
            pdf.set_font("heading", size=9)
            pdf.cell(26, 5.5, label)
            pdf.set_font("body", size=9.5)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(width - 26, 5.5, value, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
        if note:
            pdf.ln(4)
            pdf.set_font("body", size=8.5)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(width, 5, note, new_x="LMARGIN", new_y="NEXT")
        pdf.cover = False

    @staticmethod
    def _metadata_rows(work: Work) -> List[tuple]:
        genre = work.genre or {}
        parent = genre.get("parent") or {}
        rows = [
            ("データセット", work.source),
            ("URL", work.url),
            ("ジャンル", " / ".join(filter(None, [parent.get("label"), genre.get("label")]))),
            ("初出・掲載", work.published_at or ""),
            ("文字数", f"{work.stats.get('char_count', 0):,}"),
        ]
        if work.stats.get("episodes"):
            rows.append(("話数", str(work.stats["episodes"])))
        license_text = work.license or ""
        if license_text:
            rows.append(("ライセンス", license_text))
        if work.text_path:
            rows.append(("テキスト", work.text_path))
        return rows

    # ------------------------------------------------------------------
    def _render_blocks(self, pdf: _Book, blocks: Sequence[Dict[str, Any]]) -> None:
        width = pdf.w - pdf.l_margin - pdf.r_margin
        line_h = self.font_size * self.line_height * 0.3528  # pt -> mm
        indent = self.font_size * 0.3528
        pdf.set_font("body", size=self.font_size)

        for block in blocks:
            if block.get("type") == "page_break":
                pdf.add_page()
                continue
            text = block.get("text", "")
            if not text:
                continue
            if self.show_ruby and block.get("ruby"):
                text = self._annotate_ruby(text, block["ruby"])
            first = True
            for line in wrap_text(pdf, text, width - indent):
                if pdf.get_y() + line_h > pdf.h - pdf.b_margin:
                    pdf.add_page()
                pdf.set_x(pdf.l_margin + (indent if first else 0))
                self._draw_line(pdf, line, block.get("emphasis") or [], line_h)
                first = False
            pdf.ln(1.5)

    @staticmethod
    def _annotate_ruby(text: str, ruby: Iterable[Dict[str, str]]) -> str:
        for item in ruby:
            base = item.get("base", "")
            reading = item.get("reading", "")
            if base and reading:
                text = text.replace(base, f"{base}（{reading}）", 1)
        return text

    def _draw_line(
        self, pdf: _Book, line: str, emphasis: List[str], line_h: float
    ) -> None:
        """Draw one line and underline the emphasised (bōten) passages."""
        marked = None
        for word in emphasis:
            if word and word in line:
                marked = word
                break
        if marked is None:
            pdf.cell(pdf.w - pdf.l_margin - pdf.r_margin, line_h, line, new_x="LMARGIN", new_y="NEXT")
            return

        before, _, after = line.partition(marked)
        width = pdf.w - pdf.l_margin - pdf.r_margin
        x = pdf.get_x()
        if before:
            pdf.cell(pdf.get_string_width(before), line_h, before, new_x="END")
        marked_width = pdf.get_string_width(marked)
        pdf.cell(marked_width, line_h, marked, new_x="END")
        # underline the emphasised part (bōten)
        pdf.set_draw_color(40, 40, 40)
        pdf.set_line_width(0.15)
        baseline = pdf.get_y() + line_h * 0.78
        pdf.line(x + pdf.get_string_width(before), baseline, x + pdf.get_string_width(before) + marked_width, baseline)
        if after:
            pdf.cell(width, line_h, after, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_x(pdf.l_margin)
            pdf.set_y(pdf.get_y() + line_h)

    # ------------------------------------------------------------------
    def render(
        self,
        work: Work,
        blocks: Sequence[Dict[str, Any]],
        out_path: str | Path,
        note: str = "",
    ) -> Path:
        """Render ``work`` into ``out_path`` and return the path."""
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        pdf = self._new_document(work)
        self._render_cover(pdf, work, note=note)
        pdf.add_page()
        self._render_blocks(pdf, blocks)
        pdf.output(str(target))
        LOGGER.info("wrote %s", target)
        return target
