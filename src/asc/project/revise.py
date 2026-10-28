"""Carry an earlier revision's content into a new revision.

A *revise* makes a new revision of the same node; a *branch* makes a new node
that starts from another node's revision.  In both cases only the selected
chapters and design documents are regenerated.  Everything else is copied
byte-for-byte out of the source run directories, so the old revision and its
runs are never touched and unchanged artifacts keep their exact bytes.

The carry is recorded twice: ``revision.derived`` names the source node,
revision and runs, and each carried stage writes ``revise.json`` with the
source hash of every copied artifact next to the regenerated ones.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..pipeline import ChapterDraft
from ..pipeline.design import DOCS
from ..story.canon import Canon, load_canon
from .schema import DERIVED_KINDS, ProjectValidationError
from .store import DEFAULT_STAGES, ProjectError, ProjectStore


class ReviseError(ProjectError):
    """A revision cannot be derived from the requested source."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def design_history(source_design_dir: Path) -> dict[str, dict[str, Any]]:
    """Read per-document attempt history from a design run's ``design.json``.

    ``source_design_dir`` is the run's ``design/`` directory.  Called by the
    continuation and revise paths so that carried documents keep the counts of
    the run that produced them instead of being reset to zero.
    """
    path = source_design_dir.parent / "design.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    docs = data.get("docs") if isinstance(data, dict) else None
    if not isinstance(docs, dict):
        return {}
    history: dict[str, dict[str, Any]] = {}
    for name, row in docs.items():
        if not isinstance(row, dict):
            continue
        entry: dict[str, Any] = {}
        for key in ("attempts", "repairs", "findings"):
            try:
                entry[key] = max(0, int(row.get(key) or 0))
            except (TypeError, ValueError):
                entry[key] = 0
        if row.get("carried_from"):
            entry["carried_from"] = str(row["carried_from"])
        history[str(name)] = entry
    return history


