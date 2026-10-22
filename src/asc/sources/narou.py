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

import html as html_lib
import io
import json
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote, urlencode

from ..config import REPO_ROOT, NarouConfig, PathsConfig
from ..http import HttpClient
from ..schema import NAROU_SOURCE, Author, Work
from ..text.narou_html import parse_chapter, parse_index_max_page, parse_novel_index

LOGGER = logging.getLogger(__name__)

NAROU_HOME = "https://syosetu.com"
NOVEL_URL_TEMPLATE = "https://ncode.syosetu.com/{ncode}/"
NOVEL_INFO_URL_TEMPLATE = "https://ncode.syosetu.com/novelview/infotop/ncode/{ncode}/"
ANIME_LIST_URL = "https://syosetu.com/commercialization/anime/"
SYUPPAN_SEARCH_URL = "https://syosetu.com/syuppan/list/?word={word}"

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

#: Markers that indicate a commercialisation notice on the official page.
COMMERCIAL_MARKERS = (
    "商業化",
    "書籍化",
    "コミカライズ",
    "アニメ化",
    "ゲーム化",
    "漫画化",
    "文庫化",
    "メディアミックス",
    "単行本",
)

COMMERCIAL_TAG_SET = frozenset(
    {
        "商業化",
        "書籍化",
        "書籍化決定",
        "電子書籍化",
        "コミカライズ",
        "コミカライズ決定",
        "アニメ化",
        "アニメ化決定",
        "ゲーム化",
        "漫画化",
        "文庫化",
        "メディアミックス",
    }
)

TITLE_COMMERCIAL_RE = re.compile(
    r"(書籍化|商業化|コミカライズ|アニメ化|ゲーム化|漫画化|文庫化|メディアミックス|映画化|劇場版|\d+巻[^】\n]{0,12}発売)"
)
SYNOPSIS_COMMERCIAL_RE = re.compile(
    r"(書籍化|商業化|コミカライズ|アニメ化|ゲーム化|漫画化|文庫化|メディアミックス|映画化|劇場版|ドラマCD化|"
    r"書籍[：:\s]*[^\n]{1,24}(?:巻|発売|刊行)|アニメ\s*[1-9１-９一二三四]期|"
    r"書籍発売|巻発売|発売中|重版出来|"
    r"文庫(?:より|にて|様|さん|から)|ブックス(?:より|にて|様|さん|から)|"
    r"ノベル[スズ](?:より|にて|様|さん|から)|コミックス)"
)
NEGATIVE_COMMERCIAL_RE = re.compile(
    r"(自主出版|同人|(?:書籍化|商業化|コミカライズ|アニメ化)[^\n。]{0,8}(?:目指|希望|目標|夢|したい|できたら))"
)
INFO_ERROR_RE = re.compile(
    r"(<title>\s*エラー|該当する小説が存在しません|小説が存在しません|削除されました|投稿済作品が見つかりません)"
)
DIGEST_STUB_RE = re.compile(
    r"(ダイジェスト版のため削除|書籍化に伴い[^\n。]{0,20}削除|試し読み版のみ)"
)


def detect_commercialized_from_metadata(
    title: str,
    keyword: str,
    synopsis: str,
    *,
    genre_code: Optional[int] = None,
    fav_novel_cnt: Optional[int] = None,
    all_point: Optional[int] = None,
) -> Tuple[Optional[bool], List[str]]:
    """Detect commercialisation markers present in the official API metadata.

    Returns ``(True, markers)`` when unambiguous commercialisation markers are
    found, or ``(None, [])`` when unknown from metadata alone.
    """
    if genre_code in (9903, 9904, 9999):
        return None, []
    combined = f"{title}\n{keyword}\n{synopsis}"
    if NEGATIVE_COMMERCIAL_RE.search(combined):
        return None, []
    # Filter out 0-bookmark spam/essays when popularity stats are present
    if fav_novel_cnt is not None or all_point is not None:
        if (fav_novel_cnt or 0) < 20 and (all_point or 0) < 100:
            return None, []

    markers: List[str] = []
    kw_tokens = set(keyword.split()) if keyword else set()
    for tag in sorted(kw_tokens & COMMERCIAL_TAG_SET):
        markers.append(tag)
    for match in TITLE_COMMERCIAL_RE.finditer(title or ""):
        token = match.group(1)
        if token not in markers:
            markers.append(token)
    for match in SYNOPSIS_COMMERCIAL_RE.finditer(synopsis or ""):
        token = match.group(1)
        if token not in markers:
            markers.append(token)
    if markers:
        return True, markers
    return None, []


