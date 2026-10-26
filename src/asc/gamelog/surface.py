"""Advisory surface checks: places people go to, and numbers people write.

The detection-power probe (``scripts/probe_detection_power.py``) showed that two
errors slip past every existing check: a place and a trip that the log never
declares, and a quantity the log never says. This module is the candidate
answer, kept **outside** the contract on purpose:

* it is a pattern match on Japanese prose (a travel verb plus a place-shaped
  word), so its precision has to be measured before it can block a repair;
* the number side is not implemented as a check at all. Comparing numerals with
  the log sounds mechanical, but a numeral has no reference of its own: 「一本」
  in 「環には一本」 is not the same claim as 「二本」 in a canon fact. A token
  match cannot tell an invented count from ordinary language, so what is here
  is a *report* (which numerals appear, which have no counterpart in the log or
  canon), not a verdict.

Nothing here is wired into :func:`asc.gamelog.rewrite.check_rewrite`. The module
exists so the experiment can measure recall and precision on real text, and so a
later decision to adopt (or drop) it is made against numbers instead of taste.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..story.canon import Canon

#: ``<place>へ/に + <movement verb>``. Deliberately narrow: it should fire on an
#: assertion of travel, not on every use of に.
MOVEMENT_RE = re.compile(
    r"([^\s、。「」『』（）]{1,12}?)(?:へ|に)"
    r"(?:渡った|渡り|向かった|向かい|着いた|着き|発った|発ち|出発した|"
    r"戻った|戻り|行った|行き|帰った|帰り)")

#: A destination has to look like a place before it is worth checking; without
#: this, 「父は灯りの話に戻った」 is read as a trip to "父は灯りの話".
PLACE_SUFFIX_RE = re.compile(
    r"(港|島|町|村|城|塔|灯台|王都|岬|山|川|海|岸|通り|市場|宿|門)$")

#: A numeral plus a counter. Used for the report only (see the module note).
NUMBER_RE = re.compile(
    r"(?:[0-9]+|[一二三四五六七八九十半百]+)\s*"
    r"(?:日|年|度|回|度目|つ|人|本|枚|刻|時間|晩|夜|月|里)")

_KANJI_VALUE = {"一": 1.0, "二": 2.0, "三": 3.0, "四": 4.0, "五": 5.0,
                "六": 6.0, "七": 7.0, "八": 8.0, "九": 9.0, "十": 10.0,
                "半": 0.5, "百": 100.0}


@dataclass(frozen=True)
class MovementClaim:
    destination: str
    expression: str
    line: int
    sentence: str


def sentences(text: str) -> list[tuple[int, str]]:
    """``(line, sentence)`` pairs; markers are removed first."""
    stripped = re.sub(r"\{\{[^{}]*\}\}", "", text)
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(stripped.splitlines(), start=1):
        for part in re.split(r"(?<=[。！？])", raw):
            part = part.strip()
            if part:
                out.append((number, part))
    return out


def movement_claims(text: str) -> list[MovementClaim]:
    """Assertions of travel to a place-shaped destination."""
    claims: list[MovementClaim] = []
    for line, sentence in sentences(text):
        for match in MOVEMENT_RE.finditer(sentence):
            destination = _destination_name(match.group(1))
            if PLACE_SUFFIX_RE.search(destination):
                claims.append(MovementClaim(destination=destination,
                                            expression=match.group(0),
                                            line=line, sentence=sentence))
    return claims


#: Boundaries that end a leading clause before the place name. ``て``/``で`` are
#: here because real prose writes 「三日かけて王都へ着いた」: without them the
#: duration is carried into the destination (「三日かけて王都」) and the finding
#: names a place that does not exist.
_CLAUSE_SPLIT_RE = re.compile(r"[はがをでて]|から|まで|、")


def _destination_name(raw: str) -> str:
    """The place-shaped tail of a capture (「アリアは船で対岸の島」→「対岸の島」)."""
    tail = _CLAUSE_SPLIT_RE.split(raw)[-1] or raw
    match = PLACE_SUFFIX_RE.search(tail)
    if not match:
        return tail
    return tail[: match.end()]


def place_findings(text: str, chapter: dict, canon: Canon) -> list[dict]:
    """Travel to a place that the canon or the log for this chapter lacks.

    Advisory (``blocks_repair=False`` semantics): the caller decides what to do
    with it. ``chapter`` is a row from
    :func:`asc.gamelog.world.derive_timeline`.
    """
    known = set(canon.locations)
    allowed = {chapter.get("location")} | {
        place for move in chapter.get("moves", [])
        for place in (move.get("origin"), move.get("destination"))}
    findings: list[dict] = []
    for claim in movement_claims(text):
        name = claim.destination
        if name in allowed:
            continue
        if name in known:
            reason = (f"「{name}」は canon にあるが、この章の移動として"
                      f"ログに宣言されていない")
        else:
            reason = f"「{name}」は canon にもログにもない地名"
        findings.append({
            "check": "movement_surface",
            "severity": "medium",
            "advisory": True,
            "message_ja": f"「{claim.expression}」— {reason}。",
            "evidence": {"destination": name, "expression": claim.expression,
                         "line": claim.line, "sentence": claim.sentence[:80]},
        })
    return findings


def numbers_in_text(text: str) -> list[dict]:
    """Every numeral-plus-counter token in the prose, with its line."""
    out: list[dict] = []
    for line, sentence in sentences(text):
        for match in NUMBER_RE.finditer(sentence):
            token = re.sub(r"\s", "", match.group(0))
            out.append({"token": token, "value": _value(token), "line": line,
                        "sentence": sentence[:80]})
    return out


def _value(token: str) -> float | None:
    digits = re.match(r"[0-9]+", token)
    if digits:
        return float(digits.group(0))
    head = re.match(r"[一二三四五六七八九十半百]+", token)
    if not head:
        return None
    raw = head.group(0)
    if raw in _KANJI_VALUE:
        return _KANJI_VALUE[raw]
    return None


def unmatched_numbers(text: str, references: str) -> list[dict]:
    """Numerals whose *token* does not appear in the reference text.

    A report, not a check: 「一本」 never appears in the log or canon, yet
    「環には一本」 is ordinary language rather than an invented fact. The caller
    is expected to read the list rather than act on it.
    """
    haystack = references
    return [item for item in numbers_in_text(text)
            if item["token"] not in haystack]


__all__ = [
    "MOVEMENT_RE", "PLACE_SUFFIX_RE", "NUMBER_RE", "MovementClaim",
    "sentences", "movement_claims", "place_findings", "numbers_in_text",
    "unmatched_numbers",
]
