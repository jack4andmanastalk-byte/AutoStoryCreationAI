from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import setup_dataset as sd  # noqa: E402
from asc.config import Config, PathsConfig  # noqa: E402
from asc.schema import Author, Work  # noqa: E402


def _make_two_page_ascii_pdf(path: Path, body_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    # Page 1: cover (should be skipped during extraction)
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 10, "COVER METADATA ONLY", new_x="LMARGIN", new_y="NEXT")
    # Page 2: body + page number footer
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for ln in body_lines:
        pdf.cell(0, 8, ln, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "2", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def test_extract_clean_text_from_pdf_skips_cover_and_footer(tmp_path: Path):
    pdf_file = tmp_path / "N0001AA.pdf"
    _make_two_page_ascii_pdf(
        pdf_file,
        [
            "Chapter 1: Mystery Opening.",
            "Detective Sato walked down the quiet street",
            "under the autumn rain.",
        ],
    )
    txt = sd.extract_clean_text_from_pdf(pdf_file)
    assert "COVER METADATA ONLY" not in txt
    assert "Chapter 1: Mystery Opening." in txt
    assert "Detective Sato walked down the quiet streetunder the autumn rain." in txt
    assert not txt.endswith("\n2")


def test_purge_pdfs_converts_missing_texts_and_removes_all_pdfs(tmp_path: Path):
    cfg = Config(
        paths=PathsConfig(
            raw_dir=tmp_path / "raw",
            pdf_dir=tmp_path / "pdf",
            dataset_dir=tmp_path / "datasets",
            cache_dir=tmp_path / "cache",
            font_dir=tmp_path / "cache" / "fonts",
        )
    )
    # Work 1: PDF only -> must be converted to .txt before PDF deletion
    _make_two_page_ascii_pdf(
        cfg.paths.pdf_dir / "narou" / "N0001AA.pdf",
        ["Historical chronicle body text for AI training and evaluation."],
    )
    # Work 2: Both .txt and .pdf -> existing .txt kept, .pdf deleted
    txt2 = cfg.paths.raw_dir / "narou" / "texts" / "N0002BB.txt"
    txt2.parent.mkdir(parents=True, exist_ok=True)
    txt2.write_text("　既存の全話プレーンテキスト本文です。" * 20, encoding="utf-8")
    _make_two_page_ascii_pdf(cfg.paths.pdf_dir / "narou" / "N0002BB.pdf", ["redundant pdf"])

    # Aozora work: PDF only -> converted to .txt
    _make_two_page_ascii_pdf(
        cfg.paths.pdf_dir / "aozora" / "000148.pdf",
        ["Aozora public domain text extracted from PDF."],
    )

    w1 = Work(
        id="narou:N0001AA",
        source="narou",
        title="戦国年代記",
        url="https://ncode.syosetu.com/n0001aa/",
        authors=[Author(name="歴史作家", role="author")],
        genre={"code": 303, "label": "歴史〔文芸〕"},
        pdf_path=str(cfg.paths.pdf_dir / "narou" / "N0001AA.pdf"),
        stats={"episodes": 50, "char_count": 120000, "global_point": 18000, "fav_novel_cnt": 7000},
        rights={"commercialized": True},
        extra={"pdf_bytes": 12345, "ranking": {"rank": 1, "is_book": True}},
    )
    w2 = Work(
        id="narou:N0002BB",
        source="narou",
        title="密室の探偵",
        url="https://ncode.syosetu.com/n0002bb/",
        authors=[Author(name="推理作家", role="author")],
        genre={"code": 304, "label": "推理〔文芸〕"},
        pdf_path=str(cfg.paths.pdf_dir / "narou" / "N0002BB.pdf"),
        stats={"episodes": 40, "char_count": 95000, "global_point": 15000, "fav_novel_cnt": 6000, "elements": ["R15"]},
        rights={"commercialized": True},
        extra={"pdf_bytes": 23456, "ranking": {"rank": 2, "is_book": True, "is_comic": True}},
    )
    aw = Work(
        id="aozora:000148",
        source="aozora_bunko",
        title="吾輩は猫である",
        url="https://www.aozora.gr.jp/cards/000148/card148.html",
        pdf_path=str(cfg.paths.pdf_dir / "aozora" / "000148.pdf"),
        extra={"pdf_bytes": 9999},
    )
    cfg.paths.dataset_dir.mkdir(parents=True, exist_ok=True)
    sd.store_works(cfg.paths.dataset_dir / sd.NAROU_RANKED, [w1, w2])
    sd.store_works(cfg.paths.dataset_dir / sd.AOZORA_WORKS, [aw])

    sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))

    assert not cfg.paths.pdf_dir.exists()
    assert list(tmp_path.rglob("*.pdf")) == []
    assert (cfg.paths.raw_dir / "narou" / "texts" / "N0001AA.txt").exists()
    assert "Historical chronicle" in (cfg.paths.raw_dir / "narou" / "texts" / "N0001AA.txt").read_text(encoding="utf-8")
    assert "既存の全話プレーンテキスト" in txt2.read_text(encoding="utf-8")
    assert (cfg.paths.raw_dir / "aozora" / "texts" / "000148.txt").exists()

    reloaded = sd.load_works(cfg.paths.dataset_dir / sd.NAROU_RANKED)
    for w in reloaded:
        assert w.pdf_path is None
        assert "pdf_bytes" not in w.extra
        assert w.text_path is not None
        assert w.extra["text_bytes"] > 0

    md_text = (cfg.paths.dataset_dir / sd.NAROU_RANKING_MD).read_text(encoding="utf-8")
    assert "PDF廃止済" in md_text
    assert "本文TXT" in md_text
    assert "総PDFサイズ" not in md_text

    manifest = json.loads((cfg.paths.dataset_dir / sd.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["pdf_purge"]["pdfs_purged"] is True
    assert manifest["pdf_purge"]["converted_from_pdf"] == 2
    assert manifest["pdf_purge"]["removed_pdf_files"] == 3


def test_five_genre_supplement_specs_and_modern_non_isekai_filter():
    categories = [spec["category"] for spec in sd.SUPPLEMENT_GENRE_SPECS]
    assert categories == ["歴史", "推理", "現代", "SF", "ホラー"]

    modern_spec = next(s for s in sd.SUPPLEMENT_GENRE_SPECS if s["category"] == "現代")
    works = [
        # Already in Top 300 -> must be excluded
        Work(
            id="narou:N1000AA",
            source="narou",
            title="既存の現代ドラマ",
            url="https://ncode.syosetu.com/n1000aa/",
            genre={"code": 302, "label": "ヒューマンドラマ〔文芸〕"},
            stats={"char_count": 90000, "episodes": 30, "global_point": 50000},
        ),
        # Modern genre code 306, but has isekai reincarnation flag -> must be excluded
        Work(
            id="narou:N1001BB",
            source="narou",
            title="最強騎士の転生無双",
            url="https://ncode.syosetu.com/n1001bb/",
            genre={"code": 306, "label": "アクション〔文芸〕"},
            stats={"char_count": 90000, "episodes": 30, "global_point": 45000, "elements": ["異世界転生"]},
        ),
        # Modern genre code 102, but villainess/isekai keywords -> must be excluded
        Work(
            id="narou:N1002CC",
            source="narou",
            title="公爵令嬢の婚約破棄",
            url="https://ncode.syosetu.com/n1002cc/",
            genre={"code": 102, "label": "現実世界〔恋愛〕"},
            stats={"char_count": 90000, "episodes": 30, "global_point": 40000},
            extra={"keywords": "悪役令嬢 学園"},
        ),
        # Genuine modern human drama with bunko cue -> must be included
        Work(
            id="narou:N1003DD",
            source="narou",
            title="東京駅の小さな珈琲店【文庫化】",
            url="https://ncode.syosetu.com/n1003dd/",
            genre={"code": 302, "label": "ヒューマンドラマ〔文芸〕"},
            stats={"char_count": 85000, "episodes": 28, "global_point": 12000, "elements": ["R15"]},
            rights={"commercialized": True},
        ),
        # Genuine modern literary fiction -> must be included
        Work(
            id="narou:N1004EE",
            source="narou",
            title="夏休みの終わりに君と見た海",
            url="https://ncode.syosetu.com/n1004ee/",
            genre={"code": 301, "label": "純文学〔文芸〕"},
            stats={"char_count": 70000, "episodes": 20, "global_point": 9000},
        ),
    ]
    queue = sd._build_genre_candidate_queue(
        works,
        genre_codes=modern_spec["genre_codes"],
        require_non_isekai=modern_spec["require_non_isekai"],
        exclude_ids={"narou:n1000aa"},
        min_chars=5000,
        min_episodes=1,
        include_r15=True,
        max_scan=50,
    )
    assert [w.id for w in queue] == ["narou:N1004EE", "narou:N1003DD"] or set(w.id for w in queue) == {
        "narou:N1003DD",
        "narou:N1004EE",
    }


def test_text_only_reuse_requires_no_pdf(tmp_path: Path):
    reuse_txt_dir = tmp_path / "reuse" / "raw" / "narou" / "texts"
    reuse_txt_dir.mkdir(parents=True)
    cached_txt = reuse_txt_dir / "N7777ZZ.txt"
    cached_txt.write_text("宇宙船の航海日誌。" * 200, encoding="utf-8")

    prev_work = Work(
        id="narou:N7777ZZ",
        source="narou",
        title="星間航路の記録",
        url="https://ncode.syosetu.com/n7777zz/",
        stats={"episodes": 25, "char_count": 1800},
    )
    pdfs, txts, prev_map = sd._load_reuse_maps(tmp_path / "reuse")
    prev_map["narou:n7777zz"] = prev_work

    cand = Work(
        id="narou:N7777ZZ",
        source="narou",
        title="星間航路の記録",
        url="https://ncode.syosetu.com/n7777zz/",
        pdf_path="data/pdf/narou/N7777ZZ.pdf",
        stats={"episodes": 25, "char_count": 1800},
        extra={"pdf_bytes": 55555},
    )
    out_raw = tmp_path / "out_raw"
    ok = sd._try_reuse_cached_work(
        cand,
        reuse_pdfs=pdfs,
        reuse_txts=txts,
        reuse_prev=prev_map,
        raw_dir=out_raw,
        pdf_dir=tmp_path / "out_pdf",
        renderer=None,
        cover_note="",
    )
    assert ok is True
    assert cand.pdf_path is None
    assert "pdf_bytes" not in cand.extra
    assert (out_raw / "N7777ZZ.txt").exists()
    assert cand.extra["text_bytes"] > 500


def test_cmd_narou_genre_supplement_end_to_end(tmp_path: Path, monkeypatch):
    cfg = Config(
        paths=PathsConfig(
            raw_dir=tmp_path / "raw",
            pdf_dir=tmp_path / "pdf",
            dataset_dir=tmp_path / "datasets",
            cache_dir=tmp_path / "cache",
            font_dir=tmp_path / "cache" / "fonts",
        )
    )
    cfg.paths.dataset_dir.mkdir(parents=True, exist_ok=True)

    # Top-300 ranked sample (1 work to ensure exclusion)
    ranked_w = Work(
        id="narou:N0001TOP",
        source="narou",
        title="既存ランキング1位",
        url="https://ncode.syosetu.com/n0001top/",
        genre={"code": 201, "label": "ハイファンタジー〔ファンタジー〕"},
        text_path="raw/narou/texts/N0001TOP.txt",
        stats={"episodes": 100, "char_count": 300000, "global_point": 99999},
        rights={"commercialized": True},
        extra={"ranking": {"rank": 1, "is_book": True}},
    )
    sd.store_works(cfg.paths.dataset_dir / sd.NAROU_RANKED, [ranked_w])

    # Build 2 works per target category (歴史=303, 推理=304, 現代=302, SF=402, ホラー=305)
    pool: list[Work] = [ranked_w]
    for cat_idx, gcode in enumerate((303, 304, 302, 402, 305), start=1):
        for k in range(1, 3):
            ncode = f"N{cat_idx}00{k}AA"
            pool.append(
                Work(
                    id=f"narou:{ncode}",
                    source="narou",
                    title=f"商業文庫作品_{gcode}_{k}",
                    url=f"https://ncode.syosetu.com/{ncode.lower()}/",
                    authors=[Author(name=f"作家_{gcode}", role="author")],
                    genre={"code": gcode, "label": f"ジャンル{gcode}"},
                    stats={"episodes": 12, "char_count": 65000, "global_point": 15000 - k * 100},
                    rights={"commercialized": True},
                    extra={"synopsis": "双葉文庫より書籍化発売中"},
                )
            )
    sd.store_works(cfg.paths.dataset_dir / sd.NAROU_WORKS, pool)

    class _DummyNovel:
        def __init__(self) -> None:
            self.text = "第一章\n\n　プレーンテキスト本文です。" * 30
            self.char_count = len(self.text)
            self.chapters = [{"title": f"第{i}話", "paragraphs": ["本文"]} for i in range(1, 13)]
            self.origin = "https://ncode.syosetu.com/mock/"

    def _fake_verify(self, candidates, **kwargs):
        out = []
        for w in candidates:
            w.rights["commercialized"] = True
            w.rights["external_verification"] = {"verified": True, "verified_media": ["book"]}
            w.extra["ranking"] = {
                "ranking_score": float(w.stats.get("global_point") or 0),
                "verified_media": ["book"],
                "is_book": True,
                "publisher": "双葉文庫",
            }
            out.append(w)
        return out

    monkeypatch.setattr(sd.NarouSource, "fetch_anime_ncodes", lambda self: set())
    monkeypatch.setattr(sd.NarouSource, "verify_candidates_external", _fake_verify)
    monkeypatch.setattr(sd.NarouSource, "verify_web_text_available", lambda self, w: True)
    monkeypatch.setattr(sd.NarouSource, "fetch_novel_text", lambda self, ncode, **kw: _DummyNovel())

    args = argparse.Namespace(
        per_genre=2,
        min_per_genre=2,
        scan_limit_per_genre=50,
        min_chars=5000,
        min_episodes=1,
        request_interval=0.01,
        verify_web=True,
        strict_count=True,
        reuse_existing_dir=None,
    )
    sd.cmd_narou_genre_supplement(cfg, args)

    supp = sd.load_works(cfg.paths.dataset_dir / sd.NAROU_GENRE_SUPP)
    assert len(supp) == 10
    assert {w.extra["supplement_category"] for w in supp} == {"歴史", "推理", "現代", "SF", "ホラー"}
    assert "narou:N0001TOP" not in {w.id for w in supp}
    for w in supp:
        assert w.pdf_path is None
        assert w.text_path is not None
        assert w.extra["text_bytes"] > 100

    combined = sd.load_works(cfg.paths.dataset_dir / sd.NAROU_ALL_COMM)
    assert len(combined) == 11  # 1 Top-300 + 10 supplement, zero overlap
    assert list(tmp_path.rglob("*.pdf")) == []


def test_sharded_genre_supplement_and_merge(tmp_path: Path, monkeypatch):
    cfg = Config(
        paths=PathsConfig(
            raw_dir=tmp_path / "raw",
            pdf_dir=tmp_path / "pdf",
            dataset_dir=tmp_path / "datasets",
            cache_dir=tmp_path / "cache",
            font_dir=tmp_path / "cache" / "fonts",
        )
    )
    cfg.paths.dataset_dir.mkdir(parents=True, exist_ok=True)
    ranked_w = Work(
        id="narou:N0001TOP",
        source="narou",
        title="既存ランキング1位",
        url="https://ncode.syosetu.com/n0001top/",
        genre={"code": 201, "label": "ハイファンタジー〔ファンタジー〕"},
        text_path=str(cfg.paths.raw_dir / "narou" / "texts" / "N0001TOP.txt"),
        stats={"episodes": 100, "char_count": 300000, "global_point": 99999},
        rights={"commercialized": True},
        extra={"ranking": {"rank": 1, "is_book": True}},
    )
    sd.store_works(cfg.paths.dataset_dir / sd.NAROU_RANKED, [ranked_w])

    pool: list[Work] = [ranked_w]
    for cat_idx, gcode in enumerate((303, 304, 302, 402, 305), start=1):
        for k in range(1, 3):
            ncode = f"N{cat_idx}99{k}ZZ"
            pool.append(
                Work(
                    id=f"narou:{ncode}",
                    source="narou",
                    title=f"並列シャード作品_{gcode}_{k}",
                    url=f"https://ncode.syosetu.com/{ncode.lower()}/",
                    authors=[Author(name=f"作家_{gcode}", role="author")],
                    genre={"code": gcode, "label": f"ジャンル{gcode}"},
                    stats={"episodes": 10, "char_count": 50000, "global_point": 14000 - k * 100},
                    rights={"commercialized": True},
                    extra={"synopsis": "文庫化発売中"},
                )
            )
    sd.store_works(cfg.paths.dataset_dir / sd.NAROU_WORKS, pool)

    class _DummyNovel:
        def __init__(self) -> None:
            self.text = "第一章\n\n　並列シャードのプレーンテキスト本文です。" * 25
            self.char_count = len(self.text)
            self.chapters = [{"title": f"第{i}話", "paragraphs": ["本文"]} for i in range(1, 11)]
            self.origin = "https://ncode.syosetu.com/mock/"

    def _fake_verify(self, candidates, **kwargs):
        out = []
        for w in candidates:
            w.rights["commercialized"] = True
            w.rights["external_verification"] = {"verified": True, "verified_media": ["book"]}
            w.extra["ranking"] = {
                "ranking_score": float(w.stats.get("global_point") or 0),
                "verified_media": ["book"],
                "is_book": True,
                "publisher": "新潮文庫",
            }
            out.append(w)
        return out

    monkeypatch.setattr(sd.NarouSource, "fetch_anime_ncodes", lambda self: set())
    monkeypatch.setattr(sd.NarouSource, "verify_candidates_external", _fake_verify)
    monkeypatch.setattr(sd.NarouSource, "verify_web_text_available", lambda self, w: True)
    monkeypatch.setattr(sd.NarouSource, "fetch_novel_text", lambda self, ncode, **kw: _DummyNovel())

    for c_idx in range(5):
        sd.cmd_narou_genre_supplement(
            cfg,
            argparse.Namespace(
                per_genre=2,
                min_per_genre=2,
                scan_limit_per_genre=40,
                category_index=c_idx,
                min_chars=5000,
                min_episodes=1,
                request_interval=0.01,
                verify_web=True,
                strict_count=True,
                reuse_existing_dir=None,
            ),
        )
        assert (cfg.paths.dataset_dir / "shards" / f"narou_supplement_cat_{c_idx:02d}.jsonl").exists()

    sd.cmd_narou_merge_supplement_shards(
        cfg,
        argparse.Namespace(shard_dir=None, per_genre=2, min_per_genre=2, strict_count=True),
    )
    supp = sd.load_works(cfg.paths.dataset_dir / sd.NAROU_GENRE_SUPP)
    assert len(supp) == 10
    assert [w.extra["supplement_category"] for w in supp] == [
        "歴史", "歴史", "推理", "推理", "現代", "現代", "SF", "SF", "ホラー", "ホラー"
    ]
    combined = sd.load_works(cfg.paths.dataset_dir / sd.NAROU_ALL_COMM)
    assert len(combined) == 11



def _purge_config(tmp_path: Path) -> Config:
    return Config(paths=PathsConfig(
        raw_dir=tmp_path / "raw", pdf_dir=tmp_path / "pdf",
        dataset_dir=tmp_path / "datasets", cache_dir=tmp_path / "cache",
        font_dir=tmp_path / "fonts",
    ))


def test_purge_refuses_empty_extraction_without_deleting_any_pdf(tmp_path, monkeypatch):
    import pytest
    cfg = _purge_config(tmp_path)
    pdf1 = cfg.paths.pdf_dir / "narou" / "a.pdf"
    pdf2 = cfg.paths.pdf_dir / "narou" / "b.pdf"
    pdf1.parent.mkdir(parents=True)
    pdf1.write_bytes(b"first PDF")
    pdf2.write_bytes(b"second PDF")
    monkeypatch.setattr(sd, "extract_clean_text_from_pdf", lambda p: "valid text" if p == pdf1 else "  ")
    with pytest.raises(ValueError, match="no text extracted"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert pdf1.read_bytes() == b"first PDF"
    assert pdf2.read_bytes() == b"second PDF"
    assert not (cfg.paths.dataset_dir / sd.MANIFEST).exists()


def test_purge_refuses_unrecognized_pdf_without_deleting_any_pdf(tmp_path):
    import pytest
    cfg = _purge_config(tmp_path)
    known = cfg.paths.pdf_dir / "narou" / "known.pdf"
    unknown = cfg.paths.pdf_dir / "other" / "important.PDF"
    known.parent.mkdir(parents=True)
    unknown.parent.mkdir(parents=True)
    known.write_bytes(b"known")
    unknown.write_bytes(b"unknown")
    with pytest.raises(ValueError, match="unrecognized PDF location"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert known.read_bytes() == b"known"
    assert unknown.read_bytes() == b"unknown"


def test_purge_preserves_unrelated_files_and_short_existing_text(tmp_path, monkeypatch):
    import pytest
    cfg = _purge_config(tmp_path)
    pdf = cfg.paths.pdf_dir / "narou" / "known.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf")
    sidecar = cfg.paths.pdf_dir / "notes.txt"
    sidecar.write_text("do not delete", encoding="utf-8")
    existing = cfg.paths.raw_dir / "narou" / "texts" / "known.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("short", encoding="utf-8")
    with pytest.raises(ValueError, match="too short"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert pdf.read_bytes() == b"pdf"
    assert existing.read_text(encoding="utf-8") == "short"
    existing.unlink()
    monkeypatch.setattr(sd, "extract_clean_text_from_pdf", lambda _: "some extracted text")
    sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert not pdf.exists()
    assert sidecar.read_text(encoding="utf-8") == "do not delete"


def test_purge_refuses_blank_or_invalid_existing_text(tmp_path):
    import pytest
    cfg = _purge_config(tmp_path)
    pdf = cfg.paths.pdf_dir / "narou" / "known.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf")
    text = cfg.paths.raw_dir / "narou" / "texts" / "KNOWN.txt"
    text.parent.mkdir(parents=True)
    text.write_text(" " * 200, encoding="utf-8")
    with pytest.raises(ValueError, match="blank"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert pdf.read_bytes() == b"pdf"
    assert text.read_text(encoding="utf-8") == " " * 200
    text.write_bytes(b"\xff" * 200)
    with pytest.raises(UnicodeDecodeError):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert pdf.read_bytes() == b"pdf"
    assert text.read_bytes() == b"\xff" * 200


def test_purge_refuses_symlinked_source_directory_before_copy_or_deletion(tmp_path, monkeypatch):
    import pytest
    cfg = _purge_config(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    external_pdf = outside / "important.pdf"
    external_pdf.write_bytes(b"outside PDF")
    cfg.paths.pdf_dir.mkdir()
    (cfg.paths.pdf_dir / "narou").symlink_to(outside, target_is_directory=True)
    reuse = tmp_path / "reuse" / "raw" / "aozora" / "texts"
    reuse.mkdir(parents=True)
    (reuse / "copy.txt").write_text("not private data " * 20, encoding="utf-8")
    monkeypatch.setattr(sd, "extract_clean_text_from_pdf", lambda _: "nonempty" * 30)
    with pytest.raises(ValueError, match="symbolic link"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=str(tmp_path / "reuse")))
    assert external_pdf.read_bytes() == b"outside PDF"
    assert not (cfg.paths.raw_dir / "aozora" / "texts" / "copy.txt").exists()


def test_purge_refuses_case_colliding_pdfs_before_extraction_or_deletion(tmp_path, monkeypatch):
    import pytest
    cfg = _purge_config(tmp_path)
    pdf_dir = cfg.paths.pdf_dir / "narou"
    pdf_dir.mkdir(parents=True)
    first, second = pdf_dir / "Book.pdf", pdf_dir / "book.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    called = []
    monkeypatch.setattr(sd, "extract_clean_text_from_pdf", lambda p: called.append(p) or "X" * 200)
    with pytest.raises(ValueError, match="ambiguous PDF"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert first.read_bytes() == b"first" and second.read_bytes() == b"second"
    assert called == []
    assert not cfg.paths.raw_dir.exists()


def test_purge_refuses_pdf_file_and_nested_directory_symlinks(tmp_path):
    import pytest
    cfg = _purge_config(tmp_path)
    directory = cfg.paths.pdf_dir / "aozora"
    directory.mkdir(parents=True)
    known = directory / "known.pdf"
    known.write_bytes(b"known")
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "external.pdf"
    external.write_bytes(b"external")
    pdf_link = directory / "linked.PDF"
    pdf_link.symlink_to(external)
    with pytest.raises(ValueError, match="symbolic link"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert known.read_bytes() == b"known" and external.read_bytes() == b"external"
    pdf_link.unlink()
    directory_link = cfg.paths.pdf_dir / "unrecognized"
    directory_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert known.read_bytes() == b"known" and external.read_bytes() == b"external"


def test_purge_refuses_symlinked_pdf_root(tmp_path):
    import pytest
    cfg = _purge_config(tmp_path)
    outside = tmp_path / "outside"
    (outside / "narou").mkdir(parents=True)
    external = outside / "narou" / "external.pdf"
    external.write_bytes(b"external")
    cfg.paths.pdf_dir.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert external.read_bytes() == b"external"


def test_purge_allows_same_pdf_stem_in_different_sources(tmp_path, monkeypatch):
    cfg = _purge_config(tmp_path)
    narou = cfg.paths.pdf_dir / "narou" / "same.pdf"
    aozora = cfg.paths.pdf_dir / "aozora" / "same.pdf"
    for pdf in (narou, aozora):
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"fake PDF")
    monkeypatch.setattr(sd, "extract_clean_text_from_pdf", lambda _: "generated text " * 20)
    sd.cmd_purge_pdfs(cfg, argparse.Namespace(reuse_existing_dir=None))
    assert not narou.exists() and not aozora.exists()
    assert (cfg.paths.raw_dir / "narou" / "texts" / "same.txt").exists()
    assert (cfg.paths.raw_dir / "aozora" / "texts" / "same.txt").exists()
