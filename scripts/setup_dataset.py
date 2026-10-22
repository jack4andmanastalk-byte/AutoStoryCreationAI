#!/usr/bin/env python3
"""Build the research datasets of AutoStoryCreationAI.

The script has one sub-command per step so that the (potentially long)
downloads can be resumed and inspected individually:

``aozora-metadata``  bibliographic records of the Aozora Bunko works
``aozora-texts``     plain texts (+ PDFs) for a sample of Aozora works
``narou-metadata``   bibliographic records of Syosetsuka ni Narou novels
``narou-texts``      plain texts (+ PDFs) for a sample of Narou novels
``report``           statistics about the generated JSONL files
``all``              every step above, in order

Example::

    python scripts/setup_dataset.py aozora-metadata
    python scripts/setup_dataset.py aozora-texts --works 50 --pdf
    python scripts/setup_dataset.py narou-metadata
    python scripts/setup_dataset.py narou-texts --works 10 --pdf
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.config import Config, load_config  # noqa: E402
from asc.fonts import build_font_set  # noqa: E402
from asc.http import HttpClient  # noqa: E402
from asc.jsonl import read_jsonl, write_jsonl  # noqa: E402
from asc.render.pdf import BookPdfRenderer  # noqa: E402
from asc.schema import AuthorRecord, Work  # noqa: E402
from asc.sources.aozora import AozoraSource, load_ndc_map, sample_works  # noqa: E402
from asc.sources.narou import NarouSource  # noqa: E402
from asc.text.aozora_format import parse_aozora_text  # noqa: E402

LOGGER = logging.getLogger("setup_dataset")

AOZORA_WORKS = "aozora_works.jsonl"
AOZORA_AUTHORS = "aozora_authors.jsonl"
NAROU_WORKS = "narou_novels.jsonl"
MANIFEST = "manifest.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def build_client(cfg: Config) -> HttpClient:
    http = cfg.http
    return HttpClient(
        user_agent=http.user_agent,
        timeout=http.timeout_seconds,
        max_retries=http.max_retries,
        backoff=http.backoff_seconds,
        request_interval=http.request_interval_seconds,
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


# ---------------------------------------------------------------------------
# Aozora
# ---------------------------------------------------------------------------
def cmd_aozora_metadata(cfg: Config, args: argparse.Namespace) -> None:
    source = AozoraSource(cfg.aozora, cfg.paths, build_client(cfg))
    card = source.fetch_card_list()

    # NDC labels (code -> human readable name)
    ndc_map: Dict[str, str] = {}
    for candidate in sorted(cfg.paths.cache_dir.glob("aozora_pages/**/ndc_class_all.json")):
        ndc_map.update(load_ndc_map(candidate))
        break
    if not ndc_map:
        ndc_map = load_ndc_map(cfg.paths.cache_dir / "ndc_class_all.json")

    for work in card.works:
        if not work.genre:
            continue
        code = work.genre.get("code")
        if code:
            label = ndc_map.get(code)
            if label is None:
                label = ndc_map.get(code[:3]) or ndc_map.get(code[:2])
            work.genre["label"] = label
            parent_code = (work.genre.get("parent") or {}).get("code")
            if parent_code:
                work.genre["parent"]["label"] = ndc_map.get(parent_code)
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

    chosen = sample_works(
        works,
        count=args.works or cfg.aozora.sample_works,
        seed=cfg.aozora.sample_seed,
        min_chars=cfg.aozora.min_chars,
    )
    LOGGER.info("processing %s works", len(chosen))

    renderer = build_renderer(cfg) if args.pdf else None
    raw_dir = cfg.paths.raw_dir / "aozora" / "texts"
    pdf_dir = cfg.paths.pdf_dir / "aozora"

    updated: List[Work] = []
    for position, work in enumerate(chosen, start=1):
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
                {"type": "paragraph", "text": b["text"], "ruby": b.get("ruby", []), "emphasis": b.get("emphasis", [])}
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
        LOGGER.info("[%s/%s] %s", position, len(chosen), work.title)

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
    works = source.harvest()
    if args.limit:
        works = works[: args.limit]
    works.sort(key=lambda w: (w.published_year or 0, w.id), reverse=True)
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


def cmd_narou_texts(cfg: Config, args: argparse.Namespace) -> None:
    works_path = cfg.paths.dataset_dir / NAROU_WORKS
    if not works_path.exists():
        raise SystemExit(f"{works_path} not found - run 'narou-metadata' first")
    works = load_works(works_path)
    source = NarouSource(cfg.narou, cfg.paths, build_client(cfg))
    renderer = build_renderer(cfg) if args.pdf else None

    candidates = [
        work
        for work in works
        if (work.stats.get("char_count") or 0) >= cfg.narou.min_chars
        and not work.stats.get("elements")
    ]
    if not candidates:
        candidates = works
    chosen = candidates[: (args.works or cfg.narou.download_works)]

    raw_dir = cfg.paths.raw_dir / "narou" / "texts"
    pdf_dir = cfg.paths.pdf_dir / "narou"

    updated: List[Work] = []
    for position, work in enumerate(chosen, start=1):
        ncode = work.id.split(":", 1)[1]
        novel = source.fetch_novel_text(ncode, max_episodes=args.max_episodes)
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
                note="出典: 小説家になろう (syosetu.com) — 公式サイトが無料公開しているWEB版",
            )
            work.pdf_path = relative(pdf_path)
        updated.append(work)
        LOGGER.info("[%s/%s] %s", position, len(chosen), work.title)

    merged = {work.id: work for work in works}
    for work in updated:
        merged[work.id] = work
    store_works(works_path, merged.values())
    write_manifest(
        cfg,
        {
            "narou_texts": {
                "works": len(updated),
                "texts_dir": relative(raw_dir),
                "pdf_dir": relative(pdf_dir) if args.pdf else None,
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    p.set_defaults(func=cmd_narou_metadata)

    p = sub.add_parser("narou-texts", help="download texts (and PDFs) of Narou novels")
    p.add_argument("--works", type=int, default=None)
    p.add_argument("--max-episodes", type=int, default=0)
    p.add_argument("--pdf", action="store_true", help="also render PDF files")
    p.set_defaults(func=cmd_narou_texts)

    p = sub.add_parser("report", help="print statistics about the generated datasets")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("all", help="run every step")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--works", type=int, default=None)
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