def parse_commercialized_info_html(html: str) -> Optional[bool]:
    """Inspect a Narou ``infotop`` HTML page for commercialisation notices.

    Care is taken to:
    * ignore the hidden bookmark-modal template (which contains the literal
      string ``エラーが発生しました`` on every live page), and
    * strip the ``同一作者の作品`` section so other works by the same author do
      not trigger a false positive.
    """
    if not html or INFO_ERROR_RE.search(html):
        return None
    main_section = html.split("同一作者の作品", 1)[0]
    main_section = re.sub(r"<script\b[^>]*>.*?</script>", " ", main_section, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", main_section)
    if NEGATIVE_COMMERCIAL_RE.search(text):
        return False
    for marker in COMMERCIAL_MARKERS:
        if marker in text:
            return True
    return False


def parse_anime_commercialization_html(html: str) -> Set[str]:
    """Extract lowercase N-codes linked on ``syosetu.com/commercialization/anime/``."""
    if not html:
        return set()
    return {
        m.group(1).lower()
        for m in re.finditer(r"ncode\.syosetu\.com/(n[0-9a-z]+)/?", html, flags=re.I)
    }


def extract_syuppan_search_word(title: str) -> str:
    """Extract a clean core Japanese title prefix safe for ``syuppan/list/?word=``.

    Strips promotional brackets (``【アニメ化！】``), subtitles after ``～`` / ``-``,
    and ASCII punctuation (such as ``:``) that trigger WAF 403 responses on
    ``syosetu.com/syuppan/list/``.
    """
    if not title:
        return ""
    norm = unicodedata.normalize("NFKC", html_lib.unescape(title)).strip()
    # Remove bracketed promotional tags at start/end or inline 【...】
    norm = re.sub(r"【[^】]*】|\[[^\]]*\]|［[^］]*］", " ", norm).strip()
    # Split before subtitle markers when core prefix is meaningful
    for sep in ("~", "～", "〜", " - ", " ―", " —", "サブタイトル"):
        if sep in norm:
            head = norm.split(sep, 1)[0].strip()
            if len(head) >= 3:
                norm = head
                break
    # Split on ':' or '/' and pick the first segment with >=3 Japanese chars
    segments = [seg.strip() for seg in re.split(r"[:：/／!！?？]+", norm) if seg.strip()]
    chosen = ""
    for seg in segments:
        cleaned = re.sub(r"[A-Za-z0-9_\-+*&^%$#@=~`'\"<>|\\\s]+", "", seg)
        if len(cleaned) >= 3:
            chosen = cleaned
            break
    if not chosen:
        chosen = re.sub(r"[^\u3040-\u30ff\u3400-\u9fff\uff66-\uff9fー々〆〇]+", "", norm)
    return chosen[:10]


def parse_syuppan_list_html(html: str, userid: Optional[str] = None) -> Dict[str, Any]:
    """Parse ``syosetu.com/syuppan/list/?word=...`` results.

    When ``userid`` is given, only entries linking ``mypage.syosetu.com/<userid>/``
    are counted so homonymous titles by other authors never cause false matches.
    """
    result: Dict[str, Any] = {
        "matched": False,
        "volumes": 0,
        "publisher": None,
        "label": None,
    }
    if not html or "検索条件に一致する書報がありません" in html:
        return result

    main = html.split("書報を探す", 1)[0]
    # Group chunks by unique bookid
    matches = list(re.finditer(r"/syuppan/view/bookid/(\d+)/?", main))
    if not matches:
        return result

    book_Order: List[str] = []
    book_spans: Dict[str, List[int]] = {}
    for m in matches:
        bid = m.group(1)
        if bid not in book_spans:
            book_Order.append(bid)
            book_spans[bid] = [m.start(), m.end()]
        else:
            book_spans[bid][1] = m.end()

    matched_count = 0
    for idx, bid in enumerate(book_Order):
        start = book_spans[bid][0]
        end = book_spans[book_Order[idx + 1]][0] if idx + 1 < len(book_Order) else len(main)
        chunk = main[start:end]
        if userid:
            uid_pat = rf"mypage\.syosetu\.com/(?:mypage/top/userid/)?{re.escape(str(userid))}/?"
            if not re.search(uid_pat, chunk):
                continue
        matched_count += 1
        if result["publisher"] is None:
            plain = re.sub(r"<[^>]+>", "\n", html_lib.unescape(chunk))
            lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
            for i, ln in enumerate(lines):
                if ln.startswith("出版社"):
                    val = ln[len("出版社") :].strip(" ：:")
                    if not val and i + 1 < len(lines):
                        val = lines[i + 1]
                    if val:
                        result["publisher"] = val
                elif ln.startswith("レーベル"):
                    val = ln[len("レーベル") :].strip(" ：:")
                    if not val and i + 1 < len(lines):
                        val = lines[i + 1]
                    if val:
                        result["label"] = val

    result["matched"] = matched_count > 0
    result["volumes"] = matched_count
    return result


def _kanji_number_to_int(token: str) -> int:
    norm = unicodedata.normalize("NFKC", token)
    if norm.isdigit():
        return int(norm)
    kanji_digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if norm == "十":
        return 10
    if "十" in norm:
        left, _, right = norm.partition("十")
        tens = kanji_digits.get(left, 1) if left else 1
        ones = kanji_digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return kanji_digits.get(norm, 0)


def estimate_volumes_from_text(text: str) -> int:
    """Estimate published book volume count mentioned in title/synopsis."""
    if not text:
        return 0
    norm = unicodedata.normalize("NFKC", text)
    best = 0
    for m in re.finditer(
        r"(?:書籍|文庫|単行本|ノベル[スズ]?|ブックス|既刊|現在|全)[^\n。]{0,16}?(\d{1,2}|[一二三四五六七八九十]{1,3})\s*巻",
        norm,
    ):
        val = _kanji_number_to_int(m.group(1))
        if 1 <= val <= 60:
            best = max(best, val)
    for m in re.finditer(r"(\d{1,2})\s*巻[^\n。]{0,8}(?:発売|刊行)", norm):
        val = int(m.group(1))
        if 1 <= val <= 60:
            best = max(best, val)
    return best


def compute_popularity_ranking_score(work: Work) -> Dict[str, Any]:
    """Compute a composite fame / sales-longevity / popularity / evaluation score.

    Components:
    * ``global_point`` (Narou official 総合評価 = ``fav_novel_cnt * 2 + all_point``)
    * ``anime_bonus`` (+60,000 when TV/theatrical anime adaptation is confirmed)
    * ``game_bonus`` (+25,000 when game adaptation is confirmed)
    * ``comic_bonus`` (+15,000 when comic adaptation is confirmed)
    * ``volume_bonus`` (``min(estimated_volumes, 30) * 2,500``, up to +75,000 as a
      sales/series-longevity proxy from official 書報 & synopsis volume counts)
    * ``review_bonus`` (``min(review_cnt, 500) * 20``, up to +10,000)
    """
    stats = work.stats or {}
    rights = work.rights or {}
    extra = work.extra or {}
    existing = extra.get("ranking") or {}

    fav = int(stats.get("fav_novel_cnt") or 0)
    all_pt = int(stats.get("all_point") or 0)
    global_pt = int(stats.get("global_point") or (fav * 2 + all_pt))
    hyoka_cnt = int(stats.get("all_hyoka_cnt") or 0)
    review_cnt = int(stats.get("review_cnt") or 0)

    markers = set(rights.get("markers") or [])
    combined_text = "\n".join(
        filter(None, [work.title, extra.get("keywords"), extra.get("synopsis")])
    )
    is_anime = bool(
        existing.get("is_anime")
        or any("アニメ" in m or "劇場版" in m or "映画" in m for m in markers)
        or re.search(r"(アニメ化|TVアニメ|アニメ\s*[1-9１-９一二三四]期|劇場版|アニメ放送)", combined_text)
    )
    is_game = bool(
        existing.get("is_game")
        or any("ゲーム" in m for m in markers)
        or "ゲーム化" in combined_text
    )
    is_comic = bool(
        existing.get("is_comic")
        or any("コミカライズ" in m or "漫画" in m or "コミック" in m for m in markers)
        or re.search(r"(コミカライズ|漫画化|コミック)", combined_text)
    )

    syuppan_vols = int(existing.get("syuppan_volumes") or 0)
    text_vols = estimate_volumes_from_text(combined_text)
    est_vols = max(syuppan_vols, text_vols, 1 if rights.get("commercialized") is True else 0)

    score = (
        float(global_pt)
        + (60_000.0 if is_anime else 0.0)
        + (25_000.0 if is_game else 0.0)
        + (15_000.0 if is_comic else 0.0)
        + min(est_vols, 30) * 2_500.0
        + min(review_cnt, 500) * 20.0
    )
    return {
        "rank": existing.get("rank"),
        "ranking_score": round(score, 1),
        "global_point": global_pt,
        "fav_novel_cnt": fav,
        "all_point": all_pt,
        "all_hyoka_cnt": hyoka_cnt,
        "review_cnt": review_cnt,
        "syuppan_volumes": syuppan_vols,
        "estimated_volumes": est_vols,
        "is_anime": is_anime,
        "is_comic": is_comic,
        "is_game": is_game,
        "publisher": existing.get("publisher"),
        "label": existing.get("label"),
        "signals": list(existing.get("signals") or []),
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


#: The official API accepts short codes in the ``of=`` parameter and answers
#: with the long field names below.  Hand written fixtures and cached
#: responses may use the short codes or slightly different spellings, so every
#: field is looked up through a list of aliases.
FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "title": ("title", "t"),
    "ncode": ("ncode", "n"),
    "userid": ("userid", "u"),
    "writer": ("writer", "w"),
    "story": ("story", "s"),
    "keyword": ("keyword", "k"),
    "biggenre": ("biggenre", "bg"),
    "genre": ("genre", "g"),
    "generalfirstup": ("general_firstup", "generalfirstup", "gf"),
    "generallastup": ("general_lastup", "generallastup", "gl"),
    "noveltype": ("noveltype", "novel_type", "nt"),
    "end": ("end", "e"),
    "general_all_no": ("general_all_no", "ga"),
    "length": ("length", "l"),
    "time": ("time", "ti"),
    "isr15": ("isr15", "ir"),
    "isbl": ("isbl", "ibl"),
    "isgl": ("isgl", "igl"),
    "iszankoku": ("iszankoku", "izk"),
    "istensei": ("istensei", "its"),
    "istenni": ("istenni", "iti"),
    "fav_novel_cnt": ("fav_novel_cnt", "f"),
    "impression_cnt": ("impression_cnt", "i"),
    "review_cnt": ("review_cnt", "r"),
    "all_point": ("all_point", "a"),
    "all_hyoka_cnt": ("all_hyoka_cnt", "ah"),
    "global_point": ("global_point", "gp"),
    "sasie_cnt": ("sasie_cnt", "sa"),
    "kaiwaritu": ("kaiwaritu", "ka"),
}


def api_field(record: Dict[str, Any], name: str, default: Any = None) -> Any:
    """Read one field of an API record, tolerating the different spellings."""
    for alias in FIELD_ALIASES.get(name, (name,)):
        value = record.get(alias)
        if value is not None:
            return value
    return default


def normalize_novel(record: Dict[str, Any]) -> Work:
    """Convert one API record into the shared :class:`Work` schema."""
    ncode = api_field(record, "ncode") or ""
    genre_code = api_field(record, "genre")
    big_code = api_field(record, "biggenre")
    genre_info = GENRES.get(genre_code, {})
    big_label = BIG_GENRES.get(big_code, "")

    first_up = api_field(record, "generalfirstup") or ""
    published_at = first_up.split(" ")[0] if first_up else None
    published_year = None
    if published_at and published_at[:4].isdigit():
        published_year = int(published_at[:4])

    tags: List[Dict[str, Any]] = []
    keyword = html_lib.unescape(api_field(record, "keyword") or "").strip()
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
        if api_field(record, key):
            elements.append(label)

    title = html_lib.unescape(api_field(record, "title") or "")
    writer = html_lib.unescape(api_field(record, "writer") or "")
    synopsis = html_lib.unescape(api_field(record, "story") or "")
    fav_novel_cnt = api_field(record, "fav_novel_cnt")
    all_point = api_field(record, "all_point")
    global_point = api_field(record, "global_point")
    if global_point is None and (fav_novel_cnt is not None or all_point is not None):
        global_point = int(fav_novel_cnt or 0) * 2 + int(all_point or 0)
    commercialized, comm_markers = detect_commercialized_from_metadata(
        title,
        keyword,
        synopsis,
        genre_code=genre_code,
        fav_novel_cnt=fav_novel_cnt,
        all_point=all_point,
    )
    rights_note = (
        "この作品は商業化されています。商業版（紙書籍・電子書籍）は再配布せず、"
        "本データセットでは公式サイトが無料公開しているWEB版のみを扱います。"
        "二次利用には作者の許諾が必要です。"
        if commercialized
        else (
            "小説家になろう利用規約に従い、公式サイトが無料公開しているWEB版のみを扱う。"
            "二次利用には作者の許諾が必要です。"
        )
    )
    rights_obj: Dict[str, Any] = {
        "source": "Syosetsuka ni Narou",
        "commercialized": commercialized,
        "note": rights_note,
    }
    if comm_markers:
        rights_obj["markers"] = comm_markers

    userid_val = api_field(record, "userid")
    work = Work(
        id=f"narou:{ncode}",
        source=NAROU_SOURCE,
        title=title,
        url=NOVEL_URL_TEMPLATE.format(ncode=ncode.lower()),
        text_url=f"https://ncode.syosetu.com/txtdownload/{ncode.lower()}/",
        authors=[
            Author(
                name=writer,
                role="author",
                id=str(userid_val) if userid_val is not None else None,
                url=f"https://mypage.syosetu.com/{userid_val}/" if userid_val else None,
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
        rights=rights_obj,
        stats={
            "char_count": api_field(record, "length"),
            "episodes": api_field(record, "general_all_no"),
            "read_minutes": api_field(record, "time"),
            "fav_novel_cnt": fav_novel_cnt,
            "impression_cnt": api_field(record, "impression_cnt"),
            "review_cnt": api_field(record, "review_cnt"),
            "all_point": all_point,
            "all_hyoka_cnt": api_field(record, "all_hyoka_cnt"),
            "global_point": global_point,
            "comic_ratio": api_field(record, "kaiwaritu"),
            "illustrations": api_field(record, "sasie_cnt"),
            "is_completed": bool(api_field(record, "end")),
            "is_stopped": bool(api_field(record, "isstop")),
            "elements": elements,
        },
        extra={
            "synopsis": synopsis or None,
            "keywords": keyword,
            "first_up": first_up,
            "last_up": api_field(record, "generallastup"),
            "updated_at": api_field(record, "novelupdated_at"),
            "userid": userid_val,
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
    def _accept_work(self, work: Work) -> bool:
        if not self.config.include_r15 and "R15" in (work.stats.get("elements") or []):
            return False
        return True

    def _load_cached_api_files(self, works: Dict[str, Work]) -> None:
        candidate_paths: List[Path] = []
        seen_paths: Set[Path] = set()
        for file_entry in self.config.api_response_files:
            path = Path(file_entry)
            if not path.is_absolute():
                path = REPO_ROOT / path
            resolved = path.resolve()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                candidate_paths.append(path)
        api_cache_dir = self.paths.cache_dir / "narou_api"
        if api_cache_dir.is_dir():
            for path in sorted(api_cache_dir.glob("*.json")):
                resolved = path.resolve()
                if resolved not in seen_paths:
                    seen_paths.add(resolved)
                    candidate_paths.append(path)

        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                LOGGER.warning("cannot read cached API response %s: %s", path, exc)
                continue
            if isinstance(data, dict):
                data = data.get("records") or [data]
            if not isinstance(data, list):
                continue
            added = 0
            for record in data:
                if not isinstance(record, dict) or api_field(record, "ncode") is None:
                    continue
                work = normalize_novel(record)
                if self._accept_work(work) and work.id not in works:
                    works[work.id] = work
                    added += 1
            LOGGER.info("loaded %s novels from %s (total %s)", added, path.name, len(works))

    def harvest(self, cached_only: bool = False) -> List[Work]:
        """Collect metadata from cached API dumps and/or live API queries."""
        works: Dict[str, Work] = {}
        self._load_cached_api_files(works)
        if cached_only and works:
            return list(works.values())

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
                if self._accept_work(work):
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

    # -- commercialisation ---------------------------------------------
    def fetch_anime_ncodes(self) -> Set[str]:
        """Fetch official anime-adapted N-codes from syosetu.com."""
        try:
            html = self.client.get_text(ANIME_LIST_URL)
            codes = parse_anime_commercialization_html(html)
            LOGGER.info("loaded %s anime-adapted N-codes from %s", len(codes), ANIME_LIST_URL)
            return codes
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("cannot read %s: %s", ANIME_LIST_URL, exc)
            return set()

    def check_syuppan(self, title: str, userid: Optional[str] = None) -> Dict[str, Any]:
        """Search official 書報 (``syosetu.com/syuppan/list/``) for a work."""
        word = extract_syuppan_search_word(title)
        if len(word) < 3:
            return {"matched": False, "volumes": 0, "publisher": None, "label": None}
        url = SYUPPAN_SEARCH_URL.format(word=quote(word, safe=""))
        try:
            html = self.client.get_text(url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.debug("syuppan lookup failed for %s (%s): %s", title, word, exc)
            return {"matched": False, "volumes": 0, "publisher": None, "label": None}
        return parse_syuppan_list_html(html, userid=userid)

    def check_commercialized(self, ncode: str) -> Optional[bool]:
        """Check the official information page for a commercialisation banner.

        Commercialised works show a notice on their information page
        (「この作品は商業化されています」「書籍化」…).  The commercial edition
        itself is **not** downloaded - only the free web version is.
        """
        url = NOVEL_INFO_URL_TEMPLATE.format(ncode=ncode.lower())
        try:
            html = self.client.get_text(url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.debug("cannot read the info page of %s: %s", ncode, exc)
            return None
        result = parse_commercialized_info_html(html)
        if result is True:
            LOGGER.info("%s confirmed commercialised via info page", ncode)
        return result

    def verify_web_text_available(self, work: Work) -> bool:
        """Confirm that the free WEB edition is live and non-stubbed."""
        ncode = work.id.split(":", 1)[1].lower()
        synopsis = (work.extra or {}).get("synopsis") or ""
        if DIGEST_STUB_RE.search(synopsis) and (work.stats.get("episodes") or 0) <= 3:
            return False
        index_url = NOVEL_URL_TEMPLATE.format(ncode=ncode)
        try:
            html = self.client.get_text(index_url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("cannot reach index page of %s: %s", ncode, exc)
            return False
        if INFO_ERROR_RE.search(html):
            return False
        entries = parse_novel_index(html, ncode)
        if entries:
            return True
        chapter = parse_chapter(html, index=1, url=index_url)
        return bool(chapter.paragraphs)

    def verify_and_enrich_commercialization(
        self,
        work: Work,
        *,
        anime_ncodes: Optional[Set[str]] = None,
        check_syuppan: bool = True,
        check_infotop: bool = True,
    ) -> bool:
        """Run multi-signal commercialisation verification and enrich ranking data."""
        ncode = work.id.split(":", 1)[1].lower()
        userid = str((work.extra or {}).get("userid") or "") or None
        signals: List[str] = []
        ranking = dict((work.extra or {}).get("ranking") or {})

        if work.rights.get("commercialized") is True:
            signals.append("api_metadata")

        if anime_ncodes and ncode in anime_ncodes:
            work.rights["commercialized"] = True
            ranking["is_anime"] = True
            signals.append("official_anime_page")

        if check_syuppan and userid:
            syuppan = self.check_syuppan(work.title, userid=userid)
            if syuppan.get("matched"):
                work.rights["commercialized"] = True
                ranking["syuppan_volumes"] = syuppan.get("volumes") or 1
                if syuppan.get("publisher"):
                    ranking["publisher"] = syuppan["publisher"]
                if syuppan.get("label"):
                    ranking["label"] = syuppan["label"]
                signals.append(f"syuppan({syuppan.get('volumes')}vols)")

        if work.rights.get("commercialized") is not True and check_infotop:
            info_res = self.check_commercialized(ncode)
            if info_res is True:
                work.rights["commercialized"] = True
                signals.append("infotop_page")
            elif work.rights.get("commercialized") is None:
                work.rights["commercialized"] = info_res

        if work.rights.get("commercialized") is True:
            work.rights["note"] = (
                "この作品は商業化されています。商業版（紙書籍・電子書籍）は再配布せず、"
                "本データセットでは公式サイトが無料公開しているWEB版のみを扱います。"
                "二次利用には作者の許諾が必要です。"
            )
            ranking["signals"] = signals
            work.extra["ranking"] = ranking
            work.extra["ranking"] = compute_popularity_ranking_score(work)
            return True
        return False

    # -- text ----------------------------------------------------------
    def fetch_novel_text(
        self,
        ncode: str,
        max_episodes: int = 0,
        expected_episodes: int = 0,
    ) -> NovelText:
        """Download the text of a novel (all TOC pages + all episodes when ``max_episodes=0``)."""
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

        # 1) optional legacy bulk text download
        if getattr(self.config, "use_txtdownload", False):
            url = f"https://ncode.syosetu.com/txtdownload/{ncode}/"
            try:
                payload = self.client.get(url)
                novel.chapters = self._chapters_from_zip(payload)
                if max_episodes:
                    novel.chapters = novel.chapters[:max_episodes]
                if novel.chapters:
                    novel.origin = "official data download"
                    return novel
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.debug("txtdownload unavailable for %s: %s", ncode, exc)

        # 2) chapter pages (with full ?p=2..N TOC pagination for 100+ episode works)
        index_url = NOVEL_URL_TEMPLATE.format(ncode=ncode)
        try:
            index_html = self.client.get_text(index_url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("cannot read the index of %s: %s", ncode, exc)
            return novel

        if INFO_ERROR_RE.search(index_html):
            LOGGER.warning("novel %s index returned an error page", ncode)
            return novel

        entries_by_idx: Dict[int, Tuple[int, Optional[str], str]] = {}
        for idx, title, curl in parse_novel_index(index_html, ncode):
            entries_by_idx.setdefault(idx, (idx, title, curl))

        max_page = parse_index_max_page(index_html, ncode)
        if expected_episodes > 100:
            max_page = max(max_page, (expected_episodes + 99) // 100)
        if max_episodes > 0:
            needed_pages = (max_episodes + 99) // 100
            max_page = min(max_page, max(1, needed_pages))

        for page_num in range(2, max_page + 1):
            page_url = f"{index_url}?p={page_num}"
            try:
                page_html = self.client.get_text(page_url)
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("cannot read TOC page %s of %s: %s", page_num, ncode, exc)
                continue
            page_entries = parse_novel_index(page_html, ncode)
            if not page_entries:
                break
            for idx, title, curl in page_entries:
                entries_by_idx.setdefault(idx, (idx, title, curl))

        entries = [entries_by_idx[k] for k in sorted(entries_by_idx)]

        # Short story (短編) whose body lives directly on the index URL
        if not entries:
            direct_chapter = parse_chapter(index_html, index=1, url=index_url)
            if direct_chapter.paragraphs:
                novel.chapters.append(
                    {
                        "index": 1,
                        "title": direct_chapter.title,
                        "url": index_url,
                        "paragraphs": direct_chapter.paragraphs,
                        "text": direct_chapter.text,
                        "char_count": direct_chapter.char_count,
                    }
                )
                novel.origin = "chapter pages"
                return novel
            entries = [(1, None, f"{index_url}1/")]

        total_target = (
            min(len(entries), max_episodes) if max_episodes else len(entries)
        )
        for count, (index, title, chapter_url) in enumerate(entries, start=1):
            if max_episodes and len(novel.chapters) >= max_episodes:
                break
            try:
                html = self.client.get_text(chapter_url)
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("cannot download %s: %s", chapter_url, exc)
                continue
            chapter = parse_chapter(html, index=index, url=chapter_url)
            if not chapter.paragraphs:
                continue
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
            if count % 100 == 0 or count == total_target:
                LOGGER.info(
                    "%s: fetched %s/%s episodes (%s chars)",
                    ncode,
                    len(novel.chapters),
                    total_target,
                    novel.char_count,
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
