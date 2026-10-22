"""Acquisition of Aozora Bunko material.

Three acquisition paths are supported, in this order of preference:

1. **Official** - ``https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip``
   (the bibliographic CSV published by the Aozora Bunko project) plus the
   per-work text archives (``/cards/<person>/files/<file>.zip``).
2. **Metadata mirror** - the *aozorabunko-re-design* static site which stores
   the very same bibliographic records as JSON payloads.
3. **Legacy mirror** - the ``aozora`` npm package which bundles an older
   snapshot of the CSV list.

The mirrors are only used when the official host cannot be reached; they are
configured in ``configs/dataset.yaml``.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..config import AozoraConfig, PathsConfig
from ..http import HttpClient
from ..schema import AOZORA_SOURCE, Author, AuthorRecord, Work

LOGGER = logging.getLogger(__name__)

AOZORA_HOME = "https://www.aozora.gr.jp"
CARD_URL_TEMPLATE = AOZORA_HOME + "/cards/{person_id:06d}/card{work_id:06d}.html"
FILES_URL_TEMPLATE = AOZORA_HOME + "/cards/{person_id:06d}/files/{filename}"

ERA_OFFSETS = {
    "明治": 1867,
    "大正": 1911,
    "昭和": 1925,
    "平成": 1988,
    "令和": 2018,
}
#: Western style years (1500 - 2100) inside a publication date string.
WESTERN_YEAR_RE = re.compile(r"(1[5-9]\d{2}|20\d{2})")
ERA_RE = re.compile(r"(令和|平成|昭和|明治|大正)\s*(\d+)\s*年")


def parse_japanese_year(text: Optional[str]) -> Optional[int]:
    """Extract a year from a Japanese publication date string.

    ``"1970（昭和45）年6月15日"`` -> ``1970``,
    ``"「新潮」1918（大正7）年3月号"`` -> ``1918``,
    ``"「ホトトギス」1905（明治38）年1月"`` -> ``1905``.
    """
    if not text:
        return None
    match = WESTERN_YEAR_RE.search(text)
    if match:
        return int(match.group(1))
    match = ERA_RE.search(text)
    if match:
        offset = ERA_OFFSETS.get(match.group(1))
        if offset is not None:
            return offset + int(match.group(2))
    return None


def _first_date(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{4})[-/年](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    year = parse_japanese_year(text)
    return f"{year:04d}" if year else None


@dataclass
class CardList:
    """Bibliographic records of a source."""

    works: List[Work] = field(default_factory=list)
    authors: Dict[str, AuthorRecord] = field(default_factory=dict)
    origin: str = "unknown"

    def by_id(self) -> Dict[str, Work]:
        return {work.id: work for work in self.works}


# ---------------------------------------------------------------------------
# official CSV
# ---------------------------------------------------------------------------
def _pick(row: Dict[str, str], *names: str) -> Optional[str]:
    for name in names:
        value = row.get(name)
        if value:
            value = value.strip()
            if value:
                return value
    return None


def _split_ndc_codes(raw: Optional[str]) -> Tuple[Optional[str], List[str]]:
    """Split a raw NDC string (e.g. ``"NDC 289 910"`` or ``"NDC K913"``)."""
    if not raw:
        return None, []
    cleaned = raw.replace("NDC", "").strip()
    tokens = [tok for tok in cleaned.split() if tok]
    if not tokens:
        return None, []
    return tokens[0], tokens[1:]


def _ndc_parent_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    stripped = code.lstrip("K")
    return stripped[:1] if stripped else None


def parse_official_card_csv(payload: bytes) -> CardList:
    """Parse ``list_person_all_extended_utf8.csv`` (UTF-8, extended)."""
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    card = CardList(origin="aozora.gr.jp (official CSV)")
    works_by_id: Dict[str, Work] = {}

    for row in reader:
        work_id = _pick(row, "作品ID", "作品番号")
        title = _pick(row, "作品名")
        if not work_id or not title:
            continue
        person_id = _pick(row, "人物ID") or ""
        role = _pick(row, "役割フラグ") or "著者"
        surname = _pick(row, "姓") or ""
        given = _pick(row, "名") or ""
        author_name = (surname + " " + given).strip() or _pick(row, "著者名") or ""
        subtitle = _pick(row, "副題")
        if subtitle:
            title = f"{title} {subtitle}".strip()

        ndc_code, extra_ndc_codes = _split_ndc_codes(_pick(row, "分類番号"))
        ndc_parent = _ndc_parent_code(ndc_code)
        first_appearance = _pick(row, "初出")
        base_edition = _pick(row, "底本初版発行年1") or _pick(row, "底本初版発行年")
        published_at = _first_date(base_edition) or _first_date(first_appearance)
        published_year = parse_japanese_year(base_edition) or parse_japanese_year(
            first_appearance
        )
        copyright_flag = (_pick(row, "作品著作権フラグ") or "なし") != "なし"
        person_copyright = (_pick(row, "人物著作権フラグ") or "なし") != "なし"

        text_url = _pick(row, "テキストファイルURL")
        text_filename = text_url.rsplit("/", 1)[-1] if text_url and "/" in text_url else None
        card_url = _pick(row, "図書カードURL")
        if not card_url and person_id and work_id.isdigit():
            card_url = CARD_URL_TEMPLATE.format(person_id=int(person_id), work_id=int(work_id))

        author_obj = Author(
            name=author_name,
            role="translator" if "訳" in role else "author",
            id=person_id or None,
            name_kana=(_pick(row, "姓読み") or "") + (_pick(row, "名読み") or "") or None,
            url=f"{AOZORA_HOME}/cards/{person_id}/" if person_id else None,
            born_on=_first_date(_pick(row, "生年月日")),
            died_on=_first_date(_pick(row, "没年月日")),
        )

        canonical_id = f"aozora:{int(work_id):06d}" if work_id.isdigit() else f"aozora:{work_id}"
        existing = works_by_id.get(canonical_id)
        if existing is not None:
            if not any(
                a.id == author_obj.id and a.name == author_obj.name and a.role == author_obj.role
                for a in existing.authors
            ):
                existing.authors.append(author_obj)
            existing.rights["copyright_flag"] = bool(
                existing.rights.get("copyright_flag")
            ) or copyright_flag or person_copyright
            if not existing.text_url and text_url:
                existing.text_url = text_url
        else:
            work = Work(
                id=canonical_id,
                source=AOZORA_SOURCE,
                title=title,
                url=card_url or f"{AOZORA_HOME}/cards/{person_id}/",
                text_url=text_url,
                authors=[author_obj],
                genre={
                    "taxonomy": "NDC",
                    "code": ndc_code,
                    "label": None,
                    "parent": {"taxonomy": "NDC", "code": ndc_parent},
                },
                genres=[
                    {"taxonomy": "NDC", "code": extra_code, "label": None}
                    for extra_code in extra_ndc_codes
                ],
                published_at=published_at,
                published_year=published_year,
                license="青空文庫 (aozora.gr.jp) 収録作品",
                rights={
                    "copyright_flag": copyright_flag or person_copyright,
                    "source": "Aozora Bunko",
                    "note": "著作権存続作品は再配布不可のため本リポジトリでは除外する",
                },
                stats={"char_count": None},
                extra={
                    "first_appearance": first_appearance,
                    "base_book": _pick(row, "底本名1") or _pick(row, "底本名"),
                    "base_publisher": _pick(row, "底本出版社名1"),
                    "kana_type": _pick(row, "文字遣い種別"),
                    "person_id": int(person_id) if person_id.isdigit() else (person_id or None),
                    "work_id": int(work_id) if work_id.isdigit() else work_id,
                    "text_filename": text_filename,
                    "worker_input": _pick(row, "入力者"),
                    "worker_proofread": _pick(row, "校正者"),
                    "text_updated_on": _pick(row, "テキストファイル最終更新日"),
                },
            )
            works_by_id[canonical_id] = work
            card.works.append(work)

        if person_id:
            key = f"aozora:{int(person_id):06d}" if person_id.isdigit() else f"aozora:{person_id}"
            if key not in card.authors:
                card.authors[key] = AuthorRecord(
                    id=key,
                    source=AOZORA_SOURCE,
                    name=author_name,
                    name_kana=(_pick(row, "姓読み") or "") + (_pick(row, "名読み") or "") or None,
                    url=f"{AOZORA_HOME}/cards/{person_id}/",
                    born_on=_first_date(_pick(row, "生年月日")),
                    died_on=_first_date(_pick(row, "没年月日")),
                    rights={"copyright_flag": person_copyright},
                    extra={"role": role},
                )
    LOGGER.info("parsed %s works from the official CSV", len(card.works))
    return card


def parse_legacy_card_csv(payload: bytes) -> CardList:
    """Parse the older ``list_person_all.utf8.csv`` (npm mirror)."""
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    card = CardList(origin="npm mirror (aozora/list_person_all.utf8.csv)")
    for row in reader:
        work_id = _pick(row, "作品ID")
        title = _pick(row, "作品名")
        if not work_id or not title:
            continue
        person_id = _pick(row, "人物ID") or ""
        author_name = _pick(row, "著者名") or ""
        translator = _pick(row, "翻訳者名等")
        published_at = _first_date(_pick(row, "状態の開始日"))
        work = Work(
            id=f"aozora:{int(work_id):06d}" if work_id.isdigit() else f"aozora:{work_id}",
            source=AOZORA_SOURCE,
            title=title,
            url=CARD_URL_TEMPLATE.format(person_id=int(person_id or 0), work_id=int(work_id)),
            authors=[
                Author(
                    name=author_name,
                    role="author",
                    id=person_id or None,
                    url=f"{AOZORA_HOME}/cards/{person_id}/" if person_id else None,
                )
            ]
            + (
                [Author(name=translator, role="translator")]
                if translator
                else []
            ),
            genre={"taxonomy": "NDC", "code": None, "label": None},
            published_at=published_at,
            published_year=int(published_at[:4]) if published_at and published_at[:4].isdigit() else None,
            license="青空文庫 (aozora.gr.jp) 収録作品",
            rights={"copyright_flag": None, "source": "Aozora Bunko"},
            extra={
                "base_book": _pick(row, "底本名"),
                "base_publisher": _pick(row, "出版社名"),
                "kana_type": _pick(row, "仮名遣い種別"),
                "status": _pick(row, "状態"),
            },
        )
        card.works.append(work)
    LOGGER.info("parsed %s works from the legacy CSV mirror", len(card.works))
    return card


# ---------------------------------------------------------------------------
# static site mirror (JSON payloads)
# ---------------------------------------------------------------------------
def _scan_balanced(text: str, start: int, open_char: str, close_char: str) -> Tuple[str, int]:
    """Return the balanced ``open_char``/``close_char`` slice starting at ``start``."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
    raise ValueError("unbalanced expression")