def run_dir(store: ProjectStore, project_id: str, run_id: str) -> Path:
    """Return one run directory inside a project, or raise a clear error."""
    directory = store.project_dir(project_id) / "runs" / run_id
    if not directory.is_dir():
        raise ReviseError(f"source run not found: {run_id}")
    return directory


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviseError(f"cannot read run record {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviseError(f"run record must be an object: {path}")
    return data


def runs_for_revision(
    store: ProjectStore, project_id: str, node_id: str, revision_id: str,
) -> dict[str, str]:
    """Find the completed run of every stage that produced one revision.

    Current revisions expose their runs through checkpoints, but an older
    revision has none: a checkpoint is per node and moves with the current
    revision.  Its runs are therefore located by reading the recorded
    ``project-input.json`` of every run of the node and keeping the newest
    ``ok`` run per stage.
    """
    directory = store.project_dir(project_id) / "runs"
    if not directory.is_dir():
        raise ReviseError(f"project {project_id} has no runs")
    found: dict[str, tuple[str, str]] = {}
    for candidate in sorted(directory.iterdir()):
        input_path = candidate / "project-input.json"
        manifest_path = candidate / "manifest.json"
        if not input_path.is_file() or not manifest_path.is_file():
            continue
        data = _read_json(input_path)
        if data.get("project_id") != project_id or data.get("node_id") != node_id:
            continue
        if data.get("revision_id") != revision_id:
            continue
        stage = data.get("stage")
        if stage not in DEFAULT_STAGES:
            continue
        manifest = _read_json(manifest_path)
        if manifest.get("run_id") != candidate.name or manifest.get("status") != "ok":
            continue
        started = str(manifest.get("started_at") or "")
        if stage not in found or started >= found[stage][0]:
            found[stage] = (started, candidate.name)
    missing = [stage for stage in DEFAULT_STAGES if stage not in found]
    if missing:
        raise ReviseError(
            f"revision {revision_id} has no completed run for: {', '.join(missing)}"
        )
    return {stage: found[stage][1] for stage in DEFAULT_STAGES}


def _ordered(values: Iterable[str], allowed: Iterable[str]) -> tuple[str, ...]:
    wanted = set(values)
    return tuple(item for item in allowed if item in wanted)


def validate_selection(
    canon: Canon, chapters: Iterable[str], design: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the requested selection in canon/document order."""
    chapter_ids = list(chapters)
    order = canon.chapter_order()
    unknown = [item for item in chapter_ids if item not in order]
    if unknown:
        raise ReviseError(
            f"unknown chapter(s) {', '.join(unknown)}; the revision has "
            f"{', '.join(order)}"
        )
    design_names = list(design)
    unknown_docs = [item for item in design_names if item not in DOCS]
    if unknown_docs:
        raise ReviseError(
            f"unknown design document(s) {', '.join(unknown_docs)}; "
            f"choose from {', '.join(DOCS)}"
        )
    return _ordered(chapter_ids, order), _ordered(design_names, DOCS)


@dataclass(frozen=True)
class ReviseContext:
    """Everything a derived attempt needs that is not in the new revision."""

    kind: str
    source_node_id: str
    source_revision_id: str
    source_runs: dict[str, str]
    chapters: tuple[str, ...]  # regenerated
    design: tuple[str, ...]  # regenerated
    canon: Canon
    drafts: tuple[ChapterDraft, ...]  # carried chapters, in canon order
    design_dir: Path
    source_paths: dict[str, Path]
    source_sha256: dict[str, str]
    #: Operator's reason for the revision (``revise --note``); passed to the
    #: prompt so the regenerated chapter follows the intent of the edit.
    note: str = ""

    @property
    def carried_chapters(self) -> tuple[str, ...]:
        regenerated = set(self.chapters)
        return tuple(
            chapter_id for chapter_id in self.canon.chapter_order()
            if chapter_id not in regenerated
        )

    @property
    def carried_design(self) -> tuple[str, ...]:
        regenerated = set(self.design)
        return tuple(name for name in DOCS if name not in regenerated)

    @property
    def prompt_suffix(self) -> str:
        """Say exactly which chapters are new, without sending old prose back."""
        carried = ", ".join(self.carried_chapters) or "なし"
        regenerated = ", ".join(self.chapters) or "なし"
        lines = [
            "## 前版からの改訂",
            "これは完成作品の一部だけを作り直す作業です。",
            f"改訂する章: {regenerated}",
            f"変更しない章（本文を保持し、書き換えない）: {carried}",
        ]
        if self.design:
            lines.append(f"作り直す設計資料: {', '.join(self.design)}")
        if self.note:
            lines.extend(["## 改訂の意図", self.note])
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source_node_id": self.source_node_id,
            "source_revision_id": self.source_revision_id,
            "source_runs": dict(sorted(self.source_runs.items())),
            "chapters": list(self.chapters),
            "design": list(self.design),
            "carried_chapters": list(self.carried_chapters),
            "carried_design": [
                name for name in self.carried_design
                if (self.design_dir / f"{name}.json").is_file()
            ],
            "source_sha256": dict(sorted(self.source_sha256.items())),
        }


def read_context(
    store: ProjectStore, project_id: str, source_node_id: str,
    source_revision_id: str, source_runs: dict[str, str], *,
    kind: str, chapters: Iterable[str] = (), design: Iterable[str] = (),
    note: str = "",
) -> ReviseContext:
    """Load the source canon, chapter text and design documents to carry."""
    if kind not in DERIVED_KINDS:
        raise ReviseError(f"unknown derived revision kind: {kind}")
    missing = [stage for stage in DEFAULT_STAGES if stage not in source_runs]
    if missing:
        raise ReviseError(
            f"derived revision is missing source runs for: {', '.join(missing)}"
        )
    plan_dir = run_dir(store, project_id, source_runs["plan"])
    design_dir = run_dir(store, project_id, source_runs["design"]) / "design"
    draft_dir = run_dir(store, project_id, source_runs["draft"]) / "text"
    try:
        canon = load_canon(plan_dir / "canon")
    except (OSError, ValueError) as exc:
        raise ReviseError(f"cannot read the source canon: {exc}") from exc
    selected_chapters, selected_design = validate_selection(canon, chapters, design)
    sources: dict[str, str] = {}
    paths: dict[str, Path] = {}
    drafts: list[ChapterDraft] = []
    for chapter_id in canon.chapter_order():
        if chapter_id in selected_chapters:
            continue
        path = draft_dir / f"{chapter_id}.md"
        if not path.is_file():
            raise ReviseError(
                f"source chapter text is missing: {path}; regenerate {chapter_id}"
            )
        text = path.read_text(encoding="utf-8")
        chapter = canon.chapters[chapter_id]
        drafts.append(ChapterDraft(
            id=chapter_id, text=text, day=chapter.day, location=chapter.location,
            preserve_text=True,
        ))
        relative = f"text/{chapter_id}.md"
        sources[relative] = _sha256_file(path)
        paths[relative] = path
    for name in DOCS:
        if name in selected_design:
            continue
        path = design_dir / f"{name}.json"
        if not path.is_file():
            continue  # a document that was already missing stays missing
        relative = f"design/{name}.json"
        sources[relative] = _sha256_file(path)
        paths[relative] = path
    return ReviseContext(
        kind=kind,
        source_node_id=source_node_id,
        source_revision_id=source_revision_id,
        source_runs=dict(sorted(source_runs.items())),
        chapters=selected_chapters,
        design=selected_design,
        canon=canon,
        drafts=tuple(drafts),
        design_dir=design_dir,
        source_paths=paths,
        source_sha256=sources,
        note=(note or "").strip(),
    )


def context_from_revision(
    store: ProjectStore, project_id: str, node_id: str, revision: Any,
) -> ReviseContext | None:
    """Rebuild the carry context recorded in a derived revision."""
    derived = revision.derived
    if not derived:
        return None
    if revision.node_id != node_id:
        raise ReviseError(
            f"revision {revision.id} belongs to node {revision.node_id}, not {node_id}"
        )
    try:
        return read_context(
            store, project_id, derived["source_node_id"],
            derived["source_revision_id"], dict(derived.get("source_runs") or {}),
            kind=derived["kind"], chapters=derived.get("chapters") or (),
            design=derived.get("design") or (),
            note=str(derived.get("note") or ""),
        )
    except (KeyError, ProjectValidationError) as exc:
        raise ReviseError(f"invalid derived revision record: {exc}") from exc


def copy_carried_files(
    context: ReviseContext, target: Path, *, prefix: str,
) -> list[str]:
    """Copy one class of carried artifacts into a new run and verify the bytes."""
    copied = []
    for name, source in sorted(context.source_paths.items()):
        if not name.startswith(f"{prefix}/"):
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        if _sha256_file(destination) != context.source_sha256[name]:
            raise ReviseError(f"carried artifact changed while copying: {name}")
        copied.append(name)
    return copied
