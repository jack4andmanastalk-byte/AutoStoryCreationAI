"""Deterministic chronicle, regional, culture, and work-collection views."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .model import new_id, utc_now
from .nested import ProjectComposer
from .schema import (
    SCHEMA_VERSION,
    ProjectValidationError,
    canonical_json,
    validate_id,
)
from .store import ProjectError, ProjectExistsError, ProjectStore, _atomic_write_json
from .world import record_version
from .world_context import CANON_OVERLAY_ORDER, current_canon_entries, versioned_reference
from .world_store import WorldRecords, WorldStore

COMPILATION_KINDS = {"chronicle", "gazetteer", "culture", "collection"}
PROFILE_RECORD = "compilation_profile"
COMPILATION_RECORD = "asc_world_compilation"
_SELECTOR_FOR_KIND = {
    "chronicle": "timeframe_id",
    "gazetteer": "region_id",
    "culture": "culture_id",
    "collection": "node_id",
}


class CompilationError(ProjectError):
    """A compilation profile or its deterministic output is invalid."""


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{field} must be a non-empty string")
    return value


def _optional_id(value: Any, field: str) -> str | None:
    return None if value is None else validate_id(value, field)


def _stable_dict(record: Any) -> dict[str, Any]:
    data = record.to_dict()
    data.pop("created_at", None)
    return data


@dataclass(frozen=True)
class CompilationProfile:
    id: str
    project_id: str
    kind: str
    title: str
    timeframe_id: str | None
    region_id: str | None
    culture_id: str | None
    node_id: str | None
    content_version: str
    created_at: str

    @classmethod
    def create(cls, **values: Any) -> "CompilationProfile":
        record = cls(content_version="", **values)
        return replace(record, content_version=record_version(record.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": PROFILE_RECORD,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "title": self.title,
            "timeframe_id": self.timeframe_id,
            "region_id": self.region_id,
            "culture_id": self.culture_id,
            "node_id": self.node_id,
            "content_version": self.content_version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CompilationProfile":
        if not isinstance(data, dict) or data.get("record_type") != PROFILE_RECORD:
            raise ProjectValidationError("invalid compilation profile record")
        if data.get("schema_version") != SCHEMA_VERSION or isinstance(
            data.get("schema_version"), bool
        ):
            raise ProjectValidationError("unsupported compilation profile schema")
        validate_id(data.get("id"), "compilation_profile.id")
        validate_id(data.get("project_id"), "compilation_profile.project_id")
        kind = data.get("kind")
        if kind not in COMPILATION_KINDS:
            raise ProjectValidationError(f"unknown compilation kind: {kind!r}")
        expected = _SELECTOR_FOR_KIND[kind]
        selectors = {
            key: _optional_id(data.get(key), f"compilation_profile.{key}")
            for key in _SELECTOR_FOR_KIND.values()
        }
        for key, value in selectors.items():
            if (key == expected) != (value is not None):
                raise ProjectValidationError(
                    f"{kind} profile requires only {expected}"
                )
        if data.get("content_version") != record_version(data):
            raise ProjectValidationError("compilation profile content_version differs")
        _nonempty(data.get("created_at"), "compilation_profile.created_at")
        return cls(
            id=data["id"], project_id=data["project_id"], kind=kind,
            title=_nonempty(data.get("title"), "compilation_profile.title"),
            timeframe_id=selectors["timeframe_id"], region_id=selectors["region_id"],
            culture_id=selectors["culture_id"], node_id=selectors["node_id"],
            content_version=data["content_version"], created_at=data["created_at"],
        )


@dataclass(frozen=True)
class WorldCompilationResult:
    project_id: str
    profile_id: str
    kind: str
    content_version: str
    sha256: str
    text: str
    path: Path
    manifest_path: Path
    source_references: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "profile_id": self.profile_id,
            "kind": self.kind,
            "content_version": self.content_version,
            "sha256": self.sha256,
            "path": str(self.path),
            "manifest_path": str(self.manifest_path),
            "source_references": list(self.source_references),
        }


def _write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise CompilationError(f"compilation artifact differs at existing path: {path}")
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
                raise CompilationError(f"compilation artifact differs at existing path: {path}")
            return
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _references(records: list[Any]) -> list[dict[str, str]]:
    unique = {
        (row["record_type"], row["id"]): row
        for row in (versioned_reference(record) for record in records)
    }
    return [unique[key] for key in sorted(unique)]


def _canon_key(entry: Any) -> tuple[int, str, str]:
    return (
        CANON_OVERLAY_ORDER.index(entry.scope.kind),
        entry.valid_span_id or "",
        entry.id,
    )


def _canon_section(entries: list[Any]) -> list[str]:
    lines = ["## Canon"]
    if not entries:
        return [*lines, "", "- なし"]
    for entry in sorted(entries, key=_canon_key):
        lines.extend([
            "",
            f"### {entry.subject}",
            "",
            canonical_json(_stable_dict(entry)),
        ])
    return lines


def _record_section(title: str, records: list[Any]) -> list[str]:
    lines = [f"## {title}"]
    if not records:
        return [*lines, "", "- なし"]
    for record in sorted(records, key=lambda item: item.id):
        lines.extend(["", f"### {record.id}", "", canonical_json(_stable_dict(record))])
    return lines


class WorldCompiler:
    def __init__(self, store: ProjectStore):
        self.store = store

    def profiles_dir(self, project_id: str) -> Path:
        self.store.load_project(project_id)
        return self.store.project_dir(project_id) / "compilations" / "profiles"

    def profile_path(self, project_id: str, profile_id: str) -> Path:
        return self.profiles_dir(project_id) / f"{validate_id(profile_id)}.json"

    def add_profile(self, project_id: str, data: dict[str, Any]) -> CompilationProfile:
        if not isinstance(data, dict):
            raise ProjectValidationError("compilation profile must be a JSON object")
        payload = dict(data)
        payload.setdefault("record_type", PROFILE_RECORD)
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("id", new_id("profile"))
        payload.setdefault("project_id", project_id)
        if payload["project_id"] != project_id:
            raise ProjectValidationError("compilation profile project_id differs from the target")
        payload.setdefault("created_at", utc_now())
        for key in _SELECTOR_FOR_KIND.values():
            payload.setdefault(key, None)
        if payload.get("kind") == "collection" and payload.get("node_id") is None:
            payload["node_id"] = self.store.load_project(project_id).root_node_id
        if not payload.get("content_version"):
            payload["content_version"] = record_version(payload)
        return self.save_profile(CompilationProfile.from_dict(payload))

    def save_profile(self, profile: CompilationProfile) -> CompilationProfile:
        profile = CompilationProfile.from_dict(profile.to_dict())
        path = self.profile_path(profile.project_id, profile.id)
        with self.store.writer_lock(profile.project_id):
            if path.exists():
                if self.store._read_json(path) == profile.to_dict():
                    return profile
                raise ProjectExistsError(f"compilation profile already exists: {profile.id}")
            self._validate_selector(profile)
            _atomic_write_json(path, profile.to_dict())
        return profile

    def load_profile(self, project_id: str, profile_id: str) -> CompilationProfile:
        path = self.profile_path(project_id, profile_id)
        profile = self.store._parse(path, CompilationProfile.from_dict)
        if profile.id != profile_id or profile.project_id != project_id:
            raise ProjectValidationError("compilation profile identity differs from its path")
        return profile

    def list_profiles(self, project_id: str) -> list[CompilationProfile]:
        directory = self.profiles_dir(project_id)
        if not directory.is_dir():
            return []
        profiles = [
            self.load_profile(project_id, path.stem)
            for path in sorted(directory.glob("*.json"), key=lambda item: item.name)
        ]
        for profile in profiles:
            self._validate_selector(profile)
        return profiles

    def _validate_selector(
        self, profile: CompilationProfile, records: WorldRecords | None = None,
    ) -> None:
        if profile.kind == "collection":
            self.store.load_node(profile.project_id, profile.node_id)
            return
        records = records or WorldStore(self.store).validate(profile.project_id)
        if profile.kind == "chronicle":
            valid = profile.timeframe_id in {item.id for item in records.timeframes}
        elif profile.kind == "gazetteer":
            valid = profile.region_id in {item.id for item in records.regions}
        else:
            valid = profile.culture_id in {item.id for item in records.cultures}
        if not valid:
            raise ProjectValidationError(
                f"compilation profile {profile.id} has a missing {profile.kind} selector"
            )

    @staticmethod
    def _canon_for(
        records: WorldRecords, *, kinds: set[str], references: set[str],
        span_ids: set[str] | None = None,
    ) -> list[Any]:
        entries = []
        for entry in current_canon_entries(records):
            if entry.scope.kind == "global":
                scope_applies = True
            else:
                scope_applies = (
                    entry.scope.kind in kinds and entry.scope.reference_id in references
                )
            if not scope_applies:
                continue
            if (
                span_ids is not None and entry.valid_span_id is not None
                and entry.valid_span_id not in span_ids
            ):
                continue
            entries.append(entry)
        return sorted(entries, key=_canon_key)

    @staticmethod
    def _auxiliary_spans(
        records: WorldRecords, selected: list[Any],
    ) -> tuple[list[Any], list[Any]]:
        span_ids = {
            record.valid_span_id for record in selected
            if getattr(record, "valid_span_id", None) is not None
        }
        spans = [item for item in records.time_spans if item.id in span_ids]
        frame_ids = {item.timeframe_id for item in spans if item.timeframe_id is not None}
        frames = [item for item in records.timeframes if item.id in frame_ids]
        return spans, frames

    def _chronicle(
        self, profile: CompilationProfile, records: WorldRecords,
    ) -> tuple[str, list[dict[str, str]]]:
        frame = next(item for item in records.timeframes if item.id == profile.timeframe_id)
        spans = [item for item in records.time_spans if item.timeframe_id == frame.id]
        span_ids = {item.id for item in spans}
        canon = self._canon_for(
            records, kinds={"timeframe"}, references={frame.id}, span_ids=span_ids,
        )
        dated = sorted(
            (item for item in spans if item.start is not None),
            key=lambda item: (
                item.start, item.end is None,
                item.end if item.end is not None else item.start, item.id,
            ),
        )
        undated = sorted(
            (item for item in spans if item.start is None), key=lambda item: item.id,
        )
        lines = [
            "## TimeFrame", "", canonical_json(_stable_dict(frame)), "",
            "## Dated spans",
        ]
        if not dated:
            lines.extend(["", "- なし"])
        for span in dated:
            lines.extend(["", f"### {span.label or span.id}", "", canonical_json(_stable_dict(span))])
        lines.extend(["", "## Undated spans"])
        if not undated:
            lines.extend(["", "- なし"])
        for span in undated:
            lines.extend(["", f"### {span.label or span.id}", "", canonical_json(_stable_dict(span))])
        related = [item for item in spans if item.before_span_ids]
        lines.extend(["", "## Relative order"])
        if not related:
            lines.extend(["", "- なし"])
        for span in sorted(related, key=lambda item: item.id):
            lines.extend(["", f"- {span.id} before {canonical_json(list(span.before_span_ids))}"])
        lines.extend(["", *_canon_section(canon)])
        return "\n".join(lines), _references([frame, *spans, *canon])

    def _gazetteer(
        self, profile: CompilationProfile, records: WorldRecords,
    ) -> tuple[str, list[dict[str, str]]]:
        selected_regions = []
        for region in records.regions:
            current = region
            while current is not None:
                if current.id == profile.region_id:
                    selected_regions.append(region)
                    break
                current = next(
                    (item for item in records.regions if item.id == current.parent_region_id),
                    None,
                )
        region_ids = {item.id for item in selected_regions}
        relations = [
            item for item in records.spatial_relations
            if item.source_region_id in region_ids or item.target_region_id in region_ids
        ]
        states = [
            item for item in records.culture_states
            if region_ids.intersection(item.region_ids)
        ]
        culture_ids = {item.culture_id for item in states}
        cultures = [item for item in records.cultures if item.id in culture_ids]
        canon = self._canon_for(records, kinds={"region"}, references=region_ids)
        spans, frames = self._auxiliary_spans(
            records, [*selected_regions, *relations, *states, *canon],
        )
        lines = [
            *_record_section("Regions", selected_regions), "",
            *_record_section("Spatial relations", relations), "",
            *_record_section("Culture states", states), "",
            *_record_section("Cultures", cultures), "",
            *_canon_section(canon),
        ]
        source = [
            *selected_regions, *relations, *states, *cultures, *canon, *spans, *frames,
        ]
        return "\n".join(lines), _references(source)

    def _culture(
        self, profile: CompilationProfile, records: WorldRecords,
    ) -> tuple[str, list[dict[str, str]]]:
        culture = next(item for item in records.cultures if item.id == profile.culture_id)
        states = [item for item in records.culture_states if item.culture_id == culture.id]
        state_ids = {item.id for item in states}
        relations = [
            item for item in records.culture_state_relations
            if item.source_state_id in state_ids or item.target_state_id in state_ids
        ]
        canon = self._canon_for(records, kinds={"culture"}, references={culture.id})
        spans, frames = self._auxiliary_spans(records, [*states, *relations, *canon])
        lines = [
            "## Culture", "", canonical_json(_stable_dict(culture)), "",
            *_record_section("Culture states", states), "",
            *_record_section("State relations", relations), "",
            *_record_section("Referenced time spans", spans), "",
            *_canon_section(canon),
        ]
        return "\n".join(lines), _references([
            culture, *states, *relations, *canon, *spans, *frames,
        ])

    def compile(self, project_id: str, profile_id: str) -> WorldCompilationResult:
        profile = self.load_profile(project_id, profile_id)
        if profile.kind == "collection":
            self._validate_selector(profile)
            composed = ProjectComposer(self.store).compose(project_id, profile.node_id)
            references = [{
                "record_type": "asc_composition",
                "id": composed.content_version,
                "content_version": composed.content_version,
            }]
            body = composed.text.rstrip("\n")
        else:
            records = WorldStore(self.store).validate(project_id)
            self._validate_selector(profile, records)
            if profile.kind == "chronicle":
                body, references = self._chronicle(profile, records)
            elif profile.kind == "gazetteer":
                body, references = self._gazetteer(profile, records)
            else:
                body, references = self._culture(profile, records)
        content_version = hashlib.sha256(canonical_json({
            "profile_id": profile.id,
            "profile_content_version": profile.content_version,
            "kind": profile.kind,
            "source_references": references,
        }).encode("utf-8")).hexdigest()
        text = (
            f"# {profile.title}\n\n"
            f"<!-- asc-world-compilation: profile={profile.id} "
            f"kind={profile.kind} version={content_version} -->\n\n"
            f"{body.rstrip()}\n"
        )
        text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        relative = (
            f"artifacts/world/{profile.kind}-{profile.id}-{content_version[:16]}.md"
        )
        output_path = self.store.project_dir(project_id) / relative
        manifest_path = output_path.with_suffix(".json")
        manifest = {
            "record_type": COMPILATION_RECORD,
            "schema_version": SCHEMA_VERSION,
            "project_id": project_id,
            "profile_id": profile.id,
            "kind": profile.kind,
            "content_version": content_version,
            "text_sha256": text_sha256,
            "output": relative,
            "profile": _stable_dict(profile),
            "source_references": references,
        }
        _write_once(output_path, text.encode("utf-8"))
        _write_once(
            manifest_path,
            (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
        )
        return WorldCompilationResult(
            project_id=project_id, profile_id=profile.id, kind=profile.kind,
            content_version=content_version, sha256=text_sha256, text=text,
            path=output_path, manifest_path=manifest_path,
            source_references=tuple(references),
        )
