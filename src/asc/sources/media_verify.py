"""External bibliographic & multi-media commercialisation verification.

Rather than trusting self-reported keywords such as ``書籍化`` inside a web
novel's synopsis (which suffer both from aspirational false positives like
``書籍化目指して頑張ります`` and from false negatives on flagship works like
『無職転生』, 『転生したらスライムだった件』, or 『本好きの下剋上』 whose Narou
metadata omits the word ``書籍化``), this module queries **independent external
catalogs** by title, author pen name, and N-code across four media categories:

1. **Books (書籍)** — NII **CiNii Books** OpenSearch JSON-LD API
   (``https://ci.nii.ac.jp/books/opensearch/search?format=json``) for
   ISBN-backed print editions held by Japanese national & university libraries,
   cross-checked with **Japanese Wikipedia** ``Infobox animanga/Novel`` &
   commercial imprint categories.
2. **Manga (マンガ)** — NII **CiNii Books** comic imprints / mangaka credits
   plus **Japanese Wikipedia** ``Infobox animanga/Manga`` & comic categories.
3. **Anime (アニメ)** — **Japanese Wikipedia** TV/theatrical/OVA/Web anime
   infoboxes, categories, and split ``(アニメ)`` articles, plus official
   ``syosetu.com/commercialization/anime/`` when reachable.
4. **Games (ゲーム)** — **Japanese Wikipedia** ``Infobox animanga/Game``,
   dedicated game sections (console / PC / mobile / TRPG), and video-game
   release categories (explicitly excluding VRMMO *theme* categories such as
   ``コンピュータゲームを題材とした小説``).
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlencode

from ..http import HttpClient
from ..schema import Work

LOGGER = logging.getLogger(__name__)

CINII_OPEN_SEARCH_URL = "https://ci.nii.ac.jp/books/opensearch/search"
JA_WIKIPEDIA_API_URL = "https://ja.wikipedia.org/w/api.php"
#: Fixed pageid of ``Category:小説家になろうの小説`` on Japanese Wikipedia.
NAROU_WIKI_CATEGORY_PAGEID = 4521544

ROOT_NCODE_URL_RE = re.compile(
    r"^https?://ncode\.syosetu\.com/(n[0-9a-z]+)/?$",
    flags=re.I,
)

PROMO_BRACKET_WORDS = (
    "アニメ",
    "書籍",
    "コミカライズ",
    "コミック",
    "漫画",
    "マンガ",
    "ゲーム",
    "文庫",
    "単行本",
    "発売",
    "刊行",
    "決定",
    "重版",
    "巻",
    "完結",
    "更新",
    "連載",
    "放送",
    "映画",
    "劇場",
    "ドラマCD",
    "受賞",
    "Web版",
    "WEB版",
    "web版",
    "旧題",
    "改題",
    "記念",
    "御礼",
    "感謝",
    "特設",
    "フェア",
    "突破",
    "万部",
)

RENAMED_TITLE_PATTERNS = (
    re.compile(r"(?:書籍(?:版)?タイトル|改題(?:後)?(?:タイトル)?|商業(?:版)?タイトル)\s*[：:は]?\s*[『「]([^』」]{3,60})[』」]"),
    re.compile(r"[『「]([^』」]{3,60})[』」]\s*(?:に|へ)\s*改題"),
    re.compile(r"【\s*(?:書籍(?:版)?(?:タイトル|題)?|改題(?:後)?)\s*[：:]\s*([^】]{3,60})】"),
)

SELF_PUBLISHED_RE = re.compile(
    r"(Kindle Direct Publishing|Independently published|自費出版|自主出版|同人誌|BOOTH|DLsite)",
    flags=re.I,
)

MANGA_CREATOR_RE = re.compile(
    r"(漫画|作画|コミカライズ|ネーム|art\s+by|comic)",
    flags=re.I,
)
MANGA_LABEL_RE = re.compile(
    r"(コミック|COMICS?|Manga|KC|ガンガン|ジャンプ|サンデー|マガジン|チャンピオン|"
    r"シリウス|アライブ|フラッパー|電撃マオウ|電撃大王|ガルド|コロナ・コミックス|"
    r"モンスターコミックス|アース・スター\s*コミックス|アルファポリスコミックス|"
    r"バンブーコミックス|ヤングエース|コンプエース|ビーズログコミックス|リボン|フラワー)",
    flags=re.I,
)
ARTBOOK_RE = re.compile(r"(画集|ファンブック|設定資料集|アンソロジー)")

WIKI_FICTION_CATEGORY_RE = re.compile(
    r"(小説|ライトノベル|文庫|ブックス|ノベル|新文芸|漫画作品|年の漫画|コミックス|"
    r"テレビアニメ|アニメ映画|アニメ作品|OVA|Webアニメ|コンピュータゲーム|ゲームソフト|"
    r"テーブルトークRPG)"
)
WIKI_PERSON_CATEGORY_RE = re.compile(
    r"(存命人物|日本の小説家|日本のライトノベル作家|日本の漫画家|日本の声優|年生|年没)"
)
WIKI_BOOK_CATEGORY_RE = re.compile(
    r"(文庫|ブックス|ノベル|新文芸|エンターブレイン|KADOKAWAの小説|宝島社の小説|"
    r"主婦の友社の小説|スクウェア・エニックスの小説|SBクリエイティブ|講談社の小説|"
    r"集英社の小説|小学館の小説|双葉社の小説|一迅社|オーバーラップ|TOブックス|"
    r"マイクロマガジン|アルファポリス|アース・スター|ヒーロー文庫|MFブックス|電撃の新文芸|"
    r"カドカワBOOKS|ファミ通文庫|角川スニーカー文庫|富士見ファンタジア文庫|電撃文庫|"
    r"GAノベル|GA文庫|HJノベルス|HJ文庫|ダッシュエックス文庫|講談社ラノベ文庫|"
    r"モンスター文庫|ツギクルブックス|ドラゴンノベルス|ビーズログ文庫|レジーナブックス)"
)
WIKI_MANGA_CATEGORY_RE = re.compile(
    r"(漫画作品|年の漫画|コミックス|ライトノベルを原作とする漫画|小説を原作とする漫画|"
    r"ガンガン|コミッククリア|コミックガルド|電撃大王|電撃マオウ|ヤングエース|"
    r"月刊少年シリウス|コミックフラッパー|コミックアライブ|ビッグガンガン|マンガUP)"
)
WIKI_ANIME_CATEGORY_RE = re.compile(
    r"(年のテレビアニメ|のアニメ映画|年のOVA|年のWebアニメ|アニメ作品)"
)
WIKI_GAME_CATEGORY_RE = re.compile(
    r"(年のコンピュータゲーム|用ゲームソフト|用ソフト|iOS用ゲーム|Android用ゲーム|"
    r"ブラウザゲーム|日本のテーブルトークRPG)"
)
WIKI_THEME_EXCLUDE_RE = re.compile(r"(を題材とした|を舞台とした)")

WIKI_INFOBOX_NOVEL_RE = re.compile(r"\{\{\s*Infobox\s+animanga/Novel\b(.*?)(?=\n\{\{|\n\|-\s*\n|$)", flags=re.S | re.I)
WIKI_INFOBOX_MANGA_RE = re.compile(r"\{\{\s*Infobox\s+animanga/Manga\b", flags=re.I)
WIKI_INFOBOX_ANIME_RE = re.compile(
    r"\{\{\s*Infobox\s+animanga/(?:TVAnime|Anime|OVA|Movie|WebAnime)\b",
    flags=re.I,
)
WIKI_INFOBOX_GAME_RE = re.compile(r"\{\{\s*Infobox\s+animanga/Game\b", flags=re.I)

WIKI_SECTION_MANGA_RE = re.compile(r"^={2,4}\s*(?:漫画|コミカライズ|コミック)\s*={2,4}", flags=re.M)
WIKI_SECTION_ANIME_RE = re.compile(
    r"^={2,4}\s*(?:テレビアニメ|TVアニメ|アニメ|劇場アニメ|アニメ映画|Webアニメ)\s*={2,4}",
    flags=re.M,
)
WIKI_SECTION_GAME_RE = re.compile(
    r"^={2,4}\s*(?:ゲーム|コンピュータゲーム|スマートフォンゲーム|スマホゲーム|ゲームアプリ|"
    r"ソーシャルゲーム|ブラウザゲーム|家庭用ゲーム|コンシューマーゲーム|テーブルトークRPG|TRPG)\s*={2,4}",
    flags=re.M,
)
WIKI_OTHERUSES_ANIME_RE = re.compile(r"\{\{\s*Otheruses\b[^}]*アニメ[^}]*\}\}")
WIKI_OTHERUSES_GAME_RE = re.compile(r"\{\{\s*Otheruses\b[^}]*ゲーム[^}]*\}\}")


@dataclass
class MediaVerificationResult:
    """Structured result of external 4-media commercialisation verification."""

    verified: bool = False
    has_book: bool = False
    has_manga: bool = False
    has_anime: bool = False
    has_game: bool = False
    publisher: Optional[str] = None
    label: Optional[str] = None
    isbn_sample: Optional[str] = None
    manga_publisher: Optional[str] = None
    manga_label: Optional[str] = None
    manga_isbn_sample: Optional[str] = None
    wikipedia_title: Optional[str] = None
    wikipedia_pageid: Optional[int] = None
    cinii_book_hits: int = 0
    cinii_manga_hits: int = 0
    cinii_total_results: int = 0
    wikipedia_volumes: int = 0
    syuppan_volumes: int = 0
    sources: List[str] = field(default_factory=list)

    @property
    def verified_media(self) -> List[str]:
        media: List[str] = []
        if self.has_book:
            media.append("book")
        if self.has_manga:
            media.append("manga")
        if self.has_anime:
            media.append("anime")
        if self.has_game:
            media.append("game")
        return media

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "verified_media": self.verified_media,
            "has_book": self.has_book,
            "has_manga": self.has_manga,
            "has_anime": self.has_anime,
            "has_game": self.has_game,
            "publisher": self.publisher,
            "label": self.label,
            "isbn_sample": self.isbn_sample,
            "manga_publisher": self.manga_publisher,
            "manga_label": self.manga_label,
            "manga_isbn_sample": self.manga_isbn_sample,
            "wikipedia_title": self.wikipedia_title,
            "wikipedia_pageid": self.wikipedia_pageid,
            "cinii_book_hits": self.cinii_book_hits,
            "cinii_manga_hits": self.cinii_manga_hits,
            "cinii_total_results": self.cinii_total_results,
            "wikipedia_volumes": self.wikipedia_volumes,
            "syuppan_volumes": self.syuppan_volumes,
            "sources": list(self.sources),
        }


def normalize_match_key(text: str) -> str:
    """Normalize Japanese/ASCII text for fuzzy title & author comparison."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", html_lib.unescape(text)).lower()
    # Keep letters, digits, hiragana, katakana, CJK ideographs, prolonged sound mark
    norm = re.sub(
        r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff\uff66-\uff9fー々〆〇]+",
        "",
        norm,
    )
    return norm


