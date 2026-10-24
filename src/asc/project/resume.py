"""Resume an interrupted project run from its ordered response prefix.

This is deliberately separate from :class:`asc.pipeline.replay.ReplayProvider`.
Strict replay requires a completed ``status=ok`` source and consumes every
recorded response offline.  Resume is selected by the project coordinator for
an unfinished checkpoint.  Its source is normally running/waiting; the
coordinator can explicitly allow an ``ok`` manifest when a process stopped
after the ledger finished but before the checkpoint was marked done.  Resume
verifies each replayed request,
then delegates only the first new request and its successors to the normal
provider.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..pipeline import (
    GenerationRequest,
    GenerationResult,
    Provider,
    ProviderError,
    digest,
    generation_request_key,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ResumeError(ProviderError):
    """The source cannot safely answer the next request for this resume."""


class ResumeProvider:
    """Replay a verified response prefix, then delegate new requests."""

    name = "resume"

    def __init__(
        self,
        source_dir: str | Path,
        delegate: Provider,
        *,
        expected_input: dict[str, Any],
        expected_seed: int,
        expected_temperature: float,
        allow_ok: bool = False,
    ):
        self.source_dir = Path(source_dir)
        self.delegate = delegate
        self.model = delegate.model
        self.model_version = delegate.model_version
        self.manifest_path = self.source_dir / "manifest.json"
        self.input_path = self.source_dir / "project-input.json"
        self.responses_path = self.source_dir / "responses.jsonl"
        try:
            manifest_bytes = self.manifest_path.read_bytes()
            input_bytes = self.input_path.read_bytes()
            responses_bytes = (
                self.responses_path.read_bytes() if self.responses_path.is_file() else b""
            )
        except OSError as exc:
            raise ResumeError(f"cannot read resume source: {exc}") from exc
        self._source_hashes = {
            "manifest": _sha256(manifest_bytes),
            "project_input": _sha256(input_bytes),
            "responses": _sha256(responses_bytes),
        }
        self.source_responses_sha256 = self._source_hashes["responses"]
        try:
            self.source_manifest = json.loads(manifest_bytes)
            self.source_input = json.loads(input_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ResumeError(f"invalid resume source JSON: {exc}") from exc
        if not isinstance(self.source_manifest, dict) or not isinstance(self.source_input, dict):
            raise ResumeError("resume manifest and project-input must be JSON objects")
        source_status = self.source_manifest.get("status")
        allowed_statuses = {"running", "waiting_response"}
        if allow_ok:
            allowed_statuses.add("ok")
        if source_status not in allowed_statuses:
            raise ResumeError(
                "only an interrupted source run can be resumed; "
                f"got {source_status!r}"
            )
        self.source_run_id = str(self.source_manifest.get("run_id") or "")
        if not self.source_run_id:
            raise ResumeError("resume source has no run_id")
        self.source_attempt_id = self.source_input.get("attempt_id")
        for field, expected in expected_input.items():
            if self.source_input.get(field) != expected:
                raise ResumeError(
                    f"resume source {field} does not match the current revision/stage"
                )
        if self.source_manifest.get("seed") != expected_seed:
            raise ResumeError("resume seed differs from the source run")
        if self.source_manifest.get("temperature") != expected_temperature:
            raise ResumeError("resume temperature differs from the source run")

        entries = self._read_entries(responses_bytes)
        embedded_hash = self.source_manifest.get("responses_sha256")
        embedded_count = self.source_manifest.get("response_count")
        if self.source_manifest.get("status") in {"waiting_response", "ok"}:
            if embedded_hash is not None and embedded_hash != self.source_responses_sha256:
                raise ResumeError("source responses differ from the waiting manifest hash")
            if embedded_count is not None and embedded_count != len(entries):
                raise ResumeError("source response count differs from the waiting manifest")
        self._entries = [
            {"index": index, "key": self._entry_key(entry), "entry": entry}
            for index, entry in enumerate(entries)
        ]
        keys = [item["key"] for item in self._entries]
        if len(keys) != len(set(keys)):
            raise ResumeError("resume source contains a duplicate request key")
        self._next = 0
        self._audit: list[dict[str, Any]] = []

    def _read_entries(self, raw: bytes) -> list[dict[str, Any]]:
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ResumeError(f"resume responses are not UTF-8: {exc}") from exc
        entries = []
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ResumeError(
                    f"invalid resume response at line {line_number}: {exc}"
                ) from exc
            if not isinstance(entry, dict) or not isinstance(entry.get("response"), dict):
                raise ResumeError(f"invalid resume response at line {line_number}")
            prompt = entry.get("prompt")
            text = entry["response"].get("text")
            if not isinstance(prompt, str) or not prompt:
                raise ResumeError(f"resume response at line {line_number} has no prompt")
            if not isinstance(text, str) or not text.strip():
                raise ResumeError(f"resume response at line {line_number} has no text")
            if entry.get("prompt_hash") != digest(prompt):
                raise ResumeError(f"resume response at line {line_number} has a bad prompt_hash")
            response_hash = _sha256(text.encode("utf-8"))
            if entry.get("response_sha256") not in {None, response_hash}:
                raise ResumeError(f"resume response at line {line_number} has a bad response hash")
            entries.append(entry)
        return entries

    def _entry_key(self, entry: dict[str, Any]) -> str:
        usage = entry["response"].get("usage") or {}
        if entry.get("request_key") or usage.get("key"):
            return str(entry.get("request_key") or usage.get("key"))
        context = entry.get("context")
        if not isinstance(context, dict):
            raise ResumeError("project resume response has no request context")
        request = GenerationRequest(
            purpose=str(entry.get("purpose") or "generate"),
            prompt=str(entry["prompt"]),
            temperature=float(entry.get("temperature")),
            seed=int(entry.get("seed", 0)),
            context=context,
        )
        return generation_request_key(request)

    @staticmethod
    def _verify_request(entry: dict[str, Any], key: str, request: GenerationRequest) -> None:
        recorded_max_tokens = entry.get("max_tokens")
        checks = {
            "request key": key == generation_request_key(request),
            "prompt hash": entry.get("prompt_hash") == request.prompt_hash,
            "full prompt": entry.get("prompt") == request.prompt,
            "seed": entry.get("seed") == request.seed,
            "temperature": entry.get("temperature") == request.temperature,
            "max_tokens": recorded_max_tokens is None or recorded_max_tokens == request.max_tokens,
        }
        for field, matches in checks.items():
            if not matches:
                raise ResumeError(
                    f"recorded response prefix mismatch: {field} for {key}"
                )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        key = generation_request_key(request)
        if self._next < len(self._entries):
            item = self._entries[self._next]
            entry = item["entry"]
            self._verify_request(entry, item["key"], request)
            source = entry["response"]
            original_provenance = source.get("provenance") or {}
            if not isinstance(original_provenance, dict):
                original_provenance = {}
            provenance = {
                "origin": "resume",
                "source_run_id": self.source_run_id,
                "source_response_index": item["index"],
                "source_request_key": item["key"],
                "source_origin": original_provenance.get("origin", "unspecified"),
            }
            usage = dict(source.get("usage") or {})
            usage["resume_reused"] = 1
            self._next += 1
            self._audit.append({
                "request_key": key,
                "mode": "resume",
                "source_response_index": item["index"],
                "prompt_hash": request.prompt_hash,
            })
            return GenerationResult(
                text=source["text"],
                provider=self.name,
                model=str(source.get("model") or self.model),
                model_version=source.get("model_version", self.model_version),
                usage=usage,
                latency_ms=0,
                provenance=provenance,
            )

        result = self.delegate.generate(request)
        provenance = dict(result.provenance or {})
        provenance.update({
            "resume_source_run_id": self.source_run_id,
            "resume_delegate": self.delegate.name,
        })
        usage = dict(result.usage or {})
        usage["resume_delegate"] = 1
        self._next += 1
        self._audit.append({
            "request_key": key,
            "mode": "delegate",
            "source_response_index": None,
            "prompt_hash": request.prompt_hash,
            "origin": provenance.get("origin", "unspecified"),
        })
        return GenerationResult(
            text=result.text,
            provider=result.provider,
            model=result.model,
            model_version=result.model_version,
            usage=usage,
            latency_ms=result.latency_ms,
            provenance=provenance,
        )

    def finalize(self) -> dict[str, Any]:
        """Verify full prefix consumption and source immutability."""
        try:
            current = {
                "manifest": _sha256(self.manifest_path.read_bytes()),
                "project_input": _sha256(self.input_path.read_bytes()),
                "responses": _sha256(
                    self.responses_path.read_bytes() if self.responses_path.is_file() else b""
                ),
            }
        except OSError as exc:
            raise ResumeError(f"cannot recheck resume source: {exc}") from exc
        if current != self._source_hashes:
            raise ResumeError("resume source changed during the attempt")
        unconsumed = len(self._entries) - min(self._next, len(self._entries))
        if unconsumed:
            raise ResumeError(f"resume finished with {unconsumed} unconsumed source responses")
        reused = sum(row["mode"] == "resume" for row in self._audit)
        delegated = sum(row["mode"] == "delegate" for row in self._audit)
        return {
            "schema": "project-resume-audit-v1",
            "source_run_id": self.source_run_id,
            "source_attempt_id": self.source_attempt_id,
            "source_sha256": self._source_hashes,
            "source_unchanged": True,
            "all_source_responses_consumed": True,
            "reused_responses": reused,
            "delegated_responses": delegated,
            "requests": self._audit,
            "scope": "interrupted-run continuation; not strict offline replay or model reproducibility",
        }
