"""Multi-level nested-work links and deterministic recursive compilation.

Children own their revisions, runs, and canon.  A parent link contains only
ordered references to a pinned child draft; child prose is read at compilation
time and is never copied into link metadata.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .model import ArtifactRef, WorkLink, WorkNode, WorkNodeRevision
from ..story.text import without_markers
from .schema import SCHEMA_VERSION, canonical_json
from .store import ProjectError, ProjectStore


class NestedError(ProjectError):
    """A nested work cannot be rendered or compiled from its pinned inputs."""


#: Why a link was left out of a partial composition.
OMITTED_NO_PINNED_DRAFT = "no-pinned-draft"

#: Visible in the composed markdown so an omission is never silent.
OMITTED_NOTICE = "この作品は未収録（未完成）。"


@dataclass(frozen=True)
class CompositionResult:
    project_id: str
    node_id: str
    revision_id: str
    content_version: str
    sha256: str
    text: str
    path: Path | None = None
    links: tuple[dict[str, Any], ...] = ()
    omitted: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = {
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "content_version": self.content_version,
            "sha256": self.sha256,
            "path": str(self.path) if self.path is not None else None,
            "links": list(self.links),
        }
        # Additive: a complete composition keeps exactly the old shape.
        if self.omitted:
            data["omitted"] = list(self.omitted)
        return data


def _pinned_link_dict(link: WorkLink) -> dict[str, Any]:
    """Exclude mutable bookkeeping timestamps from compilation identity."""
    data = link.to_dict()
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return data


def _write_once(path: Path, data: bytes) -> None:
    """Create a deterministic artifact without replacing different bytes."""
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise NestedError(f"compilation artifact differs at existing path: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            if path.read_bytes() != data:
                raise NestedError(f"compilation artifact differs at existing path: {path}")
            return
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class ProjectComposer:
    """Render one node or append pinned child works in explicit link order."""

    def __init__(self, store: ProjectStore):
        self.store = store

    def _current_draft(
        self, project_id: str, node_id: str,
    ) -> tuple[WorkNode, WorkNodeRevision, tuple[ArtifactRef, ...]]:
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        status = self.store.status(project_id, node_id, include_descendants=False)
        if status["state"] != "complete":
            raise NestedError(
                f"node {node_id} is {status['state']}; a complete draft is required"
            )
        artifacts = tuple(
            ArtifactRef.from_dict(row)
            for row in status["checkpoints"]["draft"]["artifacts"]
        )
        return snapshot.root_node, snapshot.revision, artifacts

    def _chapters(
        self, project_id: str, artifacts: tuple[ArtifactRef, ...], *,
        reader: bool = False, heading_level: int = 2,
    ) -> str:
        by_path = {artifact.path: artifact for artifact in artifacts}
        draft_ref = next(
            (artifact for artifact in artifacts if artifact.path.endswith("/draft.json")),
            None,
        )
        chapter_ids: list[str] = []
        if draft_ref is not None:
            try:
                payload = json.loads(self.store.read_artifact(project_id, draft_ref))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise NestedError(f"invalid draft metadata: {draft_ref.path}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("chapters"), list):
                raise NestedError(f"draft metadata has no chapters: {draft_ref.path}")
            chapter_ids = [
                str(row.get("id")) for row in payload["chapters"]
                if isinstance(row, dict) and row.get("id")
            ]
        if not chapter_ids:
            chapter_ids = sorted(
                PurePosixPath(path).stem
                for path in by_path
                if "/text/" in path and path.endswith(".md")
            )
        texts = []
        for chapter_id in chapter_ids:
            suffix = f"/text/{chapter_id}.md"
            reference = next(
                (artifact for path, artifact in by_path.items() if path.endswith(suffix)),
                None,
            )
            if reference is None:
                raise NestedError(f"pinned draft is missing chapter {chapter_id}")
            try:
                text = self.store.read_artifact(project_id, reference).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise NestedError(f"chapter is not UTF-8: {reference.path}") from exc
            texts.append(text.rstrip("\n"))
        if reader:
            # A reading copy: one heading per chapter and no audit markers.
            # The chapter ID stays visible in an HTML comment so a reader can
            # still tell which chapter a passage came from.
            marks = "#" * max(1, heading_level)
            texts = [
                f"{marks} 第{index}章\n\n<!-- asc-chapter: {chapter_id} -->\n\n"
                f"{without_markers(text)}"
                for index, (chapter_id, text) in enumerate(
                    zip(chapter_ids, texts), start=1,
                )
            ]
        if not texts:
            raise NestedError("pinned draft has no chapter text")
        return "\n\n".join(texts)

    @staticmethod
    def _heading(
        node: WorkNode, revision: WorkNodeRevision, *, level: int = 1,
    ) -> list[str]:
        if level < 1:
            raise NestedError(f"composition heading level must be positive: {level}")
        return [
            f"{'#' * level} {revision.spec.title}",
            "",
            f"<!-- asc-node: {node.id} revision={revision.id} -->",
            "",
        ]

    def render(
        self, project_id: str, node_id: str | None = None, *,
        reader: bool = False,
    ) -> CompositionResult:
        """Render only the selected node's current completed draft.

        ``reader=True`` writes a reading copy: chapter headings and no audit
        markers.  The default keeps the checked text byte for byte, because the
        markers are what the audit reads and the SHA-256 of that text is the
        recorded identity of the draft.
        """
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        selected_id = snapshot.root_node.id
        with self.store.execution_lock(project_id):
            node, revision, artifacts = self._current_draft(project_id, selected_id)
            body = self._chapters(project_id, artifacts, reader=reader)
        text = "\n".join([*self._heading(node, revision), body]).rstrip() + "\n"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return CompositionResult(
            project_id=project_id, node_id=selected_id, revision_id=revision.id,
            content_version=WorkLink.version_for(revision, artifacts),
            sha256=digest, text=text,
        )

    def _current_title(self, project_id: str, node: WorkNode) -> str:
        """Best-effort title of an unpinned child, for an omission placeholder."""
        try:
            revision = self.store.load_revision(
                project_id, node.id, node.current_revision_id,
            )
        except (ProjectError, OSError, ValueError):
            return node.id
        return revision.spec.title or node.id

    def compose(
        self, project_id: str, node_id: str | None = None, *,
        partial: bool = False, reader: bool = False,
    ) -> CompositionResult:
        """Compile one current draft and all pinned descendants recursively.

        The selected node is heading level one; each descendant adds one level.
        Child and grandchild prose is read only from the revision/artifacts pinned
        by its link.  A child's current revision therefore cannot silently change
        an ancestor's composition.  Nested link payloads are part of the content
        identity, while mutable link timestamps are excluded.

        By default every link must be pinned.  ``partial=True`` keeps compiling
        when a child has no pinned draft: the link keeps its position, but its
        section becomes an explicit omission marker (a visible notice plus an
        ``asc-omitted`` comment) and the link is listed in ``omitted``.  A partial
        composition therefore has a different ``content_version`` than the full
        one and never pretends the missing work was included.
        """
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        parent_id = snapshot.root_node.id
        with self.store.execution_lock(project_id):
            parent, parent_revision, parent_artifacts = self._current_draft(
                project_id, parent_id,
            )
            parent_body = self._chapters(
                project_id, parent_artifacts, reader=reader, heading_level=2,
            )
            sections = [*self._heading(parent, parent_revision), parent_body]
            visiting: set[str] = {parent_id}
            omitted: list[dict[str, Any]] = []

            def append_children(node: WorkNode, level: int) -> list[dict[str, Any]]:
                if node.id not in visiting:
                    raise NestedError(f"composition ancestry lost track of node {node.id}")
                payloads: list[dict[str, Any]] = []
                for link in self.store.list_links(project_id, node.id):
                    child = self.store.load_node(project_id, link.child_node_id)
                    if child.id in visiting:
                        raise NestedError(f"cycle detected while composing node {child.id}")
                    if not link.artifacts:
                        if not partial:
                            raise NestedError(
                                f"link {link.id} has no pinned draft; "
                                "run the child or adopt its completed revision"
                            )
                        title = self._current_title(project_id, child)
                        omitted.append({
                            "link_id": link.id,
                            "node_id": child.id,
                            "order": link.order,
                            "title": title,
                            "reason": OMITTED_NO_PINNED_DRAFT,
                        })
                        sections.extend([
                            "",
                            f"{'#' * (level + 1)} {title}",
                            "",
                            (
                                f"<!-- asc-omitted: link={link.id} node={child.id} "
                                f"order={link.order} reason={OMITTED_NO_PINNED_DRAFT} -->"
                            ),
                            "",
                            f"> {OMITTED_NOTICE}",
                        ])
                        continue
                    child_revision = self.store.load_revision(
                        project_id, child.id, link.child_revision_id,
                    )
                    child_body = self._chapters(
                        project_id, link.artifacts,
                        reader=reader, heading_level=level + 2,
                    )
                    payload = _pinned_link_dict(link)
                    sections.extend([
                        "",
                        f"{'#' * (level + 1)} {child_revision.spec.title}",
                        "",
                        (
                            f"<!-- asc-embedded: link={link.id} node={child.id} "
                            f"revision={child_revision.id} "
                            f"content_version={link.content_version} -->"
                        ),
                        "",
                        child_body,
                    ])
                    visiting.add(child.id)
                    nested = append_children(child, level + 1)
                    visiting.remove(child.id)
                    if nested:
                        payload["children"] = nested
                    payloads.append(payload)
                return payloads

            link_payloads = append_children(parent, 1)
            text = "\n".join(sections).rstrip() + "\n"
            text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            parent_version = WorkLink.version_for(parent_revision, parent_artifacts)
            identity: dict[str, Any] = {
                "parent": {
                    "node_id": parent_id,
                    "revision_id": parent_revision.id,
                    "content_version": parent_version,
                },
                "links": link_payloads,
                "text_sha256": text_sha256,
            }
            if omitted:
                identity["omitted"] = omitted
            content_version = hashlib.sha256(
                canonical_json(identity).encode("utf-8")
            ).hexdigest()
            relative = f"artifacts/{parent_id}/combined-{content_version[:16]}.md"
            output_path = self.store.project_dir(project_id) / relative
            manifest_path = output_path.with_suffix(".json")
            manifest = {
                "record_type": "asc_composition",
                "schema_version": SCHEMA_VERSION,
                "project_id": project_id,
                "node_id": parent_id,
                "revision_id": parent_revision.id,
                "content_version": content_version,
                "text_sha256": text_sha256,
                "output": relative,
                "parent_content_version": parent_version,
                "links": link_payloads,
            }
            if omitted:
                manifest["omitted"] = omitted
            _write_once(output_path, text.encode("utf-8"))
            _write_once(
                manifest_path,
                (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
        return CompositionResult(
            project_id=project_id, node_id=parent_id, revision_id=parent_revision.id,
            content_version=content_version, sha256=text_sha256, text=text,
            path=output_path, links=tuple(link_payloads), omitted=tuple(omitted),
        )
