#!/usr/bin/env python3
"""Write the exact Stage B prompts for a bundle, so a chat can answer them.

The pipeline normally hands prompts over one at a time: it stops at the first
chapter that has no answer yet and writes ``PROMPTS.md``. That is fine for a
long run, but not for answering three samples in one sitting. This script
renders the three chapter prompts from the same function the pipeline uses
(``run_twostage.stage_b_rewrite_prompt``), so the text is byte-identical to what
would be asked, and records each prompt's hash.

It does **not** create a run, and it writes no answers. The prompt hash it
records is the same value the request file carries; a response written against a
different prompt is refused as stale by ``chat_operator.py``.

    python3 scripts/export_stageb_prompts.py \\
        --bundle experiments/2026-10-realrun-a-t01 --task t01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asc.gamelog import load_game_log  # noqa: E402
from asc.gamelog.world import build_world, derive_timeline  # noqa: E402
from asc.pipeline import load_prompt, load_tasks  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402
import run_twostage  # noqa: E402

DEFAULT_BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-a-t01"


def digest(text: str) -> str:
    """The same 16-character hash ``chat_operator.py`` puts on a request."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--task", default="t01")
    parser.add_argument("--tasks-file", default=str(run_twostage.DEFAULT_TASKS))
    parser.add_argument("--canon", default=None, help="default: <bundle>/inputs/canon")
    parser.add_argument("--design-dir", default=None,
                        help="default: <bundle>/inputs/design")
    parser.add_argument("--game-log", default=None,
                        help="default: <bundle>/inputs/game_log.json")
    parser.add_argument("--out", default=None, help="default: <bundle>/prompts")
    args = parser.parse_args(argv)

    bundle = Path(args.bundle)
    canon = load_canon(args.canon or bundle / "inputs" / "canon")
    design_dir = Path(args.design_dir or bundle / "inputs" / "design")
    log = load_game_log(args.game_log or bundle / "inputs" / "game_log.json")
    voice = load_voice(design_dir / "voice.json")
    scenes = load_scenes(design_dir / "scene.json")
    task = load_tasks(args.tasks_file).get(args.task)
    prompts = {name: load_prompt(name) for name in run_twostage.PROMPT_NAMES}
    timeline = derive_timeline(log, canon, build_world(canon))

    out_dir = Path(args.out or bundle / "prompts")
    out_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict] = {}
    for chapter in log.chapters:
        prompt = run_twostage.stage_b_rewrite_prompt(
            prompts, chapter.id, task, voice, scenes, log, timeline, canon)
        path = out_dir / f"{chapter.id}.prompt.md"
        path.write_text(prompt, encoding="utf-8")
        index[chapter.id] = {
            "file": path.name,
            "chars": len(prompt),
            "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_hash": digest(prompt),
            "purpose": f"stage_b:{chapter.id}",
        }
        print(f"{chapter.id}: {len(prompt)} chars prompt_hash={digest(prompt)}")

    (out_dir / "index.json").write_text(
        json.dumps({"schema": "stageb-prompts-v1",
                    "task": args.task,
                    "template": prompts["stage-b-rewrite"].digest,
                    "template_version": prompts["stage-b-rewrite"].version,
                    "source": "run_twostage.stage_b_rewrite_prompt",
                    "prompts": index},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(index)} prompts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
