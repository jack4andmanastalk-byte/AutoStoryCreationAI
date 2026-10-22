from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.fonts import build_font_set  # noqa: E402
from asc.render.pdf import BookPdfRenderer, wrap_text  # noqa: E402
from asc.schema import Author, Work  # noqa: E402

FONT_DIR = Path(__file__).resolve().parents[1] / "data" / "cache" / "fonts"


@pytest.fixture(scope="module")
def renderer() -> BookPdfRenderer:
    try:
        fonts = build_font_set(
            body_font="ZenOldMincho-Regular.ttf",
            heading_font="ZenKakuGothicNew-Bold.ttf",
            body_bold_font=None,
            cache_dir=FONT_DIR,
        )
    except Exception as exc:  # pragma: no cover - offline environments
        pytest.skip(f"Japanese fonts unavailable: {exc}")
    return BookPdfRenderer(fonts=fonts)


def test_wrap_text_respects_the_width(renderer: BookPdfRenderer):
    pdf = renderer._new_document(
        Work(id="x", source="test", title="t", url="https://example.org")
    )
    pdf.set_font("body", size=10.5)
    lines = wrap_text(pdf, "吾輩は猫である。名前はまだ無い。" * 6, 60)
    assert len(lines) > 1
    for line in lines:
        assert pdf.get_string_width(line) <= 60 * 1.02


def test_render_creates_a_pdf(renderer: BookPdfRenderer, tmp_path: Path):
    work = Work(
        id="aozora:000001",
        source="aozora_bunko",
        title="吾輩は猫である",
        url="https://www.aozora.gr.jp/cards/000148/card148.html",
        authors=[Author(name="夏目 漱石", role="author")],
        genre={"taxonomy": "NDC", "code": "913", "label": "日本文学／小説", "parent": {"label": "文学"}},
        published_at="1905-01-01",
        published_year=1905,
        stats={"char_count": 1200},
    )
    blocks = [{"type": "paragraph", "text": "吾輩は猫である。名前はまだ無い。"} for _ in range(20)]
    out = tmp_path / "work.pdf"
    renderer.render(work, blocks, out)
    assert out.exists()
    assert out.stat().st_size > 1000
    assert out.read_bytes()[:4] == b"%PDF"
