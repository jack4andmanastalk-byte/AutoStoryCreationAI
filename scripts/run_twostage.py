#!/usr/bin/env python3
"""Stage A -> Stage B wiring for the first two-stage vertical slice.

Stage A asks a provider for one structured ``game_log.json`` and validates it
against canon / plot.json / scene.json with ``asc.gamelog.check``. A failing log
is sent back with the findings, at most ``--max-attempts`` times. **Only a
clean log is passed to Stage B.** Stage B rewrites each chapter from that
verified log plus ``voice.json``; every chapter is checked for marker sequence,
character/fact knowledge boundaries and banned voice patterns.

Everything the run needs is copied into ``--out`` (canon, design, script,
responses, text, reports, state). ``--out`` must live under ``experiments/``;
``build/`` and ``runs/`` are rejected so an Arena relay cannot lose its state
on a workspace reset. If a command provider has no answer yet, the runner
writes ``PROMPTS.md`` + ``state.json`` into the same bundle and exits 3; after
the answers are stored, ``--resume --run-id <id>`` replays the recorded
responses in that bundle and continues with the remaining requests.

Two more entry points exist for the trial that follows:

* ``--stage b --game-log <path>`` rewrites a log that was verified earlier and
  is passed in as a file. Stage A is not requested at all, so a Stage B trial
  never needs a fabricated Stage A answer. The supplied log is re-checked here;
  a failing log is fail-closed unless ``--allow-unverified-log`` is given, and
  either way the bundle records ``unverified`` in its reports.
* ``--stage a`` stops after the log.

A run always leaves a resumable ``state.json`` (including on failure), never
truncates ``responses.jsonl`` while resuming, and refuses to resume when the
conditions or the input hashes changed (``--allow-config-change`` records an
intentional change). A recorded answer whose ``response_sha256`` no longer
matches is refused instead of replayed.

    python3 scripts/run_twostage.py --task t01 \\
        --canon experiments/2026-10-trpg-slice-t01/inputs/canon \\
        --design-dir experiments/2026-10-trpg-slice-t01/inputs/design \\
        --provider scripted \\
        --script experiments/2026-10-trpg-slice-t01/scripted.json \\
        --out experiments/2026-10-trpg-slice-t01/bundle \\
        --results experiments/2026-10-trpg-slice-t01/results.json \\
        --report-only --quiet

    # Stage B only, from a log that was verified earlier
    python3 scripts/run_twostage.py --task t01 \
        --canon experiments/<id>/inputs/canon \
        --design-dir experiments/<id>/inputs/design \
        --stage b --game-log experiments/<id>/inputs/game_log.json \
        --provider command --command "python3 scripts/chat_operator.py --dir experiments/<id>/relay" \
        --out experiments/<id> --run-id stageb-t01-s0

Exit codes: 0 clean (or --report-only), 1 unresolved checks, 2 bad input
(including a refused resume or an unverified log without the override),
3 an Arena/operator response is pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.scope import EvaluationScopeError, load_evaluation_scope  # noqa: E402
from asc.gamelog import (  # noqa: E402
    GameLog, GameLogError, check_rewrite, check_game_log, gamelog_needs_repair,
    missing_must_include, parse_game_log, rewrite_needs_repair,
)
from asc.gamelog.markers import chapter_markers  # noqa: E402
from asc.gamelog.world import (  # noqa: E402
    build_world, derive_timeline, render_chapter_timeline,
)
from asc.pipeline import (  # noqa: E402
    CommandProvider, GenerationRequest, GenerationResult, ProviderError,
    ResponsePendingError, RunLedger, ScriptedProvider, Task, TaskError,
    canon_brief, clean_text, load_prompt, load_tasks,
)
from asc.plot.check import check_plot  # noqa: E402
from asc.plot.schema import PlotDoc, load_plot  # noqa: E402
from asc.scene.check import check_scenes  # noqa: E402
from asc.scene.schema import SceneDoc, load_scenes  # noqa: E402
from asc.story.canon import Canon, CanonError, load_canon  # noqa: E402
from asc.story.continuity import audit_texts  # noqa: E402
from asc.style.schema import Voice, load_voice  # noqa: E402

DEFAULT_TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"
SYSTEM = "two-stage"
MIN_REWRITE_CHARS = 200
PROMPT_NAMES = ("stage-a-gamelog", "stage-a-repair",
                "stage-b-rewrite", "stage-b-repair")
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
LIMITS = [
    "L1 は構造・衛生の検査であり、物語の質・面白さ・読者選好の証拠ではない。",
    "L2/L3 は frozen_not_measured。G3/G4 は未達とも合格とも記録しない。",
    "Arena など版を固定できない経路では G5 を主張しない。",
    "scripted の実行は配線確認であり、実モデルの応答・効果の観測ではない。",
]
#: Added only for ``--stage b``: the log is an input file, not a model answer.
STAGE_B_LIMIT = (
    "Stage B 単独実行の入力ログは与えられたファイルであり、"
    "この run のモデル応答ではない。")

GAMELOG_SCHEMA = """\
{
  "schema_version": "1.0",
  "task": "題材 ID",
  "notes": "任意",
  "chapters": [
    {
      "id": "ch01", "day": 1, "location": "canon の場所 ID",
      "emitted_markers": ["{{time: day=1}}", "{{location: 灯台}}"],
      "scenes": [
        {
          "id": "g01", "scene_ref": "s01", "act_ref": "setup", "turn_ref": "t1",
          "situation": "状況提示", "purpose": "目的", "conflict": "対立",
          "change": "変化", "tension": "curiosity", "choice": "転換点の選択",
          "outcome": "結果", "present_characters": ["aria"],
          "actions": [
            {"id": "a1", "type": "action", "actor": "aria",
             "target": "対象", "summary": "何をしたか"},
            {"id": "a2", "type": "record_reference", "actor": "aria",
             "subject": "johan", "medium": "潮札", "summary": "記録への言及"}
          ],
          "state_delta": {
            "learned_facts": [{"character": "aria", "fact": "F-05"}],
            "used_facts": [{"character": "aria", "fact": "F-01"}],
            "foreshadow_events": [{"id": "fs-001", "event": "setup"}],
            "location_moves": [{"character": "aria", "origin": "灯台",
                                "destination": "王都", "depart_day": 1,
                                "arrival_day": 4}]
          },
          "emitted_markers": ["{{learn: aria fact=F-05}}",
                              "{{foreshadow: fs-001 setup}}"]
        }
      ]
    }
  ]
}
型: action / dialogue / record_reference / memory_mention。tension: suspense /
curiosity / surprise / irony / deadline / quiet。event: setup / payoff。"""

MARKER_CONTRACT = """\
- 章ごとに、先頭へ `{{time: day=<章の day>}}`、`{{location: <章の location>}}`
  をこの順で 1 件ずつ。この 2 件を章の `emitted_markers` に書く。
