"""Depth-one nested-work links and deterministic compilation.

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
from .schema import SCHEMA_VERSION, canonical_json
from .store import ProjectError, ProjectStore


class NestedError(ProjectError):
    """A nested work cannot be rendered or compiled from its pinned inputs."""


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "content_version": self.content_version,
            "sha256": self.sha256,
            "path": str(self.path) if self.path is not None else None,
            "links": list(self.links),
        }


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
        status = self.store.status(project_id, node_id)
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
        self, project_id: str, artifacts: tuple[ArtifactRef, ...],
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
        if not texts:
            raise NestedError("pinned draft has no chapter text")
        return "\n\n".join(texts)

    @staticmethod
    def _heading(node: WorkNode, revision: WorkNodeRevision) -> list[str]:
        return [
            f"# {revision.spec.title}",
            "",
            f"<!-- asc-node: {node.id} revision={revision.id} -->",
            "",
        ]

    def render(self, project_id: str, node_id: str | None = None) -> CompositionResult:
        """Render only the selected node's current completed draft."""
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        selected_id = snapshot.root_node.id
        with self.store.execution_lock(project_id):
            node, revision, artifacts = self._current_draft(project_id, selected_id)
            body = self._chapters(project_id, artifacts)
        text = "\n".join([*self._heading(node, revision), body]).rstrip() + "\n"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return CompositionResult(
            project_id=project_id, node_id=selected_id, revision_id=revision.id,
            content_version=WorkLink.version_for(revision, artifacts),
            sha256=digest, text=text,
        )

    def compose(self, project_id: str, node_id: str | None = None) -> CompositionResult:
        """Compile a root draft plus its pinned child drafts in link order."""
        snapshot = self.store.load_node_snapshot(project_id, node_id)
        parent_id = snapshot.root_node.id
        if parent_id != snapshot.project.root_node_id:
            raise NestedError("PR 5 combined output is available for the root node only")
        with self.store.execution_lock(project_id):
            parent, parent_revision, parent_artifacts = self._current_draft(
                project_id, parent_id,
            )
            parent_body = self._chapters(project_id, parent_artifacts)
            links = self.store.list_links(project_id, parent_id)
            sections = [*self._heading(parent, parent_revision), parent_body]
            link_payloads = []
            for link in links:
                if not link.artifacts:
                    raise NestedError(
                        f"link {link.id} has no pinned draft; run the child or adopt its completed revision"
                    )
                child = self.store.load_node(project_id, link.child_node_id)
                child_revision = self.store.load_revision(
                    project_id, child.id, link.child_revision_id,
                )
                child_body = self._chapters(project_id, link.artifacts)
                link_payloads.append(_pinned_link_dict(link))
                sections.extend([
                    "",
                    f"## {child_revision.spec.title}",
                    "",
                    (
                        f"<!-- asc-embedded: link={link.id} node={child.id} "
                        f"revision={child_revision.id} content_version={link.content_version} -->"
                    ),
                    "",
                    child_body,
                ])
            text = "\n".join(sections).rstrip() + "\n"
            text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            parent_version = WorkLink.version_for(parent_revision, parent_artifacts)
            content_version = hashlib.sha256(canonical_json({
                "parent": {
                    "node_id": parent_id,
                    "revision_id": parent_revision.id,
                    "content_version": parent_version,
                },
                "links": link_payloads,
                "text_sha256": text_sha256,
            }).encode("utf-8")).hexdigest()
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
            path=output_path, links=tuple(link_payloads),
        )
