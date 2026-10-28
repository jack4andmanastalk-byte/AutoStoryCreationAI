"""Unified record schema shared by every dataset.

The goal is that a training / evaluation pipeline can consume ``works.jsonl``
without caring whether the material came from Aozora Bunko (public domain
classics) or from Syosetsuka ni Narou (web novels, some of them later
commercialised).

Field conventions
-----------------
* ``id``            globally unique, ``<source>:<native id>`` (e.g. ``aozora:000148``)
* ``source``        ``aozora_bunko`` / ``syosetsuka_narou``
* ``url``           canonical human facing URL of the work
* ``text_url``      URL the plain text can be downloaded from (may be ``None``)
* ``genre``         ``{"taxonomy", "code", "label", "parent"}`` - the primary genre
* ``genres``        list of secondary genres / tags
* ``published_at``  ISO-8601 date (best effort: first publication / first upload)
* ``published_year`` integer year, handy for slicing the corpus by era
* ``license``       short human readable licence string
* ``rights``        machine readable rights information
* ``stats``         corpus statistics (character counts, episodes, ratings, ...)
* ``text_path``     repository relative path of the normalised plain text
* ``extra``         source specific fields that do not fit the common schema
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

AOZORA_SOURCE = "aozora_bunko"
NAROU_SOURCE = "syosetsuka_narou"


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass
class Author:
    """A person credited on a work."""

    name: str
    role: str = "author"  # author | translator | editor | unknown
    id: Optional[str] = None
    name_kana: Optional[str] = None
    url: Optional[str] = None
    born_on: Optional[str] = None
    died_on: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "id": self.id,
            "name_kana": self.name_kana,
            "url": self.url,
            "born_on": self.born_on,
            "died_on": self.died_on,
            "extra": self.extra,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Author":
        return cls(
            name=data.get("name", ""),
            role=data.get("role", "author"),
            id=data.get("id"),
            name_kana=data.get("name_kana"),
            url=data.get("url"),
            born_on=data.get("born_on"),
            died_on=data.get("died_on"),
            extra=data.get("extra") or {},
        )


@dataclass
class Work:
    """A single creative work (story, poem, essay, ...)."""

    id: str
    source: str
    title: str
    url: str
    text_url: Optional[str] = None
    authors: List[Author] = field(default_factory=list)
    genre: Optional[Dict[str, Any]] = None
    genres: List[Dict[str, Any]] = field(default_factory=list)
    published_at: Optional[str] = None
    published_year: Optional[int] = None
    language: str = "ja"
    license: Optional[str] = None
    rights: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    text_path: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "text_url": self.text_url,
            "authors": [a.to_json() for a in self.authors],
            "genre": self.genre,
            "genres": self.genres,
            "published_at": self.published_at,
            "published_year": self.published_year,
            "language": self.language,
            "license": self.license,
            "rights": self.rights,
            "stats": self.stats,
            "text_path": self.text_path,
            "extra": self.extra,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Work":
        return cls(
            id=data["id"],
            source=data["source"],
            title=data.get("title", ""),
            url=data.get("url", ""),
            text_url=data.get("text_url"),
            authors=[Author.from_json(a) for a in data.get("authors") or []],
            genre=data.get("genre"),
            genres=data.get("genres") or [],
            published_at=data.get("published_at"),
            published_year=data.get("published_year"),
            language=data.get("language", "ja"),
            license=data.get("license"),
            rights=data.get("rights") or {},
            stats=data.get("stats") or {},
            text_path=data.get("text_path"),
            extra=data.get("extra") or {},
        )

    # ------------------------------------------------------------------
    @property
    def primary_author(self) -> Optional[Author]:
        for author in self.authors:
            if author.role == "author":
                return author
        return self.authors[0] if self.authors else None

    def to_summary(self) -> str:
        author = self.primary_author
        who = author.name if author else "?"
        year = self.published_year if self.published_year else "?"
        return f"{self.id}\t{who}\t{year}\t{self.title}"


@dataclass
class AuthorRecord:
    """An author / translator entry (separate file, one row per person)."""

    id: str
    source: str
    name: str
    name_kana: Optional[str] = None
    url: Optional[str] = None
    born_on: Optional[str] = None
    died_on: Optional[str] = None
    rights: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "name": self.name,
            "name_kana": self.name_kana,
            "url": self.url,
            "born_on": self.born_on,
            "died_on": self.died_on,
            "rights": self.rights,
            "extra": self.extra,
        }