- 場面ごとに、`state_delta.learned_facts` の順で
  `{{learn: <人物ID> fact=<事実ID>}}`、続いて `used_facts` の順で
  `{{use: <人物ID> fact=<事実ID>}}`、続いて `foreshadow_events` の順で
  `{{foreshadow: <布石ID> setup|payoff}}`。これらを場面の
  `emitted_markers` に、同じ順序で書く。
- `location_moves` は移動日数の検査に使うだけで、マーカーは出さない。
- マーカーを自分で追加・削除・並べ替えしてはいけない。導出列がそのまま確定列になる。"""


# -- bundle helpers ---------------------------------------------------------
def _sha256_tree(path: Path) -> dict[str, str]:
    if not path.is_dir():
        return {}
    return {file.relative_to(path).as_posix():
            hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(path.rglob("*")) if file.is_file()}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_script_bundle(path: str | Path) -> dict[str, str]:
    """Load ``{"responses": {key: text | {"$file": relpath}}}``.

    ``$file`` resolves relative to the script, so a game log and chapter texts
    can be committed once as readable inputs and referenced by the fixed
    script without duplicating their content.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    responses = data.get("responses")
    if not isinstance(responses, dict):
        raise ProviderError(f"{path}: expected {{'responses': {{...}}}}")
    resolved: dict[str, str] = {}
    for key, value in responses.items():
        if isinstance(value, str):
            resolved[key] = value
        elif isinstance(value, dict) and "$file" in value:
            target = (path.parent / str(value["$file"])).resolve()
            if not target.is_file():
                raise ProviderError(f"{path}: $file not found: {target}")
            resolved[key] = target.read_text(encoding="utf-8")
        else:
            raise ProviderError(f"{path}: bad response for key {key!r}")
    return resolved


def validate_out(out: Path, *, allow_temp: bool = False) -> Path:
    resolved = out.resolve()
    experiments = (REPO_ROOT / "experiments").resolve()
    scratch = ((REPO_ROOT / "build").resolve(), (REPO_ROOT / "runs").resolve())
    if any(root == resolved or root in resolved.parents for root in scratch):
        raise ValueError("--out must not be under build/ or runs/ (scratch is not persisted)")
    if not allow_temp and experiments != resolved and experiments not in resolved.parents:
        raise ValueError("--out must be under experiments/<id>/ (self-contained bundle)")
    return resolved


class ReplayError(ProviderError):
    """A recorded response is missing, duplicated or no longer matches.

    Raised instead of silently asking the delegate, so a modified or ambiguous
    recording cannot pass as a model response (R-05 / R-07).
    """


class BundleProvider:
    """Replay already-recorded responses from the bundle; delegate the rest.

    Used by ``--resume`` after an operator answer was added to the relay dir.
    A changed prompt hash is never served from the recording: the delegate is
    asked instead, so a stale answer cannot silently pass as a fresh one.

    Every replay decision is recorded in ``events`` so the caller can report
    how much of the run came from the recording. A recorded response whose
    ``response_sha256`` does not match its text is refused rather than replayed
    (an edited file must not be reported as the model's answer).
    """

    def __init__(self, delegate, entries: list[dict]):
        self.delegate = delegate
        self.name = delegate.name
        self.model = delegate.model
        self.model_version = delegate.model_version
        self.events: list[dict] = []
        self.duplicates: list[str] = []
        self._recorded: dict[tuple, dict] = {}
        for entry in entries:
            context = entry.get("context") or {}
            key = (entry.get("purpose"), context.get("attempt"),
                   context.get("chapter"), entry.get("seed"))
            if key in self._recorded:
                self.duplicates.append(
                    f"{entry.get('purpose')}/attempt={context.get('attempt')}"
                    f"/chapter={context.get('chapter')}/seed={entry.get('seed')}")
            self._recorded[key] = entry

    def generate(self, request: GenerationRequest) -> GenerationResult:
        context = request.context or {}
        key = (request.purpose, context.get("attempt"),
               context.get("chapter"), request.seed)
        entry = self._recorded.get(key)
        label = (f"{request.purpose}/attempt={context.get('attempt')}"
                 f"/chapter={context.get('chapter')}/seed={request.seed}")
        if entry is None:
            self.events.append({"request": label, "outcome": "missing"})
            return self.delegate.generate(request)
        if entry.get("prompt_hash") != request.prompt_hash:
            self.events.append({"request": label, "outcome": "stale",
                                "recorded_prompt_hash": entry.get("prompt_hash"),
                                "current_prompt_hash": request.prompt_hash})
            return self.delegate.generate(request)
        source = entry.get("response") or {}
        text = source.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ReplayError(f"{label}: recorded response has no text")
        recorded_hash = entry.get("response_sha256")
        actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if recorded_hash and recorded_hash != actual_hash:
            raise ReplayError(
                f"{label}: recorded response was modified "
                f"(response_sha256 {recorded_hash[:12]}… != {actual_hash[:12]}…). "
                "Restore the record or start a new run-id.")
        self.events.append({"request": label, "outcome": "replayed",
                            "response_sha256": actual_hash})
        return GenerationResult(
            text=text, provider=self.delegate.name,
            model=str(source.get("model") or self.delegate.model),
            model_version=source.get("model_version", self.delegate.model_version),
            usage={"bundle_resume": 1},
            provenance={"origin": "bundle_resume",
                        "source_prompt_hash": entry.get("prompt_hash"),
                        "response_sha256": actual_hash})

    def report(self) -> dict:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event["outcome"]] = counts.get(event["outcome"], 0) + 1
        return {"counts": counts, "events": self.events,
                "duplicate_record_keys": self.duplicates}


# -- prompt payloads --------------------------------------------------------
def _plot_slice(plot: PlotDoc) -> str:
    lines = ["幕（ID / 章 / 問い）:"]
    for act in plot.acts:
        lines.append(f"- {act.id} / {', '.join(act.chapters)} / {act.question}")
    lines.append("転換点（ID / 章 / 選択）:")
    for turn in plot.turns:
        lines.append(f"- {turn.id} / {turn.chapter} / {turn.choice_ja}")
    return "\n".join(lines)


