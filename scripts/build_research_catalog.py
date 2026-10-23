#!/usr/bin/env python3
"""Build the unified research catalog from the curated attachment corpus.

The script is intentionally dependency-free (standard library only) so that the
catalog can be rebuilt in CI without a network connection.

Inputs : research/curated/**/*.jsonl  (structured extracts selected in the
         curation pass; see research/curation/selection_report.md)
Outputs: research/catalog/{techniques,taxonomies,tools,sources}.jsonl,
         research/catalog/executability.jsonl,
         research/catalog/executability_summary.md,
         research/catalog/manifest.json, research/catalog/validation_report.json

The executability pass answers a different question from the catalog itself:
"can this entry be turned into an instruction without further editorial work?".
It is a lexical self-assessment of the records, not a quality judgement about
the cited scholarship. See research/curation/executability_report.md.

Run:  python3 scripts/build_research_catalog.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "research" / "curated"
OUT = ROOT / "research" / "catalog"
GENERATED_ON = "2026-10-23"
SCHEMA_VERSION = "1.0"

DOMAINS = {"story", "character", "world", "history", "production", "interaction", "style", "meta"}

# Editorial mappings. They are recorded in every affected record via
# mapping_authorship="editorial" and are not claims made by the cited sources.
JP2026_DOMAINS = {
    "A": ["story", "production"],
    "B": ["story"],
    "C": ["character"],
    "D": ["story", "style"],
    "E": ["style", "story"],
    "F": ["style"],
    "G": ["style", "story"],
    "H": ["style"],
    "I": ["style"],
    "J": ["interaction", "story"],
    "K": ["world", "story"],
    "L": ["production", "meta"],
}
US2026_DOMAINS = {
    "C01": ["story"], "C02": ["story", "style"], "C03": ["character"],
    "C04": ["style"], "C05": ["story", "style"], "C06": ["style"],
    "C07": ["world"], "C08": ["story", "style"], "C09": ["style"],
    "C10": ["story", "production"], "C11": ["story"], "C12": ["style", "story"],
    "C13": ["character", "story"], "C14": ["interaction"], "C15": ["interaction"],
    "C16": ["production", "meta"], "C17": ["world", "history"], "C18": ["meta", "production"],
}
US2025_DOMAINS = {
    "macro_structure": ["story"], "plot_devices": ["story"], "character": ["character"],
    "scene_style": ["style"], "cognition_emotion": ["style", "story"],
    "narration_pov": ["style"], "tv_serial": ["story", "production"],
    "comics": ["style"], "games": ["interaction", "story"], "audio_oral": ["style"],
    "journalism": ["meta"], "marketing": ["meta"], "production": ["production"],
}
CN_DOMAINS = {
    "文学の声・現実・因果": ["story", "style"],
    "ネット文学の進行と世界": ["story", "world"],
    "女性向け文学・耽美・ファン再創作": ["character", "story"],
    "映画・テレビの時間と情報": ["story", "style"],
    "神話・ジャンル・SF": ["world", "history"],
    "短劇・マイクロドラマ": ["story", "style"],
    "ゲームとプレイヤーの位置": ["interaction"],
    "動画・SNS・Vlog": ["style", "meta"],
    "ドキュメンタリー・写真・記憶": ["meta", "history"],
    "演劇・劇本殺・コメディ": ["story", "interaction"],
    "ブランド・ライブコマース・観光": ["meta"],
    "政治・公共・ニュース": ["meta"],
}
MYTH_DOMAINS = {
    "ストーリー構築": ["story"], "キャラクター構築": ["character"],
    "世界観構築": ["world"], "歴史・年代記構築": ["history", "world"],
}


# --------------------------------------------------------------------------
# Executability assessment
# --------------------------------------------------------------------------
# Four criteria are checked per technique record. Each is deliberately a
# *lexical* test of the record, so the result can be reproduced from the
# committed catalog alone. None of them proves that the instruction works.
#
#   procedure          : an operational step exists (>= MIN_PROCEDURE chars)
#   acceptance         : the text names something that can be used to decide
#                        pass/fail (確認・検証・基準・測定・判定・照合 ...)
#   failure_condition  : the record states when the technique does not hold
#   example            : at least one concrete work / practice / case
EXECUTABILITY_CRITERIA = ("procedure", "acceptance", "failure_condition", "example")
MIN_PROCEDURE_CHARS = 30
MIN_LIMITATION_CHARS = 20

ACCEPTANCE_CUES = (
    "確認", "検証", "測定", "基準", "判定", "チェック", "照合", "逸脱",
    "満たす", "比較", "テスト", "記録",
)
EXAMPLE_FIELDS = ("work_or_practice", "title", "name", "work", "example", "case")


def _has_text(value, min_chars=1):
    return isinstance(value, str) and len(value.strip()) >= min_chars


def _acceptance_cue(rec):
    """Return the first pass/fail cue found in the operational text, if any."""
    fields = ("operation_ja", "function_ja", "mechanism_ja", "summary_ja")
    for field in fields:
        text = rec.get(field)
        if not isinstance(text, str):
            continue
        for cue in ACCEPTANCE_CUES:
            if cue in text:
                return cue, field
    return None, None


def _example_label(example):
    """A short human-readable label for an example record, or None."""
    if isinstance(example, str):
        return example.strip() or None
    if not isinstance(example, dict):
        return None
    for field in EXAMPLE_FIELDS:
        value = example.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def assess_executability(rec):
    """Score how far a catalog record is from being directly executable.

    Returns a record with the four boolean criteria, the derived score (0-4),
    a tier, and the missing parts. The tier is what the skills pipeline keys
    on: `executable` may be turned into a SKILL.md step as-is, `partial` needs
    a step or an acceptance condition written by hand, `reference_only` is a
    label or a piece of vocabulary rather than an instruction.
    """
    operation = rec.get("operation_ja")
    operation_origin = rec["extra"].get("operation_origin") if rec.get("extra") else None
    if operation_origin is None:
        operation_origin = "stated" if _has_text(operation) else "none"

    procedure = _has_text(operation, MIN_PROCEDURE_CHARS)
    cue, cue_field = _acceptance_cue(rec)
    acceptance = bool(cue)
    failure_condition = _has_text(rec.get("limitations_ja"), MIN_LIMITATION_CHARS)
    example_labels = [lbl for lbl in (_example_label(e) for e in rec.get("examples") or []) if lbl]
    example = bool(example_labels)

    criteria = {
        "procedure": procedure,
        "acceptance": acceptance,
        "failure_condition": failure_condition,
        "example": example,
    }
    score = sum(criteria.values())
    if procedure and acceptance:
        # An instruction without a way to tell whether it was followed is not
        # executable, however detailed the rest of the record is.
        tier = "executable"
    elif score >= 2:
        tier = "partial"
    else:
        tier = "reference_only"

    missing = [k for k in EXECUTABILITY_CRITERIA if not criteria[k]]
    return {
        "id": rec["id"],
        "artifact": rec["artifact"],
        "entry_type": rec["entry_type"],
        "domains": rec["domains"],
        "title_ja": rec["title_ja"],
        "criteria": criteria,
        "score": score,
        "tier": tier,
        "missing": missing,
        "operation_origin": operation_origin,
        "acceptance_cue": cue,
        "acceptance_cue_field": cue_field,
        "procedure_chars": len(operation.strip()) if isinstance(operation, str) else 0,
        "example_count": len(example_labels),
    }


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def norm_url(url):
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    url = url.split("#", 1)[0]
    url = re.sub(r"\?.*$", "", url)
    return url.rstrip("/")


def year_of(value):
    if isinstance(value, int):
        return value
    if not value:
        return None
    m = re.search(r"(1[5-9]\d{2}|20\d{2})", str(value))
    return int(m.group(1)) if m else None


class Sources:
    """Deduplicated source registry keyed by normalised URL (or DOI/title)."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.by_key: dict[str, str] = {}

    def add(self, artifact, original_id, *, title, authors=None, year=None, url=None,
            doi=None, source_type=None, language=None, peer_review=None,
            evidence=None, notes=None):
        title = clean(title) or "(untitled)"
        key = norm_url(url) or (("doi:" + doi.lower()) if doi else
                                "t:" + re.sub(r"\s+", " ", title.lower())[:160] + f"|{year or ''}")
        if key in self.by_key:
            sid = self.by_key[key]
            rec = self.records[sid]
            if not rec.get("year") and year:
                rec["year"] = year
            if not rec.get("doi") and doi:
                rec["doi"] = doi
            if not rec.get("source_type") and source_type:
                rec["source_type"] = source_type
            if not rec.get("peer_review_status") and peer_review:
                rec["peer_review_status"] = peer_review
            rec["artifacts"].append({"artifact": artifact, "original_id": original_id})
            return sid
        sid = "src-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
        self.records[sid] = {
            "id": sid,
            "title": title,
            "authors": [a for a in (authors or []) if a],
            "year": year,
            "url": norm_url(url) or url,
            "doi": doi or None,
            "source_type": source_type,
            "language": language,
            "peer_review_status": peer_review,
            "evidence_note": evidence,
            "notes": notes,
            "artifacts": [{"artifact": artifact, "original_id": original_id}],
        }
        self.by_key[key] = sid
        return sid


