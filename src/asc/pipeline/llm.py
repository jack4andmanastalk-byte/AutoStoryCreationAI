"""Model access for the generation pipeline.

The repository never holds an API key. A provider is either an external command
(JSON on stdin, JSON on stdout) or a scripted response set used by tests and by
the offline demo. Everything a run needs in order to be reproducible — model,
version, temperature, seed, prompt hash — travels with the result and ends up in
the run manifest.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class ProviderError(RuntimeError):
    """Raised when a provider cannot return usable text."""


def digest(text: str) -> str:
    """Short, stable hash used for prompt and response identity."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class GenerationRequest:
    purpose: str
    prompt: str
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    seed: int = 0
    context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return digest(self.prompt)

    def as_dict(self) -> dict:
        return {
            "purpose": self.purpose,
            "prompt": self.prompt,
            "system": self.system,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
            "context": dict(self.context),
            "prompt_hash": self.prompt_hash,
        }


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    model_version: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "usage": dict(self.usage),
            "latency_ms": self.latency_ms,
        }


class Provider(Protocol):
    name: str
    model: str
    model_version: str | None

    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class CommandProvider:
    """Calls an external program.

    The program receives one JSON object on stdin (see ``GenerationRequest``)
    and must print one JSON object with at least ``{"text": "..."}``. Anything
    else is a protocol violation, so that a half-broken adapter fails loudly
    instead of silently producing an empty chapter.
    """

    name = "command"

    def __init__(self, command: str, model: str = "external",
                 model_version: str | None = None, timeout: float = 300.0):
        self.command = command
        self.model = model
        self.model_version = model_version
        self.timeout = timeout

    def generate(self, request: GenerationRequest) -> GenerationResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                shlex.split(self.command),
                input=json.dumps(request.as_dict(), ensure_ascii=False),
                capture_output=True, text=True, timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise ProviderError(f"command not found: {self.command}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(
                f"provider timed out after {self.timeout:.0f}s: {self.command}") from exc

        latency = int((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip().splitlines()[-1:] or ["no stderr"]
            raise ProviderError(
                f"provider exited {completed.returncode}: {detail[0]}")

        stdout = completed.stdout.strip()
        if not stdout:
            raise ProviderError("provider returned no stdout")

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "provider did not return JSON on stdout (log to stderr instead)"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise ProviderError('provider JSON must contain a string field "text"')
        text = payload["text"].strip()
        if not text:
            raise ProviderError("provider returned empty text")

        return GenerationResult(
            text=text,
            provider=self.name,
            model=str(payload.get("model", self.model)),
            model_version=payload.get("model_version", self.model_version),
            usage=payload.get("usage", {}) or {},
            latency_ms=payload.get("latency_ms", latency),
        )


class ScriptedProvider:
    """Returns pre-written text. For tests and the offline demo only.

    Lookup order: ``"<purpose>:<system>:<task_id>"``, ``"<purpose>:<task_id>"``,
    then ``purpose``. A missing key is an error rather than an empty string, so a
    broken demo cannot look like a successful generation.
    """

    name = "scripted"

    def __init__(self, responses: Mapping[str, str], model: str = "scripted-fixture",
                 model_version: str = "v1"):
        self.responses = dict(responses)
        self.model = model
        self.model_version = model_version
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        task_id = str(request.context.get("task_id", ""))
        system = str(request.context.get("system", ""))
        keys = [
            f"{request.purpose}:{system}:{task_id}",
            f"{request.purpose}:{task_id}",
            request.purpose,
        ]
        for key in keys:
            if key in self.responses:
                return GenerationResult(
                    text=self.responses[key], provider=self.name,
                    model=self.model, model_version=self.model_version,
                    usage={"scripted": True}, latency_ms=0,
                )
        raise ProviderError(
            f"no scripted response for purpose={request.purpose!r} task={task_id!r}")


def load_scripted_responses(path: str | "Any") -> dict[str, str]:
    """Read a scripted-response file.

    The file is ``{"responses": {"plan:t01": "...", ...}}``. It is a fixture,
    not a recording of a real model: the ``_note`` field says so and is ignored.
    """
    from pathlib import Path

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    responses = data.get("responses")
    if not isinstance(responses, dict) or not all(
            isinstance(v, str) for v in responses.values()):
        raise ProviderError(f"{path}: expected {{'responses': {{key: text}}}}")
    return dict(responses)