def _scenes_slice(scenes: SceneDoc) -> str:
    rows = []
    for scene in scenes.scenes:
        rows.append({
            "id": scene.id, "chapter": scene.chapter,
            "purpose": scene.purpose, "conflict": scene.conflict,
            "change": scene.change, "tension": scene.tension,
            "knowledge": [{"character": flow.character, "entry": list(flow.entry),
                           "gained": list(flow.gained)} for flow in scene.knowledge],
            "disclosure": {
                "disclosed": list(scene.disclosed),
                "withheld": [{"fact": item.fact, "reason": item.reason}
                             for item in scene.withheld]},
            "foreshadows": {
                "planted": [{"id": item.id, "payoff": item.payoff}
                            for item in scene.planted],
                "paid": list(scene.paid)},
        })
    return json.dumps({"scenes": rows}, ensure_ascii=False, indent=2)


def _voice_slice(voice: Voice) -> str:
    return json.dumps({
        "viewpoint": {"person": voice.person, "character": voice.character,
                      "aliases": list(voice.aliases),
                      "pronouns": list(voice.pronouns)},
        "narrator": {"knows_ja": voice.narrator_knows_ja},
        "sample": voice.sample,
        "banned": [item.__dict__ for item in voice.banned],
        "notes": voice.notes,
    }, ensure_ascii=False, indent=2)


def _chapter_slice(log: GameLog, chapter_id: str) -> str:
    chapter = log.chapter(chapter_id)
    if chapter is None:
        return "{}"
    return json.dumps(chapter.as_dict(), ensure_ascii=False, indent=2)


def _scene_notes(scenes: SceneDoc, log: GameLog, chapter_id: str) -> str:
    chapter = log.chapter(chapter_id)
    refs = {scene.scene_ref for scene in chapter.scenes} if chapter else set()
    lines = []
    for scene in scenes.scenes:
        if scene.id not in refs:
            continue
        lines.append(f"- {scene.id}: 目的 {scene.purpose}／対立 {scene.conflict}／"
                     f"変化 {scene.change}（緊張: {scene.tension}）")
        withheld = ", ".join(item.fact for item in scene.withheld) or "なし"
        lines.append(f"  保留する事実: {withheld}")
    return "\n".join(lines) or "（この章の設計メモなし）"


def _markers_text(log: GameLog, chapter_id: str) -> str:
    return "\n".join(f"{index}. {marker.text}"
                     for index, marker in enumerate(chapter_markers(log, chapter_id), 1))


def _task_text(task: Task) -> str:
    return (f"題材: {task.title_ja}（{task.id}）\n"
            f"前提: {task.logline}\n"
            f"必ず含める語: {'、'.join(task.must_include)}\n"
            f"使ってはいけない語: {'、'.join(task.avoid)}")


def _format_findings(findings: list[dict], limit: int = 20) -> str:
    lines = []
    for item in sorted(findings, key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))[:limit]:
        lines.append(f"* [{item['severity']}] {item['check']}: {item['message_ja']}")
    if len(findings) > limit:
        lines.append(f"  （ほか {len(findings) - limit} 件）")
    return "\n".join(lines) if lines else "（所見なし）"


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped).strip()
    return stripped


def _record_once(ledger, request: GenerationRequest,
                 result: GenerationResult) -> None:
    """Record a fresh answer once.

    A response replayed from ``responses.jsonl`` during ``--resume`` already has
    its line there; appending it again would duplicate the request/response
    pairs and make the record look twice as long as the run (R-03).
    """
    if (result.provenance or {}).get("origin") == "bundle_resume":
        return
    ledger.record(request, result)


# -- stages -----------------------------------------------------------------
def run_stage_a(task: Task, provider, ledger: RunLedger, canon: Canon,
                plot: PlotDoc, scenes: SceneDoc, prompts: dict, *,
                temperature: float, seed: int, max_attempts: int) -> dict:
    findings: list[dict] = []
    report: dict | None = None
    log: GameLog | None = None
    attempts = 0
    first_findings = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        if attempt == 1:
            template = prompts["stage-a-gamelog"]
            prompt = template.render({
                "task": _task_text(task), "canon": canon_brief(canon),
                "plot": _plot_slice(plot), "scenes": _scenes_slice(scenes),
                "schema": GAMELOG_SCHEMA, "marker_contract": MARKER_CONTRACT,
            })
            purpose = "stage_a"
        else:
            template = prompts["stage-a-repair"]
            prompt = template.render({
                "findings": _format_findings(findings),
                "marker_contract": MARKER_CONTRACT,
                "schema": GAMELOG_SCHEMA,
                "previous": ledger.path.joinpath(
                    f"stage_a/attempt-{attempt - 1}.txt").read_text(encoding="utf-8"),
            })
            purpose = "stage_a:repair"
        request = GenerationRequest(
            purpose=purpose, prompt=prompt, temperature=temperature,
            max_tokens=4000, seed=seed,
            context=ledger.request_context(task_id=task.id, system=ledger.system,
                                           attempt=attempt))
        # The prompt is archived even when the operator has not answered yet,
        # so PROMPTS.md can be exported from the same self-contained bundle.
        ledger.write_text(f"stage_a/attempt-{attempt}.prompt.txt", prompt)
        result = provider.generate(request)
        _record_once(ledger, request, result)
        ledger.write_text(f"stage_a/attempt-{attempt}.txt", result.text)
        try:
            payload = json.loads(_strip_fences(result.text))
            candidate = parse_game_log(payload, ledger.path / "game_log.json")
        except (json.JSONDecodeError, GameLogError) as exc:
            findings = [{"check": "parse", "severity": "high",
                         "message_ja": f"ゲームログとして読めない: {exc}"}]
            report = None
            if attempt == 1:
                first_findings = len(findings)
            continue
        log = candidate
        report = check_game_log(log, canon, plot, scenes)
        findings = report["findings"]
        if attempt == 1:
            first_findings = len(findings)
        if not gamelog_needs_repair(findings):
            break

    if report is None:
        report = {
            "schema_version": "1.0", "tool": "game-log-check",
            "findings": findings, "checks": [], "markers": [],
            "marker_counts": {}, "allowed_dead_references": [],
            "state": {}, "summary": {"status": "unresolved", "chapters": 0,
                                     "scenes": 0, "findings": len(findings),
                                     "blocking_findings": len(findings),
                                     "by_severity": {"high": len(findings)},
                                     "by_check": {"parse": len(findings)},
                                     "checks_run": 0, "checks_skipped": 0,
                                     "markers": 0, "allowed_dead_references": 0},
        }
    report = {**report, "attempts": attempts, "repairs": max(0, attempts - 1),
              "first_attempt_findings": first_findings,
              "prompt_hashes": {name: prompts[name].digest for name in
                                ("stage-a-gamelog", "stage-a-repair")}}
    if log is not None:
        ledger.write_json("game_log.json", log.as_dict())
    ledger.write_json("game_log.report.json", report)
    return {"log": log, "report": report}


