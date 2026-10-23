#!/usr/bin/env python3
"""Build the research datasets of AutoStoryCreationAI.

The script has one sub-command per step so that the (potentially long)
downloads can be resumed and inspected individually:

``aozora-metadata``     bibliographic records of the Aozora Bunko works
``aozora-texts``        plain texts (+ PDFs) for a sample of Aozora works
``narou-metadata``      bibliographic records of Syosetsuka ni Narou novels
``narou-rank``          verify commercialisation & rank top Narou works
``narou-texts``         plain texts (+ PDFs) for Narou novels (supports sharding)
``narou-merge-shards``  merge sharded ``narou-texts`` outputs into final catalog
``report``              statistics about the generated JSONL files
``all``                 every step above, in order

Example::

    python scripts/setup_dataset.py aozora-metadata
    python scripts/setup_dataset.py aozora-texts --works 50 --pdf
    python scripts/setup_dataset.py narou-metadata
    python scripts/setup_dataset.py narou-rank --top 100
    python scripts/setup_dataset.py narou-texts --works 100 --max-episodes 0 --pdf --rank-order
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.config import Config, load_config  # noqa: E402
from asc.fonts import build_font_set  # noqa: E402
from asc.http import HttpClient  # noqa: E402
from asc.jsonl import read_jsonl, write_jsonl  # noqa: E402
from asc.render.pdf import BookPdfRenderer  # noqa: E402
from asc.schema import Work  # noqa: E402
from asc.sources.aozora import (  # noqa: E402
    AozoraSource,
    enrich_ndc_genre,
    load_ndc_map,
    sample_works,
)
from asc.sources.media_verify import MediaVerificationResult  # noqa: E402
from asc.sources.narou import (  # noqa: E402
    NarouSource,
    compute_popularity_ranking_score,
)
from asc.text.aozora_format import parse_aozora_text  # noqa: E402

LOGGER = logging.getLogger("setup_dataset")

AOZORA_WORKS = "aozora_works.jsonl"
AOZORA_AUTHORS = "aozora_authors.jsonl"
NAROU_WORKS = "narou_novels.jsonl"
NAROU_RANKED = "narou_commercialized_ranked.jsonl"
NAROU_RANKING_MD = "narou_commercialized_ranking.md"
NAROU_TOP100 = "narou_commercialized_top100.jsonl"
NAROU_TOP100_MD = "narou_top100_ranking.md"
NAROU_RANK101_PLUS = "narou_commercialized_rank101_200.jsonl"
NAROU_RANK101_PLUS_MD = "narou_rank101_200_ranking.md"
NAROU_GENRE_SUPP = "narou_commercialized_genre_supplement.jsonl"
NAROU_GENRE_SUPP_MD = "narou_genre_supplement_ranking.md"
NAROU_ALL_COMM = "narou_commercialized_all.jsonl"
MANIFEST = "manifest.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def build_client(cfg: Config, request_interval: Optional[float] = None) -> HttpClient:
    http = cfg.http
    return HttpClient(
        user_agent=http.user_agent,
        timeout=http.timeout_seconds,
        max_retries=http.max_retries,
        backoff=http.backoff_seconds,
        request_interval=(
            request_interval if request_interval is not None else http.request_interval_seconds
        ),
        cache_dir=http.cache_dir,
        cache_ttl_seconds=http.cache_ttl_seconds,
    )


def build_renderer(cfg: Config) -> BookPdfRenderer:
    fonts = build_font_set(
        body_font=cfg.pdf.body_font,
        heading_font=cfg.pdf.heading_font,
        body_bold_font=cfg.pdf.body_bold_font,
        cache_dir=cfg.paths.font_dir,
        source=cfg.pdf.font_source,
    )
    return BookPdfRenderer(
        fonts=fonts,
        page_size=cfg.pdf.page_size,
        font_size=cfg.pdf.font_size,
        heading_font_size=cfg.pdf.heading_font_size,
        margin_mm=cfg.pdf.margin_mm,
        line_height=cfg.pdf.line_height,
    )


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def write_manifest(cfg: Config, entries: Dict[str, Any]) -> None:
    manifest_path = cfg.paths.dataset_dir / MANIFEST
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            manifest = {}
    manifest.setdefault("generated_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    manifest["steps"] = manifest.get("steps", {})
    manifest["steps"].update(entries)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_works(path: Path) -> List[Work]:
    return [Work.from_json(row) for row in read_jsonl(path)]


def store_works(path: Path, works: Iterable[Work]) -> int:
    return write_jsonl(path, [work.to_json() for work in works])


_SENTENCE_END_CHARS = frozenset("。！？!?）」』】〉》〕…―ー〜~・:：;；")


def extract_clean_text_from_pdf(pdf_path: Path) -> str:
    """Extract clean, paragraph-joined UTF-8 plain text from a rendered novel PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = reader.pages[1:] if len(reader.pages) > 1 else reader.pages

    raw_lines: List[str] = []
    for page in pages:
        page_txt = page.extract_text() or ""
        plines = [ln.rstrip() for ln in page_txt.splitlines()]
        # Drop trailing standalone page number footer (e.g. "12" or "- 12 -")
        while plines and not plines[-1].strip():
            plines.pop()
        if plines and re.fullmatch(r"[-—–\s]*\d+[-—–\s]*", plines[-1].strip()):
            plines.pop()
        # Drop running header on top line when separated or formatted like a header
        while plines and not plines[0].strip():
            plines.pop(0)
        raw_lines.extend(plines)
        raw_lines.append("")

    paragraphs: List[str] = []
    buf = ""
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                paragraphs.append(buf)
                buf = ""
            continue
        is_new_para = line.startswith(("　", "「", "『", "（", "【", "第", "■", "◆", "●", "◇"))
        if not buf:
            buf = line.lstrip() if not line.startswith("　") else line
        elif is_new_para or buf[-1] in _SENTENCE_END_CHARS:
            paragraphs.append(buf)
            buf = line.lstrip() if not line.startswith("　") else line
        else:
            buf += stripped
    if buf:
        paragraphs.append(buf)
    return "\n\n".join(paragraphs).strip()


def _format_byte_cell(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "-"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f}MB"
    return f"{max(1, round(num_bytes / 1024))}KB"


