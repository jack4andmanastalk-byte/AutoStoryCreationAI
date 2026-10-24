"""``aozora-texts --ids-file`` must fetch exactly the requested works.

Fully offline: the mirror, the index and the text fetch are all stubbed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import setup_dataset as setup  # noqa: E402
from asc.config import Config, PathsConfig  # noqa: E402


def make_work(work_id: str) -> dict:
    return {"id": work_id, "source": "aozora", "title": f"作品{work_id}",
            "url": "https://example.invalid/",
            "rights": {"copyright_flag": False}}


def test_ids_file_fetches_exactly_the_requested_ids(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    works_path = dataset_dir / "aozora_works.jsonl"
    works_path.write_text("\n".join(json.dumps(make_work(f"aozora:{i:06d}"))
                                    for i in (1, 2, 3)) + "\n", encoding="utf-8")
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("aozora:000002\naozora:000003\naozora:999999\n",
                        encoding="utf-8")

    cfg = Config(paths=PathsConfig(
        raw_dir=tmp_path / "raw", pdf_dir=tmp_path / "pdf",
        dataset_dir=dataset_dir, cache_dir=tmp_path / "cache",
        font_dir=tmp_path / "fonts"))
    fetched: list[str] = []

    def fake_fetch(self, work, index=None):
        fetched.append(work.id)
        return f"raw text of {work.id}"

    monkeypatch.setattr(setup.AozoraSource, "ensure_text_mirror",
                        lambda self: tmp_path)
    monkeypatch.setattr(setup.AozoraSource, "text_index", lambda self: {})
    monkeypatch.setattr(setup.AozoraSource, "fetch_text", fake_fetch)
    monkeypatch.setattr(
        setup, "parse_aozora_text",
        lambda raw: SimpleNamespace(text=f"parsed {raw}", char_count=100,
                                    blocks=[{"type": "paragraph", "text": raw}]))

    args = argparse.Namespace(works=None, ids_file=str(ids_file), pdf=False)
    setup.cmd_aozora_texts(cfg, args)

    assert fetched == ["aozora:000002", "aozora:000003"]
    assert (tmp_path / "raw/aozora/texts/000002.txt").exists()
    assert (tmp_path / "raw/aozora/texts/000003.txt").exists()
    assert not (tmp_path / "raw/aozora/texts/000001.txt").exists()
    rows = [json.loads(line) for line in
            works_path.read_text(encoding="utf-8").splitlines()]
    by_id = {row["id"]: row for row in rows}
    assert by_id["aozora:000002"]["stats"]["char_count"] == 100
    assert by_id["aozora:000001"]["stats"] == {}