def stage_b_rewrite_prompt(prompts: dict, chapter_id: str, task: Task,
                           voice: Voice, scenes: SceneDoc, log: GameLog,
                           timeline: dict | None, canon: Canon) -> str:
    """The Stage B rewrite prompt for one chapter.

    Extracted so that the exact prompt can be exported for an operator before a
    run exists (``scripts/export_stageb_prompts.py``) without a second copy of
    the template call drifting from this one.
    """
    return prompts["stage-b-rewrite"].render({
        "chapter_id": chapter_id, "task": _task_text(task),
        "voice": _voice_slice(voice), "scene": _scene_notes(scenes, log, chapter_id),
        "game_log": _chapter_slice(log, chapter_id),
        "markers": _markers_text(log, chapter_id),
        "timeline": render_chapter_timeline(timeline or {}, chapter_id, canon),
        "target": "1 章あたり 1,000〜1,400 字を目安に書く（マーカーは字数に含めない）。",
    })


def run_stage_b_chapter(task: Task, chapter_id: str, index: int, provider,
                        ledger: RunLedger, log: GameLog, canon: Canon,
                        voice: Voice, scenes: SceneDoc, prompts: dict, *,
                        temperature: float, seed: int, max_attempts: int,
                        min_chars: int = MIN_REWRITE_CHARS,
                        timeline: dict | None = None,
                        strict_timeline: bool = False,
                        observe_surface: bool = False) -> dict:
    findings: list[dict] = []
    report: dict | None = None
    text = ""
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        if attempt == 1:
            prompt = stage_b_rewrite_prompt(prompts, chapter_id, task, voice,
                                            scenes, log, timeline, canon)
            purpose = f"stage_b:{chapter_id}"
        else:
            template = prompts["stage-b-repair"]
            prompt = template.render({
                "chapter_id": chapter_id,
                "findings": _format_findings(findings),
                "voice": _voice_slice(voice),
                "markers": _markers_text(log, chapter_id),
                "timeline": render_chapter_timeline(timeline or {}, chapter_id, canon),
                "previous": text,
            })
            purpose = f"stage_b:{chapter_id}:repair"
        request = GenerationRequest(
            purpose=purpose, prompt=prompt, temperature=temperature,
            max_tokens=2500, seed=seed + index,
            context=ledger.request_context(task_id=task.id, system=ledger.system,
                                           chapter=chapter_id, attempt=attempt))
        ledger.write_text(f"stage_b/{chapter_id}-attempt-{attempt}.prompt.txt", prompt)
        result = provider.generate(request)
        _record_once(ledger, request, result)
        ledger.write_text(f"stage_b/{chapter_id}-attempt-{attempt}.txt", result.text)
        text = clean_text(result.text)
        report = check_rewrite(text, chapter_id, log, canon, voice, scenes,
                               avoid=task.avoid, min_chars=min_chars,
                               timeline=timeline, strict_timeline=strict_timeline,
                               observe_surface=observe_surface)
        findings = report["findings"]
        if not rewrite_needs_repair(findings):
            break
    assert report is not None
    report = {**report, "attempts": attempts, "repairs": max(0, attempts - 1)}
    ledger.write_text(f"text/{chapter_id}.md", text.rstrip() + "\n")
    return {"report": report, "text": text}


# -- driver -----------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True)
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--canon", required=True, help="canon directory")
    parser.add_argument("--design-dir", required=True,
                        help="design directory with plot.json / scene.json / voice.json")
    parser.add_argument("--voice", default=None,
                        help="voice.json (default: <design-dir>/voice.json)")
    parser.add_argument("--provider", choices=["scripted", "command"], default="scripted")
    parser.add_argument("--script", default=None, help="scripted response bundle")
    parser.add_argument("--command", default=None, help="external provider command")
    parser.add_argument("--stage", choices=("both", "a", "b"), default="both",
                        help="run Stage A then B (default), Stage A only, or Stage B only")
    parser.add_argument("--game-log", default=None,
                        help="with --stage b: a verified game_log.json to rewrite "
                             "(never generated by a provider in this run)")
    parser.add_argument("--allow-unverified-log", action="store_true",
                        help="with --stage b: hand a failing game log to Stage B anyway "
                             "(recorded as unverified; not the default)")
    parser.add_argument("--out", required=True,
                        help="output directory under experiments/<id>/")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true",
                        help="resume an existing run-id in --out from its responses.jsonl")
    parser.add_argument("--allow-temp-out", action="store_true",
                        help="permit an output outside experiments/ (regression tests only)")
    parser.add_argument("--allow-config-change", action="store_true",
                        help="permit --resume with different seed/temperature/etc. "
                             "(the change is recorded in state.json)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--observe-surface", action="store_true",
                        help="record the candidate place check's observations in "
                             "each chapter report (never used as a finding or a "
                             "repair trigger; see asc.gamelog.surface)")
    parser.add_argument("--strict-timeline", action="store_true",
                        help="treat an explicit day count that contradicts the "
                             "derived timeline as a repair trigger (default: warning)")
    parser.add_argument("--min-chars", type=int, default=MIN_REWRITE_CHARS,
                        help="per-chapter length gate in characters (the prompt "
                             "target is 1,000-1,400; the default is informational)")
    parser.add_argument("--results", default=None,
                        help="write a compact, deterministic bundle summary here")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                        help="always exit 0; still report the status")
    return parser.parse_args(argv)


#: Config entries that must not change between a run and its ``--resume``.
CONFIG_COMPARE = ("task", "system", "stage", "seed", "temperature",
                  "max_attempts", "provider", "protocol_version",
                  "strict_timeline")
#: Input digests that must not change between a run and its ``--resume``.
INPUT_COMPARE = ("canon_files_sha256", "design_files_sha256",
                 "script_sha256", "game_log_sha256", "prompt_hashes")


def _config_mismatches(saved: dict, current: dict) -> dict[str, dict]:
    """Config/input entries that differ, with the recorded and current values."""
    changes: dict[str, dict] = {}
    for key in CONFIG_COMPARE + INPUT_COMPARE:
        if saved.get("config", {}).get(key) != current.get(key):
            changes[key] = {"recorded": saved.get("config", {}).get(key),
                            "current": current.get(key)}
    return changes


