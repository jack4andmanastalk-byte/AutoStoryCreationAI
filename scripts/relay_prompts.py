#!/usr/bin/env python3
"""Move prompts to a chat and answers back, without losing which is which.

``chat_operator.py`` already stores every request on disk and refuses to answer
twice for a changed prompt. What was still manual was the handoff: copy the
prompt, paste it somewhere, paste the answer back, and remember which file it
belongs to. This script is that handoff, with opaque tags so the person (or the
chat) never has to see a run key.

    # 1. run the pipeline: it stops at the first missing answer per cell
    python3 scripts/run_experiment.py --provider command \\
        --command "python3 scripts/chat_operator.py --dir build/operator/chat2" ...

    # 2. write the prompts, one block per pending request
    python3 scripts/relay_prompts.py export --dir build/operator/chat2

    # 3. paste <outbox>/PROMPTS.md into a chat, paste the answers back into a file
    python3 scripts/relay_prompts.py ingest --dir build/operator/chat2 --file answers.txt

    # 4. run the pipeline again; repeat until nothing is pending

The tag is derived from the request key, so the same request keeps the same tag
across exports. ``ingest`` pins each answer to the prompt hash it answers, so the
provider's stale check still protects the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ANSWER = re.compile(r"<<<ANSWER\s+([0-9A-Za-z]{4})>>>\s*\n?(.*?)\n?\s*<<<END\s+\1>>>", re.S)
ERROR = re.compile(r"<<<ERROR\s+([0-9A-Za-z]{4})>>>\s*\n?(.*?)\n?\s*<<<END\s+\1>>>", re.S)

PREAMBLE = """\
あなたは生成ハーネスの「モデル役」です。次の規則だけを守ってください。

1. 各リクエストは独立しています。前のリクエストの内容を持ち越さないでください。
2. 指示された成果物だけを返してください。前置き・後書き・解説・見出し・コードフェンスを
   書かないでください。
3. 回答は必ず次の形で囲んでください（タグはリクエストごとに違います）。

<<<ANSWER タグ>>>
（成果物）
<<<END タグ>>>

4. 日本語で書いてください。文字数の指定がある場合はそれに従ってください。
5. 指示に従えない場合は、成果物の代わりに次を返してください。

<<<ERROR タグ>>>
（従えない理由を 1 行）
<<<END タグ>>>