def make_technique(*, artifact, original_id, entry_type, title_ja, title_en=None,
                   terms=None, summary_ja=None, operation_ja=None, function_ja=None,
                   mechanism_ja=None, limitations_ja=None, origin_ja=None,
                   examples=None, media=None, domains=None, source_ids=None,
                   evidence_level=None, verification=None, related_ids=None,
                   extra=None, derive_operation_from_mechanism=False):
    extra = dict(extra or {})
    if not _has_text(operation_ja) and derive_operation_from_mechanism \
            and _has_text(mechanism_ja):
        # The China catalog stores the procedural description in `mechanism`.
        # Keep the original in `mechanism_ja` and expose it as an operation,
        # flagged so that consumers can tell a stated step from a derived one.
        operation_ja = mechanism_ja
        extra["operation_origin"] = "mechanism_derived"
    else:
        extra["operation_origin"] = "stated" if _has_text(operation_ja) else "none"
    rec = {
        "id": f"{artifact}:{original_id}",
        "schema_version": SCHEMA_VERSION,
        "artifact": artifact,
        "original_id": original_id,
        "entry_type": entry_type,
        "title_ja": clean(title_ja),
        "title_en": clean(title_en),
        "terms": [t for t in (terms or []) if t],
        "summary_ja": clean(summary_ja),
        "operation_ja": clean(operation_ja),
        "function_ja": clean(function_ja),
        "mechanism_ja": clean(mechanism_ja),
        "limitations_ja": clean(limitations_ja),
        "origin_ja": clean(origin_ja),
        "examples": examples or [],
        "media": [m for m in (media or []) if m],
        "domains": sorted({d for d in (domains or []) if d in DOMAINS}),
        "source_ids": sorted(set(source_ids or [])),
        "evidence": {
            "level": evidence_level,
            "verification": verification,
            "source_count": len(set(source_ids or [])),
        },
        "related_ids": sorted(set(related_ids or [])),
        "language": "ja",
        "rights": "bibliographic citation only; no third-party full text is redistributed",
        "mapping_authorship": {
            "domains": "editorial",
            "summary": "extractive from the source catalog; see provenance.path",
        },
        "provenance": {"path": f"research/curated/{artifact}"},
    }
    rec["extra"] = extra
    return rec


