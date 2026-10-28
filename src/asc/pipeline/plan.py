"""The Plan step: a premise becomes a canon that the audit can read.

The output contract is the existing canon schema (:mod:`asc.story.canon`), not a
new format. That is deliberate: the artifact a planner produces is exactly the
artifact a continuity audit consumes, so nothing has to be translated between
planning and checking — and a plan that the audit cannot read is rejected here,
not three steps later.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from ..schema import Work
from ..story.canon import Canon, CanonError, chapter_key, load_canon
from ..story.continuity import CHECKS
from .llm import GenerationRequest, Provider, ProviderError
from .prompts import PromptTemplate, load_prompt
from .run import RunLedger
from .tasks import Task

TITLE = "Plan"

CANON_SCHEMA_GUIDE = """\
{
  "brief": {
    "theme_ja": "主題を一文で",
    "protagonist_ja": "主人公と、その欲望・恐れ",
    "setting_ja": "場所と時代",
    "tone_ja": "語りの温度",
    "turn_ja": "中盤で反転する出来事",
    "ending_ja": "終わり方（解決か、未解決か）"
  },
  "characters": [
    {"id": "aria", "name": "アリア", "aliases": ["アリア姫"], "status": "alive",
     "status_since": "ch01", "location": "灯台", "age_at_start": 24,
     "birthday_day": 120, "knows": ["F-01"], "notes": "灯台守の娘"}
  ],
  "facts": [
    {"id": "F-01", "summary": "灯りを消してはいけない", "terms": ["灯り"], "setup": "ch01"}
  ],
  "locations": [
    {"id": "灯台", "travel_days": {"王都": 3}},
    {"id": "王都", "travel_days": {"灯台": 3}}
  ],
  "timeline": {
    "chapters": [
      {"id": "ch01", "day": 1, "location": "灯台"},
      {"id": "ch02", "day": 4, "location": "王都"}
    ]
  },
  "foreshadowing": [
    {"id": "fs-001", "description": "灯台の鍵", "setup": "ch01", "payoff": "ch03"}
  ]
}
"""


class PlanError(RuntimeError):
    """Raised when the planner cannot produce a canon the audit accepts."""


@dataclass(frozen=True)
class Plan:
    task: Task
    brief: dict
    canon: dict
    attempts: int

    def canon_files(self) -> dict[str, dict]:
        """Split the plan into the six canon channels."""
        return {
            "characters": {"characters": self.canon.get("characters", [])},
            "facts": {"facts": self.canon.get("facts", [])},
            "locations": {"locations": self.canon.get("locations", [])},
            "timeline": {"chapters": self.canon.get("timeline", {}).get("chapters", [])},
            "foreshadowing": {"foreshadowing": self.canon.get("foreshadowing", [])},
            "suppressions": {"suppressions": self.canon.get("suppressions", [])},
        }

    def write_canon(self, directory: str | Path) -> Path:
        return _write_payload(self.canon, directory)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped).strip()
    return stripped


def escape_for_json_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def normalise_canon(payload: dict) -> dict:
    """Shape the payload, then let ``load_canon`` be the judge of validity."""
    if not isinstance(payload, dict):
        raise CanonError("the plan must be a JSON object")
    canon = dict(payload)

    characters = canon.get("characters")
    if not isinstance(characters, list) or not characters:
        raise CanonError("'characters' must be a non-empty list")
    for entry in characters:
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("name"):
            raise CanonError("each character needs 'id' and 'name'")
        if entry.get("status_since"):
            entry["status_since"] = chapter_key(entry["status_since"])
        if entry.get("age_at_start") is not None and not isinstance(entry["age_at_start"], int):
            raise CanonError(f"character {entry['id']}: age_at_start must be an integer")

    facts = canon.setdefault("facts", [])
    if not isinstance(facts, list):
        raise CanonError("'facts' must be a list")
    for entry in facts:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise CanonError("each fact needs 'id'")
        if entry.get("setup"):
            entry["setup"] = chapter_key(entry["setup"])

    locations = canon.get("locations")
    if not isinstance(locations, list) or not locations:
        raise CanonError("'locations' must be a non-empty list")
    for entry in locations:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise CanonError("each location needs 'id'")
        days = entry.setdefault("travel_days", {})
        if not isinstance(days, dict):
            raise CanonError(f"location {entry['id']}: travel_days must be a mapping")
        for target, value in days.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise CanonError(
                    f"location {entry['id']}: travel_days[{target!r}] must be a number >= 0")

    timeline = canon.get("timeline")
    if not isinstance(timeline, dict) or not isinstance(timeline.get("chapters"), list):
        raise CanonError("'timeline' must contain a 'chapters' list")
    if not timeline["chapters"]:
        raise CanonError("'timeline.chapters' must not be empty")
    seen: list[str] = []
    for entry in timeline["chapters"]:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise CanonError("each timeline entry needs 'id'")
        if not isinstance(entry.get("day"), int):
            raise CanonError(f"chapter {entry['id']}: 'day' must be an integer")
        entry["id"] = chapter_key(entry["id"])
        if entry["id"] in seen:
            raise CanonError(f"duplicate chapter id {entry['id']}")
        seen.append(entry["id"])
    days = [entry["day"] for entry in timeline["chapters"]]
    if days != sorted(days):
        raise CanonError("chapter days must not go backwards")

    foreshadowing = canon.setdefault("foreshadowing", [])
    if not isinstance(foreshadowing, list):
        raise CanonError("'foreshadowing' must be a list")
    for entry in foreshadowing:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise CanonError("each foreshadowing entry needs 'id'")
        for key in ("setup", "payoff"):
            if entry.get(key):
                entry[key] = chapter_key(entry[key])
        setup, payoff = entry.get("setup"), entry.get("payoff")
        if setup in seen and payoff in seen and seen.index(payoff) < seen.index(setup):
            raise CanonError(
                f"foreshadowing {entry['id']}: payoff {payoff} precedes setup {setup}")

    canon["suppressions"] = canon.get("suppressions", []) or []
    brief = canon.get("brief") or {}
    if not isinstance(brief, dict):
        raise CanonError("'brief' must be an object")
    canon["brief"] = brief
    return canon


def _write_payload(canon: dict, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    channels = {
        "characters": {"characters": canon.get("characters", [])},
        "facts": {"facts": canon.get("facts", [])},
        "locations": {"locations": canon.get("locations", [])},
        "timeline": {"chapters": canon.get("timeline", {}).get("chapters", [])},
        "foreshadowing": {"foreshadowing": canon.get("foreshadowing", [])},
        "suppressions": {"suppressions": canon.get("suppressions", [])},
    }
    for name, payload in channels.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return directory


def validate_payload(payload: dict) -> dict:
    """Normalise, write to a scratch directory and load it back."""
    canon = normalise_canon(payload)
    with TemporaryDirectory() as scratch:
        _write_payload(canon, scratch)
        load_canon(scratch)  # raises CanonError on any remaining problem
    return canon


def parse_plan(text: str) -> dict:
    try:
        payload = json.loads(_strip_fences(text))
    except json.JSONDecodeError as exc:
        raise CanonError(
            f"the plan is not valid JSON ({exc.msg} at line {exc.lineno})") from exc
    return validate_payload(payload)


def canon_coverage(canon: Canon) -> dict:
    """Which checks can run against this canon (the 'skipped 0' acceptance)."""
    met: list[str] = []
    missing: list[str] = []
    for spec in CHECKS:
        ok = True
        for requirement in spec.requires:
            if requirement == "characters":
                ok = ok and bool(canon.characters)
            elif requirement == "facts":
                ok = ok and bool(canon.facts)
            elif requirement == "locations":
                ok = ok and bool(canon.locations)
            elif requirement == "foreshadowing":
                ok = ok and bool(canon.foreshadowing)
            elif requirement == "timeline":
                ok = ok and any(chapter.day for chapter in canon.chapters.values())
            elif requirement == "chapters":
                ok = ok and bool(canon.chapters)
        (met if ok else missing).append(spec.id)
    return {"met": met, "missing": missing, "total": len(CHECKS)}


def build_plan(task: Task, provider: Provider, ledger: RunLedger, *,
               chapters: int = 3, target_chars: tuple[int, int] = (3000, 4200),
               prompt_dir: str | Path | None = None, temperature: float = 0.6,
               max_tokens: int = 3000, seed: int = 0,
               max_attempts: int = 2, prompt_suffix: str = "",
               source_work: Optional[Work] = None) -> Plan:
    """Ask the provider for a canon, repairing it at most ``max_attempts`` times."""
    base = load_prompt("plan-canon", prompt_dir)
    repair = load_prompt("plan-repair", prompt_dir)
    ledger.prompt_hashes["plan-canon"] = base.digest
    ledger.prompt_hashes["plan-repair"] = repair.digest

    ledger.write_text("brief.md", _render_brief(task, chapters, target_chars, source_work))
    values = {
        "title": task.title_ja,
        "genre": task.genre,
        "logline": task.logline,
        "must_include": "、".join(task.must_include),
        "avoid": "、".join(task.avoid),
        "chapters": str(chapters),
        "ch01": "ch01",
        "target_min": str(target_chars[0]),
        "target_max": str(target_chars[1]),
        "schema": CANON_SCHEMA_GUIDE,
    }

    previous = ""
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            template: PromptTemplate = base
            prompt = template.render(values)
            purpose = "plan"
        else:
            prompt = repair.render({
                "error": last_error, "previous": previous,
                "schema": CANON_SCHEMA_GUIDE,
            })
            purpose = "plan-repair"
            template = repair
        if prompt_suffix:
            prompt = f"{prompt}\n\n{prompt_suffix}"
        request = GenerationRequest(
            purpose=purpose, prompt=prompt, temperature=temperature,
            max_tokens=max_tokens, seed=seed,
            context=ledger.request_context(
                task_id=task.id, attempt=attempt, system=ledger.system,
            ),
        )
        try:
            result = provider.generate(request)
        except ProviderError as exc:
            last_error = escape_for_json_error(exc)
            ledger.fail(f"attempt {attempt}: {last_error}")
            raise PlanError(last_error) from exc

        ledger.record(request, result)
        ledger.write_text(f"plan/attempt-{attempt}.txt", result.text)
        previous = result.text
        try:
            canon = parse_plan(result.text)
        except CanonError as exc:
            last_error = escape_for_json_error(exc)
            ledger.write_text(f"plan/attempt-{attempt}.error.txt", last_error + "\n")
            continue

        plan = Plan(task=task, brief=canon["brief"], canon=canon, attempts=attempt)
        plan.write_canon(ledger.path / "canon")
        ledger.track([f"canon/{name}.json" for name in plan.canon_files()])
        ledger.write_json("plan.json", {
            "task": task.as_dict(),
            "brief": canon["brief"],
            "canon": canon,
            "attempts": attempt,
            "prompt": {"name": template.name, "version": template.version,
                       "digest": template.digest},
        })
        ledger.write_text("canon/README.md", _render_canon_note(task, attempt))
        ledger.finish("ok")
        return plan

    message = (f"no valid canon after {max_attempts} attempts; last error: {last_error}")
    ledger.fail(message)
    raise PlanError(message)


def _render_brief(task: Task, chapters: int, target_chars: tuple[int, int],
                  source_work: Optional[Work] = None) -> str:
    lines = [
        f"# {task.title_ja}",
        "",
        f"- タスク: `{task.id}`（{task.genre}）",
        f"- ログライン: {task.logline}",
        f"- 必須語: {'、'.join(task.must_include)}",
        f"- 禁止: {'、'.join(task.avoid)}",
        f"- 章数: {chapters}",
        f"- 目安: {target_chars[0]}〜{target_chars[1]} 字",
    ]
    if source_work is not None:
        authors = "、".join(a.name for a in source_work.authors)
        lines += [
            "",
            f"- 参照作品: {source_work.id}（{source_work.title}）",
            f"- 参照著者: {authors or '不明'}",
            f"- 参照ジャンル: {source_work.genre}",
            f"- 参照元: {source_work.source}",
        ]
    lines += [
        "",
        "この企画は固定タスクセット（`benchmarks/protocol-v1/tasks.yaml`）の一部であり、",
        "変更すると評価プロトコルの版が上がります。",
        "",
    ]
    return "\n".join(lines)


def _render_canon_note(task: Task, attempts: int) -> str:
    return "\n".join([
        "# 生成された canon",
        "",
        f"タスク `{task.id}` の設定台帳です。書式は",
        "`skills/continuity-ledger/references/canon-schema.md` に従います。",
        "",
        f"- 生成試行回数: {attempts}",
        "- 本文マーカー（`{{death: ...}}` など）は、この台帳を書いた後に本文側で付けます。",
        "- 台帳は監査の正解であり、本文から推測して書き換えてはいけません。",
        "",
    ])
