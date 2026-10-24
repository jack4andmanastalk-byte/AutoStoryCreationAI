"""The run ledger: everything needed to reproduce or reject a result.

A run is a directory ``runs/<run_id>/`` containing the manifest, the inputs, the
model responses and the produced artifacts. Nothing here is committed (``runs/``
is git-ignored); the manifest exists so that an experiment note can point at a
commit and a configuration instead of a memory.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .llm import GenerationRequest, GenerationResult

REPO_ROOT = Path(__file__).resolve().parents[3]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_commit(cwd: Path | None = None) -> str | None:
    """The commit the code ran at. Recorded in every manifest."""
    cwd = cwd or REPO_ROOT
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(cwd),
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def make_run_id(task_id: str, system: str, seed: int) -> str:
    """Timestamp + random suffix: two runs in the same second must not collide.

    The suffix was two bytes, which collides about once in 50 draws at the same
    second (~2% per test run); four bytes makes that negligible.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{task_id}-{system}-s{seed}-{secrets.token_hex(4)}"


@dataclass
class RunLedger:
    root: Path
    run_id: str
    task_id: str
    system: str
    seed: int
    protocol_version: str
    model: str | None = None
    model_version: str | None = None
    temperature: float | None = None
    provider: str | None = None
    changed_paths: list[str] = field(default_factory=list)
    prompt_hashes: dict[str, str] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    status: str = "running"
    error: str | None = None
    usage: dict = field(default_factory=dict)
    repo_root: Path | None = None
    revision_id: str | None = None

    @classmethod
    def create(cls, root: str | Path, *, task_id: str, system: str, seed: int,
               protocol_version: str, run_id: str | None = None,
               model: str | None = None, provider: str | None = None,
               temperature: float | None = None,
               revision_id: str | None = None) -> "RunLedger":
        root = Path(root)
        ledger = cls(
            root=root, run_id=run_id or make_run_id(task_id, system, seed),
            task_id=task_id, system=system, seed=seed,
            protocol_version=protocol_version, model=model, provider=provider,
            temperature=temperature, revision_id=revision_id,
        )
        ledger.path.mkdir(parents=True, exist_ok=False)
        return ledger

    @property
    def path(self) -> Path:
        return self.root / self.run_id

    def request_context(self, **values) -> dict:
        """Add optional revision namespacing without changing legacy request keys."""
        context = dict(values)
        if self.revision_id is not None:
            context["revision_id"] = self.revision_id
        return context

    @property
    def commit(self) -> str | None:
        return git_commit(self.repo_root)

    def write_text(self, relative: str, text: str) -> Path:
        target = (self.path / relative).resolve()
        if not str(target).startswith(str(self.path.resolve())):
            raise ValueError(f"refusing to write outside the run directory: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.changed_paths.append(relative)
        return target

    def track(self, relatives: list[str]) -> None:
        """Record artifacts written outside the ledger, without rewriting them."""
        for relative in relatives:
            if relative not in self.changed_paths:
                self.changed_paths.append(relative)

    def write_json(self, relative: str, payload) -> Path:
        return self.write_text(relative, json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def record(self, request: GenerationRequest, result: GenerationResult) -> None:
        """Append one prompt/response pair to ``responses.jsonl``."""
        self.prompt_hashes[request.purpose] = request.prompt_hash
        entry = {
            "ts": utc_now(),
            "purpose": request.purpose,
            "prompt_hash": request.prompt_hash,
            "prompt": request.prompt,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "seed": request.seed,
            "context": dict(request.context),
            "response_sha256": hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
            "response": result.as_dict(),
        }
        with (self.path / "responses.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        if "responses.jsonl" not in self.changed_paths:
            self.changed_paths.append("responses.jsonl")
        self.model = result.model or self.model
        self.model_version = result.model_version or self.model_version
        self.provider = result.provider or self.provider
        for key, value in (result.usage or {}).items():
            if isinstance(value, (int, float)):
                self.usage[key] = self.usage.get(key, 0) + value

    def fail(self, message: str) -> None:
        self.status = "failed"
        self.error = message
        self.finished_at = utc_now()
        self.write_manifest()

    def finish(self, status: str = "ok") -> None:
        self.status = status
        self.finished_at = utc_now()
        self.write_manifest()

    def _responses_integrity(self) -> tuple[str | None, int]:
        path = self.path / "responses.jsonl"
        if not path.is_file():
            return None, 0
        raw = path.read_bytes()
        count = sum(1 for line in raw.decode("utf-8").splitlines() if line.strip())
        return hashlib.sha256(raw).hexdigest(), count

    def manifest(self) -> dict:
        responses_sha256, response_count = self._responses_integrity()
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "system": self.system,
            "seed": self.seed,
            "model": self.model,
            "model_version": self.model_version,
            "provider": self.provider,
            "temperature": self.temperature,
            "prompt_hashes": dict(sorted(self.prompt_hashes.items())),
            "responses_sha256": responses_sha256,
            "response_count": response_count,
            "git_commit": self.commit,
            "protocol_version": self.protocol_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "error": self.error,
            "usage": dict(sorted(self.usage.items())),
            "artifacts": sorted(set(self.changed_paths)),
        }

    def write_manifest(self) -> Path:
        return self.write_json("manifest.json", self.manifest())