def _quote_js_keys(text: str) -> str:
    """Quote the unquoted object keys of a JavaScript object literal.

    The NUXT payloads use the JavaScript notation ``{data:[{book:{...}}]}``
    which is not valid JSON.  Only the text outside of string literals is
    rewritten so that URLs or titles containing ``:`` stay untouched.
    """
    out: List[str] = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char in "{,":
            out.append(char)
            index += 1
            # look ahead for ``identifier :``
            match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*:", text[index:])
            if match:
                out.append(' "')
                out.append(match.group(1))
                out.append('":')
                index += match.end()
            continue
        out.append(char)
        index += 1
    return "".join(out)


def parse_nuxt_payload(text: str) -> Dict[str, Any]:
    """Parse a ``__NUXT_JSONP__`` payload into plain Python data."""
    match = re.search(r"function\(([^)]*)\)\{", text)
    if not match:
        raise ValueError("not a NUXT payload")
    params = [p.strip() for p in match.group(1).split(",") if p.strip()]

    body_start = match.end()
    body, body_end = _scan_balanced(text, body_start - 1, "{", "}")

    # the function is immediately called: ``}(arg1, arg2, ...)``
    cursor = body_end
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor >= len(text) or text[cursor] != "(":
        raise ValueError("cannot locate the argument list")
    args_text, _ = _scan_balanced(text, cursor, "(", ")")
    args = json.loads("[" + args_text[1:-1] + "]")

    # assignments such as ``f.bibclass="NDC 913";`` build the helper objects
    assignment_part, _, return_part = body.partition("return")
    assigned: Dict[str, Dict[str, Any]] = {}
    for prop, key, raw in re.findall(
        r"([A-Za-z_$][\w$]*)\.([A-Za-z_][\w]*)\s*=\s*(\"(?:[^\"\\]|\\.)*\")", assignment_part
    ):
        assigned.setdefault(prop, {})[key] = json.loads(raw)

    values: Dict[str, Any] = {}
    for position, name in enumerate(params):
        argument = args[position] if position < len(args) else None
        if name in assigned:
            merged = dict(argument) if isinstance(argument, dict) else {}
            merged.update(assigned[name])
            values[name] = merged
        else:
            values[name] = argument

    payload_json, _ = _scan_balanced(return_part.strip(), return_part.strip().index("{"), "{", "}")

    replacements = {
        name: json.dumps(values.get(name, ""), ensure_ascii=False)
        for name in params
        if name in values
    }
    for name, value in replacements.items():
        payload_json = re.sub(rf"(?<![\w\"]){re.escape(name)}(?![\w\"])", value, payload_json)
    # some payloads contain raw line breaks inside strings
    return json.loads(_quote_js_keys(payload_json), strict=False)


