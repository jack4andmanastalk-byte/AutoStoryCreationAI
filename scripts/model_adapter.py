#!/usr/bin/env python3
"""Reference provider: turn a GenerationRequest into one chat-completions call.

The pipeline talks to models over stdin/stdout JSON (see
``src/asc/pipeline/llm.py``). ``chat_operator.py`` fills that contract with a
person; this script fills it with a **pinned** model, which is what protocol §5
(G5, reproducibility) and §3 (same model and version across systems) require.

    # show the body that would be sent, without a key or a network call
    python3 scripts/model_adapter.py --model gpt-4.1 --dry-run < request.json

    # one real call
    OPENAI_API_KEY=... python3 scripts/model_adapter.py \\
        --model gpt-4.1 --model-version 2025-04-14 < request.json

    # as the pipeline sees it
    python3 scripts/run_pipeline.py --task t01 --provider command \\
        --command "python3 scripts/model_adapter.py --model gpt-4.1" \\
        --model gpt-4.1 --model-version 2025-04-14

Server contract: any endpoint that speaks OpenAI-style
``POST {base-url}/chat/completions`` — including local gateways — works; point
``--base-url`` at it. The key is read from the environment and never printed:
the adapter's stdout is the response body only, and its stderr is the error
type plus status, not the request.

Exit codes: 0 ok, 1 provider/HTTP error, 2 usage or configuration error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_KEY_ENV = "OPENAI_API_KEY"
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class ConfigError(RuntimeError):
    """Raised when the adapter cannot be configured; exits 2."""


class ProviderError(RuntimeError):
    """Raised when the endpoint refuses or breaks; exits 1."""


def build_body(request: dict, args: argparse.Namespace) -> dict:
    prompt = request.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError("the request has no prompt")
    messages = []
    system = request.get("system")
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body: dict = {"model": args.model, "messages": messages}
    temperature = request.get("temperature")
    if temperature is not None:
        body["temperature"] = float(temperature)
    max_tokens = request.get("max_tokens")
    if max_tokens:
        body[args.max_tokens_param] = int(max_tokens)
    if not args.no_seed:
        body["seed"] = int(request.get("seed") or 0)
    if args.json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


def post(url: str, body: dict, api_key: str, timeout: float) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"the endpoint returned non-JSON ({exc.msg})") from exc


def call(url: str, body: dict, api_key: str, timeout: float,
         retries: int, retry_delay: float) -> dict:
    attempt = 0
    while True:
        attempt += 1
        try:
            return post(url, body, api_key, timeout)
        except urllib.error.HTTPError as exc:
            detail = (exc.read().decode("utf-8", "replace") or "").strip()
            message = f"HTTP {exc.code} from the endpoint"
            if detail:
                message += f": {detail[:200]}"
            if exc.code in RETRY_STATUS and attempt <= retries:
                time.sleep(retry_delay * attempt)
                continue
            raise ProviderError(message) from exc
        except urllib.error.URLError as exc:
            if attempt <= retries:
                time.sleep(retry_delay * attempt)
                continue
            raise ProviderError(f"cannot reach the endpoint: {exc.reason}") from exc
        except TimeoutError as exc:
            if attempt <= retries:
                time.sleep(retry_delay * attempt)
                continue
            raise ProviderError(f"the endpoint timed out after {timeout:.0f}s") from exc


def extract(payload: dict, model: str, model_version: str | None) -> dict:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("the response has no 'choices'")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    text = message.get("content") if isinstance(message, dict) else None
    if isinstance(text, list):  # some gateways split the content into parts
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    if not isinstance(text, str) or not text.strip():
        finish = choices[0].get("finish_reason") if isinstance(choices[0], dict) else None
        raise ProviderError(f"the response has no text (finish_reason={finish!r})")
    usage = payload.get("usage") or {}
    return {
        "text": text.strip(),
        "model": model,
        "model_version": model_version or payload.get("model"),
        "usage": {key: usage[key] for key in
                  ("prompt_tokens", "completion_tokens", "total_tokens")
                  if key in usage},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="model name to request and record")
    parser.add_argument("--model-version", default=None,
                        help="pinned version (default: the endpoint's 'model' field)")
    parser.add_argument("--base-url", default=os.environ.get("MODEL_BASE_URL", DEFAULT_BASE_URL),
                        help=f"OpenAI-compatible base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV,
                        help=f"environment variable holding the key (default: {DEFAULT_KEY_ENV})")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=5.0,
                        help="seconds; multiplied by the attempt number")
    parser.add_argument("--max-tokens-param", default="max_tokens",
                        choices=["max_tokens", "max_completion_tokens"])
    parser.add_argument("--no-seed", action="store_true",
                        help="omit 'seed' for endpoints that reject it")
    parser.add_argument("--json-mode", action="store_true",
                        help="send response_format=json_object (the plan step asks for JSON)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the request body and exit; needs no key")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        request = json.loads(sys.stdin.read() or "{}")
        if not isinstance(request, dict):
            raise ConfigError("the request must be a JSON object")
        body = build_body(request, args)
    except (ConfigError, json.JSONDecodeError) as exc:
        print(f"model-adapter: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"model-adapter: {args.api_key_env} is not set", file=sys.stderr)
        return 2

    url = args.base_url.rstrip("/") + "/chat/completions"
    try:
        payload = call(url, body, api_key, args.timeout,
                       args.max_retries, args.retry_delay)
        result = extract(payload, args.model, args.model_version)
    except ProviderError as exc:
        print(f"model-adapter: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
