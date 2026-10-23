"""Build a state ledger from the canon and the text markers.

The ledger is the artefact the skill promises: for every character, where they
are, whether they are alive, what they know and when; for every foreshadow, when
it was planted and when (if ever) it paid off. It is written to disk so that the
next chapter is audited against the same object, instead of against whatever the
model happens to remember.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .canon import Canon, chapter_key
from .text import ChapterText


@dataclass
class Event:
    order: int
    chapter: str
    kind: str
    subject: str
    detail: str = ""
    evidence: str = ""
    line: int | None = None

    def as_dict(self) -> dict:
        return {
            "order": self.order,
            "chapter": self.chapter,
            "kind": self.kind,
            "subject": self.subject,
            "detail": self.detail,
            "evidence": self.evidence,
            "line": self.line,
        }


@dataclass
class CharacterState:
    id: str
    status: str
    location: str | None
    known_facts: set[str] = field(default_factory=set)
    last_seen_chapter: str | None = None
    age: int | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "location": self.location,
            "known_facts": sorted(self.known_facts),
            "last_seen_chapter": self.last_seen_chapter,
            "age": self.age,
        }


@dataclass
class ForeshadowState:
    id: str
    setup_chapter: str | None = None
    payoff_chapter: str | None = None
    declared_setup: str | None = None
    declared_payoff: str | None = None
    description: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "declared_setup": self.declared_setup,
            "declared_payoff": self.declared_payoff,
            "setup_chapter": self.setup_chapter,
            "payoff_chapter": self.payoff_chapter,
            "resolved": bool(self.payoff_chapter),
        }


@dataclass
class Ledger:
    events: list[Event] = field(default_factory=list)
    characters: dict[str, CharacterState] = field(default_factory=dict)
    foreshadowing: dict[str, ForeshadowState] = field(default_factory=dict)
    chapter_time: dict[str, dict] = field(default_factory=dict)

    def as_dict(self, canon: Canon) -> dict:
        return {
            "schema_version": "1.0",
            "canon": str(canon.root),
            "chapter_time": self.chapter_time,
            "characters": [self.characters[k].as_dict() for k in sorted(self.characters)],
            "foreshadowing": [self.foreshadowing[k].as_dict() for k in sorted(self.foreshadowing)],
            "events": [e.as_dict() for e in sorted(self.events, key=lambda e: e.order)],
        }


def build_ledger(canon: Canon, chapters: list[ChapterText]) -> Ledger:
    ledger = Ledger()
    order = 0
    chapter_index = {c: i for i, c in enumerate(canon.chapter_order())}

    def sort_key(chapter_id: str) -> tuple[int, str]:
        return (chapter_index.get(chapter_id, len(chapter_index)), chapter_id)

    ordered = sorted(chapters, key=lambda c: sort_key(c.id))

    for char in canon.characters.values():
        ledger.characters[char.id] = CharacterState(
            id=char.id,
            status=char.status,
            location=char.location,
            known_facts=set(char.knows),
            age=char.age_at_start,
        )
    for fs in canon.foreshadowing.values():
        ledger.foreshadowing[fs.id] = ForeshadowState(
            id=fs.id,
            declared_setup=fs.setup,
            declared_payoff=fs.payoff,
            setup_chapter=fs.setup,
            description=fs.description,
        )

    for chapter in ordered:
        declared = canon.chapters.get(chapter.id)
        time: dict = {}
        if declared and declared.day is not None:
            time["day"] = declared.day
        if declared and declared.year is not None:
            time["year"] = declared.year
        if declared and declared.location:
            time["location"] = declared.location

        for marker in chapter.markers:
            order += 1
            subject = marker.subject or ""
            options = marker.options()
            evidence = f"{chapter.path.name}:{marker.line}"
            if marker.kind == "time":
                for key in ("day", "year"):
                    if key in options:
                        try:
                            time[key] = float(options[key]) if key == "day" else int(options[key])
                        except ValueError:
                            pass
            elif marker.kind == "location":
                time["location"] = options.get("location") or subject
            elif marker.kind == "death":
                if (char := canon.character(subject)) is not None:
                    state = ledger.characters[char.id]
                    state.status = "dead"
                    state.location = None
                    ledger.events.append(Event(order, chapter.id, "death", char.id,
                                               options.get("note", ""), evidence, marker.line))
            elif marker.kind == "state":
                if (char := canon.character(subject)) is not None:
                    state = ledger.characters[char.id]
                    if "location" in options:
                        state.location = options["location"]
                    if "status" in options:
                        state.status = options["status"]
                    ledger.events.append(Event(order, chapter.id, "state", char.id,
                                               str(options), evidence, marker.line))
            elif marker.kind == "learn":
                fact = options.get("fact")
                if (char := canon.character(subject)) is not None and fact:
                    ledger.characters[char.id].known_facts.add(fact)
                    ledger.events.append(Event(order, chapter.id, "learn", char.id,
                                               fact, evidence, marker.line))
            elif marker.kind == "age":
                if (char := canon.character(subject)) is not None and marker.args[1:]:
                    try:
                        ledger.characters[char.id].age = int(marker.args[1])
                    except ValueError:
                        pass
                    ledger.events.append(Event(order, chapter.id, "age", char.id,
                                               marker.args[1], evidence, marker.line))
            elif marker.kind == "foreshadow":
                fs_id = subject
                action = (marker.args[1] if len(marker.args) > 1 else "").lower()
                state = ledger.foreshadowing.get(fs_id)
                if state is None:
                    state = ForeshadowState(id=fs_id)
                    ledger.foreshadowing[fs_id] = state
                if action.startswith("payoff") or action == "pay":
                    state.payoff_chapter = state.payoff_chapter or chapter.id
                else:
                    state.setup_chapter = state.setup_chapter or chapter.id
                ledger.events.append(Event(order, chapter.id, "foreshadow", fs_id,
                                           action or "setup", evidence, marker.line))

        # mentions are recorded as "seen" only; they do not change state
        for mention in chapter.mentions:
            state = ledger.characters.get(mention.character_id)
            if state is None:
                continue
            if state.last_seen_chapter is None or sort_key(chapter.id) > sort_key(state.last_seen_chapter):
                state.last_seen_chapter = chapter.id

        ledger.chapter_time[chapter.id] = time

    # canon-supplied chapter locations fill the gaps
    for chapter_id, time in ledger.chapter_time.items():
        if "location" not in time and (declared := canon.chapters.get(chapter_id)) and declared.location:
            time["location"] = declared.location
    return ledger


def declared_chapter(value: str | None) -> str | None:
    return chapter_key(value)