def parse_pages_mirror(root: Path) -> CardList:
    """Parse the *aozorabunko-re-design* static site export."""
    card = CardList(origin="GitHub mirror: aewshyae/aozorabunko-re-design_pages")
    works_dir = None
    for candidate in root.glob("**/static/*/works"):
        works_dir = candidate
        break
    if works_dir is None:
        raise FileNotFoundError(f"no works directory found below {root}")

    for payload_path in sorted(works_dir.glob("*/payload.js")):
        try:
            data = parse_nuxt_payload(payload_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("cannot parse %s: %s", payload_path, exc)
            continue
        entries = data.get("data") or []
        if not entries:
            continue
        entry = entries[0]
        book = entry.get("book") or {}
        title_info = book.get("title") or {}
        work_meta = book.get("work") or {}
        work_id = title_info.get("work_id")
        person_id = title_info.get("person_id")
        title = title_info.get("title")
        if not work_id or not title:
            continue

        authors: List[Author] = []
        for item in book.get("author") or []:
            authors.append(
                Author(
                    name=item.get("author_name") or "",
                    role="translator" if "訳" in (item.get("role") or "") else "author",
                    id=str(item.get("author_id")) if item.get("author_id") is not None else None,
                    name_kana=item.get("author_kana"),
                    url=(
                        f"{AOZORA_HOME}/cards/{int(item['author_id']):06d}/"
                        if item.get("author_id") is not None
                        else None
                    ),
                    born_on=item.get("born_on"),
                    died_on=item.get("died_on"),
                    extra={"note": item.get("author_note"), "latin": item.get("author_en")},
                )
            )

        first_appearance = work_meta.get("first_appearance")
        original_books = book.get("original_book") or []
        base_year_text = None
        base_title = None
        base_publisher = None
        for original in original_books:
            if original.get("first_edition"):
                base_year_text = original["first_edition"]
                base_title = original.get("book_title")
                base_publisher = original.get("publisher")
                break

        published_year = parse_japanese_year(base_year_text) or parse_japanese_year(
            first_appearance
        )
        published_at = _first_date(base_year_text) or _first_date(first_appearance)

        downloads = book.get("download") or []
        text_filename = None
        created_on = None
        updated_on = None
        for item in downloads:
            if item.get("filetype", "").startswith("テキストファイル"):
                text_filename = item.get("filename")
                created_on = item.get("created_on")
                updated_on = item.get("updated_on")
                break

        bibclass = work_meta.get("bibclass") or ""
        ndc_code, extra_ndc_codes = _split_ndc_codes(bibclass)
        ndc_parent = _ndc_parent_code(ndc_code)
        url = CARD_URL_TEMPLATE.format(person_id=int(person_id or 0), work_id=int(work_id))
        # the HTML rendering of the work and the downloadable archive
        html_url = entry.get("workHTMLURL")
        text_url = (
            FILES_URL_TEMPLATE.format(person_id=int(person_id or 0), filename=text_filename)
            if text_filename and person_id is not None
            else None
        )

        work = Work(
            id=f"aozora:{int(work_id):06d}",
            source=AOZORA_SOURCE,
            title=title,
            url=url,
            text_url=text_url,
            authors=authors,
            genre={
                "taxonomy": "NDC",
                "code": ndc_code,
                "label": None,
                "parent": {"taxonomy": "NDC", "code": ndc_parent},
            },
            genres=[
                {"taxonomy": "NDC", "code": extra_code, "label": None}
                for extra_code in extra_ndc_codes
            ],
            published_at=published_at,
            published_year=published_year,
            license="青空文庫 (aozora.gr.jp) 収録作品",
            rights={
                "copyright_flag": bool(book.get("copyright")),
                "source": "Aozora Bunko",
                "note": "作品著作権フラグが有効な作品は再配布不可",
            },
            stats={"char_count": None},
            extra={
                "title_kana": title_info.get("title_kana"),
                "first_appearance": first_appearance,
                "base_book": base_title,
                "base_publisher": base_publisher,
                "base_edition": base_year_text,
                "kana_type": work_meta.get("kana_type"),
                "person_id": person_id,
                "work_id": work_id,
                "text_filename": text_filename,
                "html_url": html_url,
                "text_created_on": created_on,
                "text_updated_on": updated_on,
                "worker": book.get("worker"),
            },
        )
        card.works.append(work)

        for author in authors:
            if not author.id:
                continue
            key = f"aozora:{int(author.id):06d}"
            if key not in card.authors:
                card.authors[key] = AuthorRecord(
                    id=key,
                    source=AOZORA_SOURCE,
                    name=author.name,
                    name_kana=author.name_kana,
                    url=author.url,
                    born_on=author.born_on,
                    died_on=author.died_on,
                    extra={"note": author.extra.get("note")},
                )
    LOGGER.info("parsed %s works from the static site mirror", len(card.works))
    return card


# ---------------------------------------------------------------------------
# NDC classification
# ---------------------------------------------------------------------------
#: The ten major classes of the Nippon Decimal Classification (NDC).
NDC_MAJOR_CLASSES: Dict[str, str] = {
    "0": "総記",
    "1": "哲学",
    "2": "歴史・地理・旅行",
    "3": "社会科学",
    "4": "自然科学",
    "5": "技術・工学",
    "6": "産業",
    "7": "芸術・美術",
    "8": "言語",
    "9": "文学",
}

#: Standard NDC 2-digit divisions (綱目表) and common 3-digit sections (要目表).
NDC_STANDARD_CLASSES: Dict[str, str] = {
    **NDC_MAJOR_CLASSES,
    # 00-09 総記
    "00": "総記", "01": "図書館・図書館情報学", "02": "図書・書誌学", "03": "百科事典",
    "04": "一般論文集・一般講演集", "05": "逐次刊行物", "06": "団体", "07": "ジャーナリズム・新聞",
    "08": "叢書・全集・選集", "09": "貴重書・郷土資料",
    # 10-19 哲学
    "10": "哲学総記", "11": "哲学各論", "12": "東洋思想", "13": "西洋哲学",
    "14": "心理学", "15": "倫理学・道徳", "16": "宗教", "17": "神道",
    "18": "仏教", "19": "キリスト教",
    "121": "日本思想", "147": "超心理学・心霊研究", "188": "各宗",
    # 20-29 歴史
    "20": "歴史総記", "21": "日本史", "22": "アジア史・東洋史", "23": "ヨーロッパ史・西洋史",
    "24": "アフリカ史", "25": "北アメリカ史", "26": "南アメリカ史", "27": "オセアニア史",
    "28": "伝記", "29": "地理・地誌・紀行",
    "210": "日本史", "222": "中国史", "281": "日本の伝記", "289": "個人の伝記",
    "290": "地理・地誌・紀行", "291": "日本の地理・紀行", "293": "ヨーロッパの地理・紀行",
    # 30-39 社会科学
    "30": "社会科学総記", "31": "政治", "32": "法律", "33": "経済",
    "34": "財政", "35": "統計", "36": "社会", "37": "教育",
    "38": "風俗習慣・民俗学・民族学", "39": "国防・軍事",
    "304": "社会科学論集", "309": "社会思想", "312": "政治史・事情", "319": "平和問題・国際政治",
    "361": "社会学", "367": "家族問題・女性問題", "370": "教育",
    "382": "風俗史・民俗誌", "386": "年中行事・祭礼", "387": "民間信仰・迷信", "388": "伝説・民話",
    # 40-49 自然科学
    "40": "自然科学総記", "41": "数学", "42": "物理学", "43": "化学",
    "44": "天文学・宇宙科学", "45": "地球科学・地学", "46": "生物科学・一般生物学",
    "47": "植物学", "48": "動物学", "49": "医学・薬学",
    "401": "科学理論・科学哲学", "404": "科学論集・エッセイ", "451": "気象学",
    # 50-59 技術・工学
    "50": "技術・工学総記", "51": "建設工学・土木工学", "52": "建築学", "53": "機械工学",
    "54": "電気工学・電子工学", "55": "海洋工学・船舶工学", "56": "金属工学・鉱山工学",
    "57": "化学工業", "58": "製造工業", "59": "家政学・生活科学",
    "596": "食品・料理",
    # 60-69 産業
    "60": "産業総記", "61": "農業", "62": "園芸", "63": "蚕糸業",
    "64": "畜産業", "65": "林業", "66": "水産業", "67": "商業",
    "68": "運輸・交通", "69": "通信事業",
    # 70-79 芸術・美術
    "70": "芸術・美術総記", "71": "彫刻", "72": "絵画・書道", "73": "版画",
    "74": "写真・印刷", "75": "工芸", "76": "音楽・舞踊", "77": "演劇・映画",
    "78": "スポーツ・体育", "79": "諸芸・娯楽",
    "701": "芸術理論・美学", "712": "彫刻史", "720": "絵画", "721": "日本画",
    "723": "洋画", "726": "漫画・挿絵・児童画", "728": "書・書道", "751": "陶磁工芸",
    "768": "邦楽", "770": "演劇", "771": "劇場・演出・演技", "772": "演劇史",
    "773": "能楽・狂言", "774": "歌舞伎", "775": "各種の演劇", "778": "映画",
    "779": "大衆演芸", "786": "戸外レクリエーション・登山", "787": "釣魚・遊猟",
    # 80-89 言語
    "80": "言語総記", "81": "日本語", "82": "中国語・東洋諸語", "83": "英語",
    "84": "ドイツ語", "85": "フランス語", "86": "スペイン語", "87": "イタリア語",
    "88": "ロシア語", "89": "その他の諸言語",
    # 90-99 文学（3桁要目を網羅）
    "90": "文学総記", "91": "日本文学", "92": "中国文学・東洋文学", "93": "英米文学",
    "94": "ドイツ文学", "95": "フランス文学", "96": "スペイン文学", "97": "イタリア文学",
    "98": "ロシア・ソビエト文学", "99": "その他の諸文学",
    "901": "文学理論・詩学", "902": "文学史・文芸思潮史", "904": "文学論集・エッセイ",
    "908": "世界文学叢書・全集", "909": "児童文学研究",
    "910": "日本文学", "911": "詩歌（日本文学）", "912": "戯曲（日本文学）",
    "913": "小説・物語（日本文学）", "914": "評論・エッセイ・随筆（日本文学）",
    "915": "日記・書簡・紀行（日本文学）", "916": "記録・手記・ルポルタージュ（日本文学）",
    "917": "諷刺・ユーモア・アフォリズム（日本文学）", "918": "作品集（日本文学）",
    "920": "中国文学・東洋文学", "921": "中国詩歌・漢詩", "922": "中国戯曲",
    "923": "中国小説・物語", "924": "中国評論・随筆", "929": "その他の東洋文学",
    "930": "英米文学", "931": "英米詩", "932": "英米戯曲", "933": "英米小説・物語",
    "934": "英米エッセイ・随筆", "935": "英米日記・書簡・紀行", "936": "英米記録・手記",
    "940": "ドイツ文学", "941": "ドイツ詩", "942": "ドイツ戯曲", "943": "ドイツ小説・物語",
    "944": "ドイツエッセイ・随筆", "949": "その他のゲルマン文学（北欧文学等）",
    "950": "フランス文学", "951": "フランス詩", "952": "フランス戯曲", "953": "フランス小説・物語",
    "954": "フランスエッセイ・随筆", "955": "フランス日記・書簡・紀行",
    "960": "スペイン文学", "963": "スペイン小説・物語",
    "970": "イタリア文学", "971": "イタリア詩", "973": "イタリア小説・物語",
    "980": "ロシア・ソビエト文学", "981": "ロシア詩", "982": "ロシア戯曲",
    "983": "ロシア小説・物語", "984": "ロシアエッセイ・随筆",
    "990": "その他の諸文学", "991": "ギリシア文学", "992": "ラテン文学",
}


def resolve_ndc_label(code: Optional[str], ndc_map: Dict[str, str]) -> Optional[str]:
    """Resolve an NDC code (including ``K`` juvenile prefix or decimals) to a label."""
    if not code:
        return None
    raw = code.strip()
    if raw in ndc_map:
        return ndc_map[raw]
    is_juvenile = raw.startswith("K")
    stripped = raw.lstrip("K").split(".", 1)[0]
    label = (
        ndc_map.get(stripped)
        or (ndc_map.get(stripped[:3]) if len(stripped) >= 3 else None)
        or (ndc_map.get(stripped[:2]) if len(stripped) >= 2 else None)
        or (ndc_map.get(stripped[:1]) if stripped else None)
    )
    if label and is_juvenile and "児童" not in label:
        return f"{label}（児童書）"
    return label


def enrich_ndc_genre(work: Work, ndc_map: Dict[str, str]) -> None:
    """Populate human-readable NDC labels on ``work.genre`` and ``work.genres``."""
    if work.genre:
        raw_code = work.genre.get("code")
        primary, extras = _split_ndc_codes(raw_code)
        if primary:
            work.genre["code"] = primary
            work.genre["label"] = resolve_ndc_label(primary, ndc_map)
            parent_code = _ndc_parent_code(primary)
            work.genre["parent"] = {
                "taxonomy": "NDC",
                "code": parent_code,
                "label": ndc_map.get(parent_code) if parent_code else None,
            }
        existing_codes = {g.get("code") for g in work.genres}
        for extra_code in extras:
            if extra_code not in existing_codes:
                work.genres.append({"taxonomy": "NDC", "code": extra_code, "label": None})
                existing_codes.add(extra_code)
    for item in work.genres:
        if item.get("taxonomy") == "NDC" and item.get("code") and not item.get("label"):
            item["label"] = resolve_ndc_label(item["code"], ndc_map)


def _flatten_ndc(node: Any, mapping: Dict[str, str]) -> None:
    """Walk the nested NDC classification tree."""
    if not isinstance(node, dict):
        return
    label = node.get("name") or node.get("label")
    code = node.get("code") or node.get("ndc")
    if code and label:
        mapping[str(code)] = str(label)
    children = node.get("classes") or node.get("children") or {}
    if isinstance(children, dict):
        for child_code, child in children.items():
            if isinstance(child, dict):
                child_label = child.get("name") or child.get("label")
                if child_label:
                    mapping[str(child_code)] = str(child_label)
                _flatten_ndc(child, mapping)
    elif isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                child_code = child.get("code") or child.get("ndc")
                child_label = child.get("name") or child.get("label")
                if child_code and child_label:
                    mapping[str(child_code)] = str(child_label)
                _flatten_ndc(child, mapping)


def load_ndc_map(path: Optional[Path] = None) -> Dict[str, str]:
    """Load the NDC code -> label mapping (JSON) if available.

    The mapping is always seeded with the built-in standard NDC major classes,
    divisions, and sections so that every work gets a human-readable genre
    even without an external file.
    """
    mapping: Dict[str, str] = dict(NDC_STANDARD_CLASSES)
    if not path or not Path(path).exists():
        return mapping
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return mapping
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                mapping[str(key)] = value
            elif isinstance(value, dict):
                label = value.get("name") or value.get("label")
                if label:
                    mapping[str(key)] = str(label)
                _flatten_ndc(value, mapping)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                code = item.get("code") or item.get("ndc")
                label = item.get("name") or item.get("label")
                if code and label:
                    mapping[str(code)] = str(label)
                _flatten_ndc(item, mapping)
    return mapping


# ---------------------------------------------------------------------------
# source driver
# ---------------------------------------------------------------------------
class AozoraSource:
    """Downloads Aozora Bunko metadata and texts."""

    def __init__(
        self,
        config: AozoraConfig,
        paths: PathsConfig,
        client: HttpClient,
    ) -> None:
        self.config = config
        self.paths = paths
        self.client = client

    # -- metadata -----------------------------------------------------
    def fetch_card_list(self) -> CardList:
        errors: List[str] = []
        for url in self.config.card_list_urls:
            try:
                LOGGER.info("downloading the official card list: %s", url)
                payload = self.client.get(url)
                if url.endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                        name = next(
                            (n for n in archive.namelist() if n.endswith(".csv")),
                            archive.namelist()[0],
                        )
                        payload = archive.read(name)
                return parse_official_card_csv(payload)
            except Exception as exc:  # pragma: no cover - network dependent
                errors.append(f"{url}: {exc}")
                LOGGER.warning("official card list unavailable (%s)", exc)

        for mirror in self.config.card_list_mirrors:
            try:
                LOGGER.info("downloading the card list mirror: %s", mirror)
                payload = self.client.get(mirror)
                card = self._parse_mirror_payload(payload)
                if card is not None:
                    return card
                errors.append(f"{mirror}: unsupported payload")
            except Exception as exc:  # pragma: no cover - network dependent
                errors.append(f"{mirror}: {exc}")
                LOGGER.warning("card list mirror unavailable (%s)", exc)

        raise RuntimeError("no Aozora card list could be downloaded:\n" + "\n".join(errors))

    def _extract_tarball(self, payload: bytes, name: str) -> Path:
        target = self.paths.cache_dir / name
        marker = target / ".extracted"
        if marker.exists():
            return target
        target.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                archive.extractall(target, filter="data")  # type: ignore[call-arg]
        except TypeError:  # pragma: no cover - Python < 3.11.4
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                archive.extractall(target)
        marker.write_text("ok", encoding="utf-8")
        return target

    def _parse_mirror_payload(self, payload: bytes) -> Optional[CardList]:
        """Interpret a mirror payload (tarball / zip / plain CSV)."""
        if payload[:2] == b"\x1f\x8b":  # gzip
            root = self._extract_tarball(payload, "aozora_pages")
            if list(root.glob("**/static/*/works")):
                return parse_pages_mirror(root)
            csv_files = sorted(root.rglob("*.csv"))
            if csv_files:
                return parse_legacy_card_csv(csv_files[0].read_bytes())
            return None
        if payload[:2] == b"PK":  # zip
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = [n for n in archive.namelist() if n.endswith(".csv")]
                if not names:
                    return None
                return parse_legacy_card_csv(archive.read(names[0]))
        return parse_legacy_card_csv(payload)

    # -- texts ---------------------------------------------------------
    def ensure_text_mirror(self) -> Path:
        """Download (once) and extract the mirrored text archive."""
        target = self.paths.cache_dir / "aozorabunko_text"
        marker = target / ".extracted"
        if marker.exists():
            return target
        url = self.config.text_mirror_tarball
        if not url:
            return target
        local_archive = self.paths.cache_dir / "aozorabunko_text.tar.gz"
        if local_archive.exists():
            LOGGER.info("using the cached archive %s", local_archive)
            payload = local_archive.read_bytes()
        else:
            LOGGER.info("downloading the text mirror: %s", url)
            payload = self.client.get(url)
            local_archive.write_bytes(payload)
        target.mkdir(parents=True, exist_ok=True)
        LOGGER.info("extracting %s", target)
        try:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                archive.extractall(target, filter="data")  # type: ignore[call-arg]
        except TypeError:  # pragma: no cover - Python < 3.11.4
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                archive.extractall(target)
        marker.write_text("ok", encoding="utf-8")
        return self._cards_root(target)

    @staticmethod
    def _cards_root(root: Path) -> Path:
        """Return the directory that contains the ``cards`` folder."""
        if (root / "cards").is_dir():
            return root
        for candidate in root.glob("*/cards"):
            return candidate.parent
        return root

    def text_index(self) -> Dict[int, Path]:
        """Index of the mirrored text files: ``work id -> path``."""
        index: Dict[int, Path] = {}
        root = self._cards_root(self.paths.cache_dir / "aozorabunko_text")
        if not root.exists():
            return index
        for path in root.glob("cards/*/files/*/*.txt"):
            base = path.parent.name
            prefix = base.split("_", 1)[0]
            if prefix.isdigit():
                index.setdefault(int(prefix), path)
        return index

    def fetch_text(self, work: Work, index: Optional[Dict[int, Path]] = None) -> Optional[str]:
        """Download (or read) the plain text of a single public-domain work."""
        if work.rights.get("copyright_flag") is True:
            LOGGER.warning("skipping copyrighted work %s (%s)", work.id, work.title)
            return None

        work_id = work.extra.get("work_id")
        if work_id is None and work.id.split(":")[-1].isdigit():
            work_id = int(work.id.split(":")[-1])
        elif isinstance(work_id, str) and work_id.isdigit():
            work_id = int(work_id)

        # 1) mirrored text archive
        if index is None:
            index = self.text_index()
        if isinstance(work_id, int) and work_id in index:
            path = index[work_id]
            payload = path.read_bytes()
            for encoding in ("utf-8", "cp932", "shift_jis"):
                try:
                    return payload.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return payload.decode("utf-8", errors="replace")

        # 2) official per-work archive
        url = work.text_url if (work.text_url and work.text_url.endswith(".zip")) else None
        if not url:
            filename = work.extra.get("text_filename")
            person_id = work.extra.get("person_id")
            if not filename:
                return None
            if person_id is None:
                match = re.search(r"/cards/(\d{6})/", work.url or "")
                person_id = match.group(1) if match else None
            if person_id is None:
                return None
            url = FILES_URL_TEMPLATE.format(person_id=int(person_id), filename=filename)
        try:
            payload = self.client.get(url)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("cannot download %s: %s", url, exc)
            return None
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [n for n in archive.namelist() if n.endswith(".txt")]
            if not names:
                return None
            raw = archive.read(names[0])
        for encoding in ("cp932", "shift_jis", "utf-8"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# sampling helpers
# ---------------------------------------------------------------------------
def sample_works(
    works: Sequence[Work],
    count: int,
    seed: int = 20240101,
    min_chars: int = 0,
) -> List[Work]:
    """Pick a deterministic, diverse sample of public-domain works.

    Works whose ``rights.copyright_flag`` is ``True`` are strictly excluded.
    The sample is spread over the available authors and publication years so
    that the corpus is not dominated by a single prolific writer.
    """
    import random

    public_domain = [w for w in works if w.rights.get("copyright_flag") is not True]
    candidates = [w for w in public_domain if (w.stats.get("char_count") or 0) >= min_chars]
    if not candidates:
        candidates = list(public_domain)
    rng = random.Random(seed)

    by_author: Dict[str, List[Work]] = {}
    for work in candidates:
        key = work.authors[0].id if work.authors else work.id
        by_author.setdefault(key, []).append(work)

    by_year: Dict[int, List[Work]] = {}
    for work in candidates:
        by_year.setdefault(work.published_year or 0, []).append(work)

    chosen: List[Work] = []
    seen: set = set()
    authors = sorted(by_author)
    years = sorted(by_year)
    rng.shuffle(authors)
    rng.shuffle(years)

    # round-robin over authors, then over years for the remaining slots
    while len(chosen) < count and authors:
        for author in list(authors):
            if len(chosen) >= count:
                break
            bucket = by_author[author]
            work = rng.choice(bucket)
            if work.id in seen:
                bucket.remove(work)
                if not bucket:
                    authors.remove(author)
                continue
            seen.add(work.id)
            chosen.append(work)
        if not authors:
            break
        break

    if len(chosen) < count:
        for year in years:
            if len(chosen) >= count:
                break
            for work in by_year[year]:
                if work.id in seen:
                    continue
                seen.add(work.id)
                chosen.append(work)
                if len(chosen) >= count:
                    break
    return chosen[:count]
