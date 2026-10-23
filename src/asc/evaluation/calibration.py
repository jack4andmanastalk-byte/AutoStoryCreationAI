"""L2/L3 calibration: rater agreement and judge-vs-human agreement.

* Human labels come from blind pairs (``scripts/make_blind_pairs.py``).
  Recommended layout: ``judgements/<rater_id>/<pair_id>.json``.
* The judge's verdicts over the same pairs come from ``scripts/judge_pairs.py``.
* Agreement between humans is Cohen's kappa; agreement between the judge and
  the human majority is a plain rate. A single rater cannot produce kappa —
  that is reported as a warning, not a number.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

CATEGORIES = ("a", "b", "tie")


class CalibrationError(ValueError):
    """Raised when labels or verdicts are malformed."""


def cohen_kappa(pairs: list[tuple[str, str]]) -> dict:
    """Kappa over paired labels. ``None`` when there is nothing to compare."""
    n = len(pairs)
    if n == 0:
        return {"kappa": None, "n": 0, "agreement": None,
                "reason": "no overlapping pairs"}
    agreement = sum(1 for x, y in pairs if x == y) / n
    expected = 0.0
    for category in CATEGORIES:
        px = sum(1 for x, _ in pairs if x == category) / n
        py = sum(1 for _, y in pairs if y == category) / n
        expected += px * py
    if expected >= 1.0:
        return {"kappa": None, "n": n, "agreement": round(agreement, 3),
                "reason": "no variance (a single category)"}
    kappa = (agreement - expected) / (1 - expected)
    return {"kappa": round(kappa, 3), "n": n, "agreement": round(agreement, 3)}


def _read_label(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalibrationError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise CalibrationError(f"{path}: a label must be an object")
    rater = str(data.get("rater_id", "") or "").strip()
    pair = str(data.get("pair_id", "") or "").strip()
    winner = str(data.get("winner", "") or "").strip().lower()
    if not rater or not pair:
        raise CalibrationError(f"{path}: 'rater_id' and 'pair_id' are required")
    if winner not in CATEGORIES:
        raise CalibrationError(
            f"{path}: 'winner' must be one of a/b/tie (got {winner!r})")
    return {"rater_id": rater, "pair_id": pair, "winner": winner,
            "rationale_ja": str(data.get("rationale_ja", "") or "")}


def load_judgements(path: str | Path) -> list[dict]:
    """Load labels from a directory (recursive ``*.json``) or one file."""
    path = Path(path)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise CalibrationError(f"{path}: expected a list of labels")
        labels = []
        for row in items:
            if not isinstance(row, dict):
                raise CalibrationError(f"{path}: every label must be an object")
            winner = str(row.get("winner", "") or "").strip().lower()
            if winner not in CATEGORIES:
                raise CalibrationError(f"{path}: bad winner {winner!r}")
            labels.append({
                "rater_id": str(row.get("rater_id", row.get("rater", "?"))),
                "pair_id": str(row.get("pair_id", "?")),
                "winner": winner,
                "rationale_ja": str(row.get("rationale_ja", "") or ""),
            })
        return labels
    if not path.is_dir():
        raise CalibrationError(f"labels not found: {path}")
    files = sorted(path.rglob("*.json"))
    if not files:
        raise CalibrationError(f"{path}: no label files")
    return [_read_label(f) for f in files]


def rater_agreement(labels: list[dict]) -> dict:
    """Pairwise kappa between raters on the pairs they share."""
    by_rater: dict[str, dict[str, str]] = {}
    for label in labels:
        by_rater.setdefault(label["rater_id"], {})[label["pair_id"]] = label["winner"]
    raters = sorted(by_rater)
    if len(raters) < 2:
        return {"status": "single_rater", "raters": raters, "n_labels": len(labels),
                "warning_ja": "評定者が 1 名のため、人間間の一致（κ）は測れない。"}
    kappas = []
    for first, second in itertools.combinations(raters, 2):
        shared = sorted(set(by_rater[first]) & set(by_rater[second]))
        pairs = [(by_rater[first][p], by_rater[second][p]) for p in shared]
        result = cohen_kappa(pairs)
        kappas.append({"raters": [first, second], "pairs": shared, **result})
    measured = [k["kappa"] for k in kappas if k["kappa"] is not None]
    return {
        "status": "ok",
        "raters": raters,
        "n_labels": len(labels),
        "n_pairs": len({label["pair_id"] for label in labels}),
        "kappas": kappas,
        "mean_kappa": round(sum(measured) / len(measured), 3) if measured else None,
    }


def majority(labels: list[dict]) -> dict[str, str]:
    """The human majority per pair. A tied vote is a tie, not a guess."""
    votes: dict[str, list[str]] = {}
    for label in labels:
        votes.setdefault(label["pair_id"], []).append(label["winner"])
    out = {}
    for pair_id, winners in votes.items():
        counts = {c: winners.count(c) for c in CATEGORIES}
        best = max(counts.values())
        top = [c for c in CATEGORIES if counts[c] == best]
        out[pair_id] = top[0] if len(top) == 1 else "tie"
    return out


def judge_agreement(labels: list[dict], verdicts: dict[str, str]) -> dict:
    """How often the judge matches the human majority (L2 vs L3)."""
    expected = majority(labels)
    compared, agreed = [], 0
    missing = sorted(set(expected) - set(verdicts))
    for pair_id, human in sorted(expected.items()):
        judge = str(verdicts.get(pair_id, "") or "").lower()
        if judge not in CATEGORIES:
            continue
        compared.append({"pair_id": pair_id, "human": human, "judge": judge,
                         "agree": human == judge})
        agreed += human == judge
    return {
        "n": len(compared),
        "agree": agreed,
        "rate": round(agreed / len(compared), 3) if compared else None,
        "missing_verdicts": missing,
        "pairs": compared,
    }


def render_markdown(report: dict) -> str:
    lines = ["# 較正レポート（L2/L3）", ""]
    raters = report.get("raters", {})
    if raters.get("status") == "single_rater":
        lines.append(f"評定者: {raters.get('raters')}（{raters.get('n_labels')} 件）")
        lines.append(f"警告: {raters['warning_ja']}")
    else:
        lines.append(f"評定者: {', '.join(raters.get('raters', []))}／"
                     f"{raters.get('n_pairs')} ペア／κ 平均 {raters.get('mean_kappa')}")
        for kappa in raters.get("kappas", []):
            pair = "–".join(kappa["raters"])
            lines.append(f"* {pair}: κ={kappa['kappa']} "
                         f"（一致率 {kappa['agreement']}、N={kappa['n']}）")
    judge = report.get("judge")
    if judge:
        lines += ["", f"判定器と人間の多数派の一致率: {judge.get('rate')} "
                      f"（{judge.get('agree')}/{judge.get('n')}）"]
        if judge.get("missing_verdicts"):
            lines.append(f"判定のないペア: {', '.join(judge['missing_verdicts'])}")
    else:
        lines += ["", "判定器の verdict が無いため、L2 との一致率は計算しない。"]
    return "\n".join(lines)
