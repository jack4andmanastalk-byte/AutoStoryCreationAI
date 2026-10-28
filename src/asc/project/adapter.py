"""Adapt a creative WorkSpec to the existing S1 pipeline inputs.

The frozen protocol's ``Task`` type is reused as a carrier, but project runs do
not claim to be protocol-v1 experiments.  They have no control work, required
terms, or quality gates.  Chapter and character targets come from the project's
own revision rather than ``benchmarks/protocol-v1/tasks.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..pipeline.tasks import Task
from .model import WorkSpec

PROJECT_PROTOCOL = "asc-project-v1"

#: Fraction of the per-chapter target a chapter may deviate before the draft
#: stage warns.  A project spec names one number, but a single-value band made
#: a 1201-character chapter "out of range" for a 1200-character target, so the
#: writer spent more time trimming a few characters than writing.  The band is
#: advisory: it changes the warning, never the acceptance of a chapter.
TARGET_TOLERANCE = 0.05


def target_band(target: int, tolerance: float = TARGET_TOLERANCE) -> tuple[int, int]:
    """Return the advisory ``(min, max)`` band for one character target."""
    slack = max(1, round(target * tolerance))
    return (max(1, target - slack), target + slack)


def format_band(band: tuple[int, int]) -> str:
    """Render a band the way prompts and summaries show it (``1140〜1260``)."""
    return f"{band[0]}〜{band[1]}"


@dataclass(frozen=True)
class PipelineInput:
    task: Task
    chapters: int
    chapter_target: tuple[int, int]
    total_target: tuple[int, int]


def adapt_work_spec(node_id: str, spec: WorkSpec) -> PipelineInput:
    """Convert one immutable project specification without reading frozen tasks."""
    target = spec.target_chars_per_chapter
    total = target * spec.chapter_count
    task = Task(
        id=node_id,
        # Legacy field name: this carries the title in any WorkSpec language.
        title_ja=spec.title,
        genre=spec.form,
        logline=spec.premise,
        must_include=(),
        avoid=(),
        control="creative-project",
    )
    return PipelineInput(
        task=task,
        chapters=spec.chapter_count,
        chapter_target=target_band(target),
        total_target=target_band(total),
    )
