"""The Draft step: a canon (or, for S0, a logline alone) becomes chapter text.

Chapter text carries markers (``{{time: day=3}}`` and friends) so that the audit
has evidence instead of guesses. If a chapter arrives without its time/location
markers, the pipeline inserts them from the canon and *records the insertion* —
injecting silently would make the audit look better than the text is.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..story.canon import Canon
from .llm import GenerationRequest, Provider, ProviderError
from .prompts import load_prompt
from .run import RunLedger
from .tasks import Task

CHAPTER_TARGET = (1000, 1400)
MIN_CHAPTER_CHARS = 200

MARKER = re.compile(r"\{\{([^{}]+)\}\}")
TIME_MARKER = re.compile(r"\{\{\s*time:\s*day\s*=\s*\d+N?\s*\}\}")
LOCATION_MARKER = re.compile(r"\{\{\s*location:\s*[^{}]+\}\}")


class DraftError(RuntimeError):
    """Raised when a chapter cannot be produced or violates a hard rule."""


@dataclass(frozen=True)
class ChapterDraft:
    id: str
    text: str
    day: int | None = None
    location: str | None = None
    injected: tuple[str, ...] = ()
    # Continuation uses this only for already persisted parent chapters.
    preserve_text: bool = False

    @property
    def chars(self) -> int:
        stripped = MARKER.sub("", self.text)
        return len(re.sub(r"\s", "", stripped))

    @property
    def markers(self) -> list[str]:
        return MARKER.findall(self.text)

    def as_dict(self) -> dict:
        return {"id": self.id, "chars": self.chars, "day": self.day,
                "location": self.location, "injected": list(self.injected),
                "markers": len(self.markers)}


@dataclass(frozen=True)
class Draft:
    task: Task
    chapters: tuple[ChapterDraft, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return "\n\n".join(chapter.text for chapter in self.chapters)

    @property
    def chars(self) -> int:
        return sum(chapter.chars for chapter in self.chapters)

    def write_text_dir(self, directory: str | Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for chapter in self.chapters:
            text = (
                chapter.text if chapter.preserve_text
                else chapter.text.rstrip() + "\n"
            )
            (directory / f"{chapter.id}.md").write_text(text, encoding="utf-8")
        return directory

    def must_include_hits(self) -> dict:
        body = self.text
        hits = {term: term in body for term in self.task.must_include}
        return {"hits": hits, "rate": round(
            sum(hits.values()) / len(hits), 3) if hits else 1.0}

    def as_dict(self) -> dict:
        return {
            "task": self.task.as_dict(),
            "chapters": [chapter.as_dict() for chapter in self.chapters],
            "chars": self.chars,
            "must_include": self.must_include_hits(),
            "warnings_ja": list(self.warnings),
        }


def chapter_plan(canon: Canon | None, chapters: int) -> list[dict]:
    if canon is None or not canon.chapters:
        return [{"id": f"ch{index:02d}", "day": None, "location": None}
                for index in range(1, chapters + 1)]
    ordered = sorted(canon.chapters.values(),
                     key=lambda chapter: (chapter.day is None, chapter.day or 0, chapter.id))
    return [{"id": chapter.id, "day": chapter.day, "location": chapter.location}
            for chapter in ordered]


def canon_brief(canon: Canon | None) -> str:
    """A compact, readable canon for the prompt (not the whole audit payload)."""
    if canon is None:
        return "（なし）"
    payload = {
        "characters": [
            {"id": c.id, "name": c.name, "aliases": list(c.aliases), "status": c.status,
             "location": c.location, "age_at_start": c.age_at_start,
             "knows": list(c.knows)}
            for c in canon.characters.values()
        ],
        "facts": [{"id": f.id, "summary": f.summary, "terms": list(f.terms),
                   "setup": f.setup} for f in canon.facts.values()],
        "locations": [{"id": l.id, "travel_days": l.travel_days}
                      for l in canon.locations.values()],
        "chapters": [{"id": c.id, "day": c.day, "location": c.location}
                     for c in sorted(canon.chapters.values(),
                                     key=lambda c: (c.day is None, c.day or 0, c.id))],
        "foreshadowing": [{"id": f.id, "description": f.description,
                           "setup": f.setup, "payoff": f.payoff}
                          for f in canon.foreshadowing.values()],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def clean_text(text: str) -> str:
    """Drop code fences and leading headings a model sometimes adds."""
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
    stripped = re.sub(r"\n```$", "", stripped)
    lines = stripped.splitlines()
    while lines and re.match(r"^\s*#{1,6}\s", lines[0]):
        lines.pop(0)
    return "\n".join(lines).strip()


def check_chapter(text: str, task: Task, chapter: dict) -> list[str]:
    """Hard rule violations that justify one retry.

    Missing markers are not listed here: they are repaired from the canon by
    :func:`ensure_markers` and recorded in the draft, because a marker is
    metadata about the text, not prose the model has to get right.
    """
    problems: list[str] = []
    body = MARKER.sub("", text)
    chars = len(re.sub(r"\s", "", body))
    if chars < MIN_CHAPTER_CHARS:
        problems.append(f"too short ({chars} chars, minimum {MIN_CHAPTER_CHARS})")
    for term in task.avoid:
        if term in body:
            problems.append(f"uses a forbidden cliché: {term}")
    return problems


def ensure_markers(text: str, chapter: dict) -> tuple[str, tuple[str, ...]]:
    """Insert the canonical time/location markers if the model forgot them."""
    added: list[str] = []
    body = text.rstrip()
    missing: list[str] = []
    if chapter.get("day") is not None and not TIME_MARKER.search(body):
        missing.append("{{time: day=%s}}" % chapter["day"])
    if chapter.get("location") and not LOCATION_MARKER.search(body):
        missing.append("{{location: %s}}" % chapter["location"])
    if not missing:
        return body, ()
    if not TIME_MARKER.search(body) and not LOCATION_MARKER.search(body):
        # both were missing: put them on one line, ahead of the prose
        body = "".join(missing) + "\n" + body
        added = list(missing)
    else:
        body = body + "\n" + "".join(missing)
        added = list(missing)
    return body, tuple(added)


def _prompt_values(task: Task, chapter: dict, index: int, chapters: int,
                   target: tuple[int, int], prior: str, canon: Canon | None,
                   design: str = "（設計メモなし）") -> dict:
    return {
        "title": task.title_ja,
        "logline": task.logline,
        "chapter_id": chapter["id"],
        "chapter_index": str(index),
        "chapters": str(chapters),
        "chapter_day": str(chapter["day"]) if chapter["day"] is not None else "未定",
        "chapter_location": chapter["location"] or "未定",
        "must_include": "、".join(task.must_include),
        "avoid": "、".join(task.avoid),
        "target_min": str(target[0]),
        "target_max": str(target[1]),
        "prior": prior or "（これが最初の章）",
        "canon": canon_brief(canon),
        "design": design,
    }


def build_story(task: Task, provider: Provider, ledger: RunLedger, *,
                canon: Canon | None = None, chapters: int = 3,
                target: tuple[int, int] = CHAPTER_TARGET,
                prompt_dir: str | Path | None = None, temperature: float = 0.8,
                max_tokens: int = 2500, seed: int = 0,
                max_attempts: int = 2,
                design_dir: str | Path | None = None,
                initial_drafts: tuple[ChapterDraft, ...] = (),
                preserve: tuple[ChapterDraft, ...] = ()) -> Draft:
    """Draft the chapters that are not already final.

    ``initial_drafts`` is the continuation prefix: chapters copied from the
    previous revision.  ``preserve`` is a set of chapters that must stay as
    they are, at any position (a revision regenerates selected chapters only).
    Preserved chapters are written back verbatim; regenerated ones are placed
    in canon order between them.
    """
    template = load_prompt("draft-chapter" if canon is not None else "draft-baseline",
                           prompt_dir)
    ledger.prompt_hashes[template.name] = template.digest

    plan = chapter_plan(canon, chapters)
    drafts: list[ChapterDraft] = list(initial_drafts)
    if len(drafts) > len(plan):
        raise DraftError("initial chapters exceed the requested chapter count")
    expected_initial = [chapter["id"] for chapter in plan[:len(drafts)]]
    if [chapter.id for chapter in drafts] != expected_initial:
        raise DraftError("initial chapters are not the prefix of the new canon")
    kept = {chapter.id: chapter for chapter in preserve}
    if len(kept) != len(preserve):
        raise DraftError("preserved chapters repeat an id")
    known = [chapter["id"] for chapter in plan]
    unknown = sorted(set(kept) - set(known))
    if unknown:
        raise DraftError(f"preserved chapters are not in the canon: {', '.join(unknown)}")
    overlap = sorted(set(kept) & {chapter.id for chapter in drafts})
    if overlap:
        raise DraftError(
            f"chapters cannot be both initial and preserved: {', '.join(overlap)}"
        )
    warnings: list[str] = []
    prior = drafts[-1].text[-400:] if drafts else ""
    for index, chapter in enumerate(plan, start=1):
        if index <= len(drafts):
            continue
        if chapter["id"] in kept:
            preserved = kept[chapter["id"]]
            drafts.append(ChapterDraft(
                id=preserved.id, text=preserved.text, day=preserved.day,
                location=preserved.location, injected=preserved.injected,
                preserve_text=True,
            ))
            prior = preserved.text[-400:]
            continue
        last_problems: list[str] = []
        produced: ChapterDraft | None = None
        if canon is not None:
            from .design import design_notes_for_chapter
            notes = design_notes_for_chapter(design_dir, chapter["id"], canon)
        else:
            notes = "（設計メモなし）"
        for attempt in range(1, max_attempts + 1):
            values = _prompt_values(task, chapter, index, chapters, target, prior, canon,
                                    notes)
            request = GenerationRequest(
                purpose=f"draft:{chapter['id']}", prompt=template.render(values),
                temperature=temperature, max_tokens=max_tokens, seed=seed + index,
                context=ledger.request_context(
                    task_id=task.id, chapter=chapter["id"],
                    attempt=attempt, system=ledger.system,
                ),
            )
            try:
                result = provider.generate(request)
            except ProviderError as exc:
                ledger.fail(f"{chapter['id']}: {exc}")
                raise DraftError(f"{chapter['id']}: {exc}") from exc

            ledger.record(request, result)
            ledger.write_text(f"draft/{chapter['id']}-attempt-{attempt}.txt", result.text)
            text = clean_text(result.text)
            problems = check_chapter(text, task, chapter)
            if not problems:
                body, injected = ensure_markers(text, chapter)
                produced = ChapterDraft(
                    id=chapter["id"], text=body, day=chapter["day"],
                    location=chapter["location"], injected=injected)
                break
            last_problems = problems
            ledger.write_text(f"draft/{chapter['id']}-attempt-{attempt}.issues.txt",
                              "\n".join(problems) + "\n")

        if produced is None:
            message = f"{chapter['id']}: no acceptable text ({'; '.join(last_problems)})"
            ledger.fail(message)
            raise DraftError(message)

        if produced.injected:
            warnings.append(
                f"{produced.id}: 時のマーカーを canon から補いました（{', '.join(produced.injected)}）")
        chars = produced.chars
        if not target[0] <= chars <= target[1]:
            warnings.append(
                f"{produced.id}: {chars} 字（目安 {target[0]}〜{target[1]} 字の外）")
        drafts.append(produced)
        prior = produced.text[-400:]

    if [chapter.id for chapter in drafts] != known:
        raise DraftError("drafted chapters are not in canon order")
    draft = Draft(task=task, chapters=tuple(drafts), warnings=tuple(warnings))
    draft.write_text_dir(ledger.path / "text")
    ledger.track([f"text/{chapter.id}.md" for chapter in draft.chapters])
    ledger.write_json("draft.json", draft.as_dict())
    ledger.finish("ok")
    return draft


#: Readable alias: the Plan step builds a plan, the Draft step builds a story.
draft_story = build_story
