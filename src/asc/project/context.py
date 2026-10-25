"""Deterministic ancestor and revision-bound world context packets.

Packets contain selected structured canon and chapter metadata, never ancestor
chapter prose.  World records are added only for an explicitly bound work
revision; unbound legacy projects retain the original pre1 packet shape.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..story.canon import Canon, load_canon
from .schema import SCHEMA_VERSION, ProjectValidationError, canonical_json
from .store import ProjectStore
from .world_context import build_world_context, validate_world_context

CONTEXT_PACKET_KIND = "asc-context-packet-pre1"
CONTEXT_PACKET_WORLD_KIND = "asc-context-packet-world1"
MAX_CONTEXT_ITEMS = 32
MAX_CONTEXT_TEXT = 800


def _text(value: Any, limit: int = MAX_CONTEXT_TEXT) -> str | None:
    if value is None:
        return None
    value = str(value)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _items(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return values[:MAX_CONTEXT_ITEMS]


def _canon_selection(
    canon: Canon, knowledge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select compact canon, optionally limiting facts to a character's knowledge."""
    chapters = sorted(
        canon.chapters.values(),
        key=lambda item: (item.day is None, item.day or 0, item.id),
    )
    known: set[str] | None = None
    if knowledge is not None:
        character = canon.characters.get(knowledge["character_id"])
        known = set(character.knows) if character is not None else set()
    facts = _items([
        {
            "id": item.id,
            "summary": _text(item.summary),
            "terms": [_text(term) for term in item.terms[:8]],
            "setup": item.setup,
        }
        for item in sorted(canon.facts.values(), key=lambda item: item.id)
        if known is None or item.id in known
    ])
    result = {
        "characters": _items([
            {
                "id": item.id,
                "name": _text(item.name),
                "aliases": [_text(alias) for alias in item.aliases[:8]],
                "status": item.status,
                "location": _text(item.location),
            }
            for item in sorted(canon.characters.values(), key=lambda item: item.id)
        ]),
        "facts": facts,
        "locations": _items([
            {"id": item.id, "travel_days": dict(sorted(item.travel_days.items()))}
            for item in sorted(canon.locations.values(), key=lambda item: item.id)
        ]),
        "chapters": _items([
            {"id": item.id, "day": item.day, "location": _text(item.location)}
            for item in chapters
        ]),
        "foreshadowing": _items([
            {
                "id": item.id,
                "description": _text(item.description),
                "setup": item.setup,
                "payoff": item.payoff,
            }
            for item in sorted(canon.foreshadowing.values(), key=lambda item: item.id)
        ]) if knowledge is None else [],
    }
    if knowledge is not None:
        result["knowledge"] = {
            "character_id": knowledge["character_id"],
            "known_fact_ids": [item["id"] for item in facts],
            "source": "character.knows",
            "foreshadowing": "excluded",
        }
    return result


def _knowledge_selection(options: dict[str, Any]) -> dict[str, Any] | None:
    raw = options.get("context_knowledge")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"character_id"}:
        raise ProjectValidationError(
            "WorkSpec.options.context_knowledge requires only character_id"
        )
    character_id = raw["character_id"]
    if not isinstance(character_id, str) or not character_id.strip():
        raise ProjectValidationError("context_knowledge.character_id must be non-empty")
    return {
        "character_id": character_id,
        "source": "ancestor_character_knows",
        "foreshadowing": "excluded",
    }


