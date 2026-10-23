"""The Revise step (S2): audit, critique, rewrite, re-audit.

S2 runs the Check→Act loop once around an S1 draft. The critique comes from
the deterministic audit (:mod:`asc.revision`), never from the model's own
opinion of its prose; the model only rewrites the chapters the critique
names. Each round is recorded (critique, revised chapters, before/after
comparison) so that a later reader can tell what the loop changed — and what
it left behind.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..revision import compare_reports, detect_repeats, plan_round
from ..story.canon import Canon
from ..story.continuity import audit_texts
from .draft import canon_brief, check_chapter, clean_text, ensure_markers
from .llm import GenerationRequest, Provider, ProviderError
from .prompts import load_prompt
from .run import RunLedger
from .tasks import Task

TITLE = "Revise"

REVISE_SEVERITIES = {"high", "medium"}


class RevisionError(RuntimeError):
    """Raised when the provider fails mid-revision (the run is kept)."""


@dataclass
class Revision:
    rounds: int
    converged: bool
    revised: tuple[str, ...]
    kept: tuple[str, ...]
    comparisons: tuple[dict, ...] = ()
    repeats: tuple[dict, ...] = ()

    def as_dict(self) -> dict:
        return {
            "rounds": self.rounds,
            "converged": self.converged,
            "revised": list(self.revised),
            "kept": list(self.kept),
            "comparisons": [c["summary"] for c in self.comparisons],
            "repeats": len(self.repeats),
        }


def _chapter_meta(canon: Canon | None, chapter_id: str) -> dict:
    if canon is not None:
        chapter = canon.chapters.get(chapter_id)
        if chapter is not None:
            return {"day": chapter.day, "location": chapter.location}
    return {}


def _format_findings(items: list[dict]) -> str:
    lines = []
    for item in items:
        evidence = item.get("evidence") or {}
        at = f"（{evidence.get('path', '')}:{evidence.get('line', '')}）" \
            if evidence.get("line") else ""
        lines.append(f"* [{item['severity']}] {item['problem_ja']}{at}\n"
                     f"  修正方針: {item['fix_ja']}")
    return "\n".join(lines)


def build_revision(task: Task, provider: Provider, ledger: RunLedger,
                   canon: Canon | None, *,
                   prompt_dir: str | Path | None = None,
                   temperature: float = 0.8, max_tokens: int = 2500,
                   seed: int = 0, max_rounds: int = 1) -> Revision:
    """Revise the draft in ``ledger.path / 'text'`` against its audit."""
    template = load_prompt("revise-chapter", prompt_dir)
    ledger.prompt_hashes[template.name] = template.digest
    text_dir = ledger.path / "text"
    canon_dir = ledger.path / "canon"

    audits: list[dict] = []
    comparisons: list[dict] = []
    revised_all: list[str] = []
    kept_all: list[str] = []
    converged = False

    audit = audit_texts(canon_dir, text_dir)
    audits.append(audit)
    ledger.write_json("audit-round-0.json", audit)

    for round_no in range(1, max_rounds + 1):
        critique = plan_round(audit)
        ledger.write_json(f"critique-round-{round_no}.json", critique)
        actionable = [c for c in critique["critiques"]
                      if c["severity"] in REVISE_SEVERITIES]
        if not actionable:
            converged = True
            break
        targets: dict[str, list[dict]] = {}
        for item in actionable:
            chapter = str(item.get("chapter") or "")
            if chapter.startswith("ch"):
                targets.setdefault(chapter, []).append(item)

        revised, kept = [], []
        for chapter_id in sorted(targets):
            path = text_dir / f"{chapter_id}.md"
            if not path.is_file():
                kept.append(chapter_id)
                continue
            current = path.read_text(encoding="utf-8")
            values = {
                "title": task.title_ja,
                "logline": task.logline,
                "chapter_id": chapter_id,
                "canon": canon_brief(canon),
                "findings": _format_findings(targets[chapter_id]),
                "chapter_text": current,
                "must_include": "、".join(task.must_include),
                "avoid": "、".join(task.avoid),
            }
            request = GenerationRequest(
                purpose=f"revise:{chapter_id}", prompt=template.render(values),
                temperature=temperature, max_tokens=max_tokens,
                seed=seed + round_no,
                context={"task_id": task.id, "chapter": chapter_id,
                         "round": round_no, "system": ledger.system},
            )
            try:
                result = provider.generate(request)
            except ProviderError as exc:
                ledger.fail(f"revise:{chapter_id}: {exc}")
                raise RevisionError(f"revise:{chapter_id}: {exc}") from exc
            ledger.record(request, result)
            ledger.write_text(f"draft/{chapter_id}-revise-{round_no}.txt", result.text)
            text = clean_text(result.text)
            problems = check_chapter(text, task, {"id": chapter_id})
            if problems:
                ledger.write_text(
                    f"draft/{chapter_id}-revise-{round_no}.issues.txt",
                    "\n".join(problems) + "\n")
                kept.append(chapter_id)
                continue
            body, injected = ensure_markers(text, _chapter_meta(canon, chapter_id))
            if injected:
                ledger.write_text(
                    f"draft/{chapter_id}-revise-{round_no}.injected.txt",
                    "\n".join(injected) + "\n")
            path.write_text(body, encoding="utf-8")
            revised.append(chapter_id)

        revised_all.extend(revised)
        kept_all.extend(kept)
        new_audit = audit_texts(canon_dir, text_dir)
        audits.append(new_audit)
        ledger.write_json(f"audit-round-{round_no}.json", new_audit)
        comparison = compare_reports(audit, new_audit)
        comparisons.append(comparison)
        ledger.write_json(f"comparison-round-{round_no}.json", comparison)
        audit = new_audit
        if comparison["summary"]["persisting_medium_plus"] == 0:
            converged = True
            break

    repeats = detect_repeats(audits) if len(audits) >= 2 else []
    revision = Revision(rounds=len(comparisons), converged=converged,
                        revised=tuple(revised_all), kept=tuple(kept_all),
                        comparisons=tuple(comparisons), repeats=tuple(repeats))
    ledger.write_json("revision.json", {
        **revision.as_dict(),
        "repeats": [r.get("message_ja", "") for r in repeats],
    })
    ledger.finish("ok")
    return revision
