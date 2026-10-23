"""Statistics and validation of the generated datasets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .jsonl import read_jsonl

DATASETS = {
    "aozora_works.jsonl": "青空文庫 (Aozora Bunko)",
    "aozora_authors.jsonl": "青空文庫 作家",
    "narou_novels.jsonl": "小説家になろう (Syosetsuka ni Narou)",
    "narou_commercialized_ranked.jsonl": "小説家になろう 外部確認済・商業化ランキング",
}


@dataclass
class DatasetStats:
    name: str
    title: str
    works: int = 0
    authors: int = 0
    with_text: int = 0
    with_pdf: int = 0
    commercialized: int = 0
    copyrighted: int = 0
    total_chars: int = 0
    years: Counter = field(default_factory=Counter)
    genres: Counter = field(default_factory=Counter)
    big_genres: Counter = field(default_factory=Counter)
    missing_fields: Counter = field(default_factory=Counter)
    sample: List[Dict[str, Any]] = field(default_factory=list)
    path: Optional[str] = None


class DatasetReport:
    def __init__(self, dataset_dir: Path) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.stats: Dict[str, DatasetStats] = {}

    # ------------------------------------------------------------------
    def build(self) -> "DatasetReport":
        for filename, title in DATASETS.items():
            path = self.dataset_dir / filename
            if not path.exists():
                continue
            stats = DatasetStats(name=filename, title=title, path=str(path))
            for row in read_jsonl(path):
                stats.works += 1
                if filename == "aozora_authors.jsonl":
                    stats.authors += 1
                    if len(stats.sample) < 5:
                        stats.sample.append(row)
                    continue
                stats.authors = len(
                    {a.get("id") for a in row.get("authors") or [] if a.get("id")}
                ) or stats.authors
                if row.get("text_path"):
                    stats.with_text += 1
                if row.get("pdf_path"):
                    stats.with_pdf += 1
                rights = row.get("rights") or {}
                if rights.get("commercialized") is True:
                    stats.commercialized += 1
                if rights.get("copyright_flag") is True:
                    stats.copyrighted += 1
                chars = (row.get("stats") or {}).get("char_count")
                if isinstance(chars, int):
                    stats.total_chars += chars
                year = row.get("published_year")
                if year:
                    stats.years[year] += 1
                genre = row.get("genre") or {}
                label = genre.get("label") or genre.get("code")
                if label:
                    stats.genres[str(label)] += 1
                parent = genre.get("parent") or {}
                if parent.get("label"):
                    stats.big_genres[str(parent["label"])] += 1
                for field_name in ("id", "title", "url", "genre", "published_at"):
                    if not row.get(field_name):
                        stats.missing_fields[field_name] += 1
                if len(stats.sample) < 5:
                    stats.sample.append(row)
            self.stats[filename] = stats
        return self

    # ------------------------------------------------------------------
    def render_text(self) -> str:
        lines: List[str] = []
        lines.append(f"dataset directory: {self.dataset_dir}")
        lines.append("")
        for filename, stats in self.stats.items():
            lines.append(f"== {stats.title}  ({filename})")
            lines.append(f"   records          : {stats.works}")
            if filename != "aozora_authors.jsonl":
                lines.append(f"   with plain text  : {stats.with_text}")
                lines.append(f"   with PDF         : {stats.with_pdf}")
                if stats.commercialized:
                    lines.append(f"   commercialized   : {stats.commercialized}")
                if stats.copyrighted:
                    lines.append(f"   copyright active : {stats.copyrighted}")
                lines.append(f"   total characters : {stats.total_chars:,}")
                if stats.years:
                    first = min(stats.years)
                    last = max(stats.years)
                    lines.append(f"   publication years: {first} - {last}")
                    for decade, count in sorted(_decades(stats.years).items()):
                        bar = "#" * min(40, count)
                        lines.append(f"     {decade}: {count:>6} {bar}")
                if stats.genres:
                    lines.append("   genres:")
                    for label, count in stats.genres.most_common(15):
                        lines.append(f"     {label:<24} {count}")
                if stats.big_genres:
                    lines.append("   top level genres:")
                    for label, count in stats.big_genres.most_common(10):
                        lines.append(f"     {label:<24} {count}")
                if stats.missing_fields:
                    lines.append("   missing fields:")
                    for field_name, count in stats.missing_fields.most_common():
                        lines.append(f"     {field_name:<24} {count}")
            lines.append("")
        return "\n".join(lines)


def _decades(years: Counter) -> Dict[str, int]:
    buckets: Counter = Counter()
    for year, count in years.items():
        buckets[f"{year // 10 * 10}s"] += count
    return dict(buckets)


def build_report(dataset_dir: Path) -> DatasetReport:
    return DatasetReport(dataset_dir).build()
