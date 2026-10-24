"""Context and invariants for an append-only creative-work continuation."""
from __future__ import annotations

from dataclasses import dataclass

from ..pipeline.draft import ChapterDraft, canon_brief
from ..story.canon import Canon


@dataclass(frozen=True)
class ContinuationContext:
    """The pinned parent inputs needed by every attempt of a continuation."""

    parent_revision_id: str
    parent_runs: dict[str, str]
    parent_chapter_count: int
    canon: Canon
    drafts: tuple[ChapterDraft, ...]

    @property
    def prompt_suffix(self) -> str:
        """Pass compact canon and constraints, never the full old manuscript."""
        old_chapters = ", ".join(self.canon.chapter_order())
        return "\n".join([
            "## 前版からのcontinuation",
            f"これは{self.parent_chapter_count}章の完成作品へ章を追加する作業です。",
            f"既存章（{old_chapters}）の時系列・場所を変更せず、その後ろに新しい章を追加してください。",
            "前版の本文全文は渡しません。次のcompact canonを参照してください。",
            canon_brief(self.canon),
        ])

    def as_dict(self) -> dict:
        return {
            "parent_revision_id": self.parent_revision_id,
            "parent_runs": dict(sorted(self.parent_runs.items())),
            "parent_chapter_count": self.parent_chapter_count,
            "reused_chapters": [chapter.id for chapter in self.drafts],
        }


def validate_continuation_canon(context: ContinuationContext, canon: Canon) -> None:
    """Require the new canon to retain the parent timeline as an exact prefix."""
    old_order = context.canon.chapter_order()
    new_order = canon.chapter_order()
    if new_order[:len(old_order)] != old_order:
        raise ValueError("continuation canon must preserve the parent chapter prefix")
    if len(new_order) <= len(old_order):
        raise ValueError("continuation canon must add at least one chapter")
    for chapter_id in old_order:
        old = context.canon.chapters[chapter_id]
        new = canon.chapters[chapter_id]
        if (old.day, old.year, old.location) != (new.day, new.year, new.location):
            raise ValueError(
                f"continuation changed parent chapter {chapter_id} time/year/location"
            )
    for channel in ("characters", "facts", "locations", "foreshadowing"):
        old_entries = getattr(context.canon, channel)
        new_entries = getattr(canon, channel)
        for entry_id, old_entry in old_entries.items():
            if entry_id not in new_entries or new_entries[entry_id] != old_entry:
                raise ValueError(
                    f"continuation changed parent canon {channel}/{entry_id}"
                )
    if canon.suppressions[:len(context.canon.suppressions)] != context.canon.suppressions:
        raise ValueError("continuation changed parent canon suppressions")
