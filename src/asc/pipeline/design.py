"""The Design step: design documents the checkers accept.

Between Plan and Draft, S1 asks the model for the design documents the
thirteen skills define (brief, world, history, characters, relations, plot,
scenes, voice) and validates each with its checker — against the canon where
the skill cross-references it. A document that fails is sent back with the
findings, at most ``max_attempts`` times.

Two skills are *not* produced here: ``interactive-branch`` and ``adaptation``
belong to other pipelines (a gamebook, an adaptation), not to a linear
short story. They stay connected through their own checkers, not this stage.

The stage is fail-open by design: a document that still fails after its
repairs is recorded as ``unresolved`` (or ``missing`` when unparseable) and
the run continues. Failing the whole run on a short voice sample would waste
every generation before it and teach the analysis nothing; the design report
records what held and what did not, so the experiment can condition on it.
Only a provider failure stops the run.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..story.canon import Canon
from .draft import canon_brief
from .llm import GenerationRequest, Provider
from .prompts import PromptTemplate, load_prompt
from .run import RunLedger
from .tasks import Task

TITLE = "Design"

#: documents in dependency order; each may read the ones before it
DOCS = ("brief", "world", "history", "character", "relation", "plot",
        "scene", "voice")

#: findings at or above this severity send a document back for repair
REPAIR_SEVERITIES = {"high", "medium"}

DESIGN_SCHEMAS = {
    "brief": """\
{
  "logline": "一文のログライン（20〜300字。elements の各文字列を一字一句そのまま含める）",
  "premise": "前提の要約",
  "theme": "主題を対立命題の形で（例: 務め対情）",
  "elements": {"who": "誰", "where": "どこ", "wants": "望み", "obstacle": "妨げ"},
  "similar": [
    {"title": "類似作の題名", "axis": "structure / character / world のいずれか", "difference": "10字以上の差分"}
  ],
  "prohibitions": [
    {"rule": "禁止条件", "check_ja": "後工程での確認方法"}
  ],
  "failure_questions": ["検証可能な問いの形（〜か？）"],
  "genre": "ジャンル", "audience": "想定読者"
}
similar は 3 件以上。禁止条件には確認方法を添える。""",
    "world": """\
{
  "axioms": ["変えてはいけない前提（1件以上）"],
  "rules": [
    {"id": "rule-1", "statement": "規則", "cost": "代償・制約",
     "constraint": "制約の詳細", "exception": "例外",
     "exception_condition": "例外が起きる条件"}
  ],
  "institutions": [{"name": "組織・制度", "role": "役割"}],
  "geography": ["canon の場所 ID と一致させる"],
  "disclosure": [{"info": "開示する情報", "chapter": "実在する章 ID"}],
  "notes": ""
}
すべての規則にコストを書く。例外には条件を書く（無条件の抜け道は不可）。
地名は canon の場所と対応させる。開示計画の章は実在する章にする。""",
    "history": """\
{
  "eras": [{"id": "era-1", "name": "時代名", "begins": -100, "ends": 0}],
  "events": [
    {"id": "ev-1", "year": -50, "title": "出来事", "cause": "原因となった出来事のID",
     "effect": "結果", "trace": "現在に残る痕跡", "era": "era-1"}
  ],
  "sources": [
    {"id": "src-1", "kind": "正史か異説か", "holder": "保持者",
     "origin": "由来", "citation": "引用"}
  ],
  "apocrypha": ["異説として扱う言い伝え"],
  "knowledge": {"人物ID": {"knows": ["ev-1"], "unknown": ["ev-2"]}},
  "notes": ""
}
出来事は年代順。原因の参照は実在の出来事を指し、年代が前後しない。
すべての出来事に痕跡を書く。正史と異説を分ける。
知識地図の人物は canon に、出来事は年表に存在させる。""",
    "character": """\
{
  "characters": [
    {"id": "canon の人物ID", "want": "失いたくないもの",
     "need": "本当に必要なもの（WANT と別文）",
     "fear": "恐れ", "wound": "傷", "secret": "秘密",
     "principle": "行動原理", "self_view": "自己像",
     "others_view": ["誰から見れば〜"],
     "predictions": [
       {"situation": "状況", "choice": "選択"},
       {"situation": "別の状況", "choice": "選択"},
       {"situation": "さらに別の状況", "choice": "選択"}
     ],
     "speech": {"sample": "口調サンプル（30字以上）",
                "vocab": ["使う語"], "avoid": ["避ける語"]},
     "arc": {"endpoint": "アークの終点",
             "changed": ["変わる選択"], "unchanged": ["変わらない選択"]},
     "bans": ["らしくない言動"]}
  ]
}
WANT と NEED は別文。予測は 3 件。口調サンプルは 30 字以上。
人物 ID は canon に存在させる。主要人物は全員書く。""",
    "relation": """\
{
  "pairs": [
    {"a": "人物ID", "b": "人物ID",
     "public": "表向きの関係", "stakes": "実際の利害",
     "conflict": "両立しない目的"}
  ],
  "knowledge": [
    {"character": "人物ID", "fact": "事実ID",
     "state": "knows / unknown / suspects"}
  ],
  "changes": [
    {"pair": ["人物ID", "人物ID"], "chapter": "章ID",
     "trigger": "変化の契機（選択と行動）", "after": "変化後の関係"}
  ],
  "silences": [
    {"chapter": "章ID", "who": "人物ID", "unsaid_ja": "言わないこと"}
  ]
}
両立しない目的を 1 件以上書く。人物・事実・章は canon に存在させる。
canon で既知の事実を unknown と主張しない。
変化の相手は関係表にある相手にする。沈黙には言わないことを書く。""",
    "plot": """\
{
  "logline": "一文のログライン",
  "acts": [{"id": "setup", "chapters": ["ch01"], "question": "この幕が問うもの"}],
  "turns": [
    {"id": "t1", "chapter": "章ID",
     "choice_ja": "主人公の選択（出来事ではなく選択で書く）",
     "point_of_no_return": "引き返せなくなる点"}
  ],
  "subplots": [
    {"id": "ledger", "beats": ["起動", "干渉", "決着"],
     "converges": "本筋と交わる点"}
  ],
  "ending": {"kind": "resolved / bittersweet / open",
             "summary": "結末の要約", "aftertaste_ja": "読後に残るもの"},
  "unresolved": [
    {"item": "未回収の内容", "foreshadowing": "布石ID", "intentional": false}
  ]
}
転換点は 3〜5 件。幕は章を過不足なく覆う。副筋に節目と合流を書く。
未回収は布石に結び付けるか、意図的（intentional: true）と宣言する。""",
    "scene": """\
{
  "scenes": [
    {"id": "s01", "chapter": "章ID",
     "purpose": "目的（1文）", "conflict": "対立（1文）", "change": "変化（1文）",
     "tension": "suspense / curiosity / surprise / irony / deadline / quiet",
     "knowledge": [
       {"character": "人物ID", "entry": ["入場時の既知の事実ID"],
        "gained": ["場面で得る事実ID"]}
     ],
     "disclosure": {"disclosed": ["開示する事実ID"],
                    "withheld": [{"fact": "事実ID", "reason": "伏せる理由"}]},
     "foreshadows": {"planted": [{"id": "新規の布石ID", "payoff": "回収予定の章"}],
                     "paid": ["回収する canon の布石ID"]}
    }
  ]
}
全章に場面を置く。得た事実は開示か保留のどちらかに置く。
回収は実在の布石を指し、仕掛けより前に置かない。""",
    "voice": """\
{
  "viewpoint": {"person": "first / third", "character": "視点人物の名",
                "aliases": ["別名"], "pronouns": ["一人称の自称"]},
  "narrator": {"knows_ja": "語り手が知りうる範囲"},
  "sample": "文体の固定サンプル",
  "banned": [{"id": "b1", "pattern": "禁止表現", "message_ja": "理由"}],
  "notes": ""
}
視点人物を定め、語り手の知りうる範囲を書く。一人称なら自称を宣言する。
本文がまだ無いため、本文の検査は後工程に委ね、ここでは構造だけを見る。""",
}


class DesignError(RuntimeError):
    """Raised when the provider fails mid-design (the run is kept)."""


@dataclass(frozen=True)
class DocResult:
    name: str
    status: str  # clean | unresolved | missing
    attempts: int
    findings: tuple[dict, ...] = ()
    checks_failed: int = 0
    first_attempt_findings: tuple[dict, ...] = ()
    first_attempt_checks_failed: int = 0

    def as_dict(self) -> dict:
        by_severity: dict[str, int] = {}
        for item in self.findings:
            by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
        first_by_severity: dict[str, int] = {}
        for item in self.first_attempt_findings:
            severity = item["severity"]
            first_by_severity[severity] = first_by_severity.get(severity, 0) + 1
        return {"status": self.status, "attempts": self.attempts,
                "repairs": max(0, self.attempts - 1),
                "findings": len(self.findings), "by_severity": by_severity,
                "checks_failed": self.checks_failed,
                "first_attempt_findings": len(self.first_attempt_findings),
                "first_attempt_by_severity": first_by_severity,
                "first_attempt_checks_failed": self.first_attempt_checks_failed}


@dataclass(frozen=True)
class Design:
    task_id: str
    docs: tuple[DocResult, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        by_severity: dict[str, int] = {}
        for doc in self.docs:
            for item in doc.findings:
                by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
        return {
            "task": self.task_id,
            "docs": {doc.name: doc.as_dict() for doc in self.docs},
            "unresolved": [doc.name for doc in self.docs
                            if doc.status == "unresolved"],
            "missing": [doc.name for doc in self.docs
                        if doc.status == "missing"],
            "findings": sum(len(doc.findings) for doc in self.docs),
            "by_severity": by_severity,
            "attempts": sum(doc.attempts for doc in self.docs),
            "repairs": sum(max(0, doc.attempts - 1) for doc in self.docs),
            "first_attempt_findings": sum(
                len(doc.first_attempt_findings) for doc in self.docs),
        }


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped).strip()
    return stripped


def _format_findings(items: list[dict], limit: int = 20) -> str:
    lines = []
    for item in items[:limit]:
        lines.append(f"* [{item['severity']}] {item['check']}: "
                     f"{item['message_ja']}")
    if len(items) > limit:
        lines.append(f"  （ほか {len(items) - limit} 件）")
    return "\n".join(lines) if lines else "（所見なし）"


def _validate_doc(name: str, path: Path, canon: Canon | None) -> tuple[list[dict], int]:
    """Load and check one design document. Returns (findings, checks_failed).

    Structural errors raise ValueError, which the caller turns into a repair
    round. Voice has no manuscript to check yet, so only its design-time
    viewpoint/sample/ban contracts are checked here; text checks are deferred.
    """
    if name == "brief":
        from ..brief import check_brief, load_brief
        report = check_brief(load_brief(path))
    elif name == "world":
        from ..world import check_world, load_world
        report = check_world(load_world(path), canon)
    elif name == "history":
        from ..history import check_history, load_history
        report = check_history(load_history(path), canon)
    elif name == "character":
        from ..character import check_characters, load_characters
        report = check_characters(load_characters(path), canon)
    elif name == "relation":
        from ..relation import check_relations, load_relations
        report = check_relations(load_relations(path), canon)
    elif name == "plot":
        from ..plot import check_plot, load_plot
        report = check_plot(load_plot(path), canon)
    elif name == "scene":
        from ..scene import check_scenes, load_scenes
        report = check_scenes(load_scenes(path), canon)
    elif name == "voice":
        from ..style import load_voice
        voice = load_voice(path)  # manuscript checks are deferred to the draft
        findings = []
        if voice.person == "first" and not voice.pronouns:
            findings.append({
                "check": "viewpoint_declared", "severity": "medium",
                "message_ja": "一人称の自称（pronouns）を宣言する。",
            })
        if not voice.sample:
            findings.append({
                "check": "sample_declared", "severity": "medium",
                "message_ja": "文体の固定サンプル（sample）を書く。",
            })
        for banned in voice.banned:
            if not banned.message_ja.strip():
                findings.append({
                    "check": "banned_reason", "severity": "medium",
                    "message_ja": f"禁止表現 {banned.id} に理由（message_ja）を書く。",
                })
        failed = len({item["check"] for item in findings})
        return findings, failed
    else:  # pragma: no cover - DOCS is fixed
        raise ValueError(f"unknown design document: {name}")
    failed = sum(1 for check in report["checks"] if check["status"] == "fail")
    return list(report["findings"]), failed


def _needs_repair(findings: list[dict]) -> bool:
    return any(item["severity"] in REPAIR_SEVERITIES for item in findings)


def _render_prior(accepted: dict[str, str]) -> str:
    if not accepted:
        return "（先行する設計書なし）"
    parts = []
    for name in DOCS:
        if name in accepted:
            parts.append(f"### {name}\n```json\n{accepted[name]}\n```")
    return "\n\n".join(parts)


def build_design(task: Task, provider: Provider, ledger: RunLedger,
                 canon: Canon, *,
                 prompt_dir: str | Path | None = None,
                 temperature: float = 0.6, max_tokens: int = 2000,
                 seed: int = 0, max_attempts: int = 2,
                 docs: tuple[str, ...] = DOCS) -> Design:
    """Generate and validate the design documents, in dependency order."""
    for name in docs:
        if name not in DOCS:
            raise DesignError(f"unknown design document: {name}")
    templates = {name: load_prompt(f"design-{name}", prompt_dir) for name in docs}
    repair = load_prompt("design-repair", prompt_dir)
    for template in list(templates.values()) + [repair]:
        ledger.prompt_hashes[template.name] = template.digest

    design_dir = ledger.path / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    accepted: dict[str, str] = {}
    results: list[DocResult] = []

    for name in docs:
        template = templates[name]
        findings: list[dict] = []
        checks_failed = 0
        first_findings: list[dict] = []
        first_checks_failed = 0
        last_text = ""
        attempts = 0
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            if attempt == 1:
                prompt = template.render({
                    "title": task.title_ja, "genre": task.genre,
                    "logline": task.logline,
                    "must_include": "、".join(task.must_include),
                    "avoid": "、".join(task.avoid),
                    "chapters": str(len(canon.chapters)),
                    "canon": canon_brief(canon),
                    "prior": _render_prior(accepted),
                    "schema": DESIGN_SCHEMAS[name],
                })
                purpose = f"design:{name}"
                used: PromptTemplate = template
            else:
                prompt = repair.render({
                    "doc": name, "findings": _format_findings(findings),
                    "previous": last_text, "schema": DESIGN_SCHEMAS[name],
                })
                purpose = f"design:{name}:repair"
                used = repair
            request = GenerationRequest(
                purpose=purpose, prompt=prompt, temperature=temperature,
                max_tokens=max_tokens, seed=seed,
                context=ledger.request_context(
                    task_id=task.id, doc=name, attempt=attempt, system=ledger.system,
                ),
            )
            result = provider.generate(request)
            ledger.record(request, result)
            ledger.write_text(f"design/attempts/{name}-attempt-{attempt}.txt",
                              result.text)
            last_text = result.text
            candidate = design_dir / f".{name}.attempt-{attempt}.json"
            try:
                payload = json.loads(_strip_fences(result.text))
            except json.JSONDecodeError as exc:
                findings = [{"check": "parse", "severity": "high",
                             "message_ja": f"JSON として読めない"
                                           f"（{exc.msg}、{exc.lineno} 行目）。"}]
                ledger.write_text(
                    f"design/attempts/{name}-attempt-{attempt}.error.txt",
                    findings[0]["message_ja"] + "\n")
                if attempt == 1:
                    first_findings = list(findings)
                    first_checks_failed = checks_failed
                continue
            candidate.write_text(json.dumps(payload, ensure_ascii=False,
                                            indent=2) + "\n", encoding="utf-8")
            try:
                findings, checks_failed = _validate_doc(name, candidate, canon)
            except (ValueError, OSError) as exc:
                findings = [{"check": "schema", "severity": "high",
                             "message_ja": f"書式の誤り: {exc}"}]
                checks_failed = 1
                ledger.write_text(
                    f"design/attempts/{name}-attempt-{attempt}.error.txt",
                    findings[0]["message_ja"] + "\n")
                if attempt == 1:
                    first_findings = list(findings)
                    first_checks_failed = checks_failed
                continue
            if attempt == 1:
                first_findings = list(findings)
                first_checks_failed = checks_failed
            if not _needs_repair(findings):
                break

        final = design_dir / f"{name}.json"
        if attempts and last_text and _is_usable(name, design_dir, attempts):
            payload_text = (design_dir / f".{name}.attempt-{attempts}.json"
                            ).read_text(encoding="utf-8")
            final.write_text(payload_text, encoding="utf-8")
            ledger.track([f"design/{name}.json"])
            accepted[name] = payload_text
            status = "clean" if not _needs_repair(findings) else "unresolved"
        else:
            status = "missing"
        for leftover in design_dir.glob(f".{name}.attempt-*.json"):
            leftover.unlink()
        results.append(DocResult(
            name=name, status=status, attempts=attempts,
            findings=tuple(findings), checks_failed=checks_failed,
            first_attempt_findings=tuple(first_findings),
            first_attempt_checks_failed=first_checks_failed))
        ledger.write_json(f"design/{name}.report.json", {
            "doc": name, "status": status, "attempts": attempts,
            "repairs": max(0, attempts - 1),
            "findings": findings, "checks_failed": checks_failed,
            "first_attempt": {"findings": first_findings,
                              "checks_failed": first_checks_failed},
            "prompt": {"name": used.name, "version": used.version,
                       "digest": used.digest},
        })

    design = Design(task_id=task.id, docs=tuple(results))
    ledger.write_json("design.json", design.as_dict())
    ledger.finish("ok")
    return design


def _is_usable(name: str, design_dir: Path, attempts: int) -> bool:
    """Whether the last attempt produced a parseable candidate file."""
    return (design_dir / f".{name}.attempt-{attempts}.json").is_file()


def _plot_notes_for_chapter(design_dir: Path, chapter_id: str,
                            canon: Canon | None) -> list[str]:
    """Pass only this chapter's checked act and turns to the draft prompt.

    An unresolved design is still saved by build_design (fail-open), so the
    existence of plot.json alone cannot authorize its use. Carried project
    revisions may lack the original per-document report; those need a canon
    so the checker can validate the inherited plot before it is used.
    """
    plot_path = design_dir / "plot.json"
    report_path = design_dir / "plot.report.json"
    if not plot_path.is_file():
        if report_path.is_file():
            return ["（プロット設計書が欠損したため、幕メモを省略）"]
        return []
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            status = report.get("status") if isinstance(report, dict) else None
        except (OSError, ValueError):
            status = None
        if status != "clean":
            return ["（プロット設計の検査記録が未解決または読取不可のため、幕メモを省略）"]
    elif canon is None:
        return ["（プロット設計の検査記録と canon がないため、幕メモを省略）"]

    from ..plot import check_plot, load_plot
    from ..plot.check import _chapter_key  # use the checker's chapter matching
    try:
        plot = load_plot(plot_path)
        if canon is not None:
            checked = check_plot(plot, canon)
            if _needs_repair(checked["findings"]):
                return ["（プロット設計が現在の canon で未解決のため、幕メモを省略）"]
    except (OSError, TypeError, ValueError):
        return ["（プロット設計書を読めないため、幕メモを省略）"]

    key = _chapter_key(chapter_id)
    lines: list[str] = []
    # Model-written fields stay on a single line: no other chapters or full
    # plot/ending are copied into a chapter request.
    def single_line(text: str) -> str:
        return " ".join(text.split())

    for act in plot.acts:
        if any(_chapter_key(ch) == key for ch in act.chapters):
            lines.append(f"- 幕 {single_line(act.id)}／問い: {single_line(act.question)}")
    for turn in plot.turns:
        if _chapter_key(turn.chapter) == key:
            lines.append(f"- 転換点 {single_line(turn.id)}／選択: {single_line(turn.choice_ja)}")
    return lines


def design_notes_for_chapter(design_dir: str | Path | None,
                             chapter_id: str, canon: Canon | None = None, *,
                             include_plot_memos: bool = True) -> str:
    """Checked plot, scene and voice notes for one chapter's draft prompt.

    ``include_plot_memos=False`` is a narrow ablation: it omits only the
    chapter-local checked plot lines, retaining the same scene and voice notes.
    Returns a compact block, or a marker recording that no design was used —
    the prompt then says so explicitly, which keeps ablations honest.
    """
    if design_dir is None:
        return "（設計メモなし）"
    design_dir = Path(design_dir)
    scenes_path = design_dir / "scene.json"
    voice_path = design_dir / "voice.json"
    lines = (_plot_notes_for_chapter(design_dir, chapter_id, canon)
             if include_plot_memos else [])
    if not scenes_path.is_file() and not voice_path.is_file() and not lines:
        return "（設計メモなし）"
    if scenes_path.is_file():
        try:
            scenes = json.loads(scenes_path.read_text(encoding="utf-8")
                                ).get("scenes") or []
        except (json.JSONDecodeError, AttributeError):
            scenes = []
        key = chapter_id.lower().replace("第", "").strip()
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            if str(scene.get("chapter", "")).strip().lower() != key:
                continue
            lines.append(
                f"- {scene.get('id', '?')}: {scene.get('purpose', '')}／"
                f"対立: {scene.get('conflict', '')}／"
                f"変化: {scene.get('change', '')}（緊張: {scene.get('tension', '')}）")
    if voice_path.is_file():
        try:
            voice = json.loads(voice_path.read_text(encoding="utf-8"))
            viewpoint = voice.get("viewpoint") or {}
            lines.append(f"- 文体: {viewpoint.get('person', '')}人称、"
                         f"視点: {viewpoint.get('character', '')}")
        except (json.JSONDecodeError, AttributeError):
            pass
    return "\n".join(lines) if lines else "（この章の設計メモなし）"