def _resume_command(args: argparse.Namespace, run_id: str) -> str:
    """The exact command that continues this run.

    Everything the run needs is included, because the printed command is what
    an operator copies after a ``build/`` reset (R-01). Paths stay as given so
    the command is readable; ``--resume`` re-checks them by hash.
    """
    parts = [sys.executable or "python3", "scripts/run_twostage.py",
             "--task", args.task,
             "--canon", args.canon, "--design-dir", args.design_dir]
    if args.voice:
        parts += ["--voice", args.voice]
    parts += ["--provider", args.provider]
    if args.script:
        parts += ["--script", args.script]
    if args.command:
        parts += ["--command", args.command]
    parts += ["--stage", args.stage, "--out", args.out, "--run-id", run_id,
              "--seed", str(args.seed), "--temperature", str(args.temperature),
              "--max-attempts", str(args.max_attempts)]
    if args.game_log:
        parts += ["--game-log", args.game_log]
    if args.min_chars != MIN_REWRITE_CHARS:
        parts += ["--min-chars", str(args.min_chars)]
    if args.strict_timeline:
        parts.append("--strict-timeline")
    if args.observe_surface:
        parts.append("--observe-surface")
    if args.allow_unverified_log:
        parts.append("--allow-unverified-log")
    if args.allow_temp_out:
        parts.append("--allow-temp-out")
    if args.results:
        parts += ["--results", args.results]
    parts.append("--resume")
    return shlex.join(parts)


def _limits(stage: str) -> list[str]:
    return LIMITS + ([STAGE_B_LIMIT] if stage == "b" else [])


