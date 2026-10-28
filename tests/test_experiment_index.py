"""The curated experiment index is navigation, not a quality ranking."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "experiments"
INDEX = ROOT / "INDEX.md"


def test_index_rows_are_unique_sorted_and_link_to_the_named_experiment():
    text = INDEX.read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([^`]+)` \| \[([^\]]+)\]\(([^)]+)\)", text, re.M)
    ids = [experiment_id for experiment_id, _, _ in rows]
    assert ids and ids == sorted(set(ids))
    for experiment_id, label, link in rows:
        target = ROOT / link
        assert target.resolve().is_relative_to((ROOT / experiment_id).resolve())
        if label == "ノート":
            assert link == f"{experiment_id}/note.md"
            assert target.is_file()
        else:
            assert label == "ディレクトリ"
            assert link == f"{experiment_id}/"
            assert target.is_dir()


def test_index_keeps_different_runs_and_historical_archive_distinct():
    text = INDEX.read_text(encoding="utf-8")
    for experiment_id in ("2026-10-dogfood-01", "2026-10-dogfood-02",
                          "2026-10-dogfood-03", "2026-10-realrun-a-t01",
                          "2026-10-realrun-b-t01", "2026-10-realrun-b2-t01"):
        assert f"{experiment_id}/note.md" in text
    assert "archives/legacy-fixed-canon-b-2026-10-27/README.md" in text
    assert (ROOT / "archives/legacy-fixed-canon-b-2026-10-27/README.md").is_file()
    assert "完了や妥当性の証明ではありません" in text
