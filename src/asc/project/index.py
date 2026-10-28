"""プロジェクトインデックス。

``<project>/.index.json`` にプロジェクト全体のサマリを保存し、
doctor の全ファイル走査をインデックスベースの差分検査に置き換える
ための基盤となる。

インデックスはノード・リビジョン・チェックポイント・リンクの
作成・更新時に store 側で逐次更新される。doctor はまずインデックスを
読み、最終検査時刻以降に変更のあったノード/リビジョンのみを詳細
検査することで、大規模プロジェクトでの検査コストを抑える。

スキーマ版: asc-project-index-v1
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_SCHEMA = "asc-project-index-v1"
INDEX_FILE_NAME = ".index.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class NodeIndexEntry:
    """1ノードのインデックスエントリ。"""

    id: str
    kind: str
    current_revision_id: str
    revision_count: int
    checkpoint_count: int
    artifact_count: int
    last_updated: str
    stages: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "current_revision_id": self.current_revision_id,
            "revision_count": self.revision_count,
            "checkpoint_count": self.checkpoint_count,
            "artifact_count": self.artifact_count,
            "last_updated": self.last_updated,
            "stages": self.stages,
        }


@dataclass
class RevisionIndexEntry:
    """1リビジョンのインデックスエントリ。"""

    id: str
    node_id: str
    created_at: str
    derived: bool
    artifact_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "created_at": self.created_at,
            "derived": self.derived,
            "artifact_count": self.artifact_count,
        }


@dataclass
class ProjectIndex:
    """プロジェクト全体のインデックス。"""

    schema: str = INDEX_SCHEMA
    project_id: str = ""
    updated_at: str = field(default_factory=utc_now)
    node_count: int = 0
    revision_count: int = 0
    link_count: int = 0
    checkpoint_count: int = 0
    artifact_count: int = 0
    run_count: int = 0
    last_inspected_at: str | None = None
    nodes: dict[str, NodeIndexEntry] = field(default_factory=dict)
    revisions: dict[str, RevisionIndexEntry] = field(default_factory=dict)
    checksums: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "updated_at": self.updated_at,
            "summary": {
                "node_count": self.node_count,
                "revision_count": self.revision_count,
                "link_count": self.link_count,
                "checkpoint_count": self.checkpoint_count,
                "artifact_count": self.artifact_count,
                "run_count": self.run_count,
                "last_inspected_at": self.last_inspected_at,
            },
            "nodes": {nid: e.to_dict() for nid, e in self.nodes.items()},
            "revisions": {rid: e.to_dict() for rid, e in self.revisions.items()},
            "checksums": self.checksums,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectIndex":
        nodes: dict[str, NodeIndexEntry] = {}
        for nid, ndata in (data.get("nodes") or {}).items():
            nodes[nid] = NodeIndexEntry(
                id=ndata.get("id", nid),
                kind=ndata.get("kind", ""),
                current_revision_id=ndata.get("current_revision_id", ""),
                revision_count=int(ndata.get("revision_count", 0) or 0),
                checkpoint_count=int(ndata.get("checkpoint_count", 0) or 0),
                artifact_count=int(ndata.get("artifact_count", 0) or 0),
                last_updated=ndata.get("last_updated", ""),
                stages=ndata.get("stages") or {},
            )
        revisions: dict[str, RevisionIndexEntry] = {}
        for rid, rdata in (data.get("revisions") or {}).items():
            revisions[rid] = RevisionIndexEntry(
                id=rdata.get("id", rid),
                node_id=rdata.get("node_id", ""),
                created_at=rdata.get("created_at", ""),
                derived=bool(rdata.get("derived", False)),
                artifact_count=int(rdata.get("artifact_count", 0) or 0),
            )
        return cls(
            schema=data.get("schema", INDEX_SCHEMA),
            project_id=data.get("project_id", ""),
            updated_at=data.get("updated_at", utc_now()),
            node_count=int(data.get("summary", {}).get("node_count", 0) or 0),
            revision_count=int(data.get("summary", {}).get("revision_count", 0) or 0),
            link_count=int(data.get("summary", {}).get("link_count", 0) or 0),
            checkpoint_count=int(data.get("summary", {}).get("checkpoint_count", 0) or 0),
            artifact_count=int(data.get("summary", {}).get("artifact_count", 0) or 0),
            run_count=int(data.get("summary", {}).get("run_count", 0) or 0),
            last_inspected_at=data.get("summary", {}).get("last_inspected_at"),
            nodes=nodes,
            revisions=revisions,
            checksums=data.get("checksums") or {},
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "ProjectIndex":
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls.from_dict(data)

    def update_checksum(self, relative: str, path: Path) -> None:
        """ファイルのチェックサムを記録する。"""
        try:
            self.checksums[relative] = _sha256_file(path)
        except OSError:
            self.checksums.pop(relative, None)

    def remove_checksum(self, relative: str) -> None:
        self.checksums.pop(relative, None)

    def checksum_changed(self, relative: str, path: Path) -> bool:
        """ファイルがインデックス登録時から変更されているかを返す。"""
        if relative not in self.checksums:
            return True  # 未登録＝変更ありとみなす
        try:
            return self.checksums[relative] != _sha256_file(path)
        except OSError:
            return True

    def needs_inspection(self, max_age_seconds: float = 300.0) -> bool:
        """最後の検査から十分経過していれば再検査が必要。"""
        if self.last_inspected_at is None:
            return True
        try:
            last = datetime.fromisoformat(self.last_inspected_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed > max_age_seconds

    def mark_inspected(self) -> None:
        self.last_inspected_at = utc_now()

    def changed_nodes(self) -> list[str]:
        """チェックサムが変更されたノード関連ファイルからノードIDを推定する。"""
        changed: set[str] = set()
        for relative in self.checksums:
            # nodes/<node_id>/current.json や revisions/... などのパスから
            # ノードIDを抽出（厳密な解析は store 側で行う）
            parts = relative.split("/")
            if len(parts) >= 2 and parts[0] == "nodes":
                changed.add(parts[1])
        return sorted(changed)


__all__ = [
    "INDEX_SCHEMA",
    "INDEX_FILE_NAME",
    "NodeIndexEntry",
    "RevisionIndexEntry",
    "ProjectIndex",
    "utc_now",
    "index_path_for",
]


def index_path_for(project_dir: Path) -> Path:
    return project_dir / INDEX_FILE_NAME
