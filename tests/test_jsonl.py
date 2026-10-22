from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.jsonl import load_jsonl, read_jsonl, write_jsonl  # noqa: E402
from asc.schema import Author, Work  # noqa: E402


def test_jsonl_round_trip(tmp_path: Path):
    path = tmp_path / "sample.jsonl"
    rows = [{"id": "a", "title": "テスト"}, {"id": "b", "title": "日本語"}]
    assert write_jsonl(path, rows) == 2
    assert load_jsonl(path) == rows
    assert [row["id"] for row in read_jsonl(path)] == ["a", "b"]


def test_work_serialisation():
    work = Work(
        id="aozora:000148",
        source="aozora_bunko",
        title="吾輩は猫である",
        url="https://www.aozora.gr.jp/cards/000148/card148.html",
        authors=[Author(name="夏目 漱石", role="author", id="000148")],
        genre={"taxonomy": "NDC", "code": "913", "label": "日本文学／小説"},
        published_year=1905,
        stats={"char_count": 100},
    )
    restored = Work.from_json(work.to_json())
    assert restored == work
    assert restored.primary_author is not None
    assert restored.primary_author.name == "夏目 漱石"