@dataclass(frozen=True)
class AncestorContext:
    node_id: str
    revision_id: str
    parent_node_id: str | None
    title: str
    premise: str
    state: str
    spec_sha256: str
    plan_run_id: str | None = None
    draft_run_id: str | None = None
    canon: dict[str, Any] | None = None
    chapters: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "parent_node_id": self.parent_node_id,
            "title": self.title,
            "premise": self.premise,
            "state": self.state,
            "spec_sha256": self.spec_sha256,
            "plan_run_id": self.plan_run_id,
            "draft_run_id": self.draft_run_id,
            "canon": self.canon,
            "chapters": list(self.chapters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AncestorContext":
        if not isinstance(data, dict):
            raise ValueError("ancestor context must be an object")
        chapters = data.get("chapters", [])
        canon = data.get("canon")
        if not isinstance(chapters, list) or not all(
            isinstance(row, dict) and "text" not in row for row in chapters
        ):
            raise ValueError("ancestor context chapters must be metadata objects")
        if canon is not None and not isinstance(canon, dict):
            raise ValueError("ancestor context canon must be an object or null")
        return cls(
            node_id=str(data["node_id"]),
            revision_id=str(data["revision_id"]),
            parent_node_id=data.get("parent_node_id"),
            title=str(data["title"]),
            premise=str(data["premise"]),
            state=str(data["state"]),
            spec_sha256=str(data["spec_sha256"]),
            plan_run_id=data.get("plan_run_id"),
            draft_run_id=data.get("draft_run_id"),
            canon=dict(canon) if canon is not None else None,
            chapters=tuple(dict(row) for row in chapters),
        )


@dataclass(frozen=True)
class ContextPacket:
    project_id: str
    node_id: str
    revision_id: str
    ancestors: tuple[AncestorContext, ...]
    world: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        data = {
            "record_type": (
                CONTEXT_PACKET_WORLD_KIND if self.world is not None
                else CONTEXT_PACKET_KIND
            ),
            "schema_version": SCHEMA_VERSION,
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "selection": {
                "scope": (
                    "ancestors" if self.world is None
                    else "ancestors+world" if self.ancestors else "world"
                ),
                "canon": "compact_structured_v1",
                "prose": "excluded",
                "max_items_per_collection": MAX_CONTEXT_ITEMS,
            },
            "ancestors": [ancestor.to_dict() for ancestor in self.ancestors],
        }
        if self.knowledge is not None:
            data["selection"]["knowledge"] = self.knowledge
        if self.world is not None:
            data["world"] = self.world
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextPacket":
        if not isinstance(data, dict) or data.get("record_type") not in {
            CONTEXT_PACKET_KIND, CONTEXT_PACKET_WORLD_KIND,
        }:
            raise ValueError("invalid context packet record")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported context packet schema")
        ancestors = data.get("ancestors")
        if not isinstance(ancestors, list):
            raise ValueError("context packet ancestors must be a list")
        selection = data.get("selection")
        if not isinstance(selection, dict) or selection.get("prose") != "excluded":
            raise ValueError("context packet must explicitly exclude prose")
        knowledge = selection.get("knowledge")
        if knowledge is not None:
            if (
                not isinstance(knowledge, dict)
                or not isinstance(knowledge.get("character_id"), str)
                or not knowledge["character_id"].strip()
                or knowledge.get("source") != "ancestor_character_knows"
            ):
                raise ValueError("invalid context knowledge selection")
            canonical_json(knowledge)
        world = data.get("world")
        if data.get("record_type") == CONTEXT_PACKET_KIND and world is not None:
            raise ValueError("pre1 context packet cannot contain world records")
        if data.get("record_type") == CONTEXT_PACKET_WORLD_KIND:
            if world is None:
                raise ValueError("world context packet requires its world selection")
            validate_world_context(world)
        return cls(
            project_id=str(data["project_id"]),
            node_id=str(data["node_id"]),
            revision_id=str(data["revision_id"]),
            ancestors=tuple(AncestorContext.from_dict(row) for row in ancestors),
            world=dict(world) if world is not None else None,
            knowledge=dict(knowledge) if knowledge is not None else None,
        )

    def prompt_suffix(self) -> str:
        """Return JSON-only context plus an explicit no-prose instruction."""
        if self.world is None:
            return (
                "\n\n## 祖先作品の選択文脈（本文ではありません）\n"
                "以下は選択したcanonと構造要約だけです。祖先の章本文は含めず、"
                "この作品の前提と矛盾する場合はこの作品の指定を優先してください。\n"
                + canonical_json(self.to_dict())
            )
        return (
            "\n\n## 作品と世界の選択文脈（本文ではありません）\n"
            "以下はbindingで選んだ世界資料と祖先の構造要約だけです。章本文、"
            "指定外の時間軸、未来の文化状態・canonは含めません。世界canonは"
            "selection.overlay_orderの順に適用し、後のscopeを上位overlayとします。"
            "この作品の前提と矛盾する場合はこの作品の指定を優先してください。\n"
            + canonical_json(self.to_dict())
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _ancestor_context(
    store: ProjectStore, project_id: str, node_id: str,
    knowledge: dict[str, Any] | None = None,
) -> AncestorContext:
    snapshot = store.load_node_snapshot(project_id, node_id)
    status = store.status(project_id, node_id, include_descendants=False)
    revision = snapshot.revision
    plan_run_id = status.get("checkpoints", {}).get("plan", {}).get("run_id")
    draft_run_id = status.get("checkpoints", {}).get("draft", {}).get("run_id")
    canon_selection: dict[str, Any] | None = None
    chapter_rows: list[dict[str, Any]] = []
    if status["state"] == "complete" and plan_run_id and draft_run_id:
        run_dir = store.project_dir(project_id) / "runs" / plan_run_id
        canon = load_canon(run_dir / "canon")
        canon_selection = _canon_selection(canon, knowledge)
        draft = _read_json(
            store.project_dir(project_id) / "runs" / draft_run_id / "draft.json"
        )
        for row in draft.get("chapters", []):
            if isinstance(row, dict) and row.get("id"):
                # Keep only metadata from draft.json.  In particular, never
                # copy a text field even if a future Draft schema adds one.
                chapter_rows.append({
                    key: row.get(key)
                    for key in ("id", "chars", "day", "location", "markers")
                    if key in row
                })
    if not chapter_rows:
        chapter_rows = [
            {"id": f"ch{index:02d}"}
            for index in range(1, revision.spec.chapter_count + 1)
        ]
    return AncestorContext(
        node_id=node_id,
        revision_id=revision.id,
        parent_node_id=snapshot.root_node.parent_id,
        title=_text(revision.spec.title) or revision.spec.title,
        premise=_text(revision.spec.premise) or revision.spec.premise,
        state=status["state"],
        spec_sha256=revision.spec_sha256,
        plan_run_id=plan_run_id if status["state"] == "complete" else None,
        draft_run_id=draft_run_id if status["state"] == "complete" else None,
        canon=canon_selection,
        chapters=tuple(chapter_rows[:MAX_CONTEXT_ITEMS]),
    )


def build_context_packet(
    store: ProjectStore, project_id: str, node_id: str,
) -> ContextPacket | None:
    """Build ancestor context and, when explicitly bound, world context."""
    snapshot = store.load_node_snapshot(project_id, node_id)
    knowledge = _knowledge_selection(snapshot.revision.spec.options)
    world = build_world_context(store, project_id, node_id)
    if snapshot.root_node.parent_id is None and world is None:
        return None
    ancestors: list[AncestorContext] = []
    current = snapshot.root_node
    while current.parent_id is not None:
        parent = store.load_node(project_id, current.parent_id)
        ancestors.append(_ancestor_context(store, project_id, parent.id, knowledge))
        current = parent
    ancestors.reverse()  # root -> immediate parent, stable and human-readable
    return ContextPacket(
        project_id=project_id,
        node_id=snapshot.root_node.id,
        revision_id=snapshot.revision.id,
        ancestors=tuple(ancestors),
        world=world,
        knowledge=knowledge,
    )
