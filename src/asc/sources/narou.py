"""Acquisition of Syosetsuka ni Narou material.

Two official endpoints are used:

* the **novel API** (``https://api.syosetu.com/novelapi/api/``) which returns
  bibliographic metadata (title, author, genre, publication dates, episode
  count, character count, ranking information, ...),
* the **novel data download** (``https://ncode.syosetu.com/txtdownload/<ncode>/``)
  and the chapter pages (``https://ncode.syosetu.com/<ncode>/<episode>/``)
  which provide the text of a work.

Only freely published web novels are handled.  Works that were later
commercialised (paper books / e-books) stay the property of their author; the
dataset keeps the metadata and the link to the official page, and only stores
the text that the platform itself offers for download.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

from ..config import REPO_ROOT, NarouConfig, PathsConfig
from ..http import HttpClient
from ..schema import NAROU_SOURCE, Author, Work
from ..text.narou_html import parse_chapter, parse_novel_index

LOGGER = logging.getLogger(__name__)

NAROU_HOME = "https://syosetu.com"
NOVEL_URL_TEMPLATE = "https://ncode.syosetu.com/{ncode}/"
NOVEL_INFO_URL_TEMPLATE = "https://ncode.syosetu.com/novelview/infotop/ncode/{ncode}/"

BIG_GENRES: Dict[int, str] = {
    0: "未選択",
    1: "恋愛",
    2: "ファンタジー",
    3: "文芸",
    4: "SF",
    98: "ノンジャンル",
    99: "その他",
}

GENRES: Dict[int, Dict[str, Any]] = {
    0: {"label": "未選択", "big": 0},
    101: {"label": "異世界", "big": 1},
    102: {"label": "現実世界", "big": 1},
    201: {"label": "ハイファンタジー", "big": 2},
    202: {"label": "ローファンタジー", "big": 2},
    301: {"label": "純文学", "big": 3},
    302: {"label": "ヒューマンドラマ", "big": 3},
    303: {"label": "歴史", "big": 3},
    304: {"label": "推理", "big": 3},
    305: {"label": "ホラー", "big": 3},
    306: {"label": "アクション", "big": 3},
    307: {"label": "コメディー", "big": 3},
    401: {"label": "VRゲーム", "big": 4},
    402: {"label": "宇宙", "big": 4},
    403: {"label": "空想科学", "big": 4},
    404: {"label": "パニック", "big": 4},
    9801: {"label": "ノンジャンル", "big": 98},
    9901: {"label": "童話", "big": 99},
    9902: {"label": "詩", "big": 99},
    9903: {"label": "エッセイ", "big": 99},
    9904: {"label": "リプレイ", "big": 99},
    9999: {"label": "その他", "big": 99},
}

#: Fields that are copied verbatim into the JSONL record.
COPY_FIELDS = (
    "ncode",
    "userid",
    "writer",
    "story",
    "keyword",
    "generalfirstup",
    "generallastup",
    "novelupdated_at",
    "general_all_no",
    "length",
    "time",
    "isstop",
    "isr15",
    "isbl",
    "isgl",
    "iszankoku",
    "istensei",
    "istenni",
    "sasie_cnt",
    "kaiwaritu",
    "fav_novel_cnt",
    "impression_cnt",
    "review_cnt",
    "all_point",
    "all_hyoka_cnt",
    "global_point",
    "novel_type",
    "end",
)


@dataclass
class NovelText:
    """The text of a web novel."""

    ncode: str
    title: Optional[str] = None
    chapters: List[Dict[str, Any]] = None  # type: ignore[assignment]
    origin: str = "web"

    def __post_init__(self) -> None:
        if self.chapters is None:
            self.chapters = []

    @property
    def text(self) -> str:
        return "\n\n".join(chapter.get("text", "") for chapter in self.chapters)

    @property
    def char_count(self) -> int:
        return sum(chapter.get("char_count", 0) for chapter in self.chapters)


class NarouApiClient:
    """Thin wrapper around the official novel API."""

    def __init__(self, config: NarouConfig, client: HttpClient) -> None:
        self.config = config
        self.client = client

    def fetch(self, **params: Any) -> List[Dict[str, Any]]:
        """Query the API and return the list of novels."""
        query: Dict[str, Any] = {"out": "json"}
        query.update({k: v for k, v in params.items() if v is not None})
        url = self.config.api_base + "?" + urlencode(query, doseq=True)
        payload = self.client.get(url)
        data = json.loads(payload.decode("utf-8"))
        if isinstance(data, dict):
            data = [data]
        # the first element only carries the total number of hits
        records = [row for row in data if isinstance(row, dict) and "ncode" in row]
        return records

    def total(self, **params: Any) -> int:
        query: Dict[str, Any] = {"out": "json", "lim": 1}
        query.update({k: v for k, v in params.items() if v is not None})
        url = self.config.api_base + "?" + urlencode(query, doseq=True)
        payload = self.client.get(url)
        data = json.loads(payload.decode("utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return int(data[0].get("allcount") or 0)
        return 0


def normalize_novel(record: Dict[str, Any]) -> Work:
    """Convert one API record into the shared :class:`Work` schema."""
    ncode = record.get("ncode") or ""
    genre_code = record.get("genre")
    big_code = record.get("biggenre")
    genre_info = GENRES.get(genre_code, {})
    big_label = BIG_GENRES.get(big_code, "")

    first_up = record.get("generalfirstup") or ""
    published_at = first_up.split(" ")[0] if first_up else None
    published_year = None
    if published_at and published_at[:4].isdigit():
        published_year = int(published_at[:4])

    tags: List[Dict[str, Any]] = []
    keyword = (record.get("keyword") or "").strip()
    if keyword:
        tags = [{"taxonomy": "keyword", "label": part} for part in keyword.split() if part]

    elements = []
    for key, label in (
        ("isr15", "R15"),
        ("isbl", "ボーイズラブ"),
        ("isgl", "ガールズラブ"),
        ("iszankoku", "残酷な描写あり"),
        ("istensei", "異世界転生"),
        ("istenni", "異世界転移"),
    ):
        if record.get(key):
            elements.append(label)

    work = Work(
        id=f"narou:{ncode}",
        source=NAROU_SOURCE,
        title=record.get("title") or "",
        url=NOVEL_URL_TEMPLATE.format(ncode=ncode.lower()),
        text_url=f"https://ncode.syosetu.com/txtdownload/{ncode.lower()}/",
        authors=[
            Author(
                name=record.get("writer") or "",
                role="author",
                id=str(record.get("userid")) if record.get("userid") is not None else None,
                url=(
                    f"https://mypage.syosetu.com/{record.get('userid')}/"
                    if record.get("userid")
                    else None
                ),
            )
        ],
        genre={
            "taxonomy": "syosetu_genre",
            "code": genre_code,
            "label": genre_info.get("label"),
            "parent": {"taxonomy": "syosetu_big_genre", "code": big_code, "label": big_label},
        },
        genres=tags,
        published_at=published_at,
        published_year=published_year,
        license="小説家になろう掲載作品（著作権は作者に帰属）",
        rights={
            "source": "Syosetsuka ni Narou",
            "commercialized": None,
            "note": (
                "商業化されています。二次利用には作者および小説家になろうの許諾が必要です。"
                "本データセットでは公式サイトが無料公開しているWEB版のみを扱う。"
            ),
        },
        stats={
            "char_count": record.get("length"),
            "episodes": record.get("general_all_no"),
            "read_minutes": record.get("time"),
            "fav_novel_cnt": record.get("fav_novel_cnt"),
            "impression_cnt": record.get("impression_cnt"),
            "review_cnt": record.get("review_cnt"),
            "all_point": record.get("all_point"),
            "all_hyoka_cnt": record.get("all_hyoka_cnt"),
            "global_point": record.get("global_point"),
            "comic_ratio": record.get("kaiwaritu"),
            "illustrations": record.get("sasie_cnt"),
            "is_completed": bool(record.get("end")),
            "is_stopped": bool(record.get("isstop")),
            "elements": elements,
        },
        extra={
            "synopsis": record.get("story"),
            "keywords": keyword,
            "first_up": first_up,
            "last_up": record.get("generallastup"),
            "updated_at": record.get("novelupdated_at"),
            "userid": record.get("userid"),
            "official_info_url": NOVEL_INFO_URL_TEMPLATE.format(ncode=ncode.lower()),
        },
    )
    return work


class NarouSource:
    """Downloads Narou metadata and novel texts."""

    def __init__(self, config: NarouConfig, paths: PathsConfig, client: HttpClient) -> None:
        self.config = config
        self.paths = paths
        self.client = client
        self.api = NarouApiClient(config, client)

    # -- metadata ------------------------------------------------------
    def harvest(self) -> List[Work]:
        """Collect metadata for the configured genres / rankings."""
        works: Dict[str, Work] = {}
        queries: List[Dict[str, Any]] = []

        for genre in self.config.genres:
            queries.append({"genre": genre})
            queries.append({"genre": genre, "order": "favnovelcnt"})
        for order in self.config.orders:
            queries.append({"order": order})

        for query in queries:
            try:
                records = self._paginate(query)
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("query %s failed: %s", query, exc)
                continue
            for record in records:
                work = normalize_novel(record)
                works.setdefault(work.id, work)
            LOGGER.info("query %s -> %s novels (total %s)", query, len(records), len(works))
        return list(works.values())

    def _paginate(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        start = 1
        limit = min(self.config.per_query, 500)
        while start <= self.config.max_start:
            page = self.api.fetch(lim=limit, st=start, **query)
            if not page:
                break
            records.extend(page)
            if len(page) < limit:
                break
            start += limit
        return records

    # -- text ----------------------------------------------------------
    def fetch_novel_text(self, ncode: str, max_episodes: int = 0) -> NovelText:
        """Download the text of a novel (official data download or chapters)."""
        ncode = ncode.lower()
        novel = NovelText(ncode=ncode)

        # 0) already downloaded texts
        if self.config.text_source in {"auto", "local"}:
            local = self._load_local_novel(ncode, max_episodes)
            if local is not None:
                if local.chapters or self.config.text_source == "local":
                    novel.chapters = local.chapters
                    novel.origin = "local files"
                    return novel
        if self.config.text_source == "local":
            return novel

        # 1) official bulk text download
        url = f"https://ncode.syosetu.com/txtdownload/{ncode}/"
        try:
            payload = self.client.get(url)
            novel.chapters = self._chapters_from_zip(payload)
            if novel.chapters:
                novel.origin = "official data download"
                return novel
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.debug("txtdownload unavailable for %s: %s", ncode, exc)

        # 2) chapter pages
        index_url = NOVEL_URL_TEMPLATE.format(ncode=ncode)
        try:
            index_html = self.client.get_text(index_url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("cannot read the index of %s: %s", ncode, exc)
            return novel

        entries = parse_novel_index(index_html, ncode)
        if not entries:
            entries = [(1, None, f"{index_url}1/")]
        for index, title, chapter_url in entries:
            if max_episodes and index > max_episodes:
                break
            try:
                html = self.client.get_text(chapter_url)
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("cannot download %s: %s", chapter_url, exc)
                continue
            chapter = parse_chapter(html, index=index, url=chapter_url)
            novel.chapters.append(
                {
                    "index": index,
                    "title": chapter.title or title,
                    "url": chapter_url,
                    "paragraphs": chapter.paragraphs,
                    "text": chapter.text,
                    "char_count": chapter.char_count,
                }
            )
        novel.origin = "chapter pages"
        return novel

    def _load_local_novel(self, ncode: str, max_episodes: int = 0) -> Optional[NovelText]:
        """Load a novel from ``<local_text_dir>/<ncode>/<index>.txt``.

        The first line of a chapter file may start with ``# `` and then holds
        the chapter title; the remaining lines are the paragraphs (separated
        by blank lines).
        """
        if not self.config.local_text_dir:
            return None
        folder = Path(self.config.local_text_dir) / ncode
        if not folder.is_dir():
            return None
        files = sorted(folder.glob("*.txt"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
        novel = NovelText(ncode=ncode, origin="local files")
        for position, path in enumerate(files, start=1):
            if max_episodes and position > max_episodes:
                break
            raw = path.read_text(encoding="utf-8")
            title = None
            lines = raw.split("\n")
            if lines and lines[0].startswith("# "):
                title = lines[0][2:].strip()
                lines = lines[1:]
            paragraphs = [line.strip() for line in lines if line.strip()]
            novel.chapters.append(
                {
                    "index": position,
                    "title": title,
                    "url": f"https://ncode.syosetu.com/{ncode}/{position}/",
                    "paragraphs": paragraphs,
                    "text": "\n\n".join(paragraphs),
                    "char_count": sum(len(p) for p in paragraphs),
                }
            )
        return novel

    @staticmethod
    def _chapters_from_zip(payload: bytes) -> List[Dict[str, Any]]:
        """Parse the ZIP returned by the official data download."""
        chapters: List[Dict[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = sorted(
                (n for n in archive.namelist() if n.lower().endswith(".txt")),
                key=lambda n: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", n)],
            )
            for position, name in enumerate(names, start=1):
                raw = archive.read(name)
                text = raw.decode("utf-8", errors="replace")
                paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
                chapters.append(
                    {
                        "index": position,
                        "title": None,
                        "url": None,
                        "paragraphs": paragraphs,
                        "text": "\n\n".join(paragraphs),
                        "char_count": sum(len(p) for p in paragraphs),
                    }
                )
        return chapters