ARTIFACT_LABELS = {
    "narrative/japan_2026": "日本 技法カタログ",
    "narrative/us_2026": "米国 技法カタログ",
    "narrative/us_2025": "米国 パラダイム索引",
    "narrative/china_2026": "中国 技法カタログ",
    "production/game_narrative_us": "米国 ゲーム制作実務",
    "history_myth/comparative_mythology": "比較神話",
    "history_myth/classification_systems": "物語分類体系",
}

TIER_LABELS = {
    "executable": "そのままスキル化できる",
    "partial": "条件を補えば使える",
    "reference_only": "分類・評価の語彙として使う",
}


def render_executability_summary(executability, exec_by_artifact, tier_counts,
                                 criterion_counts, origin_counts, seed_coverage=None):
    """Markdown summary of the executability pass (generated, not hand-edited)."""
    total = len(executability)
    lines = [
        "# 実行可能度の集計（自動生成）",
        "",
        "`research/catalog/executability.jsonl` の要約です。"
        "`python3 scripts/build_research_catalog.py` で再生成されます。",
        "この数字は**レコードの書き方**を測ったもので、引用元の研究の質や"
        "技法の有効性を示すものではありません。",
        "",
        "## 判定基準（4 項目・各 1 点）",
        "",
        "| 項目 | 条件 | 意味 |",
        "| --- | --- | --- |",
        f"| 手順 | `operation_ja` が {MIN_PROCEDURE_CHARS} 文字以上 | 何をするかが書かれている |",
        "| 合格条件 | 手順・機能・仕組み・要約のいずれかに判定語（"
        + "・".join(ACCEPTANCE_CUES) + "）を含む | 出来を判定できる語がある |",
        f"| 失敗条件 | `limitations_ja` が {MIN_LIMITATION_CHARS} 文字以上 | 成立しない場合が書かれている |",
        "| 例 | 具体例が 1 件以上 | 抽象語だけではない |",
        "",
        "| 区分 | 条件 |",
        "| --- | --- |",
        "| `executable` | 手順と合格条件の両方があり、他の項目も概ね揃う |",
        "| `partial` | 手順か合格条件のどちらかが欠ける（2 点以上） |",
        "| `reference_only` | 0–1 点 |",
        "",
        "## 全体",
        "",
        f"対象: **{total} 件**（`techniques.jsonl` の全レコード）",
        "",
        "| 区分 | 件数 | 比率 | 読み方 |",
        "| --- | ---: | ---: | --- |",
    ]
    for tier in ("executable", "partial", "reference_only"):
        n = tier_counts.get(tier, 0)
        lines.append(f"| `{tier}` | {n} | {n / total:.0%} | {TIER_LABELS[tier]} |")
    lines += [
        "",
        "| 項目 | 該当件数 | 比率 |",
        "| --- | ---: | ---: |",
    ]
    for name in EXECUTABILITY_CRITERIA:
        n = criterion_counts.get(name, 0)
        lines.append(f"| {name} | {n} | {n / total:.0%} |")
    lines += [
        "",
        "手順の出所: "
        + "、".join(f"`{k}` {v} 件" for k, v in sorted(origin_counts.items()))
        + "。`mechanism_derived` は、原カタログが `mechanism` 欄に書いた手順を"
        "`operation_ja` として公開したものです（原文は `mechanism_ja` に残しています）。",
        "",
        "## 成果物別",
        "",
        "| 成果物 | 件数 | executable | partial | reference_only | 手順 | 合格条件 | 失敗条件 | 例 | 平均点 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for art, row in exec_by_artifact.items():
        label = ARTIFACT_LABELS.get(art, art)
        c = row["criteria"]
        lines.append(
            f"| `{art}`<br>{label} | {row['entries']} | {row['executable']} | {row['partial']} "
            f"| {row['reference_only']} | {c['procedure']} | {c['acceptance']} "
            f"| {c['failure_condition']} | {c['example']} | {row['mean_score']} |"
        )
    executable = sorted((r for r in executability if r["tier"] == "executable"),
                        key=lambda r: (-r["score"], r["id"]))
    partial = [r for r in executability if r["tier"] == "partial"]
    reference = [r for r in executability if r["tier"] == "reference_only"]
    lines += [
        "",
        "## そのままスキル化できる候補（先頭 20 件）",
        "",
        "| ID | タイトル | 点 | 領域 |",
        "| --- | --- | ---: | --- |",
    ]
    for r in executable[:20]:
        lines.append(f"| `{r['id']}` | {r['title_ja']} | {r['score']} | {', '.join(r['domains'])} |")
    lines += [
        "",
        "## `partial` を `executable` にするために足すもの",
        "",
        "| 足すもの | 件数 | 備考 |",
        "| --- | ---: | --- |",
        f"| 合格条件（判定語・基準） | {sum(1 for r in partial if 'acceptance' in r['missing'])} "
        "| 手順はあるが、出来を判定する語がない |",
        f"| 手順 | {sum(1 for r in partial if 'procedure' in r['missing'])} "
        "| 定義・分類しかない |",
        f"| 失敗条件 | {sum(1 for r in partial if 'failure_condition' in r['missing'])} "
        "| 成立しない場合が書かれていない |",
        f"| 例 | {sum(1 for r in partial if 'example' in r['missing'])} "
        "| 抽象語だけで具体例がない |",
        "",
        "## `reference_only` の内訳",
        "",
        "| 欠けている項目 | 件数 |",
        "| --- | ---: |",
    ]
    for name in EXECUTABILITY_CRITERIA:
        n = sum(1 for r in reference if name in r["missing"])
        lines.append(f"| {name} | {n} |")
    if seed_coverage:
        counts = seed_coverage["tier_counts"]
        lines += [
            "",
            "## スキル種（13 件）が参照する技法の内訳",
            "",
            f"`research/program/skill_seeds.jsonl` が引く技法 ID は "
            f"{seed_coverage['referenced_techniques']} 件（解決 {seed_coverage['resolved']} 件）。",
            "",
            "| 区分 | 件数 |",
            "| --- | ---: |",
        ]
        for tier in ("executable", "partial", "reference_only"):
            lines.append(f"| `{tier}` | {counts.get(tier, 0)} |")
    lines += [
        "",
        "## この集計で分からないこと",
        "",
        "* 手順が**正しいか**、**効くか**は分かりません。文章が揃っているかだけを見ています。",
        "* 合格条件は語彙の有無で判定しているため、"
        "「基準」という語を含むだけの項目も該当します（過大評価の可能性）。",
        "* 中国カタログの手順は `mechanism` からの導出なので、"
        "原典が手順として書いたとは限りません。",
        "* 成果物ごとに記述の詳しさが違うため、`mean_score` の横比較は"
        "「そのカタログの書き方」の比較であって、内容の比較ではありません。",
        "",
    ]
    return "\n".join(lines)


def build():
    sources = Sources()
    techniques: list[dict] = []
    taxonomies: list[dict] = []
    tools: list[dict] = []
    input_files: list[Path] = []
    local_maps: dict[str, dict[str, str]] = {}

    # ---------------------------------------------------------------- Japan 2026
    art = "narrative/japan_2026"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    lmap = {}
    for s in read_jsonl(path):
        lmap[s["source_id"]] = sources.add(
            art, s["source_id"], title=s.get("title"), authors=s.get("authors"),
            year=year_of(s.get("publication_date")), url=s.get("url"), doi=s.get("doi"),
            source_type=s.get("source_type_label") or s.get("source_type"),
            language=s.get("language"), peer_review=s.get("peer_review_status"),
            evidence=(s.get("verification") or {}).get("extent_label")
            if isinstance(s.get("verification"), dict) else None,
        )
    local_maps[art] = lmap
    path = CUR / art / "techniques.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        ev = t.get("evidence") or []
        techniques.append(make_technique(
            artifact=art, original_id=t["technique_id"], entry_type="technique",
            title_ja=t.get("title"), terms=t.get("japan_relation") and [],
            summary_ja=t.get("intended_function"), operation_ja=t.get("procedure"),
            function_ja=t.get("intended_function"), limitations_ja=t.get("limitations"),
            media=[t.get("documented_context")] if t.get("documented_context") else [],
            domains=JP2026_DOMAINS.get(t.get("category_code"), []),
            source_ids=[lmap.get(e.get("source_id")) for e in ev if e.get("source_id")],
            verification="; ".join(sorted({e.get("verification_extent") or "" for e in ev if e.get("verification_extent")})) or None,
            extra={"category": t.get("category"), "term_status": t.get("term_status"),
                   "operationalization": t.get("operationalization"),
                   "cross_media_effectiveness": t.get("cross_media_effectiveness"),
                   "evidence_locators": [{"source_id": lmap.get(e.get("source_id")),
                                          "pinpoint": e.get("pinpoint"),
                                          "assertion_kind": e.get("source_assertion_kind")}
                                         for e in ev if e.get("source_id")]},
        ))

    # ---------------------------------------------------------------- US 2026
    art = "narrative/us_2026"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    lmap = {}
    for s in read_jsonl(path):
        lmap[s["source_id"]] = sources.add(
            art, s["source_id"], title=s.get("title"), authors=s.get("authors"),
            year=s.get("year"), url=s.get("url"), doi=s.get("doi"),
            source_type=s.get("source_type"), language=s.get("language"),
            evidence=s.get("verification_label_ja"),
        )
    local_maps[art] = lmap
    path = CUR / art / "techniques.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        refs = t.get("references") or []
        techniques.append(make_technique(
            artifact=art, original_id=t["technique_id"],
            entry_type=t.get("entry_type") or "technique",
            title_ja=t.get("title_ja"), title_en=t.get("terms_en"),
            summary_ja=t.get("definition_ja"), operation_ja=t.get("creative_operation_ja"),
            mechanism_ja=t.get("theoretical_mapping_ja"),
            limitations_ja=t.get("conditions_and_limits_ja"),
            media=t.get("media"), domains=US2026_DOMAINS.get(t.get("category_id"), []),
            source_ids=[lmap.get(sid) for sid in (t.get("source_ids") or [])],
            evidence_level=t.get("primary_source_verification_level"),
            verification="; ".join(sorted({r.get("locator") or "" for r in refs if r.get("locator")})) or None,
            related_ids=[f"{art}:{r}" for r in (t.get("related_technique_ids") or [])],
            extra={"category_id": t.get("category_id"),
                   "definition_authorship": t.get("definition_authorship"),
                   "operation_authorship": t.get("operation_authorship"),
                   "efficacy_claim": t.get("efficacy_claim"),
                   "requires_original_text_check": t.get("requires_original_text_check_for_direct_quotation")},
        ))

    # ---------------------------------------------------------------- US 2025
    art = "narrative/us_2025"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    lmap = {}
    for s in read_jsonl(path):
        lmap[s["source_id"]] = sources.add(
            art, s["source_id"], title=s.get("title"), authors=s.get("authors"),
            year=s.get("year"), url=s.get("url"), doi=s.get("doi"),
            source_type=s.get("type"), notes=f"evidence tier {s.get('tier')}",
        )
    local_maps[art] = lmap
    path = CUR / art / "techniques.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        techniques.append(make_technique(
            artifact=art, original_id=t["technique_id"], entry_type="paradigm",
            title_ja=t.get("name_ja"), title_en=t.get("name_en"),
            summary_ja=t.get("summary_ja"), origin_ja=t.get("origin_or_proponents"),
            domains=US2025_DOMAINS.get(t.get("category"), []),
            source_ids=[lmap.get(sid) for sid in (t.get("primary_source_ids") or [])],
            verification="paradigm index; per-entry sources are a reading list, not an efficacy test",
            extra={"category": t.get("category")},
        ))

    # ---------------------------------------------------------------- China 2026
    art = "narrative/china_2026"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    lmap = {}
    for s in read_jsonl(path):
        lmap[s["source_id"]] = sources.add(
            art, s["source_id"], title=s.get("title"), authors=s.get("authors"),
            year=s.get("publication_year"), url=s.get("url"), doi=s.get("doi"),
            source_type=s.get("source_type"), language=s.get("language"),
            peer_review=s.get("peer_review_status"),
            evidence=(s.get("content_review") or {}).get("label_ja")
            if isinstance(s.get("content_review"), dict) else None,
        )
    local_maps[art] = lmap
    path = CUR / art / "catalog.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        example = t.get("example")
        techniques.append(make_technique(
            artifact=art, original_id=t["entry_id"],
            entry_type="technique" if t.get("entry_type") == "T" else "concept",
            title_ja=t.get("title_ja"), terms=t.get("terms"),
            summary_ja=t.get("definition_ja"), mechanism_ja=t.get("mechanism_ja"),
            derive_operation_from_mechanism=True,
            limitations_ja=t.get("limitations_ja"),
            examples=[example] if example else [],
            domains=CN_DOMAINS.get(t.get("category"), []),
            source_ids=[lmap.get(sid) for sid in (t.get("source_ids") or [])],
            evidence_level=t.get("evidence_grade"),
            verification=t.get("evidence_locator_ja"),
            related_ids=[f"{art}:{r}" for r in (t.get("related_entry_ids") or [])],
            extra={"category": t.get("category"), "entry_type_label": t.get("entry_type_label"),
                   "label_status": t.get("label_status"), "cutoff_date": t.get("cutoff_date")},
        ))

    # ---------------------------------------------------------------- Game practices (US)
    art = "production/game_narrative_us"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    lmap = {}
    for s in read_jsonl(path):
        lmap[s["source_id"]] = sources.add(
            art, s["source_id"], title=s.get("title"), authors=s.get("authors"),
            year=year_of(s.get("publication_date")), url=s.get("url"), doi=s.get("doi"),
            source_type=s.get("source_type"), language=s.get("language"),
            evidence=(s.get("verification") or {}).get("review_extent")
            if isinstance(s.get("verification"), dict) else None,
        )
    local_maps[art] = lmap
    path = CUR / art / "practices.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        techniques.append(make_technique(
            artifact=art, original_id=t["practice_id"], entry_type="practice",
            title_ja=t.get("title_ja"), summary_ja=t.get("description_ja"),
            operation_ja=t.get("description_ja"),
            limitations_ja=t.get("limitations_ja"),
            domains=t.get("domains"), media=["game"],
            source_ids=[lmap.get(sid) for sid in (t.get("source_ids") or [])],
            verification="production practice; PDCA mapping is analytical, not a studio claim",
            extra={"phase": t.get("phase"), "artifacts": t.get("artifacts"),
                   "classification": t.get("classification"), "pdca_ja": t.get("pdca_ja")},
        ))

    # ---------------------------------------------------------------- Comparative mythology
    art = "history_myth/comparative_mythology"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        embedded_ids = []
        for i, s in enumerate(t.get("sources") or [], 1):
            embedded_ids.append(sources.add(
                art, f"{t['id']}-S{i:02d}", title=s.get("title") or s.get("url"),
                url=s.get("url"), source_type="secondary_reference",
            ))
        ca = t.get("creative_application") or {}
        techniques.append(make_technique(
            artifact=art, original_id=t["id"], entry_type="concept",
            title_ja=t.get("title"), summary_ja=t.get("summary"),
            operation_ja=" / ".join(v for v in [ca.get("practical_tips")] if v) or None,
            mechanism_ja=" / ".join(ca.get("structural_framework") or []) or None,
            examples=(t.get("mythological_examples") or []) + (t.get("creative_work_examples") or []),
            domains=MYTH_DOMAINS.get(t.get("domain"), []),
            source_ids=embedded_ids,
            verification="comparative secondary synthesis; primary texts not re-read",
            extra={"academic_discipline": t.get("academic_discipline"),
                   "key_figures": t.get("key_figures"), "core_works": t.get("core_works"),
                   "creative_use_cases": ca.get("use_cases")},
        ))

    # ---------------------------------------------------------------- Classification systems
    art = "history_myth/classification_systems"
    path = CUR / art / "catalog.jsonl"
    input_files.append(path)
    for t in read_jsonl(path):
        embedded_ids = []
        for i, s in enumerate(t.get("sources") or [], 1):
            embedded_ids.append(sources.add(
                art, f"{t['id']}-S{i:02d}", title=s.get("title") or s.get("url"),
                url=s.get("url"), source_type="classification_reference",
            ))
        taxonomies.append({
            "id": f"{art}:{t['id']}",
            "schema_version": SCHEMA_VERSION,
            "artifact": art,
            "original_id": t["id"],
            "entry_type": "taxonomy",
            "title_ja": t.get("name"),
            "title_en": t.get("name"),
            "alternate_names": t.get("alternate_names") or [],
            "scope_ja": t.get("scope"),
            "unit": t.get("unit"),
            "classification_ja": t.get("classification"),
            "operation_ja": t.get("creative_use"),
            "limitations_ja": t.get("limitations"),
            "access_note": t.get("access"),
            "source_ids": sorted(set(embedded_ids)),
            "domains": ["story", "world", "history"],
            "language": "ja",
            "rights": "bibliographic citation only",
            "mapping_authorship": {"domains": "editorial"},
            "provenance": {"path": f"research/curated/{art}"},
        })

    # ---------------------------------------------------------------- AI skills catalog (tools)
    art = "ai_creation/skills_catalog"
    path = CUR / art / "sources.jsonl"
    input_files.append(path)
    source_by_url = {}
    for s in read_jsonl(path):
        sid = sources.add(art, s["source_id"], title=s.get("title"), url=s.get("url"),
                          source_type=s.get("source_type"), language="ja",
                          notes=s.get("used_for"))
        source_by_url[norm_url(s.get("url"))] = sid
    path = CUR / art / "catalog.jsonl"
    input_files.append(path)
    seen_tool_urls = set()
    for t in read_jsonl(path):
        url = norm_url(t.get("url"))
        if url in seen_tool_urls:
            continue
        seen_tool_urls.add(url)
        tools.append({
            "id": f"{art}:{t['catalog_id']}",
            "schema_version": SCHEMA_VERSION,
            "artifact": art,
            "original_id": t.get("catalog_id"),
            "entry_type": "skill_or_tool",
            "name": t.get("name"),
            "title_ja": t.get("name"),
            "url": t.get("url"),
            "platform": t.get("platform"),
            "category": t.get("category"),
            "subtags": t.get("subtags") or [],
            "format": t.get("format"),
            "deliverables": t.get("deliverables"),
            "techniques_ja": t.get("techniques"),
            "best_for_ja": t.get("best_for"),
            "install": t.get("install"),
            "caveats_ja": t.get("caveats"),
            "documentation_language": t.get("documentation_language"),
            "scores": t.get("scores") or {},
            "score_total": t.get("score_total"),
            "rank": t.get("rank"),
            "license": t.get("license"),
            "stars": t.get("stars"),
            "last_pushed_at": t.get("last_pushed_at"),
            "retrieved_at": t.get("retrieved_at"),
            "source_ids": sorted({sid for sid in [source_by_url.get(url)] if sid}),
            "domains": ["meta", "production"],
            "rights": "points to third-party repositories; no code is redistributed",
            "provenance": {"path": f"research/curated/{art}"},
        })

    # ---------------------------------------------------------------- Pipeline tools
    art = "ai_creation/pipeline_catalog"
    path = CUR / art / "tools.jsonl"
    input_files.append(path)
    seen_tool_urls = set()
    for t in read_jsonl(path):
        url = norm_url(t.get("url"))
        if url in seen_tool_urls:
            continue
        seen_tool_urls.add(url)
        sid = sources.add(art, t["id"], title=t.get("name"), url=t.get("url"),
                          source_type="github_repository_or_dataset")
        tools.append({
            "id": f"{art}:{t['id']}",
            "schema_version": SCHEMA_VERSION,
            "artifact": art,
            "original_id": t.get("id"),
            "entry_type": "pipeline_tool",
            "name": t.get("name"),
            "title_ja": t.get("name"),
            "url": t.get("url"),
            "platform": t.get("platform"),
            "category": t.get("category"),
            "subtags": [],
            "format": ", ".join(t.get("tech_stack") or []),
            "deliverables": None,
            "techniques_ja": t.get("description"),
            "best_for_ja": t.get("practicality"),
            "install": None,
            "caveats_ja": None,
            "documentation_language": None,
            "scores": {},
            "score_total": None,
            "rank": None,
            "license": None,
            "stars": None,
            "last_pushed_at": None,
            "retrieved_at": None,
            "pipeline_stage": t.get("pipeline_stage"),
            "pdca_role_ja": t.get("pdca_role"),
            "source_ids": [sid],
            "domains": ["meta", "production"],
            "rights": "points to third-party repositories; no code is redistributed",
            "provenance": {"path": f"research/curated/{art}"},
        })

    # ---------------------------------------------------------------- cross-artifact tool dedupe
    merged_tools: dict[str, dict] = {}
    for rec in tools:
        key = norm_url(rec.get("url")) or rec["id"]
        if key in merged_tools:
            base = merged_tools[key]
            base["source_ids"] = sorted(set(base.get("source_ids", [])) | set(rec.get("source_ids", [])))
            for k, v in rec.items():
                if base.get(k) in (None, "", [], {}) and v not in (None, "", [], {}):
                    base[k] = v
            base.setdefault("merged_from", []).append(rec["id"])
        else:
            merged_tools[key] = rec
    tools = list(merged_tools.values())

    # ---------------------------------------------------------------- validate & write
    for rec in techniques:
        rec["source_ids"] = sorted({s for s in rec["source_ids"] if s})
        rec["evidence"]["source_count"] = len(rec["source_ids"])
    for rec in taxonomies:
        rec["source_ids"] = sorted({s for s in rec["source_ids"] if s})
    for rec in tools:
        rec["source_ids"] = sorted({s for s in rec["source_ids"] if s})

    ids = [r["id"] for r in techniques + taxonomies + tools]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    if dupes:
        raise SystemExit(f"duplicate ids: {dupes[:10]}")

    # related ids may point outside the normalized set; keep only resolvable ones
    known = set(ids)
    unresolved_related = 0
    for rec in techniques:
        kept = [r for r in rec["related_ids"] if r in known]
        unresolved_related += len(rec["related_ids"]) - len(kept)
        rec["related_ids"] = kept

    missing_sources = sorted({sid for rec in techniques + taxonomies + tools
                              for sid in rec["source_ids"] if sid not in sources.records})
    if missing_sources:
        raise SystemExit(f"unknown source ids: {missing_sources[:10]}")

    OUT.mkdir(parents=True, exist_ok=True)

    def dump(name, rows):
        with (OUT / name).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    executability = sorted((assess_executability(rec) for rec in techniques),
                           key=lambda r: r["id"])

    dump("techniques.jsonl", techniques)
    dump("taxonomies.jsonl", taxonomies)
    dump("tools.jsonl", tools)
    dump("sources.jsonl", sorted(sources.records.values(), key=lambda r: r["id"]))
    dump("executability.jsonl", executability)

    inputs = {}
    for p in sorted(set(input_files)):
        inputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()

    # ---- executability roll-up -------------------------------------------
    tier_counts = Counter(r["tier"] for r in executability)
    criterion_counts = Counter(
        name for r in executability for name, ok in r["criteria"].items() if ok
    )
    origin_counts = Counter(r["operation_origin"] for r in executability)
    exec_by_artifact = {}
    for art in sorted({r["artifact"] for r in executability}):
        rows = [r for r in executability if r["artifact"] == art]
        exec_by_artifact[art] = {
            "entries": len(rows),
            "executable": sum(1 for r in rows if r["tier"] == "executable"),
            "partial": sum(1 for r in rows if r["tier"] == "partial"),
            "reference_only": sum(1 for r in rows if r["tier"] == "reference_only"),
            "criteria": {name: sum(1 for r in rows if r["criteria"][name])
                         for name in EXECUTABILITY_CRITERIA},
            "mean_score": round(sum(r["score"] for r in rows) / len(rows), 2) if rows else 0.0,
        }

    seed_path = ROOT / "research" / "program" / "skill_seeds.jsonl"
    seed_coverage = None
    if seed_path.is_file():
        referenced = sorted({tid for seed in read_jsonl(seed_path)
                             for tid in seed.get("technique_ids") or []})
        exec_by_id = {r["id"]: r for r in executability}
        known = [exec_by_id[i] for i in referenced if i in exec_by_id]
        seed_coverage = {
            "seeds": sum(1 for _ in read_jsonl(seed_path)),
            "referenced_techniques": len(referenced),
            "resolved": len(known),
            "tier_counts": dict(sorted(Counter(r["tier"] for r in known).items())),
            "unresolved_ids": [i for i in referenced if i not in exec_by_id],
        }
        coverage_note = ("スキル種が参照する技法のうち、そのまま手順として使えるものは "
                         f"{seed_coverage['tier_counts'].get('executable', 0)} 件。")

    by_artifact = Counter(r["artifact"] for r in techniques)
    by_entry_type = Counter(r["entry_type"] for r in techniques)
    by_domain = Counter(d for r in techniques for d in r["domains"])
    by_level = Counter(r["evidence"]["level"] or "unrated" for r in techniques)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "generator": "scripts/build_research_catalog.py",
        "counts": {
            "techniques": len(techniques),
            "taxonomies": len(taxonomies),
            "tools": len(tools),
            "sources": len(sources.records),
        },
        "by_artifact": dict(sorted(by_artifact.items())),
        "by_entry_type": dict(sorted(by_entry_type.items())),
        "by_domain": dict(sorted(by_domain.items())),
        "by_evidence_level": dict(sorted(by_level.items())),
        "unresolved_related_ids": unresolved_related,
        "executability": {
            "definition": "lexical self-assessment of the catalog records; "
                          "not a judgement about the cited scholarship",
            "criteria": {
                "procedure": f"operation_ja exists and is >= {MIN_PROCEDURE_CHARS} characters",
                "acceptance": "the operational text names a pass/fail cue ("
                              + "/".join(ACCEPTANCE_CUES) + ")",
                "failure_condition": f"limitations_ja exists and is >= {MIN_LIMITATION_CHARS} characters",
                "example": "at least one concrete work / practice / case",
            },
            "tiers": {
                "executable": "has both a procedure and an acceptance cue",
                "partial": "2+ criteria but missing a procedure or an acceptance cue",
                "reference_only": "0-1 criteria",
            },
            "tier_counts": dict(sorted(tier_counts.items())),
            "criterion_counts": {k: criterion_counts.get(k, 0) for k in EXECUTABILITY_CRITERIA},
            "operation_origin": dict(sorted(origin_counts.items())),
            "by_artifact": exec_by_artifact,
            "seed_coverage": seed_coverage,
        },
        "inputs_sha256": inputs,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    checks = {
        "unique_ids": not dupes,
        "all_techniques_have_title": all(r["title_ja"] for r in techniques),
        "all_techniques_have_domain": all(r["domains"] for r in techniques),
        "all_records_have_provenance": all(r.get("provenance", {}).get("path")
                                          for r in techniques + taxonomies + tools),
        "all_source_refs_resolve": not missing_sources,
        "all_sources_have_title": all(r["title"] for r in sources.records.values()),
        "all_citable_sources_have_url_or_doi": all(
            r["url"] or r["doi"] for r in sources.records.values()
            if r["source_type"] not in {"web_search_query", "api_search_query"}),
        "counts_match_manifest": (by_artifact.total() == len(techniques)),
        "executability_covers_all_techniques": (
            {r["id"] for r in executability} == {r["id"] for r in techniques}),
        "all_executability_tiers_valid": all(
            r["tier"] in {"executable", "partial", "reference_only"} for r in executability),
        "executability_scores_consistent": all(
            r["score"] == sum(r["criteria"].values()) for r in executability),
    }
    report = {
        "validated_on": GENERATED_ON,
        "status": "passed" if all(checks.values()) else "failed",
        "scope": "structural checks only; not a verification of the cited scholarship",
        "checks": checks,
        "counts": manifest["counts"],
        "unresolved_related_ids": unresolved_related,
    }
    (OUT / "executability_summary.md").write_text(
        render_executability_summary(executability, exec_by_artifact, tier_counts,
                                     criterion_counts, origin_counts, seed_coverage) + "\n",
        encoding="utf-8")
    (OUT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="rebuild in memory and compare outputs with the committed catalog")
    args = ap.parse_args(argv)
    if not args.check:
        return build()

    before = {p.name: p.read_bytes() for p in OUT.iterdir() if p.is_file()}
    rc = build()
    after = {p.name: p.read_bytes() for p in OUT.iterdir() if p.is_file()}
    changed = sorted(name for name in before.keys() | after.keys()
                     if before.get(name) != after.get(name))
    if changed:
        print("catalog is stale; run scripts/build_research_catalog.py", file=sys.stderr)
        print("changed: " + ", ".join(changed), file=sys.stderr)
        return 1
    print("catalog is up to date")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
