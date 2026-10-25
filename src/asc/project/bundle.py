"""Export, verify, and restore portable project replay bundles.

A bundle contains the complete project directory needed to inspect or replay
its runs, not just the current draft.  Every payload file is pinned by size and
SHA-256 in ``bundle.json``.  Locks and temporary writer files are deliberately
excluded; they are process state, not creative source material.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .model import utc_now
from .schema import validate_id
from .store import ProjectError, ProjectStore
from .world_store import WorldStore

BUNDLE_TYPE = "asc-project-replay-bundle"
BUNDLE_SCHEMA_VERSION = 1
MANIFEST_NAME = "bundle.json"


class BundleError(ProjectError):
    """A replay bundle is invalid, incomplete, or cannot be written safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BundleError(f"{field} must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"{field} contains an unsafe path: {value!r}")
    return path.as_posix()


def _inside(root: Path, relative: str) -> Path:
    target = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise BundleError(f"bundle path escapes its root: {relative}") from exc
    return target


def _overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents


class ReplayBundle:
    """A whole-project replay source with a portable hash manifest."""

    def __init__(self, store: ProjectStore):
        self.store = store

    def export(self, project_id: str, destination: str | Path) -> dict[str, Any]:
        source = self.store.project_dir(project_id)
        if not source.is_dir():
            raise BundleError(f"project not found: {project_id}")
        destination = Path(destination).expanduser().resolve()
        if _overlap(source, destination):
            raise BundleError("bundle destination must be outside the source project")
        if destination.exists():
            raise BundleError(f"bundle destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Serialize generation while taking the snapshot.  The status read also
        # verifies all currently pinned done artifacts before they are exported.
        with self.store.execution_lock(project_id):
            status = self.store.status(project_id)
            WorldStore(self.store).validate(project_id)
            files, directories = self._source_entries(source)
            temporary = Path(tempfile.mkdtemp(
                prefix=f".{destination.name}.tmp-", dir=destination.parent,
            ))
            try:
                payload_root = temporary / "payload" / project_id
                payload_root.mkdir(parents=True)
                for relative in directories:
                    _inside(payload_root, relative).mkdir(parents=True, exist_ok=True)
                manifest_files = []
                for relative in files:
                    source_file = _inside(source, relative)
                    target_file = _inside(payload_root, relative)
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_file, target_file)
                    source_hash = _sha256(source_file)
                    target_hash = _sha256(target_file)
                    if source_hash != target_hash:
                        raise BundleError(f"source changed while exporting: {relative}")
                    manifest_files.append({
                        "path": f"payload/{project_id}/{relative}",
                        "sha256": target_hash,
                        "size": target_file.stat().st_size,
                    })
                manifest = {
                    "schema_version": BUNDLE_SCHEMA_VERSION,
                    "bundle_type": BUNDLE_TYPE,
                    "project_id": project_id,
                    "created_at": utc_now(),
                    "directories": [
                        f"payload/{project_id}/{relative}" for relative in directories
                    ],
                    "files": sorted(manifest_files, key=lambda row: row["path"]),
                }
                manifest_bytes = _json_bytes(manifest)
                (temporary / MANIFEST_NAME).write_bytes(manifest_bytes)
                if destination.exists():
                    raise BundleError(f"bundle destination already exists: {destination}")
                os.replace(temporary, destination)
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        report = self.verify(destination)
        report["status"] = status
        return report

    @staticmethod
    def _source_entries(source: Path) -> tuple[list[str], list[str]]:
        files: list[str] = []
        directories: list[str] = []
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source).as_posix()
            if any(part.startswith(".") for part in PurePosixPath(relative).parts):
                continue
            if path.is_symlink():
                raise BundleError(f"symlinks are not allowed in a replay bundle: {relative}")
            if path.is_dir():
                directories.append(relative)
            elif path.is_file():
                files.append(relative)
        if "project.json" not in files:
            raise BundleError("project.json is required for a replay bundle")
        return files, directories

    @staticmethod
    def verify(bundle_dir: str | Path) -> dict[str, Any]:
        bundle_dir = Path(bundle_dir).expanduser().resolve()
        manifest_path = bundle_dir / MANIFEST_NAME
        try:
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
        except (OSError, json.JSONDecodeError) as exc:
            raise BundleError(f"cannot read bundle manifest: {exc}") from exc
        if not isinstance(manifest, dict):
            raise BundleError("bundle manifest must be a JSON object")
        if (
            manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION
            or manifest.get("bundle_type") != BUNDLE_TYPE
        ):
            raise BundleError("unsupported replay bundle schema or type")
        project_id = manifest.get("project_id")
        try:
            validate_id(project_id, "bundle.project_id")
        except ValueError as exc:
            raise BundleError(str(exc)) from exc
        prefix = f"payload/{project_id}/"
        rows = manifest.get("files")
        directories = manifest.get("directories")
        if not isinstance(rows, list) or not rows:
            raise BundleError("bundle.files must be a non-empty list")
        if not isinstance(directories, list):
            raise BundleError("bundle.directories must be a list")
        listed: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise BundleError("each bundle file entry must be an object")
            relative = _relative(row.get("path"), "bundle file path")
            if not relative.startswith(prefix) or relative in listed:
                raise BundleError(f"invalid or duplicate bundle file path: {relative}")
            listed.add(relative)
            target = _inside(bundle_dir, relative)
            if target.is_symlink() or not target.is_file():
                raise BundleError(f"bundle file is missing: {relative}")
            if not isinstance(row.get("sha256"), str) or _sha256(target) != row["sha256"]:
                raise BundleError(f"bundle file hash differs: {relative}")
            if row.get("size") != target.stat().st_size:
                raise BundleError(f"bundle file size differs: {relative}")
        for value in directories:
            relative = _relative(value, "bundle directory path")
            if not relative.startswith(prefix):
                raise BundleError(f"directory is outside the project payload: {relative}")
            target = _inside(bundle_dir, relative)
            if not target.is_dir():
                raise BundleError(f"bundle directory is missing or not a directory: {relative}")
        payload = bundle_dir / "payload"
        actual = {
            path.relative_to(bundle_dir).as_posix()
            for path in payload.rglob("*") if path.is_file()
        } if payload.is_dir() else set()
        if actual != listed:
            missing = sorted(listed - actual)
            extra = sorted(actual - listed)
            raise BundleError(f"bundle payload file list differs (missing={missing}, extra={extra})")
        try:
            payload_store = ProjectStore(bundle_dir / "payload")
            status = payload_store.status(project_id)
            WorldStore(payload_store).validate(project_id)
        except (ProjectError, OSError, ValueError) as exc:
            raise BundleError(f"bundle project records are invalid: {exc}") from exc
        return {
            "ok": True,
            "bundle_dir": str(bundle_dir),
            "project_id": project_id,
            "file_count": len(listed),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "status": status,
        }

    @staticmethod
    def restore(bundle_dir: str | Path, destination_root: str | Path) -> dict[str, Any]:
        bundle_dir = Path(bundle_dir).expanduser().resolve()
        report = ReplayBundle.verify(bundle_dir)
        project_id = report["project_id"]
        destination_root = Path(destination_root).expanduser().resolve()
        target = destination_root / project_id
        if target.exists():
            raise BundleError(f"restore destination already exists: {target}")
        destination_root.mkdir(parents=True, exist_ok=True)
        temporary_root = Path(tempfile.mkdtemp(
            prefix=f".{project_id}.restore-", dir=destination_root,
        ))
        try:
            temporary_project = temporary_root / project_id
            temporary_project.mkdir()
            manifest = json.loads((bundle_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
            prefix = f"payload/{project_id}/"
            for value in manifest["directories"]:
                relative = value[len(prefix):]
                _inside(temporary_project, relative).mkdir(parents=True, exist_ok=True)
            for row in manifest["files"]:
                relative = row["path"][len(prefix):]
                source = _inside(bundle_dir, row["path"])
                target_file = _inside(temporary_project, relative)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target_file)
                if _sha256(target_file) != row["sha256"]:
                    raise BundleError(f"restored file hash differs: {relative}")
            # Validate the complete restored project before exposing its final ID.
            temporary_store = ProjectStore(temporary_root)
            temporary_store.status(project_id)
            WorldStore(temporary_store).validate(project_id)
            if target.exists():
                raise BundleError(f"restore destination already exists: {target}")
            os.replace(temporary_project, target)
        except Exception:
            shutil.rmtree(temporary_root, ignore_errors=True)
            raise
        shutil.rmtree(temporary_root, ignore_errors=True)
        destination_store = ProjectStore(destination_root)
        status = destination_store.status(project_id)
        WorldStore(destination_store).validate(project_id)
        return {
            "ok": True,
            "restored": True,
            "project_id": project_id,
            "project_dir": str(target),
            "source_bundle": str(bundle_dir),
            "manifest_sha256": report["manifest_sha256"],
            "file_count": report["file_count"],
            "status": status,
        }


def export_bundle(
    store: ProjectStore, project_id: str, destination: str | Path,
) -> dict[str, Any]:
    return ReplayBundle(store).export(project_id, destination)


def verify_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    return ReplayBundle.verify(bundle_dir)


def restore_bundle(bundle_dir: str | Path, destination_root: str | Path) -> dict[str, Any]:
    return ReplayBundle.restore(bundle_dir, destination_root)
