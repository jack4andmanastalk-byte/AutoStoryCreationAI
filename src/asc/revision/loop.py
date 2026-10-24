"""The deterministic half of the revision loop.

* :func:`plan_round` — findings become critique notes (location + fix direction).
* :func:`apply_patches` — explicit anchor replacements, never fuzzy.
* :func:`compare_reports` — fixed / persisting / new, keyed by identity.
* :func:`detect_repeats` — the same defect across rounds means the root cause
  was not addressed.

Fix directions are templates, not diagnoses. When a local fix stalls, the
critique says to go back to the plan (brief, canon, voice spec) instead of
rewriting the same line again.
"""
from __future__ import annotations

import json
from pathlib import Path

#: templated fix directions per continuity violation type
FIX_DIRECTIONS = {
    "dead_character_reappears":
        "死亡章以降の行為を回想・遺体・代役のいずれかに変えるか、"
        "意図的な矛盾なら suppressions.yaml に理由つきで登録する。",
    "knowledge_violation":
        "学習マーカー（{{learn}}）を早めるか、台詞の語彙を事実と無関係にする。",
    "foreshadow_order":
        "設置と回収の章を入れ替えるか、canon の setup/payoff を直す。",
    "unresolved_foreshadow":
        "回収を書くか、設置を削る。どちらもしない場合は未解決として残す。",
    "travel_time":
        "章の日付を延ばすか、移動日数表（travel_days）を直す。",
    "stated_age":
        "本文の年齢か canon の age_at_start / birthday_day を直す。",
}

VOICE_FIX = "文体仕様（voice.yaml）の該当欄を確認し、本文か仕様のどちらかを直す。"


def _violation_key(item: dict) -> tuple:
    return ("continuity", item.get("type"), item.get("subject"), item.get("chapter"))


def _voice_key(item: dict) -> tuple:
    evidence = item.get("evidence") or {}
    return ("voice", item.get("check"), evidence.get("path"), evidence.get("line"),
            (item.get("match") or "")[:30])


def plan_round(audit_report: dict, voice_report: dict | None = None) -> dict:
    """Turn deterministic findings into a critique note with fix directions."""
    critiques: list[dict] = []
    for violation in audit_report.get("violations", []):
        critiques.append({
            "id": f"CR-{len(critiques) + 1:03d}",
            "source": "continuity",
            "key": list(_violation_key(violation)),
            "severity": violation.get("severity", "medium"),
            "chapter": violation.get("chapter"),
            "evidence": violation.get("evidence", {}),
            "problem_ja": violation.get("message_ja", ""),
            "fix_ja": FIX_DIRECTIONS.get(
                violation.get("type", ""),
                "canon と本文のどちらが正しいかを決め、正しい方に寄せる。"),
            "canon_ref": violation.get("canon_ref", ""),
            "status": "open",
        })
    for finding in (voice_report or {}).get("findings", []):
        critiques.append({
            "id": f"CR-{len(critiques) + 1:03d}",
            "source": "voice",
            "key": list(_voice_key(finding)),
            "severity": finding.get("severity", "medium"),
            "chapter": (finding.get("evidence") or {}).get("path", ""),
            "evidence": finding.get("evidence", {}),
            "problem_ja": finding.get("message_ja", ""),
            "fix_ja": VOICE_FIX,
            "canon_ref": "",
            "status": "open",
        })
    order = {"high": 0, "medium": 1, "low": 2}
    critiques.sort(key=lambda c: (order.get(c["severity"], 9), c["id"]))
    for i, critique in enumerate(critiques, start=1):
        critique["id"] = f"CR-{i:03d}"
    return {
        "critiques": critiques,
        "summary": {
            "open": len(critiques),
            "by_source": {
                "continuity": sum(1 for c in critiques if c["source"] == "continuity"),
                "voice": sum(1 for c in critiques if c["source"] == "voice"),
            },
        },
    }