def render_narou_ranking_markdown(
    works: Sequence[Work],
    *,
    heading: Optional[str] = None,
    show_category: bool = False,
) -> str:
    """Format a Markdown summary table of externally verified commercialised Narou works."""
    total_eps = sum(int((w.stats or {}).get("episodes") or 0) for w in works)
    total_chars = sum(int((w.stats or {}).get("char_count") or 0) for w in works)
    total_pdf_bytes = sum(int((w.extra or {}).get("pdf_bytes") or 0) for w in works)
    total_txt_bytes = sum(int((w.extra or {}).get("text_bytes") or 0) for w in works)
    pdf_count = sum(1 for w in works if w.pdf_path)
    txt_count = sum(1 for w in works if w.text_path)
    text_only_mode = pdf_count == 0
    r15_count = sum(1 for w in works if "R15" in ((w.stats or {}).get("elements") or []))
    book_cnt = sum(1 for w in works if ((w.extra or {}).get("ranking") or {}).get("is_book"))
    manga_cnt = sum(1 for w in works if ((w.extra or {}).get("ranking") or {}).get("is_comic"))
    anime_cnt = sum(1 for w in works if ((w.extra or {}).get("ranking") or {}).get("is_anime"))
    game_cnt = sum(1 for w in works if ((w.extra or {}).get("ranking") or {}).get("is_game"))

    if not heading:
        if works:
            r_first = ((works[0].extra or {}).get("ranking") or {}).get("rank") or 1
            r_last = ((works[-1].extra or {}).get("ranking") or {}).get("rank") or len(works)
            heading = (
                f"# 小説家になろう 外部実在確認済・商業化作品 人気・評価・知名度ランキング（第{r_first}位〜第{r_last}位）"
            )
        else:
            heading = "# 小説家になろう 外部実在確認済・商業化作品 ランキング"

    storage_summary = (
        f"プレーンテキスト収録済: {txt_count} 作品・全話収録 / 話数制限なし・PDF廃止済"
        if text_only_mode
        else f"PDF 生成済: {pdf_count} 作品・全話収録 / 話数制限なし"
    )
    lines = [
        heading,
        "",
        "自己申告キーワードのみに依存せず、**CiNii Books 書誌・ISBN 検索（書籍・マンガ）**・**日本語版 Wikipedia 作品・メディアミックス検証（書籍・マンガ・アニメ・ゲーム）**・**Apple Books Japan 商業配信書誌検索（書籍・マンガ）**・公式アニメ一覧等を実際に検索し、商業化が外部データベースで実在確認された作品のみを抽出したカタログです（一般向け `novelapi` の **`R15` フラグ付与作品を含む**／18禁ノクターン等は除外）。",
        "",
        f"- **収録作品数**: {len(works)} 作品（{storage_summary}）",
        f"- **R15 フラグ付与作品数**: {r15_count} 作品（全体の {r15_count * 100.0 / max(len(works), 1):.1f}%）",
        f"- **外部確認メディア内訳**: 書籍 {book_cnt} / マンガ {manga_cnt} / アニメ {anime_cnt} / ゲーム {game_cnt}",
        f"- **総エピソード数**: {total_eps:,} 話",
        f"- **総文字数**: {total_chars:,} 文字",
    ]
    if show_category:
        cat_counts: Dict[str, int] = {}
        for w in works:
            cat = str((w.extra or {}).get("supplement_category") or "-")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        cat_str = " / ".join(f"{k} {v}作品" for k, v in cat_counts.items())
        if cat_str:
            lines.append(f"- **対象5ジャンル別収録数**: {cat_str}")
    if total_txt_bytes:
        lines.append(f"- **総プレーンテキストサイズ（UTF-8）**: {total_txt_bytes / (1024 * 1024):.2f} MB")
    if total_pdf_bytes and not text_only_mode:
        lines.append(f"- **総PDFサイズ**: {total_pdf_bytes / (1024 * 1024):.2f} MB")

    size_col_header = "本文TXT" if text_only_mode else "PDF"
    if show_category:
        lines.extend(
            [
                "",
                f"| 区分 | 区分内順位 | Nコード | タイトル | 作者 | 公式ジャンル | R15 | 総合評価pt | ブックマーク | 確認メディア | 商業刊行・ISBN | 話数 | 文字数 | {size_col_header} |",
                "|---|---:|---|---|---|---|---|---:|---:|---|---|---:|---:|---:|",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"| 順位 | Nコード | タイトル | 作者 | ジャンル | R15 | 総合評価pt | ブックマーク | 確認メディア | 商業刊行・ISBN | 話数 | 文字数 | {size_col_header} |",
                "|---:|---|---|---|---|---|---:|---:|---|---|---:|---:|---:|",
            ]
        )

    for idx, work in enumerate(works, start=1):
        ranking = (work.extra or {}).get("ranking") or {}
        rank = ranking.get("rank") or idx
        ncode = work.id.split(":", 1)[1]
        author = work.authors[0].name if work.authors else ""
        genre_label = (work.genre or {}).get("label") or ""
        is_r15 = "R15" if "R15" in ((work.stats or {}).get("elements") or []) else "-"
        gp = int((work.stats or {}).get("global_point") or 0)
        fav = int((work.stats or {}).get("fav_novel_cnt") or 0)
        eps = int((work.stats or {}).get("episodes") or 0)
        chars = int((work.stats or {}).get("char_count") or 0)

        media_badges: List[str] = []
        if ranking.get("is_book"):
            media_badges.append("書籍")
        if ranking.get("is_comic"):
            media_badges.append("漫画")
        if ranking.get("is_anime"):
            media_badges.append("アニメ")
        if ranking.get("is_game"):
            media_badges.append("ゲーム")
        media_str = "・".join(media_badges) if media_badges else "書籍"

        pub_parts: List[str] = []
        if ranking.get("label") or ranking.get("publisher"):
            pub_parts.append(str(ranking.get("label") or ranking.get("publisher")))
        if ranking.get("isbn_sample"):
            pub_parts.append(f"`{ranking['isbn_sample']}`")
        vols = int(ranking.get("estimated_volumes") or 0)
        if vols > 1:
            pub_parts.append(f"{vols}巻+")
        pub_str = " / ".join(pub_parts) if pub_parts else "-"

        if text_only_mode:
            txt_bytes = int((work.extra or {}).get("text_bytes") or 0)
            size_cell = _format_byte_cell(txt_bytes) if txt_bytes else ("済" if work.text_path else "-")
        else:
            pdf_bytes = int((work.extra or {}).get("pdf_bytes") or 0)
            size_cell = (
                f"{pdf_bytes / (1024 * 1024):.1f}MB"
                if pdf_bytes
                else ("済" if work.pdf_path else "-")
            )
        safe_title = work.title.replace("|", "｜")
        safe_author = author.replace("|", "｜")
        safe_pub = pub_str.replace("|", "｜")
        if show_category:
            cat = str((work.extra or {}).get("supplement_category") or "-")
            grank = int((work.extra or {}).get("genre_rank") or idx)
            lines.append(
                f"| **{cat}** | {grank} | `{ncode}` | {safe_title} | {safe_author} | {genre_label} | {is_r15} | "
                f"{gp:,} | {fav:,} | {media_str} | {safe_pub} | {eps:,} | {chars:,} | {size_cell} |"
            )
        else:
            lines.append(
                f"| {rank} | `{ncode}` | {safe_title} | {safe_author} | {genre_label} | {is_r15} | "
                f"{gp:,} | {fav:,} | {media_str} | {safe_pub} | {eps:,} | {chars:,} | {size_cell} |"
            )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Aozora
