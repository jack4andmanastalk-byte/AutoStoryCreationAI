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
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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


def render_narou_ranking_markdown(
    works: Sequence[Work],
    *,
    heading: Optional[str] = None,
) -> str:
    """Format a Markdown summary table of externally verified commercialised Narou works."""
    total_eps = sum(int((w.stats or {}).get("episodes") or 0) for w in works)
    total_chars = sum(int((w.stats or {}).get("char_count") or 0) for w in works)
    total_pdf_bytes = sum(int((w.extra or {}).get("pdf_bytes") or 0) for w in works)
    pdf_count = sum(1 for w in works if w.pdf_path)
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

    lines = [
        heading,
        "",
        "自己申告キーワードのみに依存せず、**CiNii Books 書誌・ISBN 検索（書籍・マンガ）**・**日本語版 Wikipedia 作品・メディアミックス検証（書籍・マンガ・アニメ・ゲーム）**・**Apple Books Japan 商業配信書誌検索（書籍・マンガ）**・公式アニメ一覧等を実際に検索し、商業化が外部データベースで実在確認された作品のみを抽出したランキングです（一般向け `novelapi` の **`R15` フラグ付与作品を含む**／18禁ノクターン等は除外）。",
        "",
        f"- **収録作品数**: {len(works)} 作品（PDF 生成済: {pdf_count} 作品・全話収録 / 話数制限なし）",
        f"- **R15 フラグ付与作品数**: {r15_count} 作品（全体の {r15_count * 100.0 / max(len(works), 1):.1f}%）",
        f"- **外部確認メディア内訳**: 書籍 {book_cnt} / マンガ {manga_cnt} / アニメ {anime_cnt} / ゲーム {game_cnt}",
        f"- **総エピソード数**: {total_eps:,} 話",
        f"- **総文字数**: {total_chars:,} 文字",
    ]
    if total_pdf_bytes:
        lines.append(f"- **総PDFサイズ**: {total_pdf_bytes / (1024 * 1024):.2f} MB")
    lines.extend(
        [
            "",
            "| 順位 | Nコード | タイトル | 作者 | ジャンル | R15 | 総合評価pt | ブックマーク | 確認メディア | 商業刊行・ISBN | 話数 | 文字数 | PDF |",
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

        pdf_bytes = int((work.extra or {}).get("pdf_bytes") or 0)
        pdf_cell = (
            f"{pdf_bytes / (1024 * 1024):.1f}MB"
            if pdf_bytes
            else ("済" if work.pdf_path else "-")
        )
        safe_title = work.title.replace("|", "｜")
        safe_author = author.replace("|", "｜")
        safe_pub = pub_str.replace("|", "｜")
        lines.append(
            f"| {rank} | `{ncode}` | {safe_title} | {safe_author} | {genre_label} | {is_r15} | "
            f"{gp:,} | {fav:,} | {media_str} | {safe_pub} | {eps:,} | {chars:,} | {pdf_cell} |"
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
        reuse_dir / "datasets" / "narou_commercialized_ranked.jsonl",
        reuse_dir / "datasets" / "narou_commercialized_top100.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_ranked.jsonl",
        reuse_dir / "data" / "datasets" / "narou_commercialized_top100.jsonl",
        reuse_dir / "narou_commercialized_ranked.jsonl",
        REPO_ROOT / "samples" / "narou_commercialized_ranked.jsonl",
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
    """Reuse a previously rendered full-episode PDF (+ text or PDF text extraction)."""
    ncode = work.id.split(":", 1)[1]
    ncode_lower = ncode.lower()
    if ncode_lower not in reuse_pdfs:
        return False

    src_pdf = reuse_pdfs[ncode_lower]
    src_txt = reuse_txts.get(ncode_lower)
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
        # Release tarball reuse (PDF + catalog metadata without separate .txt)
        episodes_fresh = prev_eps > 0 and expected_eps <= prev_eps + 3

    if not episodes_fresh:
        return False

    text_path = raw_dir / f"{ncode}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    if src_txt is not None and src_txt.exists():
        if src_txt.resolve() != text_path.resolve():
            shutil.copy2(src_txt, text_path)
    elif not text_path.exists():
        from pypdf import PdfReader

        reader = PdfReader(str(src_pdf))
        extracted = "\n\n".join(
            (page.extract_text() or "").strip() for page in reader.pages[1:]
        ).strip()
        text_path.write_text(extracted or work.title, encoding="utf-8")
        txt_content = extracted

    work.text_path = relative(text_path)
    work.stats["char_count"] = prev_chars or (
        sum(len(ln) for ln in (txt_content or "").splitlines() if ln.strip()) or expected_chars
    )
    work.stats["episodes"] = prev_eps or expected_eps
    work.extra["text_origin"] = "reused full-episode cache"
    work.extra["all_episodes_rendered"] = True

    if renderer is not None:
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
    reuse_pdfs, _, reuse_prev = _load_reuse_maps(reuse_dir)

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
        already_downloaded = ncode_lower in reuse_pdfs
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
    """Merge sharded ``narou-texts`` outputs into ``narou_novels.jsonl`` & Top-100 files."""
    shard_dir = Path(args.shard_dir) if args.shard_dir else (cfg.paths.dataset_dir / "shards")
    shard_files = sorted(shard_dir.glob("narou_shard_*.jsonl"))
    if not shard_files:
        raise SystemExit(f"no shard files found in {shard_dir}")

    updated_by_id: Dict[str, Work] = {}
    for sfile in shard_files:
        for work in load_works(sfile):
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
        renderer = build_renderer(cfg)
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
            spare.stats["char_count"] = novel.char_count
            spare.stats["episodes"] = len(novel.chapters)
            spare.extra["text_origin"] = novel.origin
            spare.extra["all_episodes_rendered"] = True
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
        if old_rank != idx and work.pdf_path:
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

    # Remove any spare PDFs/texts beyond the final Top N
    keep_ncodes = {w.id.split(":", 1)[1].lower() for w in final_ranked}
    for p in (cfg.paths.pdf_dir / "narou").glob("*.pdf"):
        if p.stem.lower() not in keep_ncodes:
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

    rendered = [w for w in final_ranked if w.pdf_path]
    total_eps = sum(int(w.stats.get("episodes") or 0) for w in rendered)
    total_chars = sum(int(w.stats.get("char_count") or 0) for w in rendered)
    total_pdf_bytes = sum(int((w.extra or {}).get("pdf_bytes") or 0) for w in rendered)

    LOGGER.info(
        "merged %s shards -> %s/%s ranked PDFs (%s episodes, %s chars, %.2f MB)",
        len(shard_files),
        len(rendered),
        len(final_ranked),
        f"{total_eps:,}",
        f"{total_chars:,}",
        total_pdf_bytes / (1024 * 1024),
    )
    if getattr(args, "strict_count", False) and len(rendered) < args.works:
        raise SystemExit(f"expected {args.works} rendered PDFs, got {len(rendered)}")

    write_manifest(
        cfg,
        {
            "narou_texts": {
                "works": len(rendered),
                "max_episodes": 0,
                "all_episodes": True,
                "total_episodes": total_eps,
                "total_chars": total_chars,
                "total_pdf_bytes": total_pdf_bytes,
                "ranked_file": relative(ranked_path),
                "ranking_markdown": relative(md_path),
                "texts_dir": relative(cfg.paths.raw_dir / "narou" / "texts"),
                "pdf_dir": relative(cfg.paths.pdf_dir / "narou"),
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
    p.add_argument("--reuse-existing-dir", default=None)
    p.add_argument("--backfill", action="store_true", help="backfill from spare ranked works")
    p.add_argument("--strict-count", action="store_true", help="exit non-zero if count < --works")
    p.set_defaults(func=cmd_narou_merge_shards)

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