def apply_patches(text_dir, patch: dict, out_dir) -> dict:
    """Apply explicit anchor replacements. Ambiguity fails, never guesses."""
    text_dir, out_dir = Path(text_dir), Path(out_dir)
    chapters = sorted(p for p in text_dir.iterdir()
                      if p.is_file() and p.suffix.lower() in {".md", ".txt"})
    contents = {p.name: p.read_text(encoding="utf-8").splitlines(keepends=True)
                for p in chapters}
    results: list[dict] = []
    for i, entry in enumerate(patch.get("patches", []), start=1):
        pid = entry.get("id", f"P-{i:03d}")
        result = {"id": pid, "chapter": entry.get("chapter"),
                  "critique_id": entry.get("critique_id", ""),
                  "status": "failed", "reason": ""}
        name = str(entry.get("chapter", ""))
        anchor, replacement = entry.get("anchor", ""), entry.get("replacement", "")
        if name not in contents:
            result["reason"] = f"章ファイル {name} がない。"
        elif not anchor:
            result["reason"] = "anchor（置換対象）が空。対象を明示する。"
        elif entry.get("line") is not None:
            line_no = entry["line"]
            lines = contents[name]
            if not 1 <= line_no <= len(lines):
                result["reason"] = f"{line_no} 行目は範囲外（全 {len(lines)} 行）。"
            elif anchor not in lines[line_no - 1]:
                result["reason"] = f"{line_no} 行目に anchor がない。行か anchor を直す。"
            else:
                lines[line_no - 1] = lines[line_no - 1].replace(anchor, replacement, 1)
                result["status"] = "applied"
                result["line"] = line_no
        else:
            hits = [n for n, line in enumerate(contents[name], start=1) if anchor in line]
            if not hits:
                result["reason"] = "anchor に一致する箇所がない。"
            elif len(hits) > 1:
                result["reason"] = (f"anchor が {len(hits)} 箇所に一致"
                                    f"（{hits}）。行を指定する。")
            else:
                contents[name][hits[0] - 1] = contents[name][hits[0] - 1].replace(
                    anchor, replacement, 1)
                result["status"] = "applied"
                result["line"] = hits[0]
        results.append(result)

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, lines in contents.items():
        (out_dir / name).write_text("".join(lines), encoding="utf-8")
    applied = sum(1 for r in results if r["status"] == "applied")
    return {"results": results,
            "summary": {"patches": len(results), "applied": applied,
                        "failed": len(results) - applied}}


def _index(report: dict) -> dict[tuple, dict]:
    index: dict[tuple, dict] = {}
    for violation in report.get("violations", []):
        index[_violation_key(violation)] = violation
    for finding in report.get("findings", []):
        index[_voice_key(finding)] = finding
    return index


def compare_reports(before: dict, after: dict) -> dict:
    """Fixed / persisting / new, keyed by defect identity."""
    old, new = _index(before), _index(after)
    fixed = [old[k] for k in old if k not in new]
    persisting = [new[k] for k in new if k in old]
    added = [new[k] for k in new if k not in old]
    medium_plus = {"high", "medium"}
    return {
        "fixed": fixed,
        "persisting": persisting,
        "new": added,
        "summary": {
            "before": len(old),
            "after": len(new),
            "fixed": len(fixed),
            "persisting": len(persisting),
            "new": len(added),
            "persisting_medium_plus": sum(
                1 for p in persisting if p.get("severity") in medium_plus),
        },
    }


def detect_repeats(history: list[dict]) -> list[dict]:
    """Defects present in every round: the root cause was not addressed."""
    if len(history) < 2:
        return []
    common = set(_index(history[0]))
    for report in history[1:]:
        common &= set(_index(report))
    latest = _index(history[-1])
    return [{**latest[k], "repeat": True,
             "note_ja": f"{len(history)} ラウンド連続で残存。根本原因が未解決の疑い。局所修正をやめ企画・台帳に戻る。"}
            for k in sorted(common, key=str)]


def render_markdown(comparison: dict, repeats: list[dict] | None = None) -> str:
    summary = comparison["summary"]
    lines = ["# 改稿の前後比較", "",
             f"前: {summary['before']} 件 → 後: {summary['after']} 件 "
             f"（解消 {summary['fixed']}／残存 {summary['persisting']}／"
             f"新規 {summary['new']}）", ""]
    if comparison["persisting"]:
        lines += ["## 残存", ""]
        for item in comparison["persisting"]:
            lines.append(f"* [{item.get('severity')}] "
                         f"{item.get('message_ja', item)}")
        lines.append("")
    if comparison["new"]:
        lines += ["## 新規（改稿で生まれた所見）", ""]
        for item in comparison["new"]:
            lines.append(f"* [{item.get('severity')}] "
                         f"{item.get('message_ja', item)}")
        lines.append("")
    if repeats:
        lines += ["## 繰り返し（根本原因の未解決の疑い）", ""]
        for item in repeats:
            lines.append(f"* {item.get('message_ja', item)}")
    if summary["persisting"] == 0 and summary["new"] == 0:
        lines.append("残存・新規なし。**質の向上ではなく、所見の解消である。**")
    return "\n".join(lines)


def load_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
