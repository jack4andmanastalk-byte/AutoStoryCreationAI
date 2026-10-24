#!/usr/bin/env python3
"""Select the 30-work control group from Aozora Bunko (protocol v1, section 6).

The control group is a ruler, not a model answer: 3 copyright-expired works
per task, genre-matched to the task's ``control`` label and length-matched to
``target_chars``. Selection runs in three steps, because genre fit cannot be
decided mechanically:

1. ``propose`` — scan the metadata, filter by rights and NDC genre, rank by
   title keywords and length, and write a proposal with a download list.
2. A human approves 3 works per task (checking genre fit by title/author).
3. ``freeze`` — validate the approved list hard (3/task, expired, allowed
   genre, text present, length in window, no duplicates) and write the frozen
   ``controls.json``. Swapping it later is a protocol version bump (§9).

Nobody is asked to trust the keyword lists: every candidate carries the
keywords it matched (or none), and the frozen file records the rules version,
the seed and the approver.

    python3 scripts/select_controls.py propose --out build/controls/proposal.json
    python3 scripts/setup_dataset.py --config configs/dataset.yaml aozora-texts \\
        --ids-file build/controls/download-list.txt   # in an env with network
    # ... edit the proposal into approved.json (3 work ids per task) ...
    python3 scripts/select_controls.py freeze --approved approved.json \\
        --out benchmarks/protocol-v1/controls.json --emit-dir build/controls/texts
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline.tasks import load_tasks  # noqa: E402

RULES_VERSION = "controls-rules-v1"

#: NDC genre codes allowed for narrative-fiction controls: **3 (novels and
#: stories) in any literature class. Poetry (911...), criticism (914...),
#: diaries (915...), plays (912: dialogue scripts read nothing like a short
#: story) and non-literature are excluded; K-prefixed codes are children's
#: books and are excluded too.
ALLOWED_GENRE = re.compile(r"^9[0-9]3$")

FANTASY_KEYWORDS = (
    "怪談", "奇談", "幻想", "妖怪", "幽霊", "お化け", "化け", "怪奇", "不思議",
    "ふしぎ", "昔話", "童話", "お伽", "御伽", "龍", "竜", "鬼", "狐", "天狗",
    "河童", "雪女", "狸", "座敷", "魔女", "魔法", "呪", "占", "予言", "巨人",
    "小人", "人魚", "夢幻", "異界", "黄泉", "竜宮", "浦島", "かぐや", "竹取",
    "桃太郎", "金太郎", "一寸", "舌切り雀", "さるかに", "花咲か", "神", "仙人",
    "地獄", "天国", "冥途", "あの世", "幻", "妖", "幽", "霊", "夢", "魔", "星",
    "銀河", "姫", "王子", "猫又", "狼",
)

HISTORY_KEYWORDS = (
    "忠臣蔵", "四十七士", "赤穂", "仇討", "仇討ち", "切腹", "新選組", "新撰組",
    "幕末", "維新", "攘夷", "開国", "黒船", "参勤", "大名", "将軍", "幕府",
    "朝廷", "公家", "天皇", "戦国", "合戦", "武士", "武家", "浪人", "剣豪",
    "剣客", "忍者", "忍び", "侍", "江戸", "明治", "大正", "藩", "奉行", "与力",
    "同心", "家老", "殿様", "若君", "姫君", "志士", "平家", "源氏", "義経",
    "弁慶", "太平記", "方丈記", "徒然草", "枕草子", "伊勢物語", "宇治拾遺",
    "今昔", "古事記", "日本書紀", "万葉", "応仁", "遣唐使", "道真", "信長",
    "秀吉", "家康", "龍馬", "西郷", "大石", "時代", "説話", "軍記", "史談",
    "壬申", "倭寇", "辻斬",
)

KEYWORDS = {"fantasy": FANTASY_KEYWORDS, "history": HISTORY_KEYWORDS,
            "contemporary": ()}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def matched_keywords(title: str, control: str) -> tuple[str, ...]:
    return tuple(k for k in KEYWORDS.get(control, ()) if k and k in title)


def genre_allowed(work: dict) -> tuple[bool, str]:
    genre = work.get("genre") or {}
    code = genre.get("code") if isinstance(genre, dict) else None
    label = genre.get("label", "") if isinstance(genre, dict) else ""
    if not code:
        return False, "unknown genre"
    if str(code).startswith("K"):
        return False, f"children's book ({code})"
    if not ALLOWED_GENRE.match(str(code)):
        return False, f"not narrative fiction ({code} {label})"
    return True, f"{code} {label}".strip()


def rights_ok(work: dict) -> tuple[bool, str]:
    rights = work.get("rights") or {}
    flag = rights.get("copyright_flag")
    if flag is None:
        return False, "copyright status unknown"
    if flag:
        return False, "copyright not expired"
    return True, "copyright expired"


def load_works(path: Path) -> list[dict]:
    works = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                works.append(json.loads(line))
    return works


def text_of(work: dict, texts_dir: Path) -> tuple[str | None, str]:
    """Return (text, status): full text when present, else a missing reason."""
    text_path = work.get("text_path")
    candidates = []
    if text_path:
        candidates.append(REPO_ROOT / text_path if not Path(text_path).is_absolute()
                          else Path(text_path))
    work_id = str(work.get("id", ""))
    if ":" in work_id:
        candidates.append(texts_dir / f"{work_id.split(':', 1)[1]}.txt")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8"), "ok"
    return None, "text_missing"


def classify_length(chars: int, window: tuple[int, int]) -> str:
    low, high = window
    if chars < low:
        return "too_short"
    if chars > high:
        return "excerpt"
    return "full"


def cut_head(text: str, window: tuple[int, int]) -> tuple[str, dict]:
    """Cut a head excerpt inside the window at a paragraph boundary.

    Paragraphs are blank-line-separated blocks. Blocks accumulate until the
    next one would exceed the maximum; the result must still reach the
    minimum, otherwise the work cannot supply an excerpt and ValueError is
    raised (the human then picks another work).
    """
    low, high = window
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    kept: list[str] = []
    total = 0
    for block in blocks:
        size = count_chars(block)
        if total + size > high:
            break
        kept.append(block)
        total += size
    if total < low:
        raise ValueError(
            f"cannot cut a {low}-{high} excerpt (paragraphs overshoot)")
    body = "\n\n".join(kept)
    start = text.index(kept[0])
    return body, {"start_char": start, "end_char": start + len(body),
                  "paragraphs": len(kept), "method": "head-cut at blank line"}


def propose_candidates(works: list[dict], tasks, texts_dir: Path,
                       per_task: int, seed: int) -> dict:
    window = tuple(tasks.target_chars)
    pool: list[dict] = []
    excluded: dict[str, int] = {}
    for work in works:
        ok, reason = rights_ok(work)
        if not ok:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        ok, genre_note = genre_allowed(work)
        if not ok:
            excluded[genre_note] = excluded.get(genre_note, 0) + 1
            continue
        text, status = text_of(work, texts_dir)
        if text is None:
            length, length_note, chars = "text_missing", status, None
        else:
            chars = count_chars(text)
            length = classify_length(chars, window)
            length_note = length
        pool.append({"work": work, "genre_note": genre_note, "chars": chars,
                     "length": length, "length_note": length_note})

    rng = random.Random(seed)
    by_task: dict[str, dict] = {}
    download: list[str] = []
    for task in tasks.tasks:
        control = task.control
        ranked = []
        for entry in pool:
            work = entry["work"]
            keywords = matched_keywords(work.get("title", ""), control)
            score = 0 if keywords or control == "contemporary" else 1
            status_rank = {"full": 0, "excerpt": 1, "text_missing": 2,
                           "too_short": 3}[entry["length"]]
            ranked.append((status_rank, score, entry, keywords))
        # deterministic shuffle inside ranks: same seed, same proposal
        rng.shuffle(ranked)
        ranked.sort(key=lambda item: (item[0], item[1]))
        candidates = []
        for _, _, entry, keywords in ranked[:per_task]:
            work = entry["work"]
            authors = [a.get("name", "") for a in work.get("authors", [])]
            candidates.append({
                "work_id": work.get("id"), "title": work.get("title"),
                "authors": authors, "url": work.get("url"),
                "text_url": work.get("text_url"), "genre": entry["genre_note"],
                "keywords": list(keywords), "status": entry["length"],
                "chars": entry["chars"],
                "has_translation": any(
                    a.get("role") == "translator"
                    for a in work.get("authors", [])),
            })
        full = sum(1 for c in candidates if c["status"] == "full")
        usable = sum(1 for c in candidates
                     if c["status"] in {"full", "excerpt"})
        by_task[task.id] = {"control": control, "candidates": candidates,
                            "full_in_list": full, "usable_in_list": usable,
                            "shortfall": max(0, 3 - usable)}
        for candidate in candidates:
            if candidate["status"] == "text_missing" and \
                    candidate["work_id"] not in download:
                download.append(candidate["work_id"])
    return {"by_task": by_task, "download_list": download,
            "excluded": excluded, "pool": len(pool)}


def cmd_propose(args: argparse.Namespace) -> int:
    try:
        tasks = load_tasks(args.tasks_file)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    works_path = Path(args.works)
    if not works_path.is_file():
        print(f"error: metadata not found: {works_path}", file=sys.stderr)
        return 2
    works = load_works(works_path)
    result = propose_candidates(works, tasks, Path(args.texts), args.per_task,
                                args.seed)
    proposal = {
        "generated_at": utc_now(), "rules": RULES_VERSION, "seed": args.seed,
        "window": list(tasks.target_chars),
        "controls": {t.id: t.control for t in tasks.tasks},
        "per_task": result["by_task"],
        "download_list": result["download_list"],
        "stats": {"metadata_works": len(works), "pool": result["pool"],
                  "excluded": result["excluded"]},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    if args.download_list:
        path = Path(args.download_list)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(result["download_list"]) + "\n",
                        encoding="utf-8")
    if not args.quiet:
        short = {t: v["shortfall"] for t, v in result["by_task"].items()}
        print(json.dumps({"proposal": str(out), "pool": result["pool"],
                          "download": len(result["download_list"]),
                          "shortfall": short},
                         ensure_ascii=False, indent=2))
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    try:
        tasks = load_tasks(args.tasks_file)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        approved = json.loads(Path(args.approved).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: approved file unreadable: {exc}", file=sys.stderr)
        return 2
    if not approved.get("approved_by"):
        print("error: approved file needs 'approved_by' (who checked genre fit)",
              file=sys.stderr)
        return 2
    picks = approved.get("picks") or {}
    task_ids = [t.id for t in tasks.tasks]
    if sorted(picks) != sorted(task_ids):
        print(f"error: picks must cover every task exactly once "
              f"(missing/extra: {sorted(set(task_ids) ^ set(picks))})",
              file=sys.stderr)
        return 2
    for task_id, work_ids in picks.items():
        if not isinstance(work_ids, list) or len(work_ids) != 3:
            print(f"error: {task_id} needs exactly 3 work ids", file=sys.stderr)
            return 2
    flat = [w for ids in picks.values() for w in ids]
    if len(set(flat)) != len(flat):
        print("error: a work may appear only once in the control group",
              file=sys.stderr)
        return 2

    works_path = Path(args.works)
    if not works_path.is_file():
        print(f"error: metadata not found: {works_path}", file=sys.stderr)
        return 2
    by_id = {w.get("id"): w for w in load_works(works_path)}
    texts_dir = Path(args.texts)
    window = tuple(tasks.target_chars)
    frozen: list[dict] = []
    emitted: dict[str, str] = {}
    for task in tasks.tasks:
        for position, work_id in enumerate(picks[task.id], start=1):
            work = by_id.get(work_id)
            if work is None:
                print(f"error: {task.id}: unknown work {work_id}", file=sys.stderr)
                return 2
            ok, reason = rights_ok(work)
            if not ok:
                print(f"error: {task.id}: {work_id}: {reason}", file=sys.stderr)
                return 2
            ok, genre_note = genre_allowed(work)
            if not ok:
                print(f"error: {task.id}: {work_id}: {reason}", file=sys.stderr)
                return 2
            text, status = text_of(work, texts_dir)
            if text is None:
                print(f"error: {task.id}: {work_id}: {status} "
                      f"(fetch it first)", file=sys.stderr)
                return 2
            chars = count_chars(text)
            kind = classify_length(chars, window)
            if kind == "too_short":
                print(f"error: {task.id}: {work_id}: {chars} chars "
                      f"(window {window[0]}-{window[1]})", file=sys.stderr)
                return 2
            if kind == "full":
                body, span = text, {"start_char": 0, "end_char": len(text),
                                    "paragraphs": None, "method": "full text"}
            else:
                try:
                    body, span = cut_head(text, window)
                except ValueError as exc:
                    print(f"error: {task.id}: {work_id}: {exc}", file=sys.stderr)
                    return 2
                chars = count_chars(body)
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            authors = [a.get("name", "") for a in work.get("authors", [])]
            frozen.append({
                "task": task.id, "control": task.control, "work_id": work_id,
                "title": work.get("title"), "authors": authors,
                "url": work.get("url"), "genre": genre_note, "kind": kind,
                "range": span, "chars": chars, "sha256": digest,
                "keywords": list(matched_keywords(work.get("title", ""),
                                                  task.control)),
            })
            emitted[f"{task.id}-{position}.txt"] = body

    controls = {
        "protocol": tasks.protocol, "frozen": utc_now(),
        "rules": RULES_VERSION, "window": list(window),
        "approved_by": approved.get("approved_by"),
        "approved_at": approved.get("approved_at", ""),
        "note": approved.get("note", ""),
        "works": frozen,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(controls, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    if args.emit_dir:
        emit = Path(args.emit_dir)
        emit.mkdir(parents=True, exist_ok=True)
        manifest = {}
        for name, body in emitted.items():
            (emit / name).write_text(body, encoding="utf-8")
            manifest[name] = next(
                w["work_id"] for w in frozen
                if f"{w['task']}-" in name and name.startswith(w["task"]))
        (emit / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    if not args.quiet:
        kinds = {"full": sum(1 for w in frozen if w["kind"] == "full"),
                 "excerpt": sum(1 for w in frozen if w["kind"] == "excerpt")}
        print(json.dumps({"controls": str(out), "works": len(frozen),
                          "kinds": kinds}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tasks-file",
                        default=str(REPO_ROOT / "benchmarks/protocol-v1/tasks.yaml"))
    common.add_argument("--works",
                        default=str(REPO_ROOT / "data/datasets/aozora_works.jsonl"))
    common.add_argument("--texts",
                        default=str(REPO_ROOT / "data/raw/aozora/texts"))
    common.add_argument("--quiet", action="store_true")
    sub = parser.add_subparsers(dest="mode", required=True)

    propose = sub.add_parser("propose", parents=[common],
                             help="rank candidates per task")
    propose.add_argument("--out", default="build/controls/proposal.json")
    propose.add_argument("--download-list",
                         default="build/controls/download-list.txt")
    propose.add_argument("--per-task", type=int, default=12)
    propose.add_argument("--seed", type=int, default=0)

    freeze = sub.add_parser("freeze", parents=[common],
                            help="validate and freeze the approved list")
    freeze.add_argument("--approved", required=True)
    freeze.add_argument("--out",
                        default=str(REPO_ROOT / "benchmarks/protocol-v1/controls.json"))
    freeze.add_argument("--emit-dir", default="build/controls/texts")

    args = parser.parse_args(argv)
    if args.mode == "propose":
        return cmd_propose(args)
    return cmd_freeze(args)


if __name__ == "__main__":
    raise SystemExit(main())