def _write_state(ledger, *, status: str, config: dict, pending: dict | None,
                 args: argparse.Namespace, resume_count: int = 0,
                 error: str | None = None,
                 config_changes: dict | None = None,
                 game_log_source: str | None = None) -> None:
    """Always leave a resumable ``state.json`` (R-02).

    A failed or unresolved run must still say what it was doing and how to
    continue; otherwise a partial ``responses.jsonl`` cannot be picked up.
    """
    payload: dict = {
        "schema": "trpg-slice-state-v1", "run_id": ledger.run_id,
        "status": status, "config": config, "pending": pending,
        "stage": args.stage, "argv": list(sys.argv[1:]),
        "resume_count": resume_count,
        "resume_command": _resume_command(args, ledger.run_id),
        "game_log_source": game_log_source,
    }
    if error:
        payload["error"] = error
    if config_changes:
        payload["config_changes"] = config_changes
    ledger.write_json("state.json", payload)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        out_root = validate_out(Path(args.out), allow_temp=args.allow_temp_out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.stage == "b" and not args.game_log:
        print("error: --stage b requires --game-log (Stage A is not run)", file=sys.stderr)
        return 2
    if args.stage != "b" and args.game_log:
        print("error: --game-log needs --stage b (Stage A generates its own log)",
              file=sys.stderr)
        return 2
    try:
        tasks = load_tasks(args.tasks_file)
        task = tasks.get(args.task)
        canon = load_canon(args.canon)
        design_dir = Path(args.design_dir)
        plot = load_plot(design_dir / "plot.json")
        scenes = load_scenes(design_dir / "scene.json")
        voice_path = Path(args.voice) if args.voice else design_dir / "voice.json"
        voice = load_voice(voice_path)
        scope = load_evaluation_scope()
        prompts = {name: load_prompt(name) for name in PROMPT_NAMES}
    except (TaskError, CanonError, EvaluationScopeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # The design documents must be clean under *this* canon before their
    # disclosure plan is used to judge a game log.
    design_reports = {"plot": check_plot(plot, canon), "scene": check_scenes(scenes, canon)}
    design_findings = {name: [item for item in report["findings"]
                              if item["severity"] in {"high", "medium"}]
                       for name, report in design_reports.items()}
    if any(design_findings.values()):
        for name, items in design_findings.items():
            for item in items:
                print(f"error: design/{name}: {item['message_ja']}", file=sys.stderr)
        return 2

    try:
        if args.provider == "scripted":
            if not args.script:
                raise ProviderError("--provider scripted requires --script")
            delegate = ScriptedProvider(load_script_bundle(args.script))
            script_path = Path(args.script)
        else:
            if not args.command:
                raise ProviderError("--provider command requires --command")
            delegate = CommandProvider(args.command, model="external")
            script_path = None
    except (ProviderError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    config = {
        "task": task.id, "system": SYSTEM, "stage": args.stage, "seed": args.seed,
        "temperature": args.temperature, "provider": args.provider,
        "strict_timeline": bool(args.strict_timeline),
        "observe_surface": bool(args.observe_surface),
        "max_attempts": args.max_attempts,
        "protocol_version": tasks.protocol,
        "canon_files_sha256": _sha256_tree(Path(args.canon)),
        "design_files_sha256": _sha256_tree(design_dir),
        "script_sha256": _sha256_file(script_path) if script_path else None,
        "game_log_sha256": (_sha256_file(Path(args.game_log))
                            if args.game_log else None),
        "prompt_hashes": {name: prompts[name].digest for name in PROMPT_NAMES},
    }
    recorded: list[dict] = []
    resume_count = 0
    config_changes: dict[str, dict] = {}
    if args.resume:
        if not args.run_id:
            print("error: --resume requires --run-id", file=sys.stderr)
            return 2
        run_path = out_root / args.run_id
        state_path = run_path / "state.json"
        log_path = run_path / "responses.jsonl"
        if not state_path.is_file():
            print("error: --resume needs state.json in the run "
                  "(a failed run now writes one; older runs may not have it)",
                  file=sys.stderr)
            return 2
        try:
            saved = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read state.json: {exc}", file=sys.stderr)
            return 2
        changes = _config_mismatches(saved, config)
        if changes and not args.allow_config_change:
            for key, diff in changes.items():
                label = ("input hash mismatch on resume"
                         if key in INPUT_COMPARE else "config mismatch on resume")
                print(f"error: {label}: {key} "
                      f"(recorded {diff['recorded']!r}, current {diff['current']!r})",
                      file=sys.stderr)
            print("error: refusing to resume with different conditions "
                  "(pass --allow-config-change to continue and record the change)",
                  file=sys.stderr)
            return 2
        if changes:
            config_changes = changes
        try:
            if log_path.is_file():
                recorded = [json.loads(line) for line in
                            log_path.read_text(encoding="utf-8").splitlines()
                            if line.strip()]
                # Keep the record: rewrite the same entries (atomically) instead
                # of truncating, so an interrupted resume cannot lose them (R-03).
                staged = run_path / "responses.jsonl.staged"
                staged.write_text("".join(
                    json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
                    for entry in recorded), encoding="utf-8")
                os.replace(staged, log_path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read responses.jsonl: {exc}", file=sys.stderr)
            return 2
        resume_count = int(saved.get("resume_count") or 0) + 1
        ledger = RunLedger(root=out_root, run_id=args.run_id, task_id=task.id,
                           system=SYSTEM, seed=args.seed,
                           protocol_version=tasks.protocol, model=delegate.model,
                           provider=delegate.name, temperature=args.temperature)
        ledger.path.mkdir(parents=True, exist_ok=True)
    else:
        try:
            ledger = RunLedger.create(
                out_root, task_id=task.id, system=SYSTEM, seed=args.seed,
                protocol_version=tasks.protocol, run_id=args.run_id,
                model=delegate.model, provider=delegate.name,
                temperature=args.temperature)
        except FileExistsError:
            print(f"error: run already exists: {out_root / str(args.run_id)} "
                  "(use --resume or a new --run-id)", file=sys.stderr)
            return 2
    provider = BundleProvider(delegate, recorded) if recorded else delegate

    # Archive the immutable inputs inside the bundle.
    if not args.resume:
        shutil.copytree(args.canon, ledger.path / "inputs" / "canon", dirs_exist_ok=True)
        shutil.copytree(design_dir, ledger.path / "inputs" / "design",
                        dirs_exist_ok=True)
        if script_path:
            shutil.copy2(script_path, ledger.path / "inputs" / "scripted.json")
        if args.game_log:
            shutil.copy2(args.game_log, ledger.path / "inputs" / "game_log.input.json")

    for template in prompts.values():
        ledger.prompt_hashes[template.name] = template.digest
    ledger.write_json("design.report.json", {
        "status": "clean",
        "note": "check_plot / check_scenes を現行 canon に対して再実行した結果。",
        "plot": {"checks_failed": design_reports["plot"]["summary"]["checks_failed"],
                 "findings": design_reports["plot"]["findings"]},
        "scene": {"checks_failed": design_reports["scene"]["summary"]["checks_failed"],
                  "findings": design_reports["scene"]["findings"]},
    })

    summary: dict = {
        "run_id": ledger.run_id, "task": task.id, "system": SYSTEM,
        "stage": args.stage,
        "provider": {"name": delegate.name, "model": delegate.model,
                     "model_version": delegate.model_version},
        "protocol_note": "protocol-v1 の系 (S0-S3) を変更しない配線確認。",
        "inputs": {"canon_files_sha256": config["canon_files_sha256"],
                   "design_files_sha256": config["design_files_sha256"],
                   "script_sha256": config["script_sha256"],
                   "game_log_sha256": config["game_log_sha256"]},
        "evaluation_scope": {
            "mode": scope.get("mode"), "active_layers": scope.get("active_layers"),
            "frozen_layers": sorted(scope.get("frozen_layers", {})),
            "gate_status": scope.get("gate_status"), "claims": scope.get("claims"),
        },
        "resume_count": resume_count,
    }
    if config_changes:
        summary["config_changes"] = config_changes

    stage_b_reports: dict[str, dict] = {}
    timeline: dict | None = None
    pending: dict | None = None
    status = "clean"
    game_log_source = None
    provided_log = None
    provided_report = None

    if args.stage == "b":
        # Stage B only: the log comes from a file and is re-verified here, so a
        # Stage A response is never fabricated just to reach the rewrite (P0-7).
        try:
            raw = json.loads(Path(args.game_log).read_text(encoding="utf-8"))
            provided_log = parse_game_log(raw, ledger.path / "game_log.json")
        except (OSError, json.JSONDecodeError, GameLogError) as exc:
            error = f"cannot load --game-log {args.game_log}: {exc}"
            print(f"error: {error}", file=sys.stderr)
            _write_state(ledger, status="failed", config=config, pending=None,
                         args=args, resume_count=resume_count, error=error,
                         config_changes=config_changes, game_log_source=args.game_log)
            ledger.fail(error)
            return 2
        provided_report = check_game_log(provided_log, canon, plot, scenes)
        if provided_report["summary"]["status"] != "clean":
            # Recorded in the report itself, so an overridden run cannot look
            # like a verified one later.
            provided_report["unverified"] = True
        game_log_source = "provided"
        ledger.write_json("game_log.json", provided_log.as_dict())
        ledger.write_json("game_log.report.json", {
            **provided_report, "source": "provided",
            "source_path": Path(args.game_log).name,
            "attempts": 0, "repairs": 0,
            "first_attempt_findings": provided_report["summary"]["findings"],
        })
        summary["stage_a"] = {
            "status": provided_report["summary"]["status"], "source": "provided",
            "attempts": 0, "repairs": 0,
            "first_attempt_findings": provided_report["summary"]["findings"],
            "findings": provided_report["summary"]["findings"],
            "checks": [{"id": c["id"], "status": c["status"],
                        "findings": c["findings"]} for c in provided_report["checks"]],
            "markers": provided_report["summary"]["markers"],
            "marker_counts": provided_report["marker_counts"],
            "allowed_dead_references": provided_report["allowed_dead_references"],
        }
        if (provided_report["summary"]["status"] != "clean"
                and not args.allow_unverified_log):
            error = ("the provided game log does not pass check_game_log; "
                     "Stage B is fail-closed (pass --allow-unverified-log to override)")
            print(f"error: {error}", file=sys.stderr)
            summary["stage_b"] = {"status": "skipped", "reason": error}
            summary["status"] = "unresolved"
            summary["gates"] = {"stage_a_clean": False, "stage_b_clean": False}
            summary["limits"] = _limits(args.stage) + [
        "時間の厳密判定はログ側だけ。本文は明示された日数だけを導出表と照合し、"
        "抽象表現（しばらく・明け方）と書かれていない誤りは対象外。"
        + ("（--strict-timeline: 不一致は修復対象）" if args.strict_timeline
           else "（既定: 不一致は警告で修復しない）"),
    ]
            ledger.write_json("run-summary.json", summary)
            _write_state(ledger, status="unresolved", config=config, pending=None,
                         args=args, resume_count=resume_count, error=error,
                         config_changes=config_changes, game_log_source=game_log_source)
            ledger.finish("unresolved")
            if args.results:
                _write_results(Path(args.results), summary, prompts)
            if not args.quiet:
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            if args.report_only:
                return 0
            return 2
        if provided_report["summary"]["status"] != "clean":
            summary["stage_a"]["unverified"] = True

    try:
        if provided_log is None:
            stage_a = run_stage_a(task, provider, ledger, canon, plot, scenes, prompts,
                                  temperature=args.temperature, seed=args.seed,
                                  max_attempts=args.max_attempts)
        else:
            stage_a = {"log": provided_log, "report": {
                **provided_report, "attempts": 0, "repairs": 0,
                "first_attempt_findings": provided_report["summary"]["findings"],
                "source": "provided"}}
    except ResponsePendingError as exc:
        pending = {"key": exc.key, "purpose": exc.purpose,
                   "prompt_hash": exc.prompt_hash, "response_path": exc.response_path}
        stage_a = None
    except ProviderError as exc:
        error = str(exc)
        print(f"error: {error}", file=sys.stderr)
        _write_state(ledger, status="failed", config=config, pending=None,
                     args=args, resume_count=resume_count, error=error,
                     config_changes=config_changes, game_log_source=game_log_source)
        ledger.fail(error)
        return 2

    if pending:
        status = "pending"
        _write_prompts(ledger, pending, prompts)
    else:
        assert stage_a is not None
        log = stage_a["log"]
        a_report = stage_a["report"]
        summary["stage_a"] = {
            "status": a_report["summary"]["status"],
            "source": a_report.get("source", "generated"),
            "attempts": a_report["attempts"], "repairs": a_report["repairs"],
            "first_attempt_findings": a_report["first_attempt_findings"],
            "findings": a_report["summary"]["findings"],
            "checks": [{"id": c["id"], "status": c["status"],
                        "findings": c["findings"]} for c in a_report["checks"]],
            "markers": a_report["summary"]["markers"],
            "marker_counts": a_report["marker_counts"],
            "allowed_dead_references": a_report["allowed_dead_references"],
        }
        if a_report.get("unverified"):
            summary["stage_a"]["unverified"] = True
        if log is not None:
            # Settled numbers: prose may omit them, but not contradict them.
            timeline = derive_timeline(log, canon, build_world(canon))
            ledger.write_json("timeline.json", timeline)
        if log is None or (a_report["summary"]["status"] != "clean"
                           and not args.allow_unverified_log):
            status = "unresolved"
            summary["stage_b"] = {"status": "skipped",
                                  "reason": "Stage A のゲームログが検証を通らなかった。"}
        elif args.stage == "a":
            summary["stage_b"] = {"status": "skipped",
                                  "reason": "--stage a（Stage A のみ実行）"}
        else:
            try:
                for index, chapter in enumerate(log.chapters, start=1):
                    result = run_stage_b_chapter(
                        task, chapter.id, index, provider, ledger, log, canon,
                        voice, scenes, prompts, temperature=args.temperature,
                        seed=args.seed, max_attempts=args.max_attempts,
                        min_chars=args.min_chars, timeline=timeline,
                        strict_timeline=args.strict_timeline,
                        observe_surface=args.observe_surface)
                    stage_b_reports[chapter.id] = result["report"]
                    if result["report"]["summary"]["status"] != "clean":
                        status = "unresolved"
            except ResponsePendingError as exc:
                pending = {"key": exc.key, "purpose": exc.purpose,
                           "prompt_hash": exc.prompt_hash,
                           "response_path": exc.response_path}
                status = "pending"
                _write_prompts(ledger, pending, prompts)
            except ProviderError as exc:
                error = str(exc)
                print(f"error: {error}", file=sys.stderr)
                _write_state(ledger, status="failed", config=config, pending=None,
                             args=args, resume_count=resume_count, error=error,
                             config_changes=config_changes,
                             game_log_source=game_log_source)
                ledger.fail(error)
                return 2
            all_chapters = bool(log.chapters) and len(stage_b_reports) == len(log.chapters)
            # A required word that never appears in the whole work is a Stage B
            # failure even when every chapter's own checks passed (B-06).
            joined = "\n\n".join(
                path.read_text(encoding="utf-8") for path in
                sorted((ledger.path / "text").glob("*.md")))
            missing_words = missing_must_include(joined, task.must_include)
            stage_b_status = (
                "pending" if pending else
                "clean" if all_chapters and all(
                    r["summary"]["status"] == "clean"
                    for r in stage_b_reports.values()) else "unresolved")
            if missing_words and not pending:
                # Every chapter may pass while the work still misses a required
                # word; that is a Stage B failure, not a chapter-level one.
                stage_b_status = "unresolved"
            ledger.write_json("rewrite.report.json", {
                "status": stage_b_status, "chapters": stage_b_reports,
                "missing_must_include": missing_words,
            })
            if summary["stage_a"].get("unverified"):
                # Stage B ran from a log that did not pass: never report clean.
                status = "unresolved"
            if stage_b_status == "unresolved":
                status = "unresolved"
            summary["stage_b"] = {
                "status": stage_b_status,
                "missing_must_include": missing_words,
                "chapters": [{
                    "id": cid, "status": report["summary"]["status"],
                    "attempts": report["attempts"], "repairs": report["repairs"],
                    "chars": report["summary"]["chars"],
                    "findings": report["summary"]["findings"],
                    "expected_markers": report["summary"]["expected_markers"],
                    "found_markers": report["summary"]["found_markers"],
                    "allowed_dead_references": report["allowed_dead_references"],
                } for cid, report in stage_b_reports.items()],
            }

    if timeline is not None:
        summary["timeline"] = _timeline_summary(timeline)
        summary["timeline"]["strict"] = bool(args.strict_timeline)
    if status != "pending":
        summary["l1_hygiene"] = _l1_hygiene(ledger, task, args.min_chars)
    summary["provider"]["observed"] = _observed_models(ledger)
    if isinstance(provider, BundleProvider):
        summary["replay"] = provider.report()
        ledger.write_json("replay.report.json", summary["replay"])
    summary["status"] = status
    summary["gates"] = {
        "stage_a_clean": summary.get("stage_a", {}).get("status") == "clean",
        "stage_b_clean": summary.get("stage_b", {}).get("status") == "clean",
    }
    summary["limits"] = _limits(args.stage) + [
        "時間の厳密判定はログ側だけ。本文は明示された日数だけを導出表と照合し、"
        "抽象表現（しばらく・明け方）と書かれていない誤りは対象外。"
        + ("（--strict-timeline: 不一致は修復対象）" if args.strict_timeline
           else "（既定: 不一致は警告で修復しない）"),
    ]
    ledger.write_json("run-summary.json", summary)
    _write_state(ledger, status=status, config=config, pending=pending, args=args,
                 resume_count=resume_count, error=None,
                 config_changes=config_changes or None,
                 game_log_source=game_log_source)
    if args.results and status != "pending":
        _write_results(Path(args.results), summary, prompts)
    ledger.finish("ok" if status == "clean" else status)
    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.report_only:
        return 0
    if status == "pending":
        return 3
    return 0 if status == "clean" else 1


def _write_prompts(ledger: RunLedger, pending: dict, prompts: dict) -> None:
    """Export the pending request into the same self-contained bundle."""
    lines = [
        "# 未回答のリクエスト (Stage A/B)",
        "",
        f"run: `{ledger.path.name}` / key: `{pending['key']}` / "
        f"purpose: `{pending['purpose']}` / prompt_hash: `{pending['prompt_hash']}`",
        "",
        f"回答は `{pending['response_path']}` に `{{\"text\": \"...\"}}` の JSON で置く。"
        "プロンプトが変わった回答は stale として拒否される。",
        "",
    ]
    files = sorted(ledger.path.rglob("*.prompt.txt"))
    answered = 0
    shown: list[Path] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        # Only the request that has no answer yet. A prompt whose digest is not
        # the pending one was already served; listing it invites the operator to
        # answer the wrong question (R-08).
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        if pending.get("prompt_hash") and text_hash == pending["prompt_hash"]:
            shown.append(path)
        else:
            answered += 1
    if not shown:
        shown = files  # hash mismatch everywhere: show all rather than nothing
        answered = 0
    if answered:
        lines += [f"回答済みのプロンプト {answered} 件は省略した。", ""]
    for path in shown:
        relative = path.relative_to(ledger.path).as_posix()
        lines += ["## " + relative, "", "```text",
                  path.read_text(encoding="utf-8").rstrip(), "```", ""]
    lines += ["同じバンドルへ回答を置いたら `state.json` の `resume_command` を実行する。",
              ""]
    ledger.write_text("PROMPTS.md", "\n".join(lines))


def _l1_hygiene(ledger: RunLedger, task: Task,
                min_chars: int = MIN_REWRITE_CHARS) -> dict:
    """Deterministic L1 bookkeeping (no quality judgement)."""
    text_dir = ledger.path / "text"
    bodies = [path.read_text(encoding="utf-8")
              for path in sorted(text_dir.glob("*.md"))] if text_dir.is_dir() else []
    joined = "\n\n".join(bodies)
    chars = len(re.sub(r"\s", "", re.sub(r"\{\{[^{}]*\}\}", "", joined)))
    hits = {term: term in joined for term in task.must_include}
    audit = None
    if bodies and (ledger.path / "inputs" / "canon").is_dir():
        audit = audit_texts(ledger.path / "inputs" / "canon", text_dir)
        ledger.write_json("audit.json", audit)
    return {
        "chars": chars,
        "chapters": len(bodies),
        "must_include": {"hits": hits,
                         "rate": round(sum(hits.values()) / len(hits), 3) if hits else 1.0},
        "task_avoid_hits": {term: joined.count(term) for term in task.avoid},
        "length_gate": {
            "min_chars": min_chars,
            "target_ja": "1 章 1,000〜1,400 字（プロンプトの目安）",
            "gate_note": ("既定の 200 字は空文の検出用。目標長は合否に使っておらず、"
                          "下回っても clean になりうる（P1-8）。"),
        },
        "continuity": (None if audit is None else {
            "violations": audit["summary"]["violations"],
            "by_type": audit["summary"]["by_type"],
            "by_severity": audit["summary"]["by_severity"],
            "checks_skipped": audit["summary"]["checks_skipped"],
            "ced_per_10k_chars": audit["summary"]["ced_per_10k_chars"],
            "note": ("name_mention による dead_character_reappears (medium) は"
                     "既存監査器の既知の限界。Stage B では宣言済みの"
                     "record_reference / memory_mention として許容している。"),
        }),
    }


#: What a summary may claim, per provider. A relay run is a real response but not
#: a reproducible model, so the scripted wording must not be reused for it.
CLAIMS = {
    "scripted": ("fixed scripted wiring check; not a model response, not evidence "
                 "of story quality or of any L1 improvement over direct generation"),
    "command": ("relay run: the prose was written by an external operator, so it is "
                "not a reproducible model and G5 is not claimed; L1 structure and "
                "hygiene only, not evidence of story quality"),
}
STAGE_B_CLAIM = ("; the game log is a supplied input, not this run's model output")


def _observed_models(ledger) -> list[dict]:
    """Distinct ``(model, model_version)`` seen in the recorded responses."""
    path = ledger.path / "responses.jsonl"
    if not path.is_file():
        return []
    seen: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        response = (json.loads(line).get("response") or {})
        item = {"model": response.get("model"),
                "model_version": response.get("model_version")}
        if item not in seen:
            seen.append(item)
    return seen


def _timeline_summary(timeline: dict) -> dict:
    """A deterministic digest of the settled numbers, for ``results.json``."""
    chapters = [{
        "id": row["id"], "day": row["day"], "location": row["location"],
        "elapsed_since_previous": row["elapsed_since_previous"],
        "days": {item["id"]: {"leaving": item["days_since_leaving_here"],
                              "arriving": item["days_since_arriving_here"]}
                 for item in row["characters"]},
    } for row in timeline.get("chapters", [])]
    canonical = json.dumps(timeline, ensure_ascii=False, sort_keys=True)
    return {"schema": timeline.get("schema"),
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "chapters": chapters}


def _write_results(path: Path, summary: dict, prompts: dict) -> None:
    """Compact, timestamp-free summary suitable for committing to a bundle."""
    provider = summary["provider"]["name"]
    claim = CLAIMS.get(provider, CLAIMS["scripted"])
    if summary.get("stage") == "b":
        claim += STAGE_B_CLAIM
    payload = {
        "schema": "trpg-slice-wiring-v1",
        "claim": claim,
        "scope": "Arena.ai x L1; L2/L3 frozen_not_measured",
        "evaluation_scope": summary["evaluation_scope"],
        "provider": summary["provider"],
        "prompt_hashes": {name: prompts[name].digest for name in PROMPT_NAMES},
        "inputs": summary["inputs"],
        "stage_a": {key: summary["stage_a"][key] for key in
                    ("status", "attempts", "repairs", "first_attempt_findings",
                     "findings", "checks", "markers", "marker_counts")},
        "stage_a_allowed_dead_references": summary["stage_a"]["allowed_dead_references"],
        "stage_b": summary["stage_b"],
        "timeline": summary.get("timeline"),
        "l1_hygiene": summary["l1_hygiene"],
        "status": summary["status"],
        "limits": summary["limits"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
