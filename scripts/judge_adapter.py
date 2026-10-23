#!/usr/bin/env python3
"""Reference adapter: turn the harness judge protocol into a model call.

The evaluation harness talks to judges over stdin/stdout JSON (see
``skills/evaluation-harness/references/measurement.md``). This script is the
missing half: it builds a prompt from that request, calls whatever LLM command
you have, and parses the answer back into the protocol.

    # inspect the prompt without calling anything
    python3 scripts/judge_adapter.py --dry-run < request.json

    # use any CLI that reads stdin and writes stdout
    python3 scripts/judge_adapter.py --llm-command "my-model --json"

    # then, from the harness
    python3 scripts/run_evaluation.py ... --judge-command "python3 scripts/judge_adapter.py --llm-command 'my-model'"

The adapter is deliberately strict: a verdict without a usable evidence entry is
passed through with empty evidence so the harness can mark it ``unevidenced``
instead of silently trusting it.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SCORE_INSTRUCTION = """\
あなたは日本語の短編小説を評価する評定者です。次のルーブリックの各次元を 1〜5 で採点し、
必ず根拠を付けてください。

# ルーブリック
{rubric}

# 作品
{story}

# 出力形式（JSON のみ。前後に説明を書かない）
{{"dimensions": [{{"dimension": "<次元ID>", "score": <1-5>,
  "evidence": [{{"path": "<章ファイル名>", "line": <行番号>, "quote": "<本文の引用>"}}],
  "rationale_ja": "<なぜその点か。1〜2文>"}}]}}

規則:
- すべての次元を、指定された ID で過不足なく返す。
- 根拠は作品から引用する。引用できない次元は、点を付けずに rationale_ja にその旨を書く。
- 総合点は出さない。次元ごとの点だけを返す。
"""

PAIRWISE_INSTRUCTION = """\
あなたは日本語の短編小説を比較する評定者です。二つの作品 A と B のどちらが良いかを選んでください。

# 評価の観点
{rubric}

# 作品 A
{a}

# 作品 B
{b}

# 出力形式（JSON のみ）
{{"winner": "a" | "b" | "tie", "rationale_ja": "<理由。1〜2文>"}}

規則:
- 長さ・文字数の多さを理由にしない。内容と語りの質で選ぶ。
- 差が小さい場合は "tie" を選ぶ。
"""


def rubric_text(payload: dict) -> str:
    rubric = payload.get("rubric") or {}
    lines = [f"- {dim.get('id')}: {dim.get('question_ja') or dim.get('question') or ''}"
             for dim in rubric.get("dimensions", [])]
    return "\n".join(lines) or "（ルーブリック未指定）"


def build_prompt(request: dict) -> str:
    if request.get("mode") == "pairwise":
        return PAIRWISE_INSTRUCTION.format(
            rubric=rubric_text(request), a=request.get("a", ""), b=request.get("b", ""))
    dimensions = [dim.get("id") for dim in request.get("rubric", {}).get("dimensions", [])]
    return SCORE_INSTRUCTION.format(
        rubric=rubric_text(request), story=request.get("story", "")
    ) + (f"\n次元: {', '.join(dimensions)}\n" if dimensions else "")


def extract_json(text: str) -> dict:
    """Find the first JSON object in a model response (it often adds prose)."""
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
    stripped = re.sub(r"\n```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    depth = 0
    start = None
    for index, char in enumerate(stripped):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = stripped[start:index + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = None
    raise ValueError("no JSON object in the model response")


def call_llm(command: str, prompt: str, timeout: float) -> str:
    completed = subprocess.run(
        shlex.split(command), input=prompt, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()[-1:]
        raise RuntimeError(f"llm command exited {completed.returncode}: {detail or 'no stderr'}")
    return completed.stdout


def respond(request: dict, answer: str) -> dict:
    payload = extract_json(answer)
    if request.get("mode") == "pairwise":
        winner = str(payload.get("winner", "")).lower()
        if winner not in {"a", "b", "tie"}:
            raise ValueError(f"invalid winner: {winner!r}")
        return {"winner": winner,
                "rationale_ja": str(payload.get("rationale_ja", ""))[:400]}
    dimensions = []
    for item in payload.get("dimensions", []):
        dimensions.append({
            "dimension": item.get("dimension"),
            "score": item.get("score"),
            "evidence": [
                {"path": str(e.get("path", "")), "line": e.get("line"),
                 "quote": str(e.get("quote", ""))[:200]}
                for e in (item.get("evidence") or []) if isinstance(e, dict)
            ],
            "rationale_ja": str(item.get("rationale_ja", ""))[:400],
        })
    return {"dimensions": dimensions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm-command", help="command that reads a prompt on stdin")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--dry-run", action="store_true", help="print the prompt, call nothing")
    parser.add_argument("--prompt-out", help="write the prompt to this file as well")
    args = parser.parse_args(argv)

    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError:
        print("adapter error: stdin must be one JSON object", file=sys.stderr)
        return 2

    prompt = build_prompt(request)
    if args.prompt_out:
        Path(args.prompt_out).write_text(prompt, encoding="utf-8")
    if args.dry_run:
        print(prompt)
        return 0
    if not args.llm_command:
        print("adapter error: --llm-command is required unless --dry-run", file=sys.stderr)
        return 2

    try:
        answer = call_llm(args.llm_command, prompt, args.timeout)
        result = respond(request, answer)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"adapter error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
