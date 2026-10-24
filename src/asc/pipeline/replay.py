"""Strict, offline replay of a completed run's recorded responses.

Replay is a pipeline audit, not fresh model generation and not evidence that an
unversioned model reproduces itself. Every request must have the same operator
key, full prompt, prompt hash, seed and temperature. The source manifest and
JSONL log are hashed before and after the run, and final artifacts are compared
byte-for-byte (apart from the run-local canon path in ``audit.json``).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .llm import GenerationRequest, GenerationResult, ProviderError, digest
from .run import RunLedger, git_commit

_TOP_LEVEL_ARTIFACTS = (
    "brief.md", "plan.json", "design.json", "draft.json", "revision.json",
    "voice.json", "audit.json",
)
_ARTIFACT_DIRS = ("canon", "design", "draft", "text")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _key(system: str, task_id: str, seed: int, purpose: str, attempt: int) -> str:
    raw = "-".join((system, task_id, f"s{seed}", purpose, f"a{attempt}"))
    return re.sub(r"[^0-9A-Za-z._-]+", "-", raw)


def generation_request_key(request: GenerationRequest) -> str:
    """Return the same readable key used by ``scripts/chat_operator.py``."""
    context = request.context or {}
    return _key(
        str(context.get("system") or "none"),
        str(context.get("task_id") or "task"),
        int(request.seed),
        str(request.purpose or "generate"),
        int(context.get("attempt", 1)),
    )


class ReplayError(ProviderError):
    """The recorded run cannot answer the current request exactly."""


class ReplayProvider:
    """Serve responses from one run directory without calling another provider.

    Optional manifest/log pins let a caller protect older runs whose manifests
    predate the embedded ``responses_sha256`` field. New runs carry that pin in
    the manifest itself. All source data is loaded into memory up front; later
    source-file changes cannot silently alter the answers being replayed.
    """

    name = "replay"

    def __init__(self, source_dir: str | Path, *,
                 expected_manifest_sha256: str | None = None,
                 expected_responses_sha256: str | None = None):
        self.source_dir = Path(source_dir)
        self.manifest_path = self.source_dir / "manifest.json"
        self.responses_path = self.source_dir / "responses.jsonl"
        try:
            manifest_bytes = self.manifest_path.read_bytes()
            responses_bytes = self.responses_path.read_bytes()
        except OSError as exc:
            raise ReplayError(f"cannot read replay source: {exc}") from exc

        self.source_manifest_sha256 = _sha256_bytes(manifest_bytes)
        self.source_responses_sha256 = _sha256_bytes(responses_bytes)
        if (expected_manifest_sha256 and
                expected_manifest_sha256 != self.source_manifest_sha256):
            raise ReplayError(
                "source manifest SHA-256 does not match --replay-manifest-sha256")
        if (expected_responses_sha256 and
                expected_responses_sha256 != self.source_responses_sha256):
            raise ReplayError(
                "source responses SHA-256 does not match --replay-responses-sha256")
        self.manifest_pin_provided = bool(expected_manifest_sha256)
        self.responses_pin_provided = bool(expected_responses_sha256)

        try:
            self.source_manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            raise ReplayError(f"invalid source manifest: {exc}") from exc
        if not isinstance(self.source_manifest, dict):
            raise ReplayError("source manifest must be a JSON object")
        if self.source_manifest.get("status") != "ok":
            raise ReplayError("only a source run with status=ok can be replayed")
        self.source_run_id = str(self.source_manifest.get("run_id") or "")
        if not self.source_run_id:
            raise ReplayError("source manifest has no run_id")

        embedded_pin = self.source_manifest.get("responses_sha256")
        if embedded_pin and embedded_pin != self.source_responses_sha256:
            raise ReplayError(
                "source responses.jsonl differs from the manifest responses_sha256")
        embedded_count = self.source_manifest.get("response_count")

        entries = []
        for line_number, line in enumerate(responses_bytes.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReplayError(
                    f"invalid source response at line {line_number}: {exc}") from exc
            if not isinstance(entry, dict) or not isinstance(entry.get("response"), dict):
                raise ReplayError(f"invalid source response at line {line_number}")
            entries.append(entry)
        if embedded_count is not None and embedded_count != len(entries):
            raise ReplayError("source response count differs from the manifest")
        if not entries:
            raise ReplayError("source run has no recorded responses")

        self.source_log_pinned_by_manifest = bool(embedded_pin)
        self._entries: dict[str, dict[str, Any]] = {}
        occurrences: dict[tuple[str, int], int] = {}
        for index, entry in enumerate(entries):
            key = self._source_key(entry, occurrences)
            if key in self._entries:
                raise ReplayError(f"duplicate source request key: {key}")
            prompt = entry.get("prompt")
            response = entry["response"]
            text = response.get("text")
            if not isinstance(prompt, str) or not prompt:
                raise ReplayError(f"source request {key} has no prompt")
            if not isinstance(text, str) or not text.strip():
                raise ReplayError(f"source response {key} has no text")
            recorded_prompt_hash = entry.get("prompt_hash")
            if recorded_prompt_hash != digest(prompt):
                raise ReplayError(f"source request {key} has an invalid prompt_hash")
            response_sha256 = _sha256_text(text)
            recorded_response_hash = entry.get("response_sha256")
            if (recorded_response_hash and
                    recorded_response_hash != response_sha256):
                raise ReplayError(f"source response {key} has an invalid response_sha256")
            self._entries[key] = {
                "index": index,
                "key": key,
                "entry": entry,
                "response_sha256": response_sha256,
            }

        first_response = entries[0]["response"]
        self.model = str(self.source_manifest.get("model") or
                         first_response.get("model") or "recorded-model")
        self.model_version = (self.source_manifest.get("model_version") or
                              first_response.get("model_version"))
        self._used: set[str] = set()
        self._request_audit: list[dict] = []

    def _source_key(self, entry: dict, occurrences: dict[tuple[str, int], int]) -> str:
        purpose = str(entry.get("purpose") or "generate")
        seed = int(entry.get("seed", 0))
        context = entry.get("context") or {}
        if context:
            system = str(context.get("system") or self.source_manifest.get("system") or "none")
            task_id = str(context.get("task_id") or self.source_manifest.get("task_id") or "task")
            attempt = int(context.get("attempt", 1))
        else:
            # Older ledgers omitted context. Attempt is recoverable from the
            # ordered JSONL: repairs are attempt 2; other retries repeat a
            # purpose at the same seed. Revision rounds use distinct seeds.
            group = (purpose, seed)
            occurrences[group] = occurrences.get(group, 0) + 1
            attempt = occurrences[group]
            if purpose == "plan-repair" or purpose.endswith(":repair"):
                attempt += 1
            system = str(self.source_manifest.get("system") or "none")
            task_id = str(self.source_manifest.get("task_id") or "task")
        computed = _key(system, task_id, seed, purpose, attempt)
        usage = (entry.get("response") or {}).get("usage") or {}
        return str(entry.get("request_key") or usage.get("key") or computed)

    def source_summary(self) -> dict:
        return {
            "run_id": self.source_run_id,
            "run_dir": str(self.source_dir),
            "git_commit": self.source_manifest.get("git_commit"),
            "model": self.model,
            "model_version": self.model_version,
            "manifest_sha256": self.source_manifest_sha256,
            "responses_sha256": self.source_responses_sha256,
            "response_count": len(self._entries),
            "responses_pinned_by_source_manifest": self.source_log_pinned_by_manifest,
            "manifest_pin_provided": self.manifest_pin_provided,
            "responses_pin_provided": self.responses_pin_provided,
        }

    def generate(self, request: GenerationRequest) -> GenerationResult:
        key = generation_request_key(request)
        item = self._entries.get(key)
        if item is None:
            raise ReplayError(f"no recorded response for replay request key: {key}")
        if key in self._used:
            raise ReplayError(f"recorded response was already consumed: {key}")
        entry = item["entry"]
        if entry.get("prompt_hash") != request.prompt_hash:
            raise ReplayError(
                f"prompt hash mismatch for {key}: source={entry.get('prompt_hash')} "
                f"replay={request.prompt_hash}")
        if entry.get("prompt") != request.prompt:
            raise ReplayError(f"full prompt mismatch for {key}")
        if int(entry.get("seed", 0)) != request.seed:
            raise ReplayError(f"seed mismatch for {key}")
        if entry.get("temperature") != request.temperature:
            raise ReplayError(f"temperature mismatch for {key}")

        source_response = entry["response"]
        original_provenance = source_response.get("provenance") or {}
        if not isinstance(original_provenance, dict):
            original_provenance = {}
        provenance = {
            "origin": "replay",
            "source_run_id": self.source_run_id,
            "source_request_key": key,
            "source_response_index": item["index"],
            "source_prompt_hash": entry["prompt_hash"],
            "source_prompt_sha256": _sha256_text(request.prompt),
            "source_response_sha256": item["response_sha256"],
            "source_origin": original_provenance.get("origin", "unspecified"),
        }
        self._used.add(key)
        self._request_audit.append({
            "request_key": key,
            "source_response_index": item["index"],
            "purpose": request.purpose,
            "prompt_hash": request.prompt_hash,
            "prompt_sha256": provenance["source_prompt_sha256"],
            "response_sha256": item["response_sha256"],
            "source_origin": provenance["source_origin"],
            "full_prompt_match": True,
            "seed_match": True,
            "temperature_match": True,
        })
        return GenerationResult(
            text=source_response["text"], provider=self.name,
            model=str(source_response.get("model") or self.model),
            model_version=source_response.get("model_version", self.model_version),
            usage={"replay": 1}, latency_ms=0, provenance=provenance,
        )

    def finalize(self, ledger: RunLedger) -> dict:
        """Verify consumption, source immutability, prompts and final artifacts."""
        manifest_now = _file_sha256(self.manifest_path)
        responses_now = _file_sha256(self.responses_path)
        source_unchanged = (
            manifest_now == self.source_manifest_sha256 and
            responses_now == self.source_responses_sha256
        )
        unconsumed = sorted(set(self._entries) - self._used)
        prompt_hashes_match = (
            dict(sorted((self.source_manifest.get("prompt_hashes") or {}).items())) ==
            dict(sorted(ledger.prompt_hashes.items()))
        )
        artifacts = self._compare_artifacts(ledger.path)
        artifacts_match = bool(artifacts) and all(row["match"] for row in artifacts)
        ok = (source_unchanged and not unconsumed and prompt_hashes_match and
              artifacts_match)
        summary = {
            "ok": ok,
            "source_run_id": self.source_run_id,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_responses_sha256": self.source_responses_sha256,
            "source_unchanged": source_unchanged,
            "all_source_responses_consumed": not unconsumed,
            "manifest_prompt_hashes_match": prompt_hashes_match,
            "artifacts_match": artifacts_match,
            "matched_artifacts": sum(1 for row in artifacts if row["match"]),
            "compared_artifacts": len(artifacts),
            "replayed_responses": len(self._used),
        }
        return {
            "schema": "replay-audit-v1",
            "scope": "offline recorded-response replay; not fresh generation or G5 model reproducibility",
            "source": self.source_summary(),
            "replay": {"run_id": ledger.run_id, "git_commit": git_commit()},
            "verification": {
                "source_manifest_sha256_now": manifest_now,
                "source_responses_sha256_now": responses_now,
                "source_unchanged": source_unchanged,
                "unconsumed_request_keys": unconsumed,
                "manifest_prompt_hashes_match": prompt_hashes_match,
                "artifacts_match": artifacts_match,
            },
            "requests": self._request_audit,
            "artifacts": artifacts,
            "summary": summary,
        }

    def _compare_artifacts(self, replay_dir: Path) -> list[dict]:
        relatives = {name for name in _TOP_LEVEL_ARTIFACTS
                     if (self.source_dir / name).is_file() or (replay_dir / name).is_file()}
        for directory in _ARTIFACT_DIRS:
            for root in (self.source_dir, replay_dir):
                base = root / directory
                if base.is_dir():
                    relatives.update(str(path.relative_to(root)) for path in base.rglob("*")
                                     if path.is_file())
        rows = []
        for relative in sorted(relatives):
            source_path = self.source_dir / relative
            replay_path = replay_dir / relative
            comparison = ("json_without_run_paths_or_timestamp"
                          if relative == "audit.json" else "bytes")
            if not source_path.is_file() or not replay_path.is_file():
                rows.append({"path": relative, "comparison": comparison,
                             "source_sha256": None, "replay_sha256": None,
                             "match": False})
                continue
            if relative == "audit.json":
                source_data = json.loads(source_path.read_text(encoding="utf-8"))
                replay_data = json.loads(replay_path.read_text(encoding="utf-8"))
                for data in (source_data, replay_data):
                    data["canon"] = "<run-local>"
                    data["generated_at"] = "<timestamp>"
                    if isinstance(data.get("ledger"), dict):
                        data["ledger"]["canon"] = "<run-local>"
                source_hash = _sha256_text(json.dumps(
                    source_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                replay_hash = _sha256_text(json.dumps(
                    replay_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            else:
                source_hash = _file_sha256(source_path)
                replay_hash = _file_sha256(replay_path)
            rows.append({"path": relative, "comparison": comparison,
                         "source_sha256": source_hash, "replay_sha256": replay_hash,
                         "match": source_hash == replay_hash})
        return rows