def _clean_bracket_segments(text: str) -> str:
    """Remove promotional ``【...】`` / ``[...]`` brackets while keeping title brackets."""

    def _repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        if any(word in inner for word in PROMO_BRACKET_WORDS):
            return " "
        return match.group(0)

    cleaned = re.sub(r"【([^】]*)】", _repl, text)
    cleaned = re.sub(r"［([^］]*)］", _repl, cleaned)
    cleaned = re.sub(r"\[([^\]]*)\]", _repl, cleaned)
    cleaned = re.sub(r"（([^）]*)）", _repl, cleaned)
    cleaned = re.sub(r"\(([^)]*)\)", _repl, cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_search_titles(title: str, synopsis: str = "") -> List[str]:
    """Extract clean core & renamed search titles from a Narou title + synopsis."""
    if not title:
        return []
    candidates: List[str] = []

    def _add(val: str) -> None:
        v = unicodedata.normalize("NFKC", html_lib.unescape(val)).strip()
        v = re.sub(r"\s+", " ", v).strip(" 　・/／|｜")
        v_no_period = v.rstrip("。.")
        for item in (v_no_period, v):
            if item and len(normalize_match_key(item)) >= 2 and item not in candidates:
                candidates.append(item)

    # 1) Check for explicit renamed commercial book title in title/synopsis
    combined = f"{title}\n{synopsis or ''}"
    for pat in RENAMED_TITLE_PATTERNS:
        for m in pat.finditer(combined):
            _add(m.group(1))

    # 2) Strip promotional brackets from raw title
    cleaned = unicodedata.normalize("NFKC", html_lib.unescape(title)).strip()
    cleaned = _clean_bracket_segments(cleaned)

    # 3) Split core title before paired or spaced subtitle delimiters:
    #    e.g. "無職転生 - 異世界行ったら本気だす -" -> "無職転生"
    #         "本好きの下剋上 ～司書になるためには...～" -> "本好きの下剋上"
    #         "＜Infinite Dendrogram＞-インフィニット・デンドログラム-" -> both parts
    tilde_match = re.split(r"\s*[〜～~]+", cleaned)
    if len(tilde_match) >= 2 and len(normalize_match_key(tilde_match[0])) >= 2:
        head = tilde_match[0].strip(" <>＜＞《》「」『』")
        _add(head)
        if re.fullmatch(r"[A-Za-z0-9\s:.'\-!?<>]+", head) and len(tilde_match[1]) >= 3:
            _add(tilde_match[1].strip(" 〜～~"))

    dash_match = re.match(
        r"^(.{2,}?)(?:\s+[-－―—]+\s*|\s*[-－―—]{2,}\s*|(?<=[＞>》」』])[-－―—]+)(.+?)(?:\s*[-－―—]+)?$",
        cleaned,
    )
    if dash_match:
        head = dash_match.group(1).strip(" <>＜＞《》「」『』")
        sub = dash_match.group(2).strip(" -－―—")
        if re.fullmatch(r"[A-Za-z0-9\s:.'\-!?<>]+", head) and sub:
            # Prefer Japanese subtitle for CiNii when head is ASCII (e.g. Infinite Dendrogram)
            _add(sub)
            _add(head)
        else:
            _add(head)

    _add(cleaned.strip(" <>＜＞"))
    return candidates[:4]


def extract_author_variants(writer: str) -> List[str]:
    """Extract normalized pen-name variants from Narou ``writer`` field."""
    if not writer:
        return []
    norm = unicodedata.normalize("NFKC", html_lib.unescape(writer)).strip()
    # Split off promo suffixes after @ / ◆ / ◇
    for marker in ("◆", "◇", "＠", "@", "★", "☆"):
        if marker in norm:
            norm = norm.split(marker, 1)[0].strip()
    parts = re.split(r"[/／|｜()（）\[\]［］【】「」『』、,]+", norm)
    variants: List[str] = []
    for part in parts:
        cleaned = re.sub(r"(?:先生|氏|様|原作|著|作)$", "", part.strip()).strip()
        key = normalize_match_key(cleaned)
        if len(key) >= 2 and key not in variants:
            variants.append(key)
    if not variants:
        fallback = normalize_match_key(norm)
        if fallback:
            variants.append(fallback)
    return variants


def _extract_isbns(item: Dict[str, Any]) -> List[str]:
    isbns: List[str] = []
    for entry in item.get("dcterms:hasPart") or []:
        if not isinstance(entry, dict):
            continue
        raw_id = str(entry.get("@id") or "")
        if "urn:isbn:" in raw_id.lower():
            code = re.sub(r"[^0-9Xx]", "", raw_id.split(":", 2)[-1])
            if len(code) in (10, 13) and code not in isbns:
                isbns.append(code.upper())
    return isbns


def _clean_publisher_name(raw_pub: str) -> str:
    val = unicodedata.normalize("NFKC", raw_pub).strip()
    val = re.sub(r"\s*[\(（]発売[\)）]\s*$", "", val).strip()
    return val


def _clean_series_label(raw_series: str) -> str:
    val = unicodedata.normalize("NFKC", raw_series).strip()
    # Strip catalog shelf numbers like "MF文庫J, [な-07-36]" or ". 本好きの下剋上..."
    val = val.split("||", 1)[0]
    val = val.split(" . ", 1)[0]
    val = re.sub(r",\s*\[?[^\],]+$", "", val).strip()
    return val[:48]


def _titles_match(
    item_texts: Sequence[str], search_keys: Sequence[str]
) -> Tuple[bool, bool, bool]:
    """Return ``(prefix_match, substring_match, long_prefix_match)``."""
    norm_items = [normalize_match_key(t) for t in item_texts if t]
    prefix_match = False
    substring_match = False
    long_match = False
    for skey in search_keys:
        if len(skey) < 2:
            continue
        for itext in norm_items:
            if not itext:
                continue
            if itext == skey or itext.startswith(skey):
                prefix_match = True
                substring_match = True
                if len(skey) >= 10:
                    long_match = True
            elif len(skey) >= 3 and skey in itext:
                substring_match = True
    return prefix_match, substring_match, long_match


def _creator_matches_author(creator: str, author_variants: Sequence[str]) -> bool:
    if not creator or not author_variants:
        return False
    norm_creator = normalize_match_key(creator)
    if not norm_creator:
        return False
    for variant in author_variants:
        if len(variant) >= 2 and variant in norm_creator:
            return True
        if len(variant) == 1:
            # Single-character pen name: require role suffix in raw creator string
            if re.search(rf"(?:^|[;\s/]){re.escape(variant)}\s*(?:\[?著\]?|作|原作)", creator):
                return True
    return False


def parse_cinii_books_response(
    data: Dict[str, Any],
    *,
    search_titles: Sequence[str],
    author_variants: Sequence[str],
    trusted_ncode: bool = False,
    metadata_positive: bool = False,
) -> Dict[str, Any]:
    """Validate and classify CiNii Books OpenSearch JSON-LD items into book vs manga."""
    out: Dict[str, Any] = {
        "matched": False,
        "has_book": False,
        "has_manga": False,
        "publisher": None,
        "label": None,
        "isbn_sample": None,
        "manga_publisher": None,
        "manga_label": None,
        "manga_isbn_sample": None,
        "book_hits": 0,
        "manga_hits": 0,
        "total_results": 0,
    }
    graph = data.get("@graph")
    if not isinstance(graph, list) or not graph or not isinstance(graph[0], dict):
        return out

    channel = graph[0]
    try:
        total_results = int(channel.get("opensearch:totalResults") or 0)
    except (TypeError, ValueError):
        total_results = 0
    items = channel.get("items") or []
    if not isinstance(items, list) or not items:
        return out

    search_keys = [normalize_match_key(t) for t in search_titles if normalize_match_key(t)]
    if not search_keys:
        return out

    seen_book_keys: Set[str] = set()
    seen_manga_keys: Set[str] = set()
    author_confirmed_any = False

    for item in items:
        if not isinstance(item, dict):
            continue
        item_title = str(item.get("title") or "")
        creator = str(item.get("dc:creator") or "")
        raw_pubs = item.get("dc:publisher") or []
        if isinstance(raw_pubs, str):
            raw_pubs = [raw_pubs]
        publishers = [_clean_publisher_name(str(p)) for p in raw_pubs if p]
        pub_joined = " / ".join(publishers)
        if not publishers or SELF_PUBLISHED_RE.search(pub_joined):
            continue

        series_titles: List[str] = []
        for part in item.get("dcterms:isPartOf") or []:
            if isinstance(part, dict) and part.get("dc:title"):
                series_titles.append(str(part["dc:title"]))

        title_prefix_ok, title_sub_ok, long_title_ok = _titles_match(
            [item_title, *series_titles], search_keys
        )
        author_ok = _creator_matches_author(creator, author_variants)
        isbns = _extract_isbns(item)
        try:
            owner_count = int(item.get("cinii:ownerCount") or 0)
        except (TypeError, ValueError):
            owner_count = 0

        # Require real ISBN or library holdings under a commercial publisher
        if not isbns and owner_count < 1:
            continue

        # Strict identity gate:
        #   (A) Author pen-name match + title/series match
        #   (B) Work already verified via exact N-code link on Wikipedia + title prefix match
        #   (C) >=10-char distinctive title prefix + Japanese ISBN + non-negative Narou notice
        jp_isbn = any(code.startswith(("9784", "4")) for code in isbns)
        identity_ok = False
        if author_ok and title_sub_ok:
            identity_ok = True
            author_confirmed_any = True
        elif trusted_ncode and title_prefix_ok:
            identity_ok = True
        elif long_title_ok and jp_isbn and metadata_positive:
            identity_ok = True

        if not identity_ok:
            continue

        dedup_id = isbns[0] if isbns else str(item.get("@id") or item_title)
        series_joined = " ".join(series_titles)
        is_manga = bool(
            MANGA_CREATOR_RE.search(creator)
            or MANGA_LABEL_RE.search(series_joined)
            or MANGA_LABEL_RE.search(pub_joined)
            or MANGA_LABEL_RE.search(item_title)
        )
        is_artbook = bool(ARTBOOK_RE.search(item_title))
        clean_label = _clean_series_label(series_titles[0]) if series_titles else None

        if is_manga and not is_artbook:
            seen_manga_keys.add(dedup_id)
            out["has_manga"] = True
            if out["manga_publisher"] is None and publishers:
                out["manga_publisher"] = publishers[0]
            if out["manga_label"] is None and clean_label:
                out["manga_label"] = clean_label
            if out["manga_isbn_sample"] is None and isbns:
                out["manga_isbn_sample"] = isbns[0]
        else:
            seen_book_keys.add(dedup_id)
            out["has_book"] = True
            if out["publisher"] is None and publishers:
                out["publisher"] = publishers[0]
            if out["label"] is None and clean_label:
                out["label"] = clean_label
            if out["isbn_sample"] is None and isbns:
                out["isbn_sample"] = isbns[0]

    out["book_hits"] = len(seen_book_keys)
    out["manga_hits"] = len(seen_manga_keys)
    out["matched"] = bool(out["has_book"] or out["has_manga"])
    if out["matched"]:
        out["total_results"] = (
            total_results if author_confirmed_any else (out["book_hits"] + out["manga_hits"])
        )
    return out


def _clean_wiki_markup(raw: str) -> str:
    val = re.sub(r"<ref\b[^>]*>.*?</ref>", "", raw, flags=re.S | re.I)
    val = re.sub(r"<ref\b[^>]*/\s*>", "", val, flags=re.I)
    val = re.sub(r"\{\{[^{}]*\}\}", "", val)
    val = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", val)
    val = re.sub(r"<[^>]+>", "", val)
    val = val.replace("'''", "").replace("''", "")
    # Take first publisher before arrow if multiple (or keep concise)
    val = re.sub(r"\s+", " ", val).strip(" 　、,")
    return val[:48]


def _extract_infobox_field(block: str, field_name: str) -> Optional[str]:
    m = re.search(rf"\|\s*{re.escape(field_name)}\s*=\s*([^\n|}}]+)", block)
    if not m:
        return None
    cleaned = _clean_wiki_markup(m.group(1))
    return cleaned or None


def _extract_wiki_volumes(wikitext: str) -> int:
    best = 0
    for block_match in WIKI_INFOBOX_NOVEL_RE.finditer(wikitext):
        vol_str = _extract_infobox_field(block_match.group(1), "巻数") or ""
        for m in re.finditer(r"(\d{1,3})\s*巻", unicodedata.normalize("NFKC", vol_str)):
            val = int(m.group(1))
            if 1 <= val <= 100:
                best = max(best, val)
    return best


def parse_wikipedia_page_media(
    page: Dict[str, Any],
    *,
    ncode: str,
    search_titles: Sequence[str],
    author_variants: Sequence[str],
    matched_by_ncode: bool = False,
) -> Dict[str, Any]:
    """Inspect a Wikipedia page's categories + wikitext for book/manga/anime/game proof."""
    out: Dict[str, Any] = {
        "matched": False,
        "has_book": False,
        "has_manga": False,
        "has_anime": False,
        "has_game": False,
        "publisher": None,
        "label": None,
        "volumes": 0,
        "wikipedia_title": page.get("title"),
        "wikipedia_pageid": page.get("pageid"),
    }
    if not page or "missing" in page or page.get("ns", 0) != 0:
        return out

    wiki_title = str(page.get("title") or "")
    # Strip Wikipedia disambiguation suffix like " (小説)" for title matching
    wiki_base_title = re.sub(r"\s*\([^)]*\)\s*$", "", wiki_title).strip()

    categories = [
        str(c.get("title") or "").removeprefix("Category:")
        for c in (page.get("categories") or [])
        if isinstance(c, dict)
    ]
    revisions = page.get("revisions") or []
    wikitext = ""
    if revisions and isinstance(revisions[0], dict):
        slots = revisions[0].get("slots") or {}
        main_slot = slots.get("main") or {}
        wikitext = str(main_slot.get("*") or revisions[0].get("*") or "")

    # Filter out non-work pages (e.g. author biography articles)
    has_fiction_cat = any(
        WIKI_FICTION_CATEGORY_RE.search(cat) and not WIKI_THEME_EXCLUDE_RE.search(cat)
        for cat in categories
    )
    has_person_cat = any(WIKI_PERSON_CATEGORY_RE.search(cat) for cat in categories)
    if has_person_cat and not has_fiction_cat:
        return out
    if not has_fiction_cat and "Infobox animanga" not in wikitext:
        return out

    # Identity verification between Wikipedia page and candidate Narou work
    ncode_lower = ncode.lower()
    wikitext_lower = wikitext.lower()
    explicit_ncode_in_text = bool(
        ncode_lower
        and (
            f"ncode.syosetu.com/{ncode_lower}" in wikitext_lower
            or re.search(rf"\|\s*ncode\s*=\s*{re.escape(ncode_lower)}\b", wikitext_lower)
            or re.search(rf"小説家になろう\|{re.escape(ncode_lower)}\b", wikitext_lower)
        )
    )
    is_narou_cat = "小説家になろうの小説" in categories or "小説家になろう" in wikitext
    search_keys = [normalize_match_key(t) for t in search_titles if normalize_match_key(t)]
    title_ok, _, _ = _titles_match([wiki_base_title, wiki_title], search_keys)

    norm_wikitext_head = normalize_match_key(wikitext[:6000])
    author_ok = any(
        len(v) >= 2 and v in norm_wikitext_head for v in author_variants
    )

    identity_ok = False
    if matched_by_ncode or explicit_ncode_in_text:
        # Even for N-code links, ensure it's genuinely about this Narou work (not an unrelated footnote)
        if is_narou_cat or author_ok or title_ok:
            identity_ok = True
    elif title_ok and (author_ok or (is_narou_cat and any(len(k) >= 4 for k in search_keys))):
        identity_ok = True

    if not identity_ok:
        return out

    # 1) Book (書籍) verification — requires commercial publisher/imprint/ISBN proof
    novel_publisher: Optional[str] = None
    novel_label: Optional[str] = None
    for m in WIKI_INFOBOX_NOVEL_RE.finditer(wikitext):
        block = m.group(1)
        pub = _extract_infobox_field(block, "出版社")
        lbl = _extract_infobox_field(block, "レーベル")
        if pub and "小説家になろう" not in pub and not SELF_PUBLISHED_RE.search(pub):
            novel_publisher = novel_publisher or pub
            novel_label = novel_label or lbl
            out["has_book"] = True
        elif lbl and not SELF_PUBLISHED_RE.search(lbl):
            novel_label = novel_label or lbl
            out["has_book"] = True

    if not out["has_book"]:
        for cat in categories:
            if WIKI_THEME_EXCLUDE_RE.search(cat):
                continue
            if WIKI_BOOK_CATEGORY_RE.search(cat):
                out["has_book"] = True
                break
    if not out["has_book"] and re.search(r"ISBN\s*978-?4", wikitext, flags=re.I):
        out["has_book"] = True

    out["publisher"] = novel_publisher
    out["label"] = novel_label
    out["volumes"] = _extract_wiki_volumes(wikitext)

    # 2) Manga (マンガ) verification
    if WIKI_INFOBOX_MANGA_RE.search(wikitext) or WIKI_SECTION_MANGA_RE.search(wikitext):
        out["has_manga"] = True
    else:
        for cat in categories:
            if not WIKI_THEME_EXCLUDE_RE.search(cat) and WIKI_MANGA_CATEGORY_RE.search(cat):
                out["has_manga"] = True
                break

    # 3) Anime (アニメ) verification
    if (
        WIKI_INFOBOX_ANIME_RE.search(wikitext)
        or WIKI_SECTION_ANIME_RE.search(wikitext)
        or WIKI_OTHERUSES_ANIME_RE.search(wikitext)
    ):
        out["has_anime"] = True
    else:
        for cat in categories:
            if not WIKI_THEME_EXCLUDE_RE.search(cat) and WIKI_ANIME_CATEGORY_RE.search(cat):
                out["has_anime"] = True
                break

    # 4) Game (ゲーム) verification — strictly excluding VRMMO theme categories
    if (
        WIKI_INFOBOX_GAME_RE.search(wikitext)
        or WIKI_SECTION_GAME_RE.search(wikitext)
        or WIKI_OTHERUSES_GAME_RE.search(wikitext)
    ):
        out["has_game"] = True
    else:
        for cat in categories:
            if not WIKI_THEME_EXCLUDE_RE.search(cat) and WIKI_GAME_CATEGORY_RE.search(cat):
                out["has_game"] = True
                break

    out["matched"] = bool(
        out["has_book"] or out["has_manga"] or out["has_anime"] or out["has_game"]
    )
    return out


class ExternalMediaVerifier:
    """Batch & per-work external commercialisation verifier across 4 media types."""

    def __init__(
        self,
        client: HttpClient,
        *,
        cinii_url: str = CINII_OPEN_SEARCH_URL,
        wikipedia_api_url: str = JA_WIKIPEDIA_API_URL,
    ) -> None:
        self.client = client
        self.cinii_url = cinii_url
        self.wikipedia_api_url = wikipedia_api_url
        self._wiki_ncode_pageids: Dict[str, Set[int]] = {}
        self._wiki_title_pageids: Dict[str, Set[int]] = {}
        self._wiki_page_cache: Dict[int, Dict[str, Any]] = {}
        self._cinii_cache: Dict[str, Dict[str, Any]] = {}
        self._indexes_warmed: bool = False

    # -- Wikipedia API helpers -----------------------------------------
    def _wiki_get_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        clean_params: Dict[str, str] = {"format": "json"}
        for key, value in params.items():
            if value is not None:
                clean_params[key] = unicodedata.normalize("NFC", str(value))
        url = self.wikipedia_api_url + "?" + urlencode(clean_params)
        payload = self.client.get(url)
        return json.loads(payload.decode("utf-8"))

    def warm_bulk_indexes(self) -> None:
        """Pre-load Wikipedia's N-code link index & ``Category:小説家になろうの小説``."""
        if self._indexes_warmed:
            return
        self._indexes_warmed = True

        # 1) External link index: ncode.syosetu.com (both https and http)
        for proto in ("https", "http"):
            eucontinue: Optional[str] = None
            for _ in range(12):
                params: Dict[str, Any] = {
                    "action": "query",
                    "list": "exturlusage",
                    "euprotocol": proto,
                    "euquery": "ncode.syosetu.com",
                    "eunamespace": 0,
                    "eulimit": 500,
                }
                if eucontinue:
                    params["eucontinue"] = eucontinue
                try:
                    data = self._wiki_get_json(params)
                except Exception as exc:  # pragma: no cover - network dependent
                    LOGGER.warning("Wikipedia exturlusage (%s) failed: %s", proto, exc)
                    break
                rows = (data.get("query") or {}).get("exturlusage") or []
                for row in rows:
                    url = str(row.get("url") or "")
                    m = ROOT_NCODE_URL_RE.match(url)
                    if m and row.get("pageid"):
                        ncode = m.group(1).lower()
                        self._wiki_ncode_pageids.setdefault(ncode, set()).add(int(row["pageid"]))
                cont = data.get("continue") or {}
                eucontinue = cont.get("eucontinue")
                if not eucontinue:
                    break

        # 2) Category:小説家になろうの小説 members
        cmcontinue: Optional[str] = None
        for _ in range(12):
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmpageid": NAROU_WIKI_CATEGORY_PAGEID,
                "cmnamespace": 0,
                "cmlimit": 500,
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            try:
                data = self._wiki_get_json(params)
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("Wikipedia categorymembers failed: %s", exc)
                break
            members = (data.get("query") or {}).get("categorymembers") or []
            for row in members:
                pid = row.get("pageid")
                title = str(row.get("title") or "")
                base_title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
                key = normalize_match_key(base_title)
                if pid and key:
                    self._wiki_title_pageids.setdefault(key, set()).add(int(pid))
                # Also index prefix before tilde/dash on Wikipedia article titles
                for st in extract_search_titles(base_title):
                    skey = normalize_match_key(st)
                    if pid and len(skey) >= 3:
                        self._wiki_title_pageids.setdefault(skey, set()).add(int(pid))
            cont = data.get("continue") or {}
            cmcontinue = cont.get("cmcontinue")
            if not cmcontinue:
                break

        LOGGER.info(
            "warmed Wikipedia indexes: %s N-codes linked, %s title keys in Category:小説家になろうの小説",
            len(self._wiki_ncode_pageids),
            len(self._wiki_title_pageids),
        )

    def _search_wikipedia_title(
        self, search_titles: Sequence[str], author_variants: Sequence[str]
    ) -> Set[int]:
        """Targeted Wikipedia title search fallback when not in bulk indexes."""
        if not search_titles:
            return set()
        core = search_titles[0]
        if len(normalize_match_key(core)) < 3:
            return set()
        query = f'intitle:"{core}"'
        if author_variants and len(normalize_match_key(core)) < 7:
            query += f' "{author_variants[0]}"'
        try:
            data = self._wiki_get_json(
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srnamespace": 0,
                    "srlimit": 5,
                }
            )
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.debug("Wikipedia search failed for %s: %s", query, exc)
            return set()
        hits = (data.get("query") or {}).get("search") or []
        return {int(h["pageid"]) for h in hits if isinstance(h, dict) and h.get("pageid")}

    def _fetch_wikipedia_pages(self, pageids: Iterable[int]) -> None:
        missing = sorted({int(pid) for pid in pageids if int(pid) not in self._wiki_page_cache})
        batch_size = 10
        for idx in range(0, len(missing), batch_size):
            chunk = missing[idx : idx + batch_size]
            joined = "|".join(str(pid) for pid in chunk)
            merged_pages: Dict[int, Dict[str, Any]] = {}
            clcontinue: Optional[str] = None
            for _ in range(5):
                params: Dict[str, Any] = {
                    "action": "query",
                    "pageids": joined,
                    "prop": "categories|revisions",
                    "rvprop": "content",
                    "rvslots": "main",
                    "cllimit": "max",
                }
                if clcontinue:
                    params["clcontinue"] = clcontinue
                try:
                    data = self._wiki_get_json(params)
                except Exception as exc:  # pragma: no cover - network dependent
                    LOGGER.warning("Wikipedia page fetch failed for %s: %s", joined, exc)
                    break
                pages = (data.get("query") or {}).get("pages") or {}
                for pid_str, pobj in pages.items():
                    try:
                        pid_int = int(pid_str)
                    except ValueError:
                        continue
                    if pid_int not in merged_pages:
                        merged_pages[pid_int] = dict(pobj)
                        merged_pages[pid_int]["categories"] = list(pobj.get("categories") or [])
                    else:
                        merged_pages[pid_int]["categories"].extend(pobj.get("categories") or [])
                        if pobj.get("revisions") and not merged_pages[pid_int].get("revisions"):
                            merged_pages[pid_int]["revisions"] = pobj["revisions"]
                cont = data.get("continue") or {}
                clcontinue = cont.get("clcontinue")
                if not clcontinue:
                    break
            for pid_int, pobj in merged_pages.items():
                self._wiki_page_cache[pid_int] = pobj

    # -- CiNii Books API helpers ---------------------------------------
    def _query_cinii_title(self, title_query: str) -> Dict[str, Any]:
        q = unicodedata.normalize("NFC", title_query.strip())
        if q in self._cinii_cache:
            return self._cinii_cache[q]
        url = self.cinii_url + "?" + urlencode({"format": "json", "count": 20, "title": q})
        try:
            payload = self.client.get(url)
            data = json.loads(payload.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.debug("CiNii Books lookup failed for %s: %s", q, exc)
            data = {}
        self._cinii_cache[q] = data
        return data

    def verify_work_cinii(
        self,
        work: Work,
        *,
        search_titles: Sequence[str],
        author_variants: Sequence[str],
        trusted_ncode: bool = False,
    ) -> Dict[str, Any]:
        """Search CiNii Books across extracted core/renamed titles of ``work``."""
        best: Optional[Dict[str, Any]] = None
        metadata_positive = work.rights.get("commercialized") is True
        # Try up to first 2 distinct search titles (core title + renamed/subtitle fallback)
        for query in search_titles[:2]:
            if len(normalize_match_key(query)) < 2:
                continue
            raw = self._query_cinii_title(query)
            parsed = parse_cinii_books_response(
                raw,
                search_titles=search_titles,
                author_variants=author_variants,
                trusted_ncode=trusted_ncode,
                metadata_positive=metadata_positive,
            )
            if parsed["matched"]:
                if best is None:
                    best = parsed
                else:
                    best["has_book"] = best["has_book"] or parsed["has_book"]
                    best["has_manga"] = best["has_manga"] or parsed["has_manga"]
                    best["book_hits"] = max(best["book_hits"], parsed["book_hits"])
                    best["manga_hits"] = max(best["manga_hits"], parsed["manga_hits"])
                    best["total_results"] = max(best["total_results"], parsed["total_results"])
                    for field_name in (
                        "publisher",
                        "label",
                        "isbn_sample",
                        "manga_publisher",
                        "manga_label",
                        "manga_isbn_sample",
                    ):
                        if best.get(field_name) is None and parsed.get(field_name) is not None:
                            best[field_name] = parsed[field_name]
                # Stop after primary core title if both book & manga or >=2 hits already found
                if best["has_book"] and (best["has_manga"] or best["book_hits"] >= 2):
                    break
        return best or {
            "matched": False,
            "has_book": False,
            "has_manga": False,
            "publisher": None,
            "label": None,
            "isbn_sample": None,
            "manga_publisher": None,
            "manga_label": None,
            "manga_isbn_sample": None,
            "book_hits": 0,
            "manga_hits": 0,
            "total_results": 0,
        }

    # -- Combined multi-media verification -----------------------------
    def verify_candidates(
        self,
        candidates: Sequence[Work],
        *,
        anime_ncodes: Optional[Set[str]] = None,
        use_wikipedia_search_fallback: bool = True,
    ) -> Dict[str, MediaVerificationResult]:
        """Verify a batch of candidate works across CiNii Books + Wikipedia + official lists."""
        self.warm_bulk_indexes()

        work_meta: Dict[str, Tuple[str, List[str], List[str], Set[int], bool]] = {}
        all_needed_pageids: Set[int] = set()

        for work in candidates:
            ncode = work.id.split(":", 1)[1].lower()
            synopsis = str((work.extra or {}).get("synopsis") or "")
            author_name = work.authors[0].name if work.authors else ""
            search_titles = extract_search_titles(work.title, synopsis)
            author_variants = extract_author_variants(author_name)

            ncode_pids = set(self._wiki_ncode_pageids.get(ncode) or set())
            title_pids: Set[int] = set()
            for st in search_titles:
                skey = normalize_match_key(st)
                if skey in self._wiki_title_pageids:
                    title_pids.update(self._wiki_title_pageids[skey])

            pids = ncode_pids | title_pids
            if not pids and use_wikipedia_search_fallback:
                pids = self._search_wikipedia_title(search_titles, author_variants)

            all_needed_pageids.update(pids)
            work_meta[work.id] = (
                ncode,
                search_titles,
                author_variants,
                pids,
                bool(ncode_pids),
            )

        if all_needed_pageids:
            LOGGER.info("fetching %s unique Wikipedia franchise pages in batches", len(all_needed_pageids))
            self._fetch_wikipedia_pages(all_needed_pageids)

        results: Dict[str, MediaVerificationResult] = {}
        for idx, work in enumerate(candidates, start=1):
            ncode, search_titles, author_variants, pids, has_ncode_pid = work_meta[work.id]
            res = MediaVerificationResult()

            # 1) Official Syosetu anime registry (when available)
            if anime_ncodes and ncode in anime_ncodes:
                res.has_anime = True
                res.sources.append("official_anime_page")

            # 2) Wikipedia franchise verification (Book / Manga / Anime / Game)
            wiki_matched = False
            ncode_pid_set = self._wiki_ncode_pageids.get(ncode) or set()
            for pid in sorted(pids):
                page_obj = self._wiki_page_cache.get(pid)
                if not page_obj:
                    continue
                parsed_wiki = parse_wikipedia_page_media(
                    page_obj,
                    ncode=ncode,
                    search_titles=search_titles,
                    author_variants=author_variants,
                    matched_by_ncode=(pid in ncode_pid_set),
                )
                if parsed_wiki["matched"]:
                    wiki_matched = True
                    res.has_book = res.has_book or parsed_wiki["has_book"]
                    res.has_manga = res.has_manga or parsed_wiki["has_manga"]
                    res.has_anime = res.has_anime or parsed_wiki["has_anime"]
                    res.has_game = res.has_game or parsed_wiki["has_game"]
                    res.publisher = res.publisher or parsed_wiki["publisher"]
                    res.label = res.label or parsed_wiki["label"]
                    res.wikipedia_volumes = max(res.wikipedia_volumes, parsed_wiki["volumes"])
                    if res.wikipedia_title is None:
                        res.wikipedia_title = parsed_wiki["wikipedia_title"]
                        res.wikipedia_pageid = parsed_wiki["wikipedia_pageid"]
            if wiki_matched and "wikipedia" not in res.sources:
                res.sources.append("wikipedia")

            # 3) CiNii Books OpenSearch verification (ISBN-backed Books & Manga)
            cinii = self.verify_work_cinii(
                work,
                search_titles=search_titles,
                author_variants=author_variants,
                trusted_ncode=(has_ncode_pid or wiki_matched or res.has_anime),
            )
            if cinii["matched"]:
                res.has_book = res.has_book or cinii["has_book"]
                res.has_manga = res.has_manga or cinii["has_manga"]
                res.cinii_book_hits = cinii["book_hits"]
                res.cinii_manga_hits = cinii["manga_hits"]
                res.cinii_total_results = cinii["total_results"]
                res.publisher = cinii["publisher"] or res.publisher
                res.label = cinii["label"] or res.label
                res.isbn_sample = cinii["isbn_sample"]
                res.manga_publisher = cinii["manga_publisher"]
                res.manga_label = cinii["manga_label"]
                res.manga_isbn_sample = cinii["manga_isbn_sample"]
                if "cinii_books" not in res.sources:
                    res.sources.append("cinii_books")

            res.verified = bool(res.has_book or res.has_manga or res.has_anime or res.has_game)
            results[work.id] = res
            if idx % 50 == 0 or idx == len(candidates):
                verified_so_far = sum(1 for r in results.values() if r.verified)
                LOGGER.info(
                    "external media verification progress: %s/%s scanned (%s verified)",
                    idx,
                    len(candidates),
                    verified_so_far,
                )

        return results
