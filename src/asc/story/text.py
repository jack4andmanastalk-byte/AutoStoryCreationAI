"""Chapter text parsing: explicit markers, name mentions and dialogue spans.

Two kinds of evidence are used by the continuity audit:

* **markers** — ``{{death: aria | 崩落}}`` — written by the drafting step (or a
  human editor). They are unambiguous but only as complete as the writer made
  them.
* **mentions** — a character name appearing in the prose. They are complete but
  ambiguous: a mention can be a memory, a corpse, a letter or a flashback.

Keeping the two apart is what lets the audit report *how* it knows something
(``evidence_basis``), which the measurement spec requires: a violation found
only by name mention is reported at a lower severity than one backed by a
marker.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MARKER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*:\s*([^}]*)\}\}")
DIALOGUE_RE = re.compile(r"「([^」]*)」")
QUOTED_RE = re.compile(r"「[^」]*」|『[^』]*』")

#: Words that mark a *reference* to someone rather than a present-time act.
#: Stage B uses the same deliberately small, documented heuristic when a
#: declared ``memory_mention`` / ``record_reference`` names a dead person.
#: Keeping the list here lets the prose parser and both checkers share one
#: contract instead of drifting into two near-duplicates.
REFERENCE_CUES = (
    # records and relics
    "筆跡", "手形", "文字", "記録", "帳面", "頁", "札", "書き", "印",
    "遺した", "残した", "預けた", "手紙", "日記", "写真", "墓", "遺体",
    # recollection and past narration
    "思い出", "思い返", "記憶", "覚えて", "覚えてい", "回想", "面影",
    "昔", "あの頃", "なつかし", "かつて", "生前", "三年前", "あの夜",
    "あの嵐", "あの日", "その夜", "横顔", "名を", "声を聞",
)

#: markers the audit understands, and what they mean
MARKER_KINDS = {
    "death": "人物が死亡した（args: 人物ID | 補足）",
    "state": "状態変化（args: 人物ID key=value ...）",
    "learn": "人物が事実を知った（args: 人物ID fact=ID）",
    "use": "人物が事実を利用した（args: 人物ID fact=ID）",
    "time": "章の時点（args: day=N | year=YYYY）",
    "location": "章の場所（args: 場所ID）",
    "foreshadow": "伏線の設置・回収（args: fs-ID setup|payoff）",
    "age": "人物の年齢の明示（args: 人物ID 年齢）",
}


@dataclass(frozen=True)
class Marker:
    kind: str
    args: tuple[str, ...]
    raw: str
    chapter: str
    line: int
    offset: int

    @property
    def subject(self) -> str | None:
        return self.args[0] if self.args else None

    def options(self) -> dict[str, str]:
        opts: dict[str, str] = {}
        for arg in self.args[1:]:
            if "=" in arg:
                key, _, value = arg.partition("=")
                opts[key.strip()] = value.strip()
        return opts


@dataclass(frozen=True)
class Mention:
    chapter: str
    line: int
    character_id: str
    name: str
    in_dialogue: bool
    quoted_line: bool  # this mention is attributed speech before a 「 span
    text: str
    offset: int = 0
    sentence: str = ""
    following: str = ""
    in_quoted_text: bool = False

    @property
    def reference_cues(self) -> tuple[str, ...]:
        """Reference/past cues in the sentence containing this mention."""
        return tuple(cue for cue in REFERENCE_CUES if cue in self.sentence)


@dataclass
class ChapterText:
    id: str
    path: Path
    text: str
    lines: list[str] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return len(re.sub(r"\s", "", self.text))


def parse_markers(text: str, chapter: str) -> list[Marker]:
    markers: list[Marker] = []
    for index, line in enumerate(text.splitlines(), start=1):
        for match in MARKER_RE.finditer(line):
            kind = match.group(1)
            body = match.group(2)
            parts = [p.strip() for p in body.split("|")]
            head = [p for p in re.split(r"[\s]+", parts[0]) if p]
            args = tuple(head + [p for p in parts[1:] if p])
            markers.append(Marker(kind=kind, args=args, raw=match.group(0),
                                  chapter=chapter, line=index, offset=match.start()))
    return markers


def _sentence_span(line: str, start: int, end: int) -> tuple[str, str]:
    """Return ``(sentence, following_text_in_sentence)`` for one occurrence.

    Markers are removed from the returned prose. Sentence boundaries are the
    explicit Japanese/ASCII terminators already used by speaker attribution;
    this is deliberately not a linguistic parser.
    """
    sentence_start = max(line.rfind(mark, 0, start) for mark in "。！？!?") + 1
    candidates = [line.find(mark, end) for mark in "。！？!?"]
    candidates = [pos for pos in candidates if pos != -1]
    sentence_end = min(candidates) + 1 if candidates else len(line)
    sentence = MARKER_RE.sub("", line[sentence_start:sentence_end]).strip()
    following = MARKER_RE.sub("", line[end:sentence_end]).strip()
    return sentence, following


def find_mentions(text: str, chapter: str, names: dict[str, str]) -> list[Mention]:
    """Locate character names and decide whether the line attributes speech.

    ``names`` maps a literal name/alias to the character id.

    A mention counts as speech when all of the following hold:

    * it sits before the opening ``「`` of a dialogue span on the same line,
    * no other character name sits between it and that ``「``,
    * no sentence-final punctuation (``。！？``) sits between them.

    These rules are deliberately conservative. A wrong speaker attribution
    produces a false high-severity violation, so when the line is ambiguous the
    mention is left as a plain mention (medium severity).
    """
    mentions: list[Mention] = []
    for index, line in enumerate(text.splitlines(), start=1):
        spans = [(m.start(), m.end()) for m in DIALOGUE_RE.finditer(line)]
        quoted_spans = [(m.start(), m.end()) for m in QUOTED_RE.finditer(line)]
        occurrences = []
        for name, cid in names.items():
            start = 0
            while (pos := line.find(name, start)) != -1:
                start = pos + len(name)
                occurrences.append((pos, pos + len(name), name, cid))
        occurrences.sort()

        for pos, end, name, cid in occurrences:
            quoted = any(a <= pos < b for a, b in spans)
            speaks = False
            if not quoted:
                for start, _ in spans:
                    if start < pos:
                        continue
                    between = [o for o in occurrences if pos < o[0] < start]
                    if between and between[0][3] != cid:
                        break
                    gap = line[pos + len(name):start]
                    speaks = not re.search(r"[。！？!?]", gap)
                    break
            sentence, following = _sentence_span(line, pos, end)
            mentions.append(Mention(
                chapter=chapter,
                line=index,
                character_id=cid,
                name=name,
                in_dialogue=quoted,
                quoted_line=speaks,
                text=line.strip()[:160],
                offset=pos,
                sentence=sentence,
                following=following,
                in_quoted_text=any(a <= pos < b for a, b in quoted_spans),
            ))
    return mentions


def load_chapters(paths: list[tuple[str, Path]], names: dict[str, str]) -> list[ChapterText]:
    chapters: list[ChapterText] = []
    for cid, path in paths:
        text = path.read_text(encoding="utf-8")
        chapter = ChapterText(id=cid, path=path, text=text, lines=text.splitlines())
        chapter.markers = parse_markers(text, cid)
        chapter.mentions = find_mentions(text, cid, names)
        chapters.append(chapter)
    return chapters
