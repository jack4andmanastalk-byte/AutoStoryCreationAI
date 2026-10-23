"""Deterministic measurements for a story.

Everything in this module is computed without a language model, so the numbers
are reproducible and can be diffed between revisions. Some are standard
(counts, dialogue ratio); others are **proxies** for style uniformity, based on
the Japanese findings summarised in the research corpus. Proxies are labelled
``kind: "proxy"`` and must not be presented as validated quality scores.

References used for the proxies (see research/curation/added_sources.jsonl):

* ADD-20 (三浦 2026) — orthographic choice converges across LLMs, while the
  distribution of hiragana before a comma is model-specific.
* ADD-19 (Asano & Bastos 2026) — AI involvement raises mean quality but narrows
  the variance between works.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])\s*|\n+")
DIALOGUE = re.compile(r"「([^」]*)」")
COMMA = "、"

#: pairs where Japanese allows a kanji or a hiragana spelling
ORTHOGRAPHIC_PAIRS = {
    "こと/事": (re.compile(r"こと"), re.compile(r"事")),
    "できる/出来る": (re.compile(r"できる"), re.compile(r"出来る")),
    "ため/為": (re.compile(r"ため"), re.compile(r"為")),
    "もの/物": (re.compile(r"もの"), re.compile(r"物")),
}


@dataclass
class Document:
    path: Path
    text: str

    @property
    def chars(self) -> int:
        return len(re.sub(r"\s", "", self.text))


def load_documents(text_dir: str | Path) -> list[Document]:
    root = Path(text_dir)
    paths = sorted(p for p in root.iterdir()
                   if p.is_file() and p.suffix.lower() in {".md", ".txt", ".markdown"})
    return [Document(path=p, text=p.read_text(encoding="utf-8")) for p in paths]


def _sentences(text: str) -> list[str]:
    stripped = re.sub(r"\{\{[^}]*\}\}", "", text)  # markers are not prose
    return [s.strip() for s in SENTENCE_SPLIT.split(stripped) if s.strip()]


def style_uniformity(texts: list[str]) -> dict:
    """Proxies for stylistic homogenisation (ADD-20).

    * ``orthography_dominance`` — for each kanji/hiragana pair, the share of the
      dominant spelling. High values mean one spelling is used consistently;
      across many works, uniformly high values suggest homogenisation.
    * ``pre_comma_hiragana_rate`` — share of commas preceded by a hiragana.
    * ``sentence_length_cv`` — coefficient of variation of sentence length.
      Low values mean uniform rhythm.
    """
    joined = "\n".join(texts)
    pairs: dict[str, dict] = {}
    for label, (hira, kanji) in ORTHOGRAPHIC_PAIRS.items():
        h, k = len(hira.findall(joined)), len(kanji.findall(joined))
        total = h + k
        pairs[label] = {
            "hiragana": h,
            "kanji": k,
            "dominance": round(max(h, k) / total, 3) if total else None,
            "uses": total,
        }
    commas = [m.start() for m in re.finditer(COMMA, joined)]
    hiragana_before = sum(
        1 for i in commas
        if i > 0 and "\u3041" <= joined[i - 1] <= "\u309f"
    )
    lengths = [len(s) for s in _sentences(joined)]
    return {
        "kind": "proxy",
        "note_ja": "文体の均質化を測る代理指標。作品の質を直接測るものではない。",
        "orthography": pairs,
        "pre_comma_hiragana_rate": round(hiragana_before / len(commas), 3) if commas else None,
        "comma_count": len(commas),
        "sentence_length_mean": round(statistics.mean(lengths), 1) if lengths else 0.0,
        "sentence_length_cv": (
            round(statistics.pstdev(lengths) / statistics.mean(lengths), 3)
            if len(lengths) > 1 and statistics.mean(lengths) else None
        ),
        "sentence_count": len(lengths),
    }


def dialogue_ratio(text: str) -> float:
    lines = [m.group(1) for m in DIALOGUE.finditer(text)]
    quoted = sum(len(s) for s in lines)
    stripped = len(re.sub(r"\s", "", DIALOGUE.sub("", text)))
    total = quoted + stripped
    return round(quoted / total, 3) if total else 0.0


def measure(documents: list[Document]) -> dict:
    texts = [d.text for d in documents]
    joined = "\n".join(texts)
    chars = sum(d.chars for d in documents)
    paragraphs = [p for p in re.split(r"\n\s*\n", joined) if p.strip()]
    return {
        "documents": len(documents),
        "chars": chars,
        "paragraphs": len(paragraphs),
        "mean_paragraph_chars": round(chars / len(paragraphs), 1) if paragraphs else 0.0,
        "dialogue_ratio": dialogue_ratio(joined),
        "style": style_uniformity(texts),
    }


def find_forbidden(documents: list[Document], patterns: list[dict]) -> list[dict]:
    """Deterministic pattern checks (``patterns`` from a YAML file).

    Each pattern is ``{id, pattern, message_ja, severity, note?}``. Patterns are
    applied line by line so that a hit can be reported with a file and line.
    """
    hits: list[dict] = []
    for pattern in patterns:
        try:
            regex = re.compile(pattern["pattern"])
        except re.error as exc:  # a broken pattern must not break the run
            hits.append({"id": pattern.get("id", "?"), "error": str(exc),
                         "severity": "low", "message_ja": "正規表現が不正"})
            continue
        for document in documents:
            for number, line in enumerate(document.text.splitlines(), start=1):
                for match in regex.finditer(line):
                    hits.append({
                        "id": pattern.get("id"),
                        "severity": pattern.get("severity", "low"),
                        "message_ja": pattern.get("message_ja", ""),
                        "pattern": pattern["pattern"],
                        "match": match.group(0)[:80],
                        "evidence": {"path": document.path.name, "line": number},
                    })
    return hits


def density(defects: int, chars: int) -> float | None:
    """Defects per 10,000 characters (ConStory-Bench CED analogue)."""
    return round(defects / chars * 10_000, 3) if chars else None
