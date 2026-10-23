"""Judge adapters for the model-graded layer (L2).

The harness never calls a model by itself. A judge is injected, which keeps the
repository offline-testable and lets the operator choose the model, the
temperature and the reasoning budget — all of which must be recorded for the
result to be comparable later (see the measurement reference of the skill).

Two adapters are provided:

``CommandJudge``
    Runs an external command. The request is a single JSON object on stdin; the
    response must be a single JSON object on stdout. This is the way to plug in
    any CLI or HTTP wrapper without adding a dependency to this repository.

``FixtureJudge``
    Reads judgements from a JSON file. Used by the tests and to replay a run
    recorded elsewhere, without spending tokens.

Both return :class:`Verdict` objects. A verdict without evidence is rejected
when the dimension requires it: an unevidenced score is worse than no score,
because it looks like a measurement.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class JudgeError(RuntimeError):
    pass


@dataclass
class Verdict:
    dimension: str
    score: float | None
    evidence: list[dict] = field(default_factory=list)
    rationale_ja: str = ""
    judge: str = "unknown"
    unevidenced: bool = False

    def as_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "evidence": self.evidence,
            "rationale_ja": self.rationale_ja,
            "judge": self.judge,
            "unevidenced": self.unevidenced,
        }


def _validate(payload: dict, rubric, judge_name: str) -> list[Verdict]:
    verdicts: list[Verdict] = []
    rows = payload.get("dimensions") or payload.get("verdicts") or []
    if not isinstance(rows, list):
        raise JudgeError("judge response: 'dimensions' must be a list")
    by_id = {d.id: d for d in rubric.dimensions}
    for row in rows:
        if not isinstance(row, dict) or row.get("dimension") not in by_id:
            raise JudgeError(f"judge response: unknown dimension {row!r}")
        dimension = by_id[row["dimension"]]
        score = row.get("score")
        if score is not None:
            score = float(score)
            if not rubric.scale_min <= score <= rubric.scale_max:
                raise JudgeError(
                    f"judge response: score {score} outside "
                    f"{rubric.scale_min}-{rubric.scale_max} for {dimension.id}")
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        evidence = [e for e in evidence if isinstance(e, dict)
                    and (e.get("quote") or e.get("path"))]
        verdicts.append(Verdict(
            dimension=dimension.id,
            score=score,
            evidence=evidence,
            rationale_ja=str(row.get("rationale_ja") or row.get("rationale") or ""),
            judge=judge_name,
            unevidenced=dimension.evidence_required and not evidence,
        ))
    missing = set(by_id) - {v.dimension for v in verdicts}
    if missing:
        raise JudgeError(f"judge response: missing dimensions {sorted(missing)}")
    return verdicts


class Judge:
    name = "base"

    def score_story(self, text: str, rubric, context: dict | None = None) -> list[Verdict]:
        raise NotImplementedError

    def pairwise(self, a: str, b: str, rubric, context: dict | None = None) -> dict:
        raise NotImplementedError

    @property
    def supports_pairwise(self) -> bool:
        return False


class FixtureJudge(Judge):
    """Replay judgements recorded in a JSON file (tests, offline re-runs)."""

    name = "fixture"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.name = f"fixture:{self.path.name}"

    def score_story(self, text, rubric, context=None):
        key = (context or {}).get("story") or "default"
        payload = (self.data.get("scores") or {}).get(key)
        if payload is None:
            payload = self.data.get("scores", {}).get("default")
        if payload is None:
            raise JudgeError(f"fixture has no scores for '{key}'")
        return _validate(payload, rubric, self.name)

    @property
    def supports_pairwise(self) -> bool:
        return bool(self.data.get("pairwise"))

    def pairwise(self, a, b, rubric, context=None):
        payload = self.data.get("pairwise")
        if not payload:
            raise JudgeError("fixture has no pairwise judgements")
        return payload


class CommandJudge(Judge):
    """Run an external command that speaks the JSON protocol.

    Request (stdin)::

        {"mode": "score", "rubric": {...}, "story": "...", "context": {...}}
        {"mode": "pairwise", "rubric": {...}, "a": "...", "b": "...", "context": {...}}

    Response (stdout)::

        {"dimensions": [{"dimension": "coherence", "score": 4,
                         "evidence": [{"quote": "...", "path": "ch02.md", "line": 12}],
                         "rationale_ja": "..."}]}
        {"winner": "a" | "b" | "tie", "rationale_ja": "..."}
    """

    name = "command"

    def __init__(self, command: str, timeout: int = 300):
        self.command = command
        self.timeout = timeout
        self.name = f"command:{command.split()[0]}"

    def _call(self, payload: dict) -> dict:
        try:
            completed = subprocess.run(
                self.command, shell=True, input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, timeout=self.timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise JudgeError(f"judge timed out after {self.timeout}s") from exc
        if completed.returncode != 0:
            raise JudgeError(f"judge exited {completed.returncode}: "
                             f"{completed.stderr.strip()[:400]}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"judge did not return JSON: {exc}") from exc

    def score_story(self, text, rubric, context=None):
        payload = self._call({"mode": "score", "rubric": rubric.as_dict(),
                              "story": text, "context": context or {}})
        return _validate(payload, rubric, self.name)

    @property
    def supports_pairwise(self) -> bool:
        return True

    def pairwise(self, a, b, rubric, context=None):
        return self._call({"mode": "pairwise", "rubric": rubric.as_dict(),
                           "a": a, "b": b, "context": context or {}})


def compare_pairwise(judge: Judge, a: str, b: str, rubric, context=None) -> dict:
    """Run a pairwise comparison twice with the order swapped (LitBench bias control).

    If the judge prefers the same *position* both times (``a`` first, then ``b``
    first), the result is marked ``position_bias: true`` and treated as a tie.
    """
    forward = judge.pairwise(a, b, rubric, context)
    backward = judge.pairwise(b, a, rubric, context)
    first = str(forward.get("winner", "tie")).lower()
    second = str(backward.get("winner", "tie")).lower()
    # map the second run back to the original labels
    second_mapped = {"a": "b", "b": "a"}.get(second, second)
    position_bias = first != second_mapped and second in {"a", "b"}
    winner = "tie" if position_bias else first
    return {
        "winner": winner,
        "winner_forward": first,
        "winner_backward_mapped": second_mapped,
        "position_bias": position_bias,
        "rationale_ja": forward.get("rationale_ja", ""),
        "rationale_backward_ja": backward.get("rationale_ja", ""),
        "judge": judge.name,
    }
