"""Human-readable work, canon, design, and editorial check summary (U-06..U-08, F-26).

Reads the pinned artifacts of a node revision (with a fallback to
``<project>/relay/responses`` when ``runs/`` is not present on disk) and
formats:

* **info** — work metadata, revision lineage, per-chapter character counts, and
  child links.
* **canon** — characters, locations, facts, chapter timeline, foreshadowing,
  and suppressions.
* **design** — status and human-readable digest of all 8 design documents
  (``brief``, ``world``, ``history``, ``character``, ``relation``, ``plot``,
  ``scene``, ``voice``).
* **checks** — editorial triage separated into **blockers** (stop the standard
  flow), **warnings** (non-blocking revision candidates), **observations**
  (non-blocking reference notes such as dead-character references), and
  copy-pasteable **next edit commands**.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..pipeline.design import DOCS
from ..story.continuity import audit_texts
from ..story.text import without_markers
from .model import StageCheckpoint, WorkLink, WorkNode, WorkNodeRevision
from .store import ProjectError, ProjectStore

PROJECT_SUMMARY_SCHEMA = "asc-project-summary-v1"
SUMMARY_SECTIONS = ("info", "canon", "design", "checks")

DESIGN_TITLES_JA: dict[str, str] = {
    "brief": "企画核（brief）",
    "world": "世界規則（world）",
    "history": "歴史年表（history）",
    "character": "人物核（character）",
    "relation": "関係網（relation）",
    "plot": "物語構造（plot）",
    "scene": "場面情報（scene）",
    "voice": "文体制御（voice）",
}


class SummaryError(ProjectError):
    """A requested project, node, revision, or section cannot be summarized."""


@dataclass(frozen=True)
class ProjectSummaryResult:
    project_id: str
    node_id: str
    revision_id: str
    title: str
    state: str
    sections: tuple[str, ...]
    info: dict[str, Any]
    canon: dict[str, Any]
    design: dict[str, Any]
    checks: dict[str, Any]
    markdown: str

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": PROJECT_SUMMARY_SCHEMA,
            "project_id": self.project_id,
            "node_id": self.node_id,
            "revision_id": self.revision_id,
            "title": self.title,
            "state": self.state,
            "sections": list(self.sections),
        }
        if "info" in self.sections:
            payload["info"] = self.info
        if "canon" in self.sections:
            payload["canon"] = self.canon
        if "design" in self.sections:
            payload["design"] = self.design
        if "checks" in self.sections:
            payload["checks"] = self.checks
        return payload


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    candidate = fence.group(1) if fence else stripped
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _cli_base(store: ProjectStore) -> str:
    return f"python3 scripts/story_project.py --root {store.root}"


def _node_flag(node_id: str, root_node_id: str) -> str:
    return f" --node {node_id}" if node_id != root_node_id else ""


def _revision_chain(
    store: ProjectStore, project_id: str, node: WorkNode, revision: WorkNodeRevision,
) -> list[WorkNodeRevision]:
    """Return ``[revision, parent, ...]`` following ``parent_revision_id``."""
    chain = [revision]
    seen = {revision.id}
    current = revision
    while current.parent_revision_id and current.parent_revision_id not in seen:
        parent_id = current.parent_revision_id
        seen.add(parent_id)
        try:
            current = store.load_revision(project_id, node.id, parent_id)
        except ProjectError:
            break
        chain.append(current)
    return chain


def _relay_purpose_json(
    project_dir: Path, node_id: str, revision_ids: list[str], purpose: str,
) -> dict[str, Any] | None:
    """Find the latest answered JSON payload in ``relay/`` for ``purpose``."""
    requests_dir = project_dir / "relay" / "requests"
    responses_dir = project_dir / "relay" / "responses"
    if not requests_dir.is_dir() or not responses_dir.is_dir():
        return None
    candidates: list[tuple[int, int, str, Path]] = []
    purposes = {purpose, f"{purpose}:repair"}
    for req_path in requests_dir.glob("*.json"):
        req = _read_json(req_path)
        if not req or req.get("task_id") != node_id:
            continue
        req_purpose = str(req.get("purpose") or "")
        if req_purpose not in purposes:
            continue
        key = str(req.get("key") or req_path.stem)
        resp_path = responses_dir / f"{key}.json"
        if not resp_path.is_file():
            continue
        rev_rank = len(revision_ids)
        for idx, rev_id in enumerate(revision_ids):
            if rev_id in key:
                rev_rank = idx
                break
        is_repair = 0 if req_purpose.endswith(":repair") else 1
        attempt = -int(req.get("attempt") or 1)
        candidates.append((rev_rank, is_repair, f"{attempt:04d}-{key}", resp_path))
    if not candidates:
        return None
    candidates.sort()
    for _, _, _, resp_path in candidates:
        resp = _read_json(resp_path)
        if not resp or not isinstance(resp.get("text"), str):
            continue
        parsed = _extract_json_object(resp["text"])
        if parsed is not None:
            return parsed
    return None


def _summarize_design_doc(name: str, data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if name == "brief":
        if data.get("logline"):
            lines.append(f"ログライン: {data['logline']}")
        if data.get("theme"):
            lines.append(f"主題: {data['theme']}")
        elements = data.get("elements")
        if isinstance(elements, dict):
            parts = [
                f"{label}={elements[key]}"
                for key, label in (
                    ("who", "誰が"),
                    ("where", "どこで"),
                    ("wants", "何を望み"),
                    ("obstacle", "何に阻まれるか"),
                )
                if elements.get(key)
            ]
            if parts:
                lines.append("構成要素: " + " / ".join(parts))
        prohibitions = data.get("prohibitions")
        if isinstance(prohibitions, list) and prohibitions:
            formatted_prohibitions = [
                str(x.get("rule") or x.get("statement") or x)
                if isinstance(x, dict) else str(x)
                for x in prohibitions[:4]
            ]
            lines.append(f"禁止条件: {' / '.join(formatted_prohibitions)}")
    elif name == "world":
        axioms = data.get("axioms")
        if isinstance(axioms, list) and axioms:
            lines.append("公理: " + " / ".join(str(x) for x in axioms[:3]))
        rules = data.get("rules")
        if isinstance(rules, list):
            for rule in rules[:4]:
                if isinstance(rule, dict):
                    rid = rule.get("id", "?")
                    stmt = rule.get("statement", "")
                    cost = rule.get("cost", "")
                    lines.append(f"規則 {rid}: {stmt}" + (f"（代償: {cost}）" if cost else ""))
    elif name == "history":
        eras = data.get("eras")
        if isinstance(eras, list) and eras:
            era_labels = [
                f"{e.get('id', '?')}:{e.get('name', '')}({e.get('begins')}〜{e.get('ends')})"
                for e in eras if isinstance(e, dict)
            ]
            if era_labels:
                lines.append("時代区分: " + " / ".join(era_labels))
        events = data.get("events")
        if isinstance(events, list):
            for ev in events[:5]:
                if isinstance(ev, dict):
                    title = ev.get("title") or ev.get("name") or ev.get("id", "?")
                    detail = ev.get("effect") or ev.get("outcome") or ev.get("trace") or ""
                    arrow = f" → {detail}" if detail else ""
                    lines.append(
                        f"出来事 {ev.get('id', '?')} (year={ev.get('year')}): {title}{arrow}"
                    )
        apocrypha = data.get("apocrypha")
        if isinstance(apocrypha, list) and apocrypha:
            lines.append(f"異説: {len(apocrypha)} 件")
    elif name == "character":
        chars = data.get("characters")
        if isinstance(chars, list):
            for ch in chars:
                if isinstance(ch, dict):
                    cid = ch.get("id", "?")
                    want = ch.get("want", "")
                    need = ch.get("need", "")
                    lines.append(f"{cid}: WANT={want} / NEED={need}")
    elif name == "relation":
        pairs = data.get("pairs")
        if isinstance(pairs, list):
            for pair in pairs[:5]:
                if isinstance(pair, dict):
                    a = pair.get("a", "?")
                    b = pair.get("b", "?")
                    conflict = pair.get("conflict") or pair.get("public") or ""
                    lines.append(f"{a} × {b}: {conflict}")
        silences = data.get("silences")
        if isinstance(silences, list) and silences:
            lines.append(f"沈黙・不言の約束: {len(silences)} 件")
    elif name == "plot":
        if data.get("logline"):
            lines.append(f"ログライン: {data['logline']}")
        acts = data.get("acts")
        if isinstance(acts, list):
            act_parts = []
            for act in acts:
                if isinstance(act, dict):
                    ch_list = ",".join(str(c) for c in (act.get("chapters") or []))
                    act_parts.append(f"{act.get('id', '?')}[{ch_list}]: {act.get('question', '')}")
            if act_parts:
                lines.append("幕構成: " + " / ".join(act_parts))
        turns = data.get("turns")
        if isinstance(turns, list) and turns:
            lines.append(f"転換点: {len(turns)} 件")
        ending = data.get("ending")
        if isinstance(ending, dict) and ending.get("state"):
            lines.append(f"結末状態: {ending['state']}")
        elif isinstance(ending, str) and ending:
            lines.append(f"結末状態: {ending}")
    elif name == "scene":
        scenes = data.get("scenes")
        if isinstance(scenes, list):
            for sc in scenes:
                if isinstance(sc, dict):
                    sid = sc.get("id", "?")
                    ch = sc.get("chapter", "?")
                    purpose = sc.get("purpose", "")
                    disclosure = sc.get("disclosure") if isinstance(sc.get("disclosure"), dict) else {}
                    disclosed = ",".join(str(x) for x in (disclosure.get("disclosed") or []))
                    suffix = f"（開示: {disclosed}）" if disclosed else ""
                    lines.append(f"{sid} ({ch}): {purpose}{suffix}")
    elif name == "voice":
        vp = data.get("viewpoint")
        if isinstance(vp, dict):
            lines.append(
                f"視点: person={vp.get('person', '?')}, character={vp.get('character', '-')}"
            )
        narrator = data.get("narrator")
        if isinstance(narrator, dict) and narrator.get("knows_ja"):
            lines.append(f"語り手の知識範囲: {narrator['knows_ja']}")
        banned = data.get("banned")
        if isinstance(banned, list) and banned:
            words = [str(item.get("pattern")) for item in banned if isinstance(item, dict) and item.get("pattern")]
            if words:
                lines.append("禁止表現: " + "、".join(words))
    return lines


class ProjectSummary:
    """Build a structured and Markdown summary for one project node revision."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def summarize(
        self,
        project_id: str,
        node_id: str | None = None,
        *,
        revision_id: str | None = None,
        sections: tuple[str, ...] | list[str] = SUMMARY_SECTIONS,
    ) -> ProjectSummaryResult:
        requested = tuple(sections) if sections else SUMMARY_SECTIONS
        invalid = [s for s in requested if s not in SUMMARY_SECTIONS]
        if invalid:
            raise SummaryError(
                f"unknown summary section(s): {', '.join(invalid)} "
                f"(expected: {', '.join(SUMMARY_SECTIONS)})"
            )

        project = self.store.load_project(project_id)
        target_node_id = node_id or project.root_node_id
        node = self.store.load_node(project_id, target_node_id)
        target_revision_id = revision_id or node.current_revision_id
        revision = self.store.load_revision(project_id, target_node_id, target_revision_id)
        project_dir = self.store.project_dir(project_id)
        checkpoints = self._load_checkpoints_for_revision(
            project_id, project_dir, node, revision,
        )
        try:
            status = self.store.status(project_id, target_node_id)
        except ProjectError:
            stage_states = {
                s: (checkpoints[s].status if s in checkpoints else "pending")
                for s in ("plan", "design", "draft")
            }
            if all(v == "done" for v in stage_states.values()):
                inferred_state = "complete"
            elif any(v == "failed" for v in stage_states.values()):
                inferred_state = "failed"
            elif any(v == "waiting_response" for v in stage_states.values()):
                inferred_state = "waiting_response"
            else:
                inferred_state = "running"
            status = {
                "project_id": project_id,
                "node_id": node.id,
                "root_node_id": project.root_node_id,
                "current_revision_id": revision.id,
                "state": inferred_state,
            }
        rev_chain = _revision_chain(self.store, project_id, node, revision)
        rev_chain_ids = [rev.id for rev in rev_chain]

        info = self._build_info(
            project_id, project.root_node_id, node, revision, checkpoints, status, project_dir,
        )
        canon, canon_dir = self._build_canon(
            project_dir, node.id, rev_chain_ids, checkpoints.get("plan"),
        )
        design = self._build_design(
            project_dir, node.id, revision, rev_chain_ids, checkpoints.get("design"),
        )
        checks = self._build_checks(
            project_id, project.root_node_id, node, revision, checkpoints,
            status, project_dir, canon_dir, design,
        )
        markdown = self._render_markdown(
            project_id, node, revision, requested, info, canon, design, checks,
        )
        return ProjectSummaryResult(
            project_id=project_id,
            node_id=node.id,
            revision_id=revision.id,
            title=revision.spec.title,
            state=str(status.get("state", "unknown")),
            sections=requested,
            info=info,
            canon=canon,
            design=design,
            checks=checks,
            markdown=markdown,
        )

    def _safe_list_links(
        self, project_id: str, parent_node_id: str,
    ) -> list[WorkLink]:
        try:
            return self.store.list_links(project_id, parent_node_id)
        except ProjectError:
            directory = self.store.node_dir(project_id, parent_node_id) / "links"
            if not directory.is_dir():
                return []
            links: list[WorkLink] = []
            for path in sorted(directory.glob("*.json")):
                raw = _read_json(path)
                if raw is None:
                    continue
                try:
                    links.append(WorkLink.from_dict(raw))
                except Exception:
                    continue
            return sorted(links, key=lambda item: (item.order, item.id))

    def _load_checkpoints_for_revision(
        self,
        project_id: str,
        project_dir: Path,
        node: WorkNode,
        revision: WorkNodeRevision,
    ) -> dict[str, StageCheckpoint]:
        checkpoints: dict[str, StageCheckpoint] = {}
        checkpoint_dir = self.store.node_dir(project_id, node.id) / "checkpoints"
        if checkpoint_dir.is_dir():
            for path in sorted(checkpoint_dir.glob("*.json")):
                raw = _read_json(path)
                if raw is None:
                    continue
                try:
                    cp = StageCheckpoint.from_dict(raw)
                except Exception:
                    continue
                if cp.revision_id == revision.id and cp.node_id == node.id:
                    checkpoints[cp.stage] = cp
        if len(checkpoints) == 3:
            return checkpoints

        # For historical revisions, look up parent_runs on child revisions or scan runs/.
        for candidate_rev in self.store.list_revisions(project_id, node.id):
            if candidate_rev.parent_revision_id == revision.id and candidate_rev.parent_runs:
                for stage, run_id in candidate_rev.parent_runs.items():
                    if stage not in checkpoints:
                        checkpoints[stage] = StageCheckpoint(
                            project_id=project_id,
                            node_id=node.id,
                            revision_id=revision.id,
                            stage=stage,
                            status="done",
                            attempt_id=run_id.removesuffix(f"-{stage}"),
                            run_id=run_id,
                        )
        runs_dir = project_dir / "runs"
        if runs_dir.is_dir() and len(checkpoints) < 3:
            for input_path in sorted(runs_dir.glob("*/project-input.json")):
                inp = _read_json(input_path)
                if not inp:
                    continue
                if (
                    inp.get("node_id") == node.id
                    and inp.get("revision_id") == revision.id
                    and inp.get("stage") in ("plan", "design", "draft")
                ):
                    stage = str(inp["stage"])
                    run_id = input_path.parent.name
                    manifest = _read_json(input_path.parent / "manifest.json") or {}
                    status_val = "done" if manifest.get("status") == "completed" else "running"
                    checkpoints[stage] = StageCheckpoint(
                        project_id=project_id,
                        node_id=node.id,
                        revision_id=revision.id,
                        stage=stage,
                        status=status_val,
                        attempt_id=str(inp.get("attempt_id") or run_id),
                        run_id=run_id,
                    )
        return checkpoints

    def _build_info(
        self,
        project_id: str,
        root_node_id: str,
        node: WorkNode,
        revision: WorkNodeRevision,
        checkpoints: dict[str, StageCheckpoint],
        status: dict[str, Any],
        project_dir: Path,
    ) -> dict[str, Any]:
        draft_cp = checkpoints.get("draft")
        draft_dir = (
            project_dir / "runs" / draft_cp.run_id
            if draft_cp and draft_cp.run_id
            else None
        )
        draft_meta = _read_json(draft_dir / "draft.json") if draft_dir else None
        plan_cp = checkpoints.get("plan")
        plan_dir = (
            project_dir / "runs" / plan_cp.run_id
            if plan_cp and plan_cp.run_id
            else None
        )
        plan_revise = _read_json(plan_dir / "revise.json") if plan_dir else None
        design_cp = checkpoints.get("design")
        design_dir = (
            project_dir / "runs" / design_cp.run_id
            if design_cp and design_cp.run_id
            else None
        )
        design_revise = _read_json(design_dir / "revise.json") if design_dir else None
        draft_revise = _read_json(draft_dir / "revise.json") if draft_dir else None

        if revision.derived is not None:
            revision_kind = str(revision.derived.get("kind") or "revise")
        elif any(r and r.get("kind") == "branch" for r in (plan_revise, design_revise, draft_revise)):
            revision_kind = "branch"
        elif revision.parent_revision_id is not None:
            revision_kind = "continue"
        else:
            revision_kind = "initial"

        revision_ids = [r.id for r in self.store.list_revisions(project_id, node.id)]

        chapters_info: list[dict[str, Any]] = []
        total_with_markers = 0
        total_body = 0
        target_per_ch = revision.spec.target_chars_per_chapter

        if draft_dir and (draft_dir / "text").is_dir():
            meta_by_id = {
                str(row.get("id")): row
                for row in (draft_meta.get("chapters") if isinstance(draft_meta, dict) else None) or []
                if isinstance(row, dict) and row.get("id")
            }
            for ch_path in sorted((draft_dir / "text").glob("*.md")):
                cid = ch_path.stem
                raw_text = ch_path.read_text(encoding="utf-8")
                body_text = without_markers(raw_text)
                chars_with_markers = len(re.sub(r"\s", "", raw_text))
                chars_body = len(re.sub(r"\s", "", body_text))
                total_with_markers += chars_with_markers
                total_body += chars_body
                meta_row = meta_by_id.get(cid, {})
                chapters_info.append({
                    "id": cid,
                    "day": meta_row.get("day"),
                    "location": meta_row.get("location"),
                    "chars_body": int(meta_row.get("chars") or chars_body),
                    "chars_with_markers": chars_with_markers,
                    "target_chars": target_per_ch,
                    "markers": meta_row.get("markers"),
                })

        child_links: list[dict[str, Any]] = []
        for link in self._safe_list_links(project_id, node.id):
            child_node = self.store.load_node(project_id, link.child_node_id)
            child_links.append({
                "link_id": link.id,
                "child_node_id": link.child_node_id,
                "order": link.order,
                "pinned_revision_id": link.child_revision_id,
                "current_child_revision_id": child_node.current_revision_id,
                "pinned_is_current": link.child_revision_id == child_node.current_revision_id,
            })

        return {
            "project_id": project_id,
            "node_id": node.id,
            "root_node_id": root_node_id,
            "parent_node_id": node.parent_id,
            "revision_id": revision.id,
            "parent_revision_id": revision.parent_revision_id,
            "revision_kind": revision_kind,
            "revision_ids": revision_ids,
            "continuation_design": (
                list(revision.continuation_design)
                if revision.continuation_design is not None else None
            ),
            "title": revision.spec.title,
            "premise": revision.spec.premise,
            "form": revision.spec.form,
            "chapter_count": revision.spec.chapter_count,
            "target_chars_per_chapter": target_per_ch,
            "total_target_chars": revision.spec.chapter_count * target_per_ch,
            "total_chars_body": total_body,
            "total_chars_with_markers": total_with_markers,
            "stages": {
                stage: (checkpoints[stage].status if stage in checkpoints else "not_started")
                for stage in ("plan", "design", "draft")
            },
            "chapters": chapters_info,
            "child_links": child_links,
        }

    def _build_canon(
        self,
        project_dir: Path,
        node_id: str,
        rev_chain_ids: list[str],
        plan_cp: StageCheckpoint | None,
    ) -> tuple[dict[str, Any], Path | None]:
        canon_dir: Path | None = None
        if plan_cp and plan_cp.run_id:
            candidate = project_dir / "runs" / plan_cp.run_id / "canon"
            if candidate.is_dir():
                canon_dir = candidate

        if canon_dir is not None:
            chars_raw = _read_json(canon_dir / "characters.json") or {}
            locs_raw = _read_json(canon_dir / "locations.json") or {}
            facts_raw = _read_json(canon_dir / "facts.json") or {}
            tl_raw = _read_json(canon_dir / "timeline.json") or {}
            fs_raw = _read_json(canon_dir / "foreshadowing.json") or {}
            sup_raw = _read_json(canon_dir / "suppressions.json") or {}
            return {
                "source": "run",
                "characters": list(chars_raw.get("characters") or []),
                "locations": list(locs_raw.get("locations") or []),
                "facts": list(facts_raw.get("facts") or []),
                "chapters": list(tl_raw.get("chapters") or []),
                "foreshadowing": list(fs_raw.get("foreshadowing") or []),
                "suppressions": list(sup_raw.get("suppressions") or []),
            }, canon_dir

        relay_plan = _relay_purpose_json(project_dir, node_id, rev_chain_ids, "plan")
        if relay_plan is not None:
            tl = relay_plan.get("timeline")
            chapters = tl.get("chapters") if isinstance(tl, dict) else relay_plan.get("chapters")
            return {
                "source": "relay",
                "characters": list(relay_plan.get("characters") or []),
                "locations": list(relay_plan.get("locations") or []),
                "facts": list(relay_plan.get("facts") or []),
                "chapters": list(chapters or []),
                "foreshadowing": list(relay_plan.get("foreshadowing") or []),
                "suppressions": list(relay_plan.get("suppressions") or []),
            }, None

        return {
            "source": "missing",
            "characters": [],
            "locations": [],
            "facts": [],
            "chapters": [],
            "foreshadowing": [],
            "suppressions": [],
        }, None

    def _build_design(
        self,
        project_dir: Path,
        node_id: str,
        revision: WorkNodeRevision,
        rev_chain_ids: list[str],
        design_cp: StageCheckpoint | None,
    ) -> dict[str, Any]:
        design_dir: Path | None = None
        if design_cp and design_cp.run_id:
            candidate = project_dir / "runs" / design_cp.run_id
            if candidate.is_dir():
                design_dir = candidate

        design_meta = _read_json(design_dir / "design.json") if design_dir else None
        revise_meta = _read_json(design_dir / "revise.json") if design_dir else None
        copied_set = set((revise_meta or {}).get("copied") or [])
        carried_set = set((design_meta or {}).get("carried") or [])
        docs_meta = (design_meta or {}).get("docs") or {}
        unresolved_set = set((design_meta or {}).get("unresolved") or [])

        documents: list[dict[str, Any]] = []
        source_used = "missing"

        for name in DOCS:
            doc_data: dict[str, Any] | None = None
            report_data: dict[str, Any] | None = None
            doc_source = "missing"
            if design_dir is not None:
                doc_data = _read_json(design_dir / "design" / f"{name}.json")
                report_data = _read_json(design_dir / "design" / f"{name}.report.json")
                if doc_data is not None:
                    doc_source = "run"
                    source_used = "run"
            if doc_data is None:
                doc_data = _relay_purpose_json(
                    project_dir, node_id, rev_chain_ids, f"design:{name}",
                )
                if doc_data is not None:
                    doc_source = "relay"
                    if source_used == "missing":
                        source_used = "relay"

            row_meta = docs_meta.get(name) if isinstance(docs_meta, dict) else None
            if isinstance(row_meta, dict) and row_meta.get("status"):
                doc_status = str(row_meta["status"])
            elif report_data and report_data.get("status"):
                doc_status = str(report_data["status"])
            elif name in carried_set:
                doc_status = "carried"
            elif f"design/{name}.json" in copied_set:
                doc_status = "copied"
            elif doc_data is not None:
                doc_status = "clean"
            else:
                doc_status = "missing"

            if name in unresolved_set and doc_status not in {"fail_open", "unresolved"}:
                doc_status = "unresolved"

            findings_list = (
                list(report_data.get("findings") or [])
                if isinstance(report_data, dict) else []
            )
            findings_count = (
                int(row_meta.get("findings", len(findings_list)))
                if isinstance(row_meta, dict) else len(findings_list)
            )
            attempts = (
                int(row_meta.get("attempts", (report_data or {}).get("attempts", 0)))
                if isinstance(row_meta, dict) or isinstance(report_data, dict) else 0
            )
            repairs = (
                int(row_meta.get("repairs", (report_data or {}).get("repairs", 0)))
                if isinstance(row_meta, dict) or isinstance(report_data, dict) else 0
            )

            documents.append({
                "doc": name,
                "title_ja": DESIGN_TITLES_JA.get(name, name),
                "source": doc_source,
                "status": doc_status,
                "attempts": attempts,
                "repairs": repairs,
                "findings_count": findings_count,
                "findings": findings_list,
                "summary_lines": _summarize_design_doc(name, doc_data) if doc_data else [],
            })

        return {
            "source": source_used,
            "unresolved": sorted(unresolved_set),
            "carried": sorted(carried_set),
            "copied": sorted(
                item.removeprefix("design/").removesuffix(".json")
                for item in copied_set
                if item.startswith("design/") and item.endswith(".json")
            ),
            "documents": documents,
        }

    def _build_checks(
        self,
        project_id: str,
        root_node_id: str,
        node: WorkNode,
        revision: WorkNodeRevision,
        checkpoints: dict[str, StageCheckpoint],
        status: dict[str, Any],
        project_dir: Path,
        canon_dir: Path | None,
        design: dict[str, Any],
    ) -> dict[str, Any]:
        base = _cli_base(self.store)
        node_opt = _node_flag(node.id, root_node_id)

        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        next_commands: list[str] = []

        def add_cmd(cmd: str | None) -> None:
            if cmd and cmd not in next_commands:
                next_commands.append(cmd)

        # 1. Stage checkpoint failures (blockers)
        for stage in ("plan", "design", "draft"):
            cp = checkpoints.get(stage)
            if cp and cp.status == "failed":
                err_msg = (cp.error or {}).get("message") or f"{stage} stage failed"
                cmd = f"{base} resume {project_id}{node_opt} --retry-failed"
                blockers.append({
                    "stage": stage,
                    "target": stage,
                    "rule": "stage_failed",
                    "message": str(err_msg),
                    "command": cmd,
                })
                add_cmd(cmd)

        # 2. Design findings (warnings when fail-open / unresolved)
        for doc_row in design.get("documents") or []:
            doc_name = doc_row["doc"]
            if doc_row["status"] in {"fail_open", "unresolved"} or doc_row["findings_count"] > 0:
                cmd = f"{base} revise {project_id}{node_opt} --design {doc_name}"
                findings = doc_row.get("findings") or []
                if findings:
                    for finding in findings:
                        rule = str(finding.get("check") or finding.get("code") or "design_check")
                        msg = str(finding.get("message_ja") or finding.get("message") or rule)
                        warnings.append({
                            "stage": "design",
                            "target": f"design:{doc_name}",
                            "rule": rule,
                            "message": msg,
                            "command": cmd,
                        })
                else:
                    warnings.append({
                        "stage": "design",
                        "target": f"design:{doc_name}",
                        "rule": "design_unresolved",
                        "message": f"{DESIGN_TITLES_JA.get(doc_name, doc_name)} に未解決の検査所見があります。",
                        "command": cmd,
                    })
                add_cmd(cmd)

        # 3. Draft checks: must_include, length warnings, and continuity audit
        draft_cp = checkpoints.get("draft")
        draft_dir = (
            project_dir / "runs" / draft_cp.run_id
            if draft_cp and draft_cp.run_id else None
        )
        draft_meta = _read_json(draft_dir / "draft.json") if draft_dir else None
        if isinstance(draft_meta, dict):
            must_inc = draft_meta.get("must_include") or {}
            hits = must_inc.get("hits") if isinstance(must_inc, dict) else {}
            if isinstance(hits, dict):
                missing_words = [w for w, count in hits.items() if not count]
                if missing_words:
                    cmd = f"{base} revise {project_id}{node_opt} --chapter ch01"
                    blockers.append({
                        "stage": "draft",
                        "target": "draft",
                        "rule": "must_include",
                        "message": f"必須語が本文に未出現です: {', '.join(missing_words)}",
                        "command": cmd,
                    })
                    add_cmd(cmd)
            for w_msg in draft_meta.get("warnings_ja") or ():
                ch_match = re.search(r"\b(ch\d+)\b", str(w_msg))
                ch_id = ch_match.group(1) if ch_match else None
                cmd = (
                    f"{base} revise {project_id}{node_opt} --chapter {ch_id}"
                    if ch_id else None
                )
                warnings.append({
                    "stage": "draft",
                    "target": ch_id or "draft",
                    "rule": "chapter_length_advisory",
                    "message": str(w_msg),
                    "command": cmd,
                })
                add_cmd(cmd)

        # 4. Continuity audit (high -> blocker, medium/low -> warning, observations -> observation)
        audit_summary: dict[str, Any] | None = None
        if canon_dir is not None and draft_dir is not None and (draft_dir / "text").is_dir():
            try:
                audit_data = audit_texts(canon_dir, draft_dir / "text")
            except Exception:
                audit_data = None
            if isinstance(audit_data, dict):
                audit_summary = audit_data.get("summary")
                seen_violations: set[tuple[str, str, str, Any, str]] = set()
                for v in audit_data.get("violations") or ():
                    ev = v.get("evidence") or {}
                    dedup_key = (
                        str(v.get("type") or ""),
                        str(v.get("subject") or ""),
                        str(v.get("chapter") or ""),
                        ev.get("line"),
                        str(ev.get("sentence") or ""),
                    )
                    if dedup_key in seen_violations:
                        continue
                    seen_violations.add(dedup_key)
                    ch_id = str(v.get("chapter") or "")
                    cmd = (
                        f"{base} revise {project_id}{node_opt} --chapter {ch_id}"
                        if ch_id else None
                    )
                    item = {
                        "stage": "audit",
                        "target": ch_id or "draft",
                        "rule": str(v.get("type") or "continuity"),
                        "severity": str(v.get("severity") or "medium"),
                        "subject": v.get("subject"),
                        "line": ev.get("line"),
                        "sentence": ev.get("sentence"),
                        "message": str(v.get("message_ja") or ""),
                        "command": cmd,
                    }
                    if v.get("severity") == "high":
                        blockers.append(item)
                    else:
                        warnings.append(item)
                    add_cmd(cmd)

                seen_obs: set[tuple[str, str, str, Any, str]] = set()
                for obs in audit_data.get("observations") or ():
                    ev = obs.get("evidence") or {}
                    dedup_key = (
                        str(obs.get("type") or ""),
                        str(obs.get("subject") or ""),
                        str(obs.get("chapter") or ""),
                        ev.get("line"),
                        str(ev.get("sentence") or ""),
                    )
                    if dedup_key in seen_obs:
                        continue
                    seen_obs.add(dedup_key)
                    observations.append({
                        "stage": "audit",
                        "target": str(obs.get("chapter") or "draft"),
                        "rule": str(obs.get("type") or "observation"),
                        "subject": obs.get("subject"),
                        "line": ev.get("line"),
                        "reasons": list(ev.get("reasons") or ()),
                        "sentence": ev.get("sentence"),
                        "message": str(obs.get("message_ja") or ""),
                    })

        # 5. Child / parent link staleness warnings
        if node.parent_id:
            for link in self._safe_list_links(project_id, node.parent_id):
                if (
                    link.child_node_id == node.id
                    and link.child_revision_id != revision.id
                    and status.get("state") == "complete"
                ):
                    cmd = f"{base} adopt-child {project_id} {link.id}"
                    warnings.append({
                        "stage": "compose",
                        "target": link.id,
                        "rule": "child_link_not_adopted",
                        "message": (
                            f"親リンク {link.id} は旧版 ({link.child_revision_id}) を指しています。"
                            f" 編纂前に adopt-child で現リビジョン ({revision.id}) を採用してください。"
                        ),
                        "command": cmd,
                    })
                    add_cmd(cmd)
        for link in self._safe_list_links(project_id, node.id):
            child_node = self.store.load_node(project_id, link.child_node_id)
            if link.child_revision_id != child_node.current_revision_id:
                cmd = f"{base} adopt-child {project_id} {link.id}"
                warnings.append({
                    "stage": "compose",
                    "target": link.id,
                    "rule": "child_link_stale",
                    "message": (
                        f"子ノード {link.child_node_id} の最新リビジョン ({child_node.current_revision_id}) が"
                        f" 親リンク {link.id} ({link.child_revision_id}) に未反映です。"
                    ),
                    "command": cmd,
                })
                add_cmd(cmd)

        return {
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "observation_count": len(observations),
            "blockers": blockers,
            "warnings": warnings,
            "observations": observations,
            "audit_summary": audit_summary,
            "next_edit_commands": next_commands,
        }

    def _render_markdown(
        self,
        project_id: str,
        node: WorkNode,
        revision: WorkNodeRevision,
        sections: tuple[str, ...],
        info: dict[str, Any],
        canon: dict[str, Any],
        design: dict[str, Any],
        checks: dict[str, Any],
    ) -> str:
        out: list[str] = [
            f"# 作品要約: {info['title']} (`{project_id}` / `{node.id}`)",
            "",
        ]
        if "info" in sections:
            out.extend([
                "## 1. 作品情報（Info）",
                "",
                f"- **プロジェクト / ノード**: `{project_id}` / `{node.id}`",
                f"- **現在リビジョン**: `{revision.id}`（種別: `{info['revision_kind']}`、全 {len(info['revision_ids'])} 版）",
                f"- **前提（Premise）**: {info['premise']}",
                f"- **工程状態**: plan=`{info['stages']['plan']}`, design=`{info['stages']['design']}`, draft=`{info['stages']['draft']}`",
                f"- **文字数合計**: 本文 **{info['total_chars_body']} 字**（監査マーカー込み {info['total_chars_with_markers']} 字 / 目安合計 {info['total_target_chars']} 字）",
            ])
            if info.get("continuation_design") is not None:
                out.append(
                    f"- **continuation 再生成設計書**: `{', '.join(info['continuation_design']) or 'なし'}`"
                )
            if info["chapters"]:
                out.extend([
                    "",
                    "| 章 | 日 | 場所 | 本文文字数 | マーカー込み | 目安 |",
                    "| --- | ---: | --- | ---: | ---: | ---: |",
                ])
                for ch in info["chapters"]:
                    out.append(
                        f"| `{ch['id']}` | {ch['day'] if ch['day'] is not None else '-'} "
                        f"| {ch['location'] or '-'} | {ch['chars_body']} 字 "
                        f"| {ch['chars_with_markers']} 字 | {ch['target_chars']} 字 |"
                    )
            if info["child_links"]:
                out.append("")
                out.append("### 子作品リンク")
                for link in info["child_links"]:
                    pin_state = "最新" if link["pinned_is_current"] else "要 adopt-child"
                    out.append(
                        f"- `{link['link_id']}` → `{link['child_node_id']}` "
                        f"(order={link['order']}, pinned=`{link['pinned_revision_id']}`, {pin_state})"
                    )
            out.append("")

        if "canon" in sections:
            out.extend([
                f"## 2. 設定台帳（Canon Summary, source=`{canon['source']}`）",
                "",
                "### 人物（Characters）",
            ])
            if canon["characters"]:
                for ch in canon["characters"]:
                    aliases = f"（別名: {', '.join(ch.get('aliases') or [])}）" if ch.get("aliases") else ""
                    knows = ",".join(ch.get("knows") or []) or "-"
                    notes = f" — {ch['notes']}" if ch.get("notes") else ""
                    out.append(
                        f"- **`{ch.get('id')}` {ch.get('name', '')}**{aliases}: "
                        f"状態=`{ch.get('status', 'alive')}`, 場所=`{ch.get('location', '-')}`, "
                        f"初期既知=`[{knows}]`{notes}"
                    )
            else:
                out.append("- （未登録）")

            out.extend(["", "### 場所・移動日数（Locations）"])
            if canon["locations"]:
                for loc in canon["locations"]:
                    lid = loc.get("id") or loc.get("name") or "?"
                    td = loc.get("travel_days") or {}
                    routes = ", ".join(f"{k}:{v}日" for k, v in td.items()) if isinstance(td, dict) and td else "移動定義なし"
                    out.append(f"- **`{lid}`**: {routes}")
            else:
                out.append("- （未登録）")

            out.extend(["", "### 事実（Facts）"])
            if canon["facts"]:
                for fact in canon["facts"]:
                    fid = fact.get("id", "?")
                    summary = fact.get("summary") or fact.get("statement") or ""
                    terms = ", ".join(fact.get("terms") or [])
                    out.append(f"- **`{fid}`**: {summary}" + (f"（語彙: `{terms}`）" if terms else ""))
            else:
                out.append("- （未登録）")

            out.extend(["", "### 章立て・伏線（Timeline & Foreshadowing）"])
            for ch in canon["chapters"]:
                out.append(
                    f"- 章 `{ch.get('id')}`: day={ch.get('day', '-')}, 場所={ch.get('location', '-')}"
                )
            for fs in canon["foreshadowing"]:
                out.append(
                    f"- 伏線 `{fs.get('id')}` ({fs.get('setup', '?')} → {fs.get('payoff', '?')}): "
                    f"{fs.get('description', '')}"
                )
            out.append("")

        if "design" in sections:
            out.extend([
                f"## 3. 設計書 8 種の要約（Design Summary, source=`{design['source']}`）",
                "",
            ])
            for doc in design["documents"]:
                out.append(
                    f"### {doc['title_ja']} — 状態: `{doc['status']}` "
                    f"(試行 {doc['attempts']}, 修復 {doc['repairs']}, 残存所見 {doc['findings_count']})"
                )
                if doc["summary_lines"]:
                    for line in doc["summary_lines"]:
                        out.append(f"- {line}")
                else:
                    out.append("- （要約データなし）")
                out.append("")

        if "checks" in sections:
            out.extend([
                "## 4. 検査・監査の編集支援要約（Editorial Checks）",
                "",
                f"- **Blocker（重大・完走阻止）**: {checks['blocker_count']} 件",
                f"- **Warning（警告・改訂候補）**: {checks['warning_count']} 件",
                f"- **Observation（観測・参考記録）**: {checks['observation_count']} 件（標準経路を止めない参照記録）",
                "",
            ])
            if checks["blockers"]:
                out.append("### Blocker（直ちに修正が必要）")
                for b in checks["blockers"]:
                    cmd_note = f" → `{b['command']}`" if b.get("command") else ""
                    out.append(f"- **[{b['stage']}:{b['target']}]** (`{b['rule']}`): {b['message']}{cmd_note}")
                out.append("")
            if checks["warnings"]:
                out.append("### Warning（必要に応じ部分改訂で対応可能）")
                for w in checks["warnings"]:
                    line_info = f" (line {w['line']})" if w.get("line") else ""
                    cmd_note = f" → `{w['command']}`" if w.get("command") else ""
                    out.append(
                        f"- **[{w['stage']}:{w['target']}{line_info}]** (`{w['rule']}`): "
                        f"{w['message']}{cmd_note}"
                    )
                out.append("")
            if checks["observations"]:
                out.append("### Observation（標準経路を止めない観測）")
                for obs in checks["observations"]:
                    line_info = f" (line {obs['line']})" if obs.get("line") else ""
                    reasons = f" [{', '.join(obs.get('reasons') or ())}]" if obs.get("reasons") else ""
                    out.append(
                        f"- **[{obs['stage']}:{obs['target']}{line_info}]** (`{obs['rule']}`{reasons}): "
                        f"{obs['message']}"
                    )
                out.append("")
            if checks["next_edit_commands"]:
                out.append("### 次に直すコマンド（選択的再生成・採用）")
                for cmd in checks["next_edit_commands"]:
                    out.append(f"- `{cmd}`")
                out.append("")
            else:
                out.append("### 次に直すコマンド")
                out.append("- 修正が必要な Blocker / Warning はありません。")
                out.append("")

        return "\n".join(out).rstrip() + "\n"