6. 質問を返さないでください。判断が必要な点は、作品として自然なほうを選んでください。
"""


def tag_for(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:4].upper()


def load_request(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def all_requests(directory: Path) -> list[dict]:
    items = []
    for path in sorted((directory / "requests").glob("*.json")):
        data = load_request(path)
        items.append({"key": path.stem, "tag": tag_for(path.stem),
                      "prompt": data["prompt"], "prompt_hash": data["prompt_hash"],
                      "purpose": data.get("purpose")})
    return items


def pending(directory: Path) -> list[dict]:
    responses = directory / "responses"
    return [item for item in all_requests(directory)
            if not (responses / f"{item['key']}.json").is_file()]


def render_prompt_markdown(items: list[dict], total: int, done: int) -> str:
    lines = [
        "# 生成リクエスト（貼り付け用）",
        "",
        "上から順に、1 リクエストずつチャットへ送ってください。",
        "**この節より上は送らないでください。**各リクエストの見出しも送る必要はありません。",
        "",
        f"- 残り {total} 件 / 回答済み {done} 件",
        "",
        "## 最初に一度だけ送る文章（プリアンブル）",
        "",
        "```text",
        PREAMBLE.rstrip(),
        "```",
        "",
        "---",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines += [
            f"## リクエスト {index}/{total}（タグ `{item['tag']}`）",
            "",
            "```text",
            item["prompt"].rstrip(),
            "```",
            "",
            f"タグは必ずこの 4 文字 **`{item['tag']}`** を使ってください"
            "（`ch01` やファイル名を使わないでください）。",
            "",
            "回答はこの形で返ってきます（そのまま貼り返してください）。",
            "",
            "```text",
            f"<<<ANSWER {item['tag']}>>>",
            "…本文…",
            f"<<<END {item['tag']}>>>",
            "```",
            "",
        ]
    return "\n".join(lines)


def export(directory: Path, out: Path | None = None) -> dict:
    items = pending(directory)
    responses = directory / "responses"
    done = len(list(responses.glob("*.json"))) if responses.is_dir() else 0
    out = out or directory / "relay"
    (out / "outbox").mkdir(parents=True, exist_ok=True)
    for stale in (out / "outbox").glob("request-*.md"):
        stale.unlink()
    for index, item in enumerate(items, start=1):
        (out / "outbox" / f"request-{index:02d}-{item['tag']}.md").write_text(
            f"# リクエスト {index}/{len(items)}（タグ `{item['tag']}`）\n\n"
            f"```text\n{item['prompt'].rstrip()}\n```\n", encoding="utf-8")
    (out / "PROMPTS.md").write_text(
        render_prompt_markdown(items, len(items), done), encoding="utf-8")
    (out / "index.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pending": [{"tag": item["tag"], "key": item["key"],
                     "purpose": item["purpose"],
                     "prompt_hash": item["prompt_hash"]} for item in items],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pending": len(items), "done": done, "out": str(out)}


def ingest(directory: Path, text: str, *, model: str, model_version: str,
           tag_map: dict[str, str] | None = None) -> dict:
    # An answer is accepted for any known request, even one already answered:
    # re-ingesting is how a bad paste gets corrected.
    by_tag = {item["tag"]: item for item in all_requests(directory)}

    errors: list[dict] = []
    for match in ERROR.finditer(text):
        errors.append({"tag": match.group(1), "reason": match.group(2).strip()})

    tag_map = tag_map or {}
    seen: set[str] = set()
    remapped: list[dict] = []
    written: list[str] = []
    rejected: list[dict] = []
    for match in ANSWER.finditer(text):
        raw, body = match.group(1), match.group(2).strip()
        tag = tag_map.get(raw, raw)
        if tag != raw:
            remapped.append({"from": raw, "to": tag})
        item = by_tag.get(tag)
        if item is None:
            rejected.append({"tag": raw, "reason": "unknown tag"})
            continue
        if tag in seen:
            rejected.append({"tag": tag, "reason": "duplicate tag in the same file"})
            continue
        seen.add(tag)
        if not body:
            rejected.append({"tag": tag, "reason": "empty answer"})
            continue
        payload = {"text": body, "prompt_hash": item["prompt_hash"],
                   "model": model, "model_version": model_version,
                   "operator_note": "relayed from a chat session (G5 unmet)"}
        (directory / "responses").mkdir(parents=True, exist_ok=True)
        (directory / "responses" / f"{item['key']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(item["key"])

    return {"written": written, "errors": errors, "rejected": rejected,
            "remapped": remapped, "still_pending": len(pending(directory))}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    exporter = sub.add_parser("export", help="write PROMPTS.md and one file per pending request")
    exporter.add_argument("--dir", required=True, help="operator directory")
    exporter.add_argument("--out", default=None, help="default: <dir>/relay")

    ingester = sub.add_parser("ingest", help="read a pasted answer file")
    ingester.add_argument("--dir", required=True, help="operator directory")
    ingester.add_argument("--file", required=True, help="text file with <<<ANSWER tag>>> blocks")
    ingester.add_argument("--model", default="arena-chat-worker")
    ingester.add_argument("--model-version", default=None,
                          help="default: unversioned-<today>")
    ingester.add_argument("--map", action="append", default=[], metavar="FROM=TO",
                          help="accept a mistyped tag explicitly, e.g. --map ch01=9234. "
                               "Repeatable; ingest never guesses which request an answer means")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory = Path(args.dir)
    if not (directory / "requests").is_dir():
        print(f"error: no requests directory in {directory}", file=sys.stderr)
        return 2

    if args.command == "export":
        summary = export(directory, Path(args.out) if args.out else None)
        if not summary["pending"]:
            print(json.dumps({**summary, "message": "nothing pending"}, ensure_ascii=False))
            return 0
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    path = Path(args.file)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2
    version = args.model_version or datetime.now(timezone.utc).strftime("unversioned-%Y-%m-%d")
    tag_map: dict[str, str] = {}
    for entry in args.map:
        if "=" not in entry:
            print(f"error: --map expects FROM=TO, got {entry!r}", file=sys.stderr)
            return 2
        source, target = entry.split("=", 1)
        tag_map[source.strip()] = target.strip()

    summary = ingest(directory, path.read_text(encoding="utf-8"),
                     model=args.model, model_version=version, tag_map=tag_map)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["rejected"] or summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
