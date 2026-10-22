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


def parse_official_card_csv(payload: bytes) -> CardList:
    """Parse ``list_person_all_extended_utf8.csv`` (UTF-8, extended)."""
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    card = CardList(origin="aozora.gr.jp (official CSV)")
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
        title += (" " + _pick(row, "副題")).strip() if _pick(row, "副題") else ""

        ndc = _pick(row, "分類番号") or ""
        ndc_code = ndc.replace("NDC", "").strip()
        first_appearance = _pick(row, "初出")
        base_edition = _pick(row, "底本初版発行年1") or _pick(row, "底本初版発行年")
        published_at = _first_date(base_edition) or _first_date(first_appearance)
        published_year = parse_japanese_year(base_edition) or parse_japanese_year(
            first_appearance
        )
        copyright_flag = (_pick(row, "作品著作権フラグ") or "なし") != "なし"

        text_url = _pick(row, "テキストファイルURL")
        card_url = _pick(row, "図書カードURL")
        if not card_url and person_id and work_id.isdigit():
            card_url = CARD_URL_TEMPLATE.format(person_id=int(person_id), work_id=int(work_id))

        work = Work(
            id=f"aozora:{int(work_id):06d}" if work_id.isdigit() else f"aozora:{work_id}",
            source=AOZORA_SOURCE,
            title=title,
            url=card_url or f"{AOZORA_HOME}/cards/{person_id}/",
            text_url=text_url,
            authors=[
                Author(
                    name=author_name,
                    role="translator" if "訳" in role else "author",
                    id=person_id or None,
                    name_kana=(_pick(row, "姓読み") or "") + (_pick(row, "名読み") or "") or None,
                    url=f"{AOZORA_HOME}/cards/{person_id}/" if person_id else None,
                    born_on=_first_date(_pick(row, "生年月日")),
                    died_on=_first_date(_pick(row, "没年月日")),
                )
            ],
            genre={
                "taxonomy": "NDC",
                "code": ndc_code or None,
                "label": None,
                "parent": {"taxonomy": "NDC", "code": ndc_code[:1] or None},
            },
            published_at=published_at,
            published_year=published_year,
            license="青空文庫 (aozora.gr.jp) 収録作品",
            rights={
                "copyright_flag": copyright_flag,
                "source": "Aozora Bunko",
                "note": "著作権存続作品は再配布不可のため本リポジトリでは除外する",
            },
            stats={"char_count": None},
            extra={
                "first_appearance": first_appearance,
                "base_book": _pick(row, "底本名1") or _pick(row, "底本名"),
                "base_publisher": _pick(row, "底本出版社名1"),
                "kana_type": _pick(row, "文字遣い種別"),
                "worker_input": _pick(row, "入力者"),
                "worker_proofread": _pick(row, "校正者"),
                "text_updated_on": _pick(row, "テキストファイル最終更新日"),
            },
        )
        card.works.append(work)

        if person_id:
            key = f"aozora:{person_id}"
            if key not in card.authors:
                card.authors[key] = AuthorRecord(
                    id=key,
                    source=AOZORA_SOURCE,
                    name=author_name,
                    name_kana=(_pick(row, "姓読み") or "") + (_pick(row, "名読み") or "") or None,
                    url=f"{AOZORA_HOME}/cards/{person_id}/",
                    born_on=_first_date(_pick(row, "生年月日")),
                    died_on=_first_date(_pick(row, "没年月日")),
                    rights={"copyright_flag": (_pick(row, "人物著作権フラグ") or "なし") != "なし"},
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
        ndc_code = bibclass.replace("NDC", "").strip() or None
        url = entry.get("workHTMLURL") or (
            CARD_URL_TEMPLATE.format(person_id=int(person_id or 0), work_id=int(work_id))
        )
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
                "parent": {"taxonomy": "NDC", "code": ndc_code[:1] if ndc_code else None},
            },
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
def load_ndc_map(path: Path) -> Dict[str, str]:
    """Load the NDC code -> label mapping (JSON) if available."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return {}
    mapping: Dict[str, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                mapping[str(key)] = value
            elif isinstance(value, dict):
                label = value.get("name") or value.get("label")
                if label:
                    mapping[str(key)] = label
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                code = item.get("code") or item.get("ndc")
                label = item.get("name") or item.get("label")
                if code and label:
                    mapping[str(code)] = label
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
        """Download (or read) the plain text of a single work."""
        work_id = work.extra.get("work_id")
        if work_id is None and work.id.split(":")[-1].isdigit():
            work_id = int(work.id.split(":")[-1])

        # 1) mirrored text archive
        if index is None:
            index = self.text_index()
        if work_id is not None and work_id in index:
            path = index[work_id]
            payload = path.read_bytes()
            for encoding in ("utf-8", "cp932", "shift_jis"):
                try:
                    return payload.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return payload.decode("utf-8", errors="replace")

        # 2) official per-work archive
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
    """Pick a deterministic, diverse sample of works.

    The sample is spread over the available authors and publication years so
    that the corpus is not dominated by a single prolific writer.
    """
    import random

    candidates = [w for w in works if (w.stats.get("char_count") or 0) >= min_chars]
    if not candidates:
        candidates = list(works)
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