# ---------------------------------------------------------------------------
def cmd_aozora_metadata(cfg: Config, args: argparse.Namespace) -> None:
    source = AozoraSource(cfg.aozora, cfg.paths, build_client(cfg))
    card = source.fetch_card_list()

    ndc_map = load_ndc_map(cfg.paths.cache_dir / "ndc_class_all.json")
    for candidate in sorted(cfg.paths.cache_dir.glob("aozora_pages/**/ndc_class_all.json")):
        ndc_map.update(load_ndc_map(candidate))
        break

    for work in card.works:
        enrich_ndc_genre(work, ndc_map)
        work.extra["metadata_origin"] = card.origin

    if args.limit:
        card.works = card.works[: args.limit]

    works_path = cfg.paths.dataset_dir / AOZORA_WORKS
    authors_path = cfg.paths.dataset_dir / AOZORA_AUTHORS
    store_works(works_path, card.works)
    write_jsonl(
        authors_path,
        [author.to_json() for author in sorted(card.authors.values(), key=lambda a: a.id)],
    )
    LOGGER.info("wrote %s works and %s authors", len(card.works), len(card.authors))
    write_manifest(
        cfg,
        {
            "aozora_metadata": {
                "origin": card.origin,
                "works": len(card.works),
                "authors": len(card.authors),
                "file": relative(works_path),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


def cmd_aozora_texts(cfg: Config, args: argparse.Namespace) -> None:
    works_path = cfg.paths.dataset_dir / AOZORA_WORKS
    if not works_path.exists():
        raise SystemExit(f"{works_path} not found - run 'aozora-metadata' first")
    works = load_works(works_path)
    source = AozoraSource(cfg.aozora, cfg.paths, build_client(cfg))
    source.ensure_text_mirror()
    index = source.text_index()
    if not index:
        LOGGER.warning("no mirrored texts found - the official archives will be used")

    target = args.works or cfg.aozora.sample_works
    pool_size = max(target * 2, target + 25)
    chosen = sample_works(
        works,
        count=pool_size,
        seed=cfg.aozora.sample_seed,
        min_chars=cfg.aozora.min_chars,
    )
    LOGGER.info("sampling up to %s public-domain works (pool %s)", target, len(chosen))

    renderer = build_renderer(cfg) if args.pdf else None
    raw_dir = cfg.paths.raw_dir / "aozora" / "texts"
    pdf_dir = cfg.paths.pdf_dir / "aozora"

    updated: List[Work] = []
    for work in chosen:
        if len(updated) >= target:
            break
        raw = source.fetch_text(work, index=index)
        if not raw:
            LOGGER.warning("no text for %s (%s)", work.id, work.title)
            continue
        parsed = parse_aozora_text(raw)
        text_path = raw_dir / f"{work.id.split(':', 1)[1]}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(parsed.text, encoding="utf-8")

        work.text_path = relative(text_path)
        work.stats["char_count"] = parsed.char_count
        work.stats["paragraph_count"] = len(parsed.blocks)
        ruby_count = sum(len(block.get("ruby", [])) for block in parsed.blocks)
        if ruby_count:
            work.stats["ruby_count"] = ruby_count
        if renderer is not None:
            pdf_path = pdf_dir / f"{work.id.split(':', 1)[1]}.pdf"
            blocks = [
                {
                    "type": "paragraph",
                    "text": b["text"],
                    "ruby": b.get("ruby", []),
                    "emphasis": b.get("emphasis", []),
                }
                for b in parsed.blocks
                if b["type"] == "paragraph"
            ]
            renderer.render(
                work,
                blocks,
                pdf_path,
                note="出典: 青空文庫 (aozora.gr.jp) — 作品著作権フラグ「なし」の作品のみ収録",
            )
            work.pdf_path = relative(pdf_path)
        updated.append(work)
        LOGGER.info("[%s/%s] %s", len(updated), target, work.title)

    merged = {work.id: work for work in works}
    for work in updated:
        merged[work.id] = work
    store_works(works_path, merged.values())
    write_manifest(
        cfg,
        {
            "aozora_texts": {
                "works": len(updated),
                "texts_dir": relative(raw_dir),
                "pdf_dir": relative(pdf_dir) if args.pdf else None,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


# ---------------------------------------------------------------------------
# Narou
# ---------------------------------------------------------------------------
def cmd_narou_metadata(cfg: Config, args: argparse.Namespace) -> None:
    source = NarouSource(cfg.narou, cfg.paths, build_client(cfg))
    works = source.harvest(cached_only=getattr(args, "cached_only", False))
    if args.limit:
        works = works[: args.limit]
    works.sort(
        key=lambda w: (
            w.stats.get("global_point") or 0,
            w.stats.get("fav_novel_cnt") or 0,
            w.published_year or 0,
            w.id,
        ),
        reverse=True,
    )
    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    store_works(works_path, works)
    LOGGER.info("wrote %s novels", len(works))
    write_manifest(
        cfg,
        {
            "narou_metadata": {
                "works": len(works),
                "file": relative(works_path),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


def _write_ranked_catalogs(
    cfg: Config,
    works: Sequence[Work],
    out_path: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """Write full ranked JSONL/Markdown plus Top-100 and 100-work continuation slices."""
    primary_jsonl = out_path or (cfg.paths.dataset_dir / NAROU_RANKED)
    store_works(primary_jsonl, works)

    md_path = cfg.paths.dataset_dir / NAROU_RANKING_MD
    md_path.write_text(render_narou_ranking_markdown(works), encoding="utf-8")

    top100 = list(works[:100])
    if top100:
        store_works(cfg.paths.dataset_dir / NAROU_TOP100, top100)
        (cfg.paths.dataset_dir / NAROU_TOP100_MD).write_text(
            render_narou_ranking_markdown(
                top100,
                heading="# 小説家になろう 外部実在確認済・商業化作品 人気・評価・知名度ランキング Top 100（第1位〜第100位）",
            ),
            encoding="utf-8",
        )

    # Clean up any spare-pool slice files beyond len(works) (e.g. 301_400 from prepare)
    for stale in cfg.paths.dataset_dir.glob("narou_commercialized_rank[0-9]*.jsonl"):
        stale.unlink(missing_ok=True)
    for stale in cfg.paths.dataset_dir.glob("narou_rank[0-9]*_ranking.md"):
        stale.unlink(missing_ok=True)

    for start_idx in range(100, len(works), 100):
        bracket = list(works[start_idx : start_idx + 100])
        if not bracket:
            continue
        start_rank = start_idx + 1
        end_label = start_idx + 100
        actual_last = (
            ((bracket[-1].extra or {}).get("ranking") or {}).get("rank")
            or (start_idx + len(bracket))
        )
        slice_jsonl = cfg.paths.dataset_dir / f"narou_commercialized_rank{start_rank}_{end_label}.jsonl"
        slice_md = cfg.paths.dataset_dir / f"narou_rank{start_rank}_{end_label}_ranking.md"
        store_works(slice_jsonl, bracket)
        slice_md.write_text(
            render_narou_ranking_markdown(
                bracket,
                heading=(
                    f"# 小説家になろう 外部実在確認済・商業化作品 人気・評価・知名度ランキング "
                    f"第{start_rank}位〜第{actual_last}位"
                ),
            ),
            encoding="utf-8",
        )
    return primary_jsonl, md_path


def _load_reuse_maps(
    reuse_dir: Optional[Path],
) -> Tuple[Dict[str, Path], Dict[str, Path], Dict[str, Work]]:
    """Index existing full-episode PDFs, texts, and metadata for incremental continuation."""
    pdfs: Dict[str, Path] = {}
    txts: Dict[str, Path] = {}
    prev_works: Dict[str, Work] = {}
    if not reuse_dir or not reuse_dir.exists():
        return pdfs, txts, prev_works

    for sub in ("pdf/narou", "data/pdf/narou", "narou", "."):
        pdir = reuse_dir / sub
        if pdir.is_dir():
            for p in pdir.glob("*.pdf"):
                if p.stat().st_size > 2048:
                    pdfs.setdefault(p.stem.lower(), p)

    for sub in ("raw/narou/texts", "data/raw/narou/texts", "texts", "."):
        tdir = reuse_dir / sub
        if tdir.is_dir():
            for p in tdir.glob("*.txt"):
                if p.stat().st_size > 256:
                    txts.setdefault(p.stem.lower(), p)

    candidate_jsonls = [
        reuse_dir / "datasets" / "narou_commercialized_all.jsonl",
        reuse_dir / "datasets" / "narou_commercialized_ranked.jsonl",
        reuse_dir / "datasets" / "narou_commercialized_genre_supplement.jsonl",
        reuse_dir / "datasets" / "narou_commercialized_top100.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_all.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_ranked.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_genre_supplement.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_top100.jsonl",
        reuse_dir / "narou_commercialized_ranked.jsonl",
        REPO_ROOT / "samples" / "narou_commercialized_ranked.jsonl",
        REPO_ROOT / "samples" / "narou_commercialized_genre_supplement.jsonl",
    ]
    for jpath in candidate_jsonls:
        if jpath.is_file():
            for w in load_works(jpath):
                prev_works.setdefault(w.id.lower(), w)
    for shard_jpath in sorted(reuse_dir.glob("**/narou_shard_*.jsonl")):
        if shard_jpath.is_file():
            for w in load_works(shard_jpath):
                prev_works.setdefault(w.id.lower(), w)

    return pdfs, txts, prev_works


def _try_reuse_cached_work(
    work: Work,
    *,
    reuse_pdfs: Dict[str, Path],
    reuse_txts: Dict[str, Path],
    reuse_prev: Dict[str, Work],
    raw_dir: Path,
    pdf_dir: Path,
    renderer: Optional[BookPdfRenderer],
    cover_note: str,
) -> bool:
    """Reuse a previously downloaded full-episode plain text (or legacy PDF)."""
    ncode = work.id.split(":", 1)[1]
    ncode_lower = ncode.lower()
    src_txt = reuse_txts.get(ncode_lower)
    src_pdf = reuse_pdfs.get(ncode_lower)
    if src_txt is None and src_pdf is None:
        return False
    if renderer is not None and src_pdf is None:
        return False

    prev_w = reuse_prev.get(work.id.lower())
    prev_eps = int((prev_w.stats if prev_w else {}).get("episodes") or 0)
    prev_chars = int((prev_w.stats if prev_w else {}).get("char_count") or 0)
    expected_eps = int(work.stats.get("episodes") or 0)
    expected_chars = int(work.stats.get("char_count") or 0)

    txt_content: Optional[str] = None
    if src_txt is not None and src_txt.exists():
        txt_content = src_txt.read_text(encoding="utf-8")
        episodes_fresh = (
            (prev_eps > 0 and expected_eps <= prev_eps + 3)
            or (prev_eps == 0 and len(txt_content) >= max(1000, int(expected_chars * 0.70)))
        )
    else:
        episodes_fresh = prev_eps > 0 and expected_eps <= prev_eps + 3

    if not episodes_fresh:
        return False

    text_path = raw_dir / f"{ncode}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    if src_txt is not None and src_txt.exists():
        if src_txt.resolve() != text_path.resolve():
            shutil.copy2(src_txt, text_path)
    elif not text_path.exists() and src_pdf is not None:
        extracted = extract_clean_text_from_pdf(src_pdf)
        text_path.write_text(extracted or work.title, encoding="utf-8")
        txt_content = extracted

    work.text_path = relative(text_path)
    work.extra["text_bytes"] = text_path.stat().st_size
    work.stats["char_count"] = prev_chars or (
        sum(len(ln) for ln in (txt_content or "").splitlines() if ln.strip()) or expected_chars
    )
    work.stats["episodes"] = prev_eps or expected_eps
    work.extra["text_origin"] = "reused full-episode cache"
    work.extra["all_episodes_rendered"] = True

    if renderer is not None and src_pdf is not None:
        pdf_path = pdf_dir / f"{ncode}.pdf"
        try:
            renderer.refresh_cover(work, src_pdf, pdf_path, note=cover_note)
        except Exception as exc:
            LOGGER.warning("cover refresh fallback copy for %s: %s", ncode, exc)
            if src_pdf.resolve() != pdf_path.resolve():
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_pdf, pdf_path)
        work.pdf_path = relative(pdf_path)
        work.extra["pdf_bytes"] = pdf_path.stat().st_size
    else:
        work.pdf_path = None
        work.extra.pop("pdf_bytes", None)
    return True


def cmd_narou_rank(cfg: Config, args: argparse.Namespace) -> None:
    """Verify commercialisation via external book/manga/anime/game catalogs & rank works."""
    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    if not works_path.exists():
        raise SystemExit(f"{works_path} not found - run 'narou-metadata' first")
    works = load_works(works_path)
    interval = getattr(args, "request_interval", None) or 0.20
    source = NarouSource(cfg.narou, cfg.paths, build_client(cfg, request_interval=interval))

    anime_ncodes = source.fetch_anime_ncodes()
    candidates = [
        w
        for w in works
        if (w.stats.get("char_count") or 0) >= max(cfg.narou.min_chars, args.min_chars)
        and (w.stats.get("episodes") or 0) >= args.min_episodes
        and (w.genre or {}).get("code") not in (9902, 9903, 9904, 9999)
        and (cfg.narou.include_r15 or "R15" not in (w.stats.get("elements") or []))
    ]
    candidates.sort(
        key=lambda w: (
            w.stats.get("global_point") or 0,
            w.stats.get("fav_novel_cnt") or 0,
            w.stats.get("all_point") or 0,
        ),
        reverse=True,
    )

    top_target = args.top
    scan_limit = max(args.scan_limit, top_target * 3 + 150)
    strict_flag = (
        cfg.narou.strict_external_verification
        if getattr(args, "strict_external", None) is None
        else bool(args.strict_external)
    )

    reuse_dir = Path(args.reuse_existing_dir) if getattr(args, "reuse_existing_dir", None) else None
    reuse_pdfs, reuse_txts, reuse_prev = _load_reuse_maps(reuse_dir)

    seed_verifications: Dict[str, MediaVerificationResult] = {}
    seed_sources: List[Work] = list(reuse_prev.values())
    repo_sample_ranked = REPO_ROOT / "samples" / NAROU_RANKED
    if repo_sample_ranked.is_file() and not getattr(args, "no_seed_verified", False):
        seed_sources.extend(load_works(repo_sample_ranked))
    for sw in seed_sources:
        ext_dict = (sw.rights or {}).get("external_verification")
        if isinstance(ext_dict, dict) and ext_dict.get("verified"):
            ncode_key = sw.id.split(":", 1)[1].lower()
            seed_verifications.setdefault(ncode_key, MediaVerificationResult.from_dict(ext_dict))

    LOGGER.info(
        "externally verifying commercialisation (books/manga/anime/games, R15=%s, strict=%s, seeded=%s) "
        "across up to %s top Narou candidates (target=%s)",
        cfg.narou.include_r15,
        strict_flag,
        len(seed_verifications),
        min(scan_limit, len(candidates)),
        top_target,
    )

    verified = source.verify_candidates_external(
        candidates[:scan_limit],
        anime_ncodes=anime_ncodes,
        strict=strict_flag,
        check_syuppan=getattr(args, "check_syuppan", False),
        seed_verifications=seed_verifications,
        target_verified_pool=top_target + 35,
        min_scan_before_stop=max(700, top_target * 2 + 50),
    )

    verified.sort(
        key=lambda w: (
            (w.extra.get("ranking") or {}).get("ranking_score") or 0,
            w.stats.get("global_point") or 0,
            w.stats.get("fav_novel_cnt") or 0,
            w.stats.get("all_point") or 0,
        ),
        reverse=True,
    )

    selected: List[Work] = []
    for work in verified:
        if len(selected) >= top_target:
            break
        ncode_lower = work.id.split(":", 1)[1].lower()
        already_downloaded = ncode_lower in reuse_pdfs or ncode_lower in reuse_txts
        if args.verify_web and not already_downloaded and not source.verify_web_text_available(work):
            LOGGER.warning("skipping %s (%s) - WEB episodes unavailable/stubbed", work.id, work.title)
            continue
        rank_num = len(selected) + 1
        work.extra.setdefault("ranking", {})["rank"] = rank_num
        selected.append(work)
        LOGGER.info(
            "Rank #%s: %s (%s) | R15=%s | media=%s | score=%s | gp=%s | eps=%s",
            rank_num,
            work.title,
            work.id,
            "R15" in (work.stats.get("elements") or []),
            ",".join(work.extra["ranking"].get("verified_media") or []),
            work.extra["ranking"]["ranking_score"],
            work.stats.get("global_point"),
            work.stats.get("episodes"),
        )

    if len(selected) < top_target:
        LOGGER.warning("selected %s commercialised works (target was %s)", len(selected), top_target)

    explicit_out = Path(args.out_file) if args.out_file else None
    out_path, md_path = _write_ranked_catalogs(cfg, selected, out_path=explicit_out)

    merged = {w.id: w for w in works}
    for w in verified:
        merged[w.id] = w
    for w in selected:
        merged[w.id] = w
    store_works(works_path, merged.values())

    r15_selected = sum(1 for w in selected if "R15" in (w.stats.get("elements") or []))
    write_manifest(
        cfg,
        {
            "narou_rank": {
                "ranked_works": len(selected),
                "r15_works": r15_selected,
                "verified_pool": len(verified),
                "strict_external_verification": strict_flag,
                "include_r15": cfg.narou.include_r15,
                "file": relative(out_path),
                "ranking_markdown": relative(md_path),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


def _diversify_by_genre(candidates: Sequence[Work]) -> List[Work]:
    """Interleave pre-sorted candidates across genres so multiple genres appear."""
    buckets: Dict[Any, List[Work]] = {}
    genre_order: List[Any] = []
    for work in candidates:
        gcode = (work.genre or {}).get("code")
        if gcode not in buckets:
            buckets[gcode] = []
            genre_order.append(gcode)
        buckets[gcode].append(work)

    interleaved: List[Work] = []
    idx = 0
    while True:
        progressed = False
        for gcode in genre_order:
            bucket = buckets[gcode]
            if idx < len(bucket):
                interleaved.append(bucket[idx])
                progressed = True
        if not progressed:
            break
        idx += 1
    return interleaved


def cmd_narou_texts(cfg: Config, args: argparse.Namespace) -> None:
    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    ranked_path = (
        Path(args.ranked_file)
        if getattr(args, "ranked_file", None)
        else (cfg.paths.dataset_dir / NAROU_RANKED)
    )
    use_ranked_file = ranked_path.exists() and not getattr(args, "ignore_ranked_file", False)

    if not use_ranked_file and not works_path.exists():
        raise SystemExit(f"{works_path} not found - run 'narou-metadata' first")

    interval = getattr(args, "request_interval", None)
    source = NarouSource(cfg.narou, cfg.paths, build_client(cfg, request_interval=interval))
    renderer = build_renderer(cfg) if args.pdf else None

    commercialized_only = cfg.narou.commercialized_only and not getattr(
        args, "allow_uncommercialized", False
    )

    if use_ranked_file:
        ordered_pool = load_works(ranked_path)
        ordered_pool.sort(
            key=lambda w: (
                (w.extra.get("ranking") or {}).get("rank") or 999999,
                -((w.extra.get("ranking") or {}).get("ranking_score") or 0),
            )
        )
        LOGGER.info("loaded %s pre-ranked commercialised works from %s", len(ordered_pool), ranked_path)
    else:
        works = load_works(works_path)
        candidates = [
            work
            for work in works
            if (work.stats.get("char_count") or 0) >= cfg.narou.min_chars
            and (cfg.narou.include_r15 or "R15" not in (work.stats.get("elements") or []))
        ]
        if not candidates:
            candidates = [
                w
                for w in works
                if cfg.narou.include_r15 or "R15" not in (w.stats.get("elements") or [])
            ]
        for w in candidates:
            if w.rights.get("commercialized") is True and "ranking" not in w.extra:
                w.extra["ranking"] = compute_popularity_ranking_score(w)

        candidates.sort(
            key=lambda w: (
                1 if w.rights.get("commercialized") is True else 0,
                (w.extra.get("ranking") or {}).get("ranking_score") or 0,
                w.stats.get("global_point") or 0,
                w.stats.get("fav_novel_cnt") or 0,
                w.stats.get("all_point") or 0,
                w.stats.get("char_count") or 0,
            ),
            reverse=True,
        )
        comm_candidates = [w for w in candidates if w.rights.get("commercialized") is True]
        other_candidates = [w for w in candidates if w.rights.get("commercialized") is not True]
        if getattr(args, "rank_order", False) or not getattr(args, "diversify_genres", False):
            ordered_pool = comm_candidates + (
                [] if commercialized_only and comm_candidates else other_candidates
            )
        else:
            ordered_pool = _diversify_by_genre(comm_candidates) + (
                []
                if commercialized_only and comm_candidates
                else _diversify_by_genre(other_candidates)
            )

    target = args.works or cfg.narou.download_works
    start_rank = max(1, int(getattr(args, "start_rank", 1) or 1))
    offset = start_rank - 1
    shard_count = int(getattr(args, "shard_count", 1) or 1)
    shard_index = int(getattr(args, "shard_index", 0) or 0)

    ordered_pool = ordered_pool[offset:]
    if shard_count > 1:
        top_slice = ordered_pool[:target]
        ordered_pool = [
            work for idx, work in enumerate(top_slice) if idx % shard_count == shard_index
        ]
        target = len(ordered_pool)
        LOGGER.info(
            "shard %s/%s (start_rank=%s) assigned %s works: %s",
            shard_index,
            shard_count,
            start_rank,
            target,
            [
                f"#{((w.extra.get('ranking') or {}).get('rank') or '?')}:{w.id}"
                for w in ordered_pool
            ],
        )

    reuse_dir = Path(args.reuse_existing_dir) if getattr(args, "reuse_existing_dir", None) else None
    reuse_pdfs, reuse_txts, reuse_prev = _load_reuse_maps(reuse_dir)

    raw_dir = cfg.paths.raw_dir / "narou" / "texts"
    pdf_dir = cfg.paths.pdf_dir / "narou"

    updated: List[Work] = []
    for work in ordered_pool:
        if len(updated) >= target:
            break
        ncode = work.id.split(":", 1)[1]
        ncode_lower = ncode.lower()
        if not use_ranked_file and (
            getattr(args, "check_commercialization", False)
            or (commercialized_only and work.rights.get("commercialized") is not True)
        ):
            info_comm = source.check_commercialized(ncode)
            if info_comm is True:
                work.rights["commercialized"] = True
            elif work.rights.get("commercialized") is not True:
                work.rights["commercialized"] = info_comm
        if commercialized_only and work.rights.get("commercialized") is not True:
            LOGGER.info("skipping non-commercialised candidate %s (%s)", work.id, work.title)
            continue

        expected_eps = int(work.stats.get("episodes") or 0)
        expected_chars = int(work.stats.get("char_count") or 0)
        work.extra.setdefault("api_char_count", expected_chars)
        work.extra.setdefault("api_episodes", expected_eps)

        rank_label = (work.extra.get("ranking") or {}).get("rank")
        cover_note = (
            "出典: 小説家になろう (syosetu.com) — 外部確認済・商業化作品の無料公開WEB版（全話収録）"
            if work.rights.get("commercialized") is True and args.max_episodes == 0
            else (
                "出典: 小説家になろう (syosetu.com) — 外部確認済・商業化作品の無料公開WEB版"
                if work.rights.get("commercialized") is True
                else "出典: 小説家になろう (syosetu.com) — 公式サイトが無料公開しているWEB版"
            )
        )

        # Fast incremental reuse when an already-rendered full-episode PDF exists
        if args.max_episodes == 0 and _try_reuse_cached_work(
            work,
            reuse_pdfs=reuse_pdfs,
            reuse_txts=reuse_txts,
            reuse_prev=reuse_prev,
            raw_dir=raw_dir,
            pdf_dir=pdf_dir,
            renderer=renderer,
            cover_note=cover_note,
        ):
            updated.append(work)
            LOGGER.info(
                "[%s/%s] Rank #%s %s -> REUSED (%s episodes, %s chars, pdf=%s)",
                len(updated),
                target,
                rank_label or "-",
                work.title,
                work.stats["episodes"],
                f"{work.stats['char_count']:,}",
                work.pdf_path,
            )
            continue

        LOGGER.info(
            "fetching %s (Rank #%s, expected %s episodes): %s",
            work.id,
            rank_label or "-",
            expected_eps,
            work.title,
        )
        novel = source.fetch_novel_text(
            ncode,
            max_episodes=args.max_episodes,
            expected_episodes=expected_eps,
        )
        if not novel.chapters:
            LOGGER.warning("no text for %s (%s)", work.id, work.title)
            continue
        text_path = raw_dir / f"{ncode}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(novel.text, encoding="utf-8")

        work.text_path = relative(text_path)
        work.extra["text_bytes"] = text_path.stat().st_size
        work.stats["char_count"] = novel.char_count
        work.stats["episodes"] = len(novel.chapters)
        work.extra["text_origin"] = novel.origin
        work.extra["all_episodes_rendered"] = args.max_episodes == 0
        if work.rights.get("commercialized") is True:
            work.rights["note"] = (
                "この作品は外部書誌・メディアDBにより商業化が実在確認されています。"
                "商業版（紙書籍・電子書籍）は再配布せず、"
                "本データセットでは公式サイトが無料公開しているWEB版のみを扱います。"
                "二次利用には作者の許諾が必要です。"
            )
        if renderer is not None:
            pdf_path = pdf_dir / f"{ncode}.pdf"
            blocks = []
            for chapter in novel.chapters:
                if chapter.get("title"):
                    blocks.append({"type": "paragraph", "text": chapter["title"], "chapter": True})
                for paragraph in chapter.get("paragraphs", []):
                    blocks.append({"type": "paragraph", "text": paragraph})
            renderer.render(
                work,
                blocks,
                pdf_path,
                note=cover_note,
            )
            work.pdf_path = relative(pdf_path)
            work.extra["pdf_bytes"] = pdf_path.stat().st_size
        else:
            work.pdf_path = None
            work.extra.pop("pdf_bytes", None)
        updated.append(work)
        LOGGER.info(
            "[%s/%s] Rank #%s %s -> %s episodes, %s chars, pdf=%s",
            len(updated),
            target,
            rank_label or "-",
            work.title,
            len(novel.chapters),
            f"{novel.char_count:,}",
            work.pdf_path,
        )

    if shard_count > 1:
        shard_dir = cfg.paths.dataset_dir / "shards"
        shard_file = shard_dir / f"narou_shard_{shard_index:02d}.jsonl"
        store_works(shard_file, updated)
        LOGGER.info("wrote %s shard records to %s", len(updated), shard_file)
        return

    if works_path.exists():
        all_works = load_works(works_path)
        merged = {work.id: work for work in all_works}
        for work in updated:
            merged[work.id] = work
        store_works(works_path, merged.values())
    if use_ranked_file:
        ranked_works = load_works(ranked_path)
        rmerged = {w.id: w for w in ranked_works}
        for w in updated:
            rmerged[w.id] = w
        final_ranked = sorted(
            rmerged.values(),
            key=lambda w: ((w.extra.get("ranking") or {}).get("rank") or 999999),
        )
        _write_ranked_catalogs(cfg, final_ranked, out_path=ranked_path)

    write_manifest(
        cfg,
        {
            "narou_texts": {
                "works": len(updated),
                "max_episodes": args.max_episodes,
                "total_episodes": sum(int(w.stats.get("episodes") or 0) for w in updated),
                "total_chars": sum(int(w.stats.get("char_count") or 0) for w in updated),
                "texts_dir": relative(raw_dir),
                "pdf_dir": relative(pdf_dir) if args.pdf else None,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


def cmd_narou_merge_shards(cfg: Config, args: argparse.Namespace) -> None:
    """Merge sharded ``narou-texts`` outputs into ``narou_novels.jsonl`` & ranked files."""
    shard_dir = Path(args.shard_dir) if args.shard_dir else (cfg.paths.dataset_dir / "shards")
    shard_files = sorted(shard_dir.glob("narou_shard_*.jsonl"))
    if not shard_files:
        raise SystemExit(f"no shard files found in {shard_dir}")

    want_pdf = bool(getattr(args, "pdf", False))
    updated_by_id: Dict[str, Work] = {}
    for sfile in shard_files:
        for work in load_works(sfile):
            if work.text_path:
                txt_full = REPO_ROOT / work.text_path
                if txt_full.exists() and txt_full.stat().st_size > 256:
                    work.extra["text_bytes"] = txt_full.stat().st_size
                    if not want_pdf:
                        work.pdf_path = None
                        work.extra.pop("pdf_bytes", None)
                        updated_by_id[work.id] = work
                        continue
            if work.pdf_path:
                pdf_full = REPO_ROOT / work.pdf_path
                if pdf_full.exists() and pdf_full.stat().st_size > 1024:
                    work.extra["pdf_bytes"] = pdf_full.stat().st_size
                    updated_by_id[work.id] = work

    ranked_path = cfg.paths.dataset_dir / NAROU_RANKED
    ranked_pool = load_works(ranked_path) if ranked_path.exists() else []
    ranked_pool.sort(
        key=lambda w: (
            (w.extra.get("ranking") or {}).get("rank") or 999999,
            -((w.extra.get("ranking") or {}).get("ranking_score") or 0),
        )
    )

    # Backfill from spare ranked works (#101+) if any primary shard item failed
    if getattr(args, "backfill", False) and len(updated_by_id) < args.works and ranked_pool:
        needed = args.works - len(updated_by_id)
        LOGGER.info("backfilling %s works from spare ranked candidates", needed)
        reuse_dir = (
            Path(args.reuse_existing_dir)
            if getattr(args, "reuse_existing_dir", None)
            else None
        )
        reuse_pdfs, reuse_txts, reuse_prev = _load_reuse_maps(reuse_dir)
        source = NarouSource(cfg.narou, cfg.paths, build_client(cfg, request_interval=0.25))
        renderer = build_renderer(cfg) if want_pdf else None
        raw_dir = cfg.paths.raw_dir / "narou" / "texts"
        pdf_dir = cfg.paths.pdf_dir / "narou"
        cover_note = "出典: 小説家になろう (syosetu.com) — 外部確認済・商業化作品の無料公開WEB版（全話収録）"
        for spare in ranked_pool:
            if len(updated_by_id) >= args.works:
                break
            if spare.id in updated_by_id:
                continue
            if _try_reuse_cached_work(
                spare,
                reuse_pdfs=reuse_pdfs,
                reuse_txts=reuse_txts,
                reuse_prev=reuse_prev,
                raw_dir=raw_dir,
                pdf_dir=pdf_dir,
                renderer=renderer,
                cover_note=cover_note,
            ):
                updated_by_id[spare.id] = spare
                continue
            ncode = spare.id.split(":", 1)[1]
            expected_eps = int(spare.stats.get("episodes") or 0)
            novel = source.fetch_novel_text(ncode, max_episodes=0, expected_episodes=expected_eps)
            if not novel.chapters:
                continue
            text_path = raw_dir / f"{ncode}.txt"
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(novel.text, encoding="utf-8")
            spare.text_path = relative(text_path)
            spare.extra["text_bytes"] = text_path.stat().st_size
            spare.stats["char_count"] = novel.char_count
            spare.stats["episodes"] = len(novel.chapters)
            spare.extra["text_origin"] = novel.origin
            spare.extra["all_episodes_rendered"] = True
            if renderer is not None:
                pdf_path = pdf_dir / f"{ncode}.pdf"
                blocks = []
                for chapter in novel.chapters:
                    if chapter.get("title"):
                        blocks.append({"type": "paragraph", "text": chapter["title"], "chapter": True})
                    for paragraph in chapter.get("paragraphs", []):
                        blocks.append({"type": "paragraph", "text": paragraph})
                renderer.render(
                    spare,
                    blocks,
                    pdf_path,
                    note=cover_note,
                )
                spare.pdf_path = relative(pdf_path)
                spare.extra["pdf_bytes"] = pdf_path.stat().st_size
            else:
                spare.pdf_path = None
                spare.extra.pop("pdf_bytes", None)
            updated_by_id[spare.id] = spare

    if ranked_pool:
        ordered_rendered: List[Work] = []
        for w in ranked_pool:
            if w.id in updated_by_id:
                ordered_rendered.append(updated_by_id[w.id])
        final_ranked = ordered_rendered[: args.works]
    else:
        final_ranked = sorted(
            updated_by_id.values(),
            key=lambda w: ((w.extra.get("ranking") or {}).get("rank") or 999999),
        )[: args.works]

    cover_renderer: Optional[BookPdfRenderer] = None
    for idx, work in enumerate(final_ranked, start=1):
        old_rank = (work.extra.get("ranking") or {}).get("rank")
        work.extra.setdefault("ranking", {})["rank"] = idx
        if want_pdf and old_rank != idx and work.pdf_path:
            pdf_full = REPO_ROOT / work.pdf_path
            if pdf_full.exists():
                if cover_renderer is None:
                    cover_renderer = build_renderer(cfg)
                try:
                    cover_renderer.refresh_cover(
                        work,
                        pdf_full,
                        pdf_full,
                        note="出典: 小説家になろう (syosetu.com) — 外部確認済・商業化作品の無料公開WEB版（全話収録）",
                    )
                    work.extra["pdf_bytes"] = pdf_full.stat().st_size
                except Exception as exc:
                    LOGGER.warning("cover rank refresh skipped for %s: %s", work.id, exc)

    # Preserve genre-supplement texts if present while removing unused spare files
    keep_ncodes = {w.id.split(":", 1)[1].lower() for w in final_ranked}
    supp_path = cfg.paths.dataset_dir / NAROU_GENRE_SUPP
    if supp_path.exists():
        for sw in load_works(supp_path):
            keep_ncodes.add(sw.id.split(":", 1)[1].lower())
    if (cfg.paths.pdf_dir / "narou").exists():
        for p in (cfg.paths.pdf_dir / "narou").glob("*.pdf"):
            if not want_pdf or p.stem.lower() not in keep_ncodes:
                p.unlink(missing_ok=True)
    for p in (cfg.paths.raw_dir / "narou" / "texts").glob("*.txt"):
        if p.stem.lower() not in keep_ncodes:
            p.unlink(missing_ok=True)

    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    if works_path.exists():
        all_works = load_works(works_path)
        merged = {w.id: w for w in all_works}
        for w in final_ranked:
            merged[w.id] = w
        store_works(works_path, merged.values())

    ranked_path, md_path = _write_ranked_catalogs(cfg, final_ranked, out_path=ranked_path)

    completed = [w for w in final_ranked if (w.pdf_path if want_pdf else w.text_path)]
    total_eps = sum(int(w.stats.get("episodes") or 0) for w in completed)
    total_chars = sum(int(w.stats.get("char_count") or 0) for w in completed)
    total_txt_bytes = sum(int((w.extra or {}).get("text_bytes") or 0) for w in completed)
    total_pdf_bytes = sum(int((w.extra or {}).get("pdf_bytes") or 0) for w in completed)

    LOGGER.info(
        "merged %s shards -> %s/%s ranked works (%s episodes, %s chars, %.2f MB txt)",
        len(shard_files),
        len(completed),
        len(final_ranked),
        f"{total_eps:,}",
        f"{total_chars:,}",
        total_txt_bytes / (1024 * 1024),
    )
    if getattr(args, "strict_count", False) and len(completed) < args.works:
        raise SystemExit(f"expected {args.works} works, got {len(completed)}")

    write_manifest(
        cfg,
        {
            "narou_texts": {
                "works": len(completed),
                "max_episodes": 0,
                "all_episodes": True,
                "total_episodes": total_eps,
                "total_chars": total_chars,
                "total_text_bytes": total_txt_bytes,
                "total_pdf_bytes": total_pdf_bytes,
                "ranked_file": relative(ranked_path),
                "ranking_markdown": relative(md_path),
                "texts_dir": relative(cfg.paths.raw_dir / "narou" / "texts"),
                "pdf_dir": relative(cfg.paths.pdf_dir / "narou") if want_pdf else None,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


# ---------------------------------------------------------------------------
# PDF-to-text conversion & purge + 5-genre commercialized supplement
# ---------------------------------------------------------------------------
_ISEKAI_FANTASY_CUE_RE = re.compile(
    r"(異世界|転生|転移|悪役令嬢|ダンジョン|魔王|勇者|聖女|ギルド|ステータス|チート|"
    r"ドラゴン|エルフ|魔法学園|王国|公爵|伯爵|侯爵|辺境|迷宮|冒険者|魔導|召喚獣)"
)
_COMM_HINT_RE = re.compile(
    r"(書籍化|文庫化|単行本|コミカライズ|漫画化|マンガ化|アニメ化|映画化|ドラマ化|舞台化|"
    r"発売中|好評発売|刊行|受賞|大賞|文庫|ノベルス|ノベルズ|ブックス)"
)

SUPPLEMENT_GENRE_SPECS: List[Dict[str, Any]] = [
    {
        "category": "歴史",
        "genre_codes": (303,),
        "require_non_isekai": False,
        "description": "歴史〔文芸〕（時代小説・戦国・幕末・大河・架空戦記）",
    },
    {
        "category": "推理",
        "genre_codes": (304,),
        "require_non_isekai": False,
        "description": "推理〔文芸〕（ミステリー・探偵・日常の謎・本格推理）",
    },
    {
        "category": "現代",
        "genre_codes": (302, 301, 102, 306, 307),
        "require_non_isekai": True,
        "description": "現代（ヒューマンドラマ・純文学・現実世界・現代アクション・コメディー／非異世界）",
    },
    {
        "category": "SF",
        "genre_codes": (402, 403, 404, 401),
        "require_non_isekai": False,
        "description": "SF（宇宙・空想科学・パニック・VRゲーム）",
    },
    {
        "category": "ホラー",
        "genre_codes": (305,),
        "require_non_isekai": False,
        "description": "ホラー〔文芸〕（怪談・オカルト・民俗ホラー・都市伝説）",
    },
]


def _interleave_by_subgenre(
    works: Sequence[Work],
    genre_codes: Sequence[int],
) -> List[Work]:
    buckets: Dict[int, List[Work]] = {int(c): [] for c in genre_codes}
    for w in works:
        gc = int((w.genre or {}).get("code") or 0)
        if gc in buckets:
            buckets[gc].append(w)
    out: List[Work] = []
    idx = 0
    while True:
        progressed = False
        for gc in genre_codes:
            b = buckets[int(gc)]
            if idx < len(b):
                out.append(b[idx])
                progressed = True
        if not progressed:
            break
        idx += 1
    return out


def _build_genre_candidate_queue(
    works: Sequence[Work],
    *,
    genre_codes: Sequence[int],
    require_non_isekai: bool,
    exclude_ids: Set[str],
    min_chars: int,
    min_episodes: int,
    include_r15: bool,
    max_scan: int,
) -> List[Work]:
    """Build a prioritized candidate queue for one of the 5 target supplement categories."""
    per_sub_cued: Dict[int, List[Work]] = {int(c): [] for c in genre_codes}
    per_sub_other: Dict[int, List[Work]] = {int(c): [] for c in genre_codes}
    code_set = {int(c) for c in genre_codes}

    for w in works:
        if w.id.lower() in exclude_ids:
            continue
        gc = int((w.genre or {}).get("code") or 0)
        if gc not in code_set:
            continue
        if (w.stats.get("char_count") or 0) < min_chars:
            continue
        if (w.stats.get("episodes") or 0) < min_episodes:
            continue
        elems = w.stats.get("elements") or []
        if not include_r15 and "R15" in elems:
            continue
        if require_non_isekai:
            if "異世界転生" in elems or "異世界転移" in elems:
                continue
            kw_title = f"{w.title} {(w.extra or {}).get('keywords') or ''}"
            if _ISEKAI_FANTASY_CUE_RE.search(kw_title):
                continue

        synopsis = (w.extra or {}).get("synopsis") or ""
        blob = f"{w.title} {(w.extra or {}).get('keywords') or ''} {synopsis}"
        has_cue = (w.rights or {}).get("commercialized") is True or bool(_COMM_HINT_RE.search(blob))
        if has_cue:
            per_sub_cued[gc].append(w)
        else:
            per_sub_other[gc].append(w)

    sort_key = lambda x: (
        x.stats.get("global_point") or 0,
        x.stats.get("fav_novel_cnt") or 0,
        x.stats.get("all_point") or 0,
    )
    for gc in code_set:
        per_sub_cued[gc].sort(key=sort_key, reverse=True)
        per_sub_other[gc].sort(key=sort_key, reverse=True)

    cued_flat: List[Work] = []
    other_flat: List[Work] = []
    if len(genre_codes) == 1:
        only = int(genre_codes[0])
        cued_flat = per_sub_cued[only]
        other_flat = per_sub_other[only]
    else:
        for bucket_map, target_list in ((per_sub_cued, cued_flat), (per_sub_other, other_flat)):
            idx = 0
            while True:
                progressed = False
                for gc in genre_codes:
                    b = bucket_map[int(gc)]
                    if idx < len(b):
                        target_list.append(b[idx])
                        progressed = True
                if not progressed:
                    break
                idx += 1

    # Put top 20 novel-length high-point works + all explicit commercialisation-cue works
    # + remaining high-point works so stealth commercialised hits and bunko hits both verify fast.
    seen: Set[str] = set()
    ordered: List[Work] = []
    novel_length_other = [
        w for w in other_flat if (w.stats.get("char_count") or 0) >= 25000
    ]
    for w in novel_length_other[:20]:
        if w.id not in seen:
            seen.add(w.id)
            ordered.append(w)
    for w in cued_flat:
        if len(ordered) >= max_scan:
            break
        if w.id not in seen:
            seen.add(w.id)
            ordered.append(w)
    for w in other_flat:
        if len(ordered) >= max_scan:
            break
        if w.id not in seen:
            seen.add(w.id)
            ordered.append(w)
    return ordered[:max_scan]


def _write_combined_commercialized_catalog(cfg: Config) -> Optional[Path]:
    """Combine Top-300 ranked works + 5-genre supplement into ``narou_commercialized_all.jsonl``."""
    ranked_path = cfg.paths.dataset_dir / NAROU_RANKED
    supp_path = cfg.paths.dataset_dir / NAROU_GENRE_SUPP
    combined: List[Work] = []
    seen: Set[str] = set()
    for p in (ranked_path, supp_path):
        if p.exists():
            for w in load_works(p):
                if w.id not in seen:
                    seen.add(w.id)
                    combined.append(w)
    if not combined:
        return None
    out_path = cfg.paths.dataset_dir / NAROU_ALL_COMM
    store_works(out_path, combined)
    return out_path


def cmd_purge_pdfs(cfg: Config, args: argparse.Namespace) -> None:
    """Convert any text-less PDFs to plain UTF-8 text, clear PDF fields, and delete all PDFs."""
    reuse_dir = Path(args.reuse_existing_dir) if getattr(args, "reuse_existing_dir", None) else None

    converted_count = 0
    verified_txt_count = 0
    removed_pdf_files = 0
    removed_pdf_bytes = 0

    source_specs = [
        ("narou", cfg.paths.pdf_dir / "narou", cfg.paths.raw_dir / "narou" / "texts"),
        ("aozora", cfg.paths.pdf_dir / "aozora", cfg.paths.raw_dir / "aozora" / "texts"),
    ]
    if reuse_dir and reuse_dir.exists():
        for sub_src, pdf_rel, txt_rel in (
            ("narou", "pdf/narou", "raw/narou/texts"),
            ("narou", "data/pdf/narou", "data/raw/narou/texts"),
            ("aozora", "pdf/aozora", "raw/aozora/texts"),
            ("aozora", "data/pdf/aozora", "data/raw/aozora/texts"),
        ):
            rp = reuse_dir / pdf_rel
            rt = reuse_dir / txt_rel
            target_txt_dir = cfg.paths.raw_dir / sub_src / "texts"
            if rt.is_dir():
                target_txt_dir.mkdir(parents=True, exist_ok=True)
                for tf in rt.glob("*.txt"):
                    dest = target_txt_dir / tf.name
                    if not dest.exists() and tf.stat().st_size > 64:
                        shutil.copy2(tf, dest)
            if rp.is_dir():
                source_specs.append((sub_src, rp, target_txt_dir))

    for src_name, pdir, tdir in source_specs:
        if not pdir.is_dir():
            continue
        tdir.mkdir(parents=True, exist_ok=True)
        for pdf_file in sorted(pdir.glob("*.pdf")):
            stem = pdf_file.stem
            # Match existing case-insensitive .txt if present
            existing_txt: Optional[Path] = None
            for cand in (tdir / f"{stem}.txt", tdir / f"{stem.lower()}.txt", tdir / f"{stem.upper()}.txt"):
                if cand.exists() and cand.stat().st_size > 128:
                    existing_txt = cand
                    break
            if existing_txt is None:
                extracted = extract_clean_text_from_pdf(pdf_file)
                out_txt = tdir / f"{stem}.txt"
                out_txt.write_text(extracted, encoding="utf-8")
                converted_count += 1
                verified_txt_count += 1
                LOGGER.info("extracted plain text from PDF %s -> %s (%s chars)", pdf_file.name, out_txt, len(extracted))
            else:
                verified_txt_count += 1

    # Delete all PDFs under cfg.paths.pdf_dir
    if cfg.paths.pdf_dir.exists():
        for pdf_file in cfg.paths.pdf_dir.rglob("*.pdf"):
            removed_pdf_files += 1
            removed_pdf_bytes += pdf_file.stat().st_size
            pdf_file.unlink(missing_ok=True)
        shutil.rmtree(cfg.paths.pdf_dir, ignore_errors=True)

    # Index all verified .txt files by lowercase stem
    narou_txt_map = {
        p.stem.lower(): p
        for p in (cfg.paths.raw_dir / "narou" / "texts").glob("*.txt")
        if p.is_file() and p.stat().st_size > 0
    }
    aozora_txt_map = {
        p.stem.lower(): p
        for p in (cfg.paths.raw_dir / "aozora" / "texts").glob("*.txt")
        if p.is_file() and p.stat().st_size > 0
    }

    # Update all dataset JSONL catalogs to text-only (pdf_path = None)
    for jpath in sorted(cfg.paths.dataset_dir.glob("*.jsonl")):
        if jpath.name == AOZORA_AUTHORS:
            continue
        works = load_works(jpath)
        changed = False
        for w in works:
            wid_tail = w.id.split(":", 1)[1].lower() if ":" in w.id else w.id.lower()
            is_aozora = w.source.startswith("aozora") or w.id.startswith("aozora:")
            tmap = aozora_txt_map if is_aozora else narou_txt_map
            matched_txt = tmap.get(wid_tail)
            if matched_txt is not None:
                rel_txt = relative(matched_txt)
                tbytes = matched_txt.stat().st_size
                if w.text_path != rel_txt or w.extra.get("text_bytes") != tbytes:
                    w.text_path = rel_txt
                    w.extra["text_bytes"] = tbytes
                    changed = True
            elif w.text_path:
                full_t = REPO_ROOT / w.text_path
                if full_t.exists():
                    w.extra["text_bytes"] = full_t.stat().st_size
                    changed = True
            if w.pdf_path is not None or "pdf_bytes" in w.extra:
                w.pdf_path = None
                w.extra.pop("pdf_bytes", None)
                changed = True
        if changed:
            store_works(jpath, works)

    # Re-render Markdown catalogs with text-only metadata
    ranked_path = cfg.paths.dataset_dir / NAROU_RANKED
    if ranked_path.exists():
        ranked_works = load_works(ranked_path)
        _write_ranked_catalogs(cfg, ranked_works, out_path=ranked_path)
    supp_path = cfg.paths.dataset_dir / NAROU_GENRE_SUPP
    if supp_path.exists():
        supp_works = load_works(supp_path)
        (cfg.paths.dataset_dir / NAROU_GENRE_SUPP_MD).write_text(
            render_narou_ranking_markdown(
                supp_works,
                heading="# 小説家になろう 5ジャンル限定（歴史・推理・現代・SF・ホラー）外部確認済・商業化追加作品カタログ",
                show_category=True,
            ),
            encoding="utf-8",
        )
    _write_combined_commercialized_catalog(cfg)

    total_narou_txt_bytes = sum(p.stat().st_size for p in narou_txt_map.values())
    total_aozora_txt_bytes = sum(p.stat().st_size for p in aozora_txt_map.values())
    LOGGER.info(
        "purge-pdfs complete: converted=%s PDFs, verified_narou_txts=%s (%.2f MB), "
        "verified_aozora_txts=%s (%.2f MB), deleted=%s PDFs (%.2f MB freed)",
        converted_count,
        len(narou_txt_map),
        total_narou_txt_bytes / (1024 * 1024),
        len(aozora_txt_map),
        total_aozora_txt_bytes / (1024 * 1024),
        removed_pdf_files,
        removed_pdf_bytes / (1024 * 1024),
    )

    # Update manifest entries to reflect PDF removal
    manifest_path = cfg.paths.dataset_dir / MANIFEST
    existing_manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing_manifest = {}
    if isinstance(existing_manifest.get("aozora_texts"), dict):
        existing_manifest["aozora_texts"]["pdf_dir"] = None
        existing_manifest["aozora_texts"]["total_text_bytes"] = total_aozora_txt_bytes
    if isinstance(existing_manifest.get("narou_texts"), dict):
        existing_manifest["narou_texts"]["pdf_dir"] = None
        existing_manifest["narou_texts"]["total_pdf_bytes"] = 0
        existing_manifest["narou_texts"]["total_text_bytes"] = total_narou_txt_bytes
    existing_manifest["pdf_purge"] = {
        "pdfs_purged": True,
        "converted_from_pdf": converted_count,
        "removed_pdf_files": removed_pdf_files,
        "freed_pdf_bytes": removed_pdf_bytes,
        "narou_text_files": len(narou_txt_map),
        "aozora_text_files": len(aozora_txt_map),
        "total_text_bytes": total_narou_txt_bytes + total_aozora_txt_bytes,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(existing_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cmd_narou_genre_supplement(cfg: Config, args: argparse.Namespace) -> None:
    """Select, externally verify, and download 10-15 commercialized works in each of 5 genres."""
    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    if not works_path.exists():
        raise SystemExit(f"{works_path} not found - run 'narou-metadata' first")
    works = load_works(works_path)

    ranked_path = cfg.paths.dataset_dir / NAROU_RANKED
    existing_ranked = load_works(ranked_path) if ranked_path.exists() else []
    exclude_ids: Set[str] = {w.id.lower() for w in existing_ranked}
    repo_sample_ranked = REPO_ROOT / "samples" / NAROU_RANKED
    if repo_sample_ranked.is_file():
        for w in load_works(repo_sample_ranked):
            exclude_ids.add(w.id.lower())

    reuse_dir = Path(args.reuse_existing_dir) if getattr(args, "reuse_existing_dir", None) else None
    reuse_pdfs, reuse_txts, reuse_prev = _load_reuse_maps(reuse_dir)

    seed_verifications: Dict[str, MediaVerificationResult] = {}
    seed_sources: List[Work] = list(reuse_prev.values())
    repo_sample_supp = REPO_ROOT / "samples" / NAROU_GENRE_SUPP
    if repo_sample_supp.is_file():
        seed_sources.extend(load_works(repo_sample_supp))
    for sw in seed_sources:
        ext_dict = (sw.rights or {}).get("external_verification")
        if isinstance(ext_dict, dict) and ext_dict.get("verified"):
            ncode_key = sw.id.split(":", 1)[1].lower()
            seed_verifications.setdefault(ncode_key, MediaVerificationResult.from_dict(ext_dict))

    interval = getattr(args, "request_interval", None) or 0.22
    source = NarouSource(cfg.narou, cfg.paths, build_client(cfg, request_interval=interval))
    anime_ncodes = source.fetch_anime_ncodes()

    per_genre = int(args.per_genre)
    min_per_genre = int(args.min_per_genre)
    scan_per_genre = int(args.scan_limit_per_genre)
    raw_dir = cfg.paths.raw_dir / "narou" / "texts"
    pdf_dir = cfg.paths.pdf_dir / "narou"
    raw_dir.mkdir(parents=True, exist_ok=True)

    all_supplement: List[Work] = []
    category_counts: Dict[str, int] = {}

    for spec in SUPPLEMENT_GENRE_SPECS:
        cat_name = spec["category"]
        gcodes = spec["genre_codes"]
        req_non_isekai = bool(spec["require_non_isekai"])

        queue = _build_genre_candidate_queue(
            works,
            genre_codes=gcodes,
            require_non_isekai=req_non_isekai,
            exclude_ids=exclude_ids,
            min_chars=args.min_chars,
            min_episodes=args.min_episodes,
            include_r15=cfg.narou.include_r15,
            max_scan=scan_per_genre,
        )
        LOGGER.info(
            "=== [%s] (%s) verifying up to %s candidates (target=%s, min=%s) ===",
            cat_name,
            spec["description"],
            len(queue),
            per_genre,
            min_per_genre,
        )

        verified = source.verify_candidates_external(
            queue,
            anime_ncodes=anime_ncodes,
            strict=True,
            check_syuppan=False,
            seed_verifications=seed_verifications,
            target_verified_pool=per_genre + 8,
            min_scan_before_stop=min(len(queue), max(55, per_genre * 3 + 10)),
        )
        verified.sort(
            key=lambda w: (
                (w.extra.get("ranking") or {}).get("ranking_score") or 0,
                w.stats.get("global_point") or 0,
                w.stats.get("fav_novel_cnt") or 0,
                w.stats.get("all_point") or 0,
            ),
            reverse=True,
        )
        if len(gcodes) > 1:
            verified = _interleave_by_subgenre(verified, gcodes)

        cat_selected: List[Work] = []
        for cand in verified:
            if len(cat_selected) >= per_genre:
                break
            if cand.id.lower() in exclude_ids:
                continue
            ncode = cand.id.split(":", 1)[1]
            ncode_lower = ncode.lower()

            if _try_reuse_cached_work(
                cand,
                reuse_pdfs=reuse_pdfs,
                reuse_txts=reuse_txts,
                reuse_prev=reuse_prev,
                raw_dir=raw_dir,
                pdf_dir=pdf_dir,
                renderer=None,
                cover_note="",
            ):
                exclude_ids.add(cand.id.lower())
                grank = len(cat_selected) + 1
                cand.extra["supplement_category"] = cat_name
                cand.extra["genre_rank"] = grank
                cand.extra.setdefault("ranking", {})["rank"] = grank
                cand.pdf_path = None
                cand.extra.pop("pdf_bytes", None)
                cat_selected.append(cand)
                LOGGER.info(
                    "[%s %s/%s] %s (%s) -> REUSED (%s eps, %s chars)",
                    cat_name,
                    grank,
                    per_genre,
                    cand.title,
                    cand.id,
                    cand.stats.get("episodes"),
                    f"{int(cand.stats.get('char_count') or 0):,}",
                )
                continue

            if args.verify_web and not source.verify_web_text_available(cand):
                LOGGER.warning("skipping %s (%s) - WEB episodes unavailable", cand.id, cand.title)
                continue

            expected_eps = int(cand.stats.get("episodes") or 0)
            cand.extra.setdefault("api_char_count", int(cand.stats.get("char_count") or 0))
            cand.extra.setdefault("api_episodes", expected_eps)
            novel = source.fetch_novel_text(
                ncode,
                max_episodes=0,
                expected_episodes=expected_eps,
            )
            if not novel.chapters:
                LOGGER.warning("skipping %s (%s) - 0 episodes fetched", cand.id, cand.title)
                continue

            text_path = raw_dir / f"{ncode}.txt"
            text_path.write_text(novel.text, encoding="utf-8")
            cand.text_path = relative(text_path)
            cand.extra["text_bytes"] = text_path.stat().st_size
            cand.pdf_path = None
            cand.extra.pop("pdf_bytes", None)
            cand.stats["char_count"] = novel.char_count
            cand.stats["episodes"] = len(novel.chapters)
            cand.extra["text_origin"] = novel.origin
            cand.extra["all_episodes_rendered"] = True
            cand.rights["note"] = (
                "この作品は外部書誌・メディアDBにより商業化が実在確認されています。"
                "商業版（紙書籍・電子書籍）は再配布せず、"
                "本データセットでは公式サイトが無料公開しているWEB版のみを扱います。"
                "二次利用には作者の許諾が必要です。"
            )
            exclude_ids.add(cand.id.lower())
            grank = len(cat_selected) + 1
            cand.extra["supplement_category"] = cat_name
            cand.extra["genre_rank"] = grank
            cand.extra.setdefault("ranking", {})["rank"] = grank
            cat_selected.append(cand)
            LOGGER.info(
                "[%s %s/%s] %s (%s) -> %s eps, %s chars (media=%s)",
                cat_name,
                grank,
                per_genre,
                cand.title,
                cand.id,
                len(novel.chapters),
                f"{novel.char_count:,}",
                ",".join((cand.extra.get("ranking") or {}).get("verified_media") or []),
            )

        category_counts[cat_name] = len(cat_selected)
        if len(cat_selected) < min_per_genre and getattr(args, "strict_count", False):
            raise SystemExit(
                f"category '{cat_name}' yielded {len(cat_selected)} works (< min_per_genre={min_per_genre})"
            )
        all_supplement.extend(cat_selected)

    supp_jsonl = cfg.paths.dataset_dir / NAROU_GENRE_SUPP
    supp_md = cfg.paths.dataset_dir / NAROU_GENRE_SUPP_MD
    store_works(supp_jsonl, all_supplement)
    supp_md.write_text(
        render_narou_ranking_markdown(
            all_supplement,
            heading="# 小説家になろう 5ジャンル限定（歴史・推理・現代・SF・ホラー）外部確認済・商業化追加作品カタログ",
            show_category=True,
        ),
        encoding="utf-8",
    )

    merged = {w.id: w for w in works}
    for w in all_supplement:
        merged[w.id] = w
    store_works(works_path, merged.values())
    all_comm_path = _write_combined_commercialized_catalog(cfg)

    total_eps = sum(int(w.stats.get("episodes") or 0) for w in all_supplement)
    total_chars = sum(int(w.stats.get("char_count") or 0) for w in all_supplement)
    total_txt_bytes = sum(int((w.extra or {}).get("text_bytes") or 0) for w in all_supplement)
    r15_cnt = sum(1 for w in all_supplement if "R15" in (w.stats.get("elements") or []))

    write_manifest(
        cfg,
        {
            "narou_genre_supplement": {
                "works": len(all_supplement),
                "per_genre_target": per_genre,
                "min_per_genre": min_per_genre,
                "category_counts": category_counts,
                "r15_works": r15_cnt,
                "all_episodes": True,
                "pdf_generated": False,
                "total_episodes": total_eps,
                "total_chars": total_chars,
                "total_text_bytes": total_txt_bytes,
                "supplement_file": relative(supp_jsonl),
                "supplement_markdown": relative(supp_md),
                "combined_file": relative(all_comm_path) if all_comm_path else None,
                "texts_dir": relative(raw_dir),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
    )


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def cmd_report(cfg: Config, args: argparse.Namespace) -> None:
    from asc.report import build_report  # local import keeps the CLI light

    report = build_report(cfg.paths.dataset_dir)
    print(report.render_text())


# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=None, help="path to the YAML configuration")
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("aozora-metadata", help="download the Aozora Bunko bibliographic records")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_aozora_metadata)

    p = sub.add_parser("aozora-texts", help="download texts (and PDFs) of Aozora works")
    p.add_argument("--works", type=int, default=None)
    p.add_argument("--pdf", action="store_true", help="also render PDF files")
    p.set_defaults(func=cmd_aozora_texts)

    p = sub.add_parser("narou-metadata", help="download the Narou bibliographic records")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--cached-only", action="store_true", help="only import cached API JSON files")
    p.set_defaults(func=cmd_narou_metadata)

    p = sub.add_parser("narou-rank", help="externally verify & rank commercialised Narou works")
    p.add_argument("--top", type=int, default=300, help="number of top ranked works to select")
    p.add_argument("--scan-limit", type=int, default=1100, help="max top candidates to inspect")
    p.add_argument("--min-chars", type=int, default=10000)
    p.add_argument("--min-episodes", type=int, default=1)
    p.add_argument("--request-interval", type=float, default=0.20)
    p.add_argument("--check-syuppan", action="store_true", default=False)
    p.add_argument("--no-syuppan", dest="check_syuppan", action="store_false")
    p.add_argument("--strict-external", dest="strict_external", action="store_true", default=None)
    p.add_argument("--no-strict-external", dest="strict_external", action="store_false")
    p.add_argument("--verify-web", action="store_true", default=True)
    p.add_argument("--no-verify-web", dest="verify_web", action="store_false")
    p.add_argument("--no-seed-verified", action="store_true", default=False)
    p.add_argument("--reuse-existing-dir", default=None)
    p.add_argument("--out-file", default=None)
    p.set_defaults(func=cmd_narou_rank)

    p = sub.add_parser("narou-texts", help="download texts (and PDFs) of Narou novels")
    p.add_argument("--start-rank", type=int, default=1, help="1-indexed rank to start from (e.g. 101)")
    p.add_argument("--works", type=int, default=None)
    p.add_argument("--max-episodes", type=int, default=0)
    p.add_argument("--pdf", action="store_true", help="also render PDF files")
    p.add_argument("--ranked-file", default=None, help="path to pre-ranked JSONL file")
    p.add_argument("--ignore-ranked-file", action="store_true")
    p.add_argument("--rank-order", action="store_true", help="execute strictly in rank order")
    p.add_argument("--diversify-genres", action="store_true", help="interleave across genres")
    p.add_argument("--reuse-existing-dir", default=None, help="directory with previous PDFs/texts")
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--shard-count", type=int, default=1)
    p.add_argument("--request-interval", type=float, default=None)
    p.add_argument(
        "--check-commercialization",
        action="store_true",
        help="query the official information page and flag commercialised works",
    )
    p.add_argument(
        "--allow-uncommercialized",
        action="store_true",
        help="allow non-commercialised novels when selecting texts/PDFs",
    )
    p.set_defaults(func=cmd_narou_texts)

    p = sub.add_parser("narou-merge-shards", help="merge sharded narou-texts outputs")
    p.add_argument("--shard-dir", default=None)
    p.add_argument("--works", type=int, default=300)
    p.add_argument("--pdf", action="store_true", help="preserve/render PDF files")
    p.add_argument("--reuse-existing-dir", default=None)
    p.add_argument("--backfill", action="store_true", help="backfill from spare ranked works")
    p.add_argument("--strict-count", action="store_true", help="exit non-zero if count < --works")
    p.set_defaults(func=cmd_narou_merge_shards)

    p = sub.add_parser(
        "purge-pdfs",
        help="convert any text-less PDFs to plain UTF-8 text and delete all PDF files",
    )
    p.add_argument("--reuse-existing-dir", default=None)
    p.set_defaults(func=cmd_purge_pdfs)

    p = sub.add_parser(
        "narou-genre-supplement",
        help="verify & download 10-15 commercialised Narou works per genre (歴史・推理・現代・SF・ホラー)",
    )
    p.add_argument("--per-genre", type=int, default=15, help="target works per genre (default 15)")
    p.add_argument("--min-per-genre", type=int, default=10, help="minimum works per genre (default 10)")
    p.add_argument("--scan-limit-per-genre", type=int, default=260)
    p.add_argument("--min-chars", type=int, default=5000)
    p.add_argument("--min-episodes", type=int, default=1)
    p.add_argument("--request-interval", type=float, default=0.22)
    p.add_argument("--verify-web", action="store_true", default=True)
    p.add_argument("--no-verify-web", dest="verify_web", action="store_false")
    p.add_argument("--strict-count", action="store_true", default=False)
    p.add_argument("--reuse-existing-dir", default=None)
    p.set_defaults(func=cmd_narou_genre_supplement)

    p = sub.add_parser("report", help="print statistics about the generated datasets")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("all", help="run every step")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--works", type=int, default=None)
    p.add_argument("--max-episodes", type=int, default=0)
    p.add_argument("--pdf", action="store_true")
    p.set_defaults(func=None)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    cfg = load_config(args.config)

    if args.command == "all":
        steps = [
            ("aozora-metadata", cmd_aozora_metadata),
            ("aozora-texts", cmd_aozora_texts),
            ("narou-metadata", cmd_narou_metadata),
            ("narou-texts", cmd_narou_texts),
        ]
        for name, func in steps:
            LOGGER.info("=== %s ===", name)
            func(cfg, args)
        return 0

    args.func(cfg, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
