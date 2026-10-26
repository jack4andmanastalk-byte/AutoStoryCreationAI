"""The place check on other wordings: paraphrases fire, lookalikes stay silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import load_game_log  # noqa: E402
from asc.gamelog.surface import (movement_claims, place_findings,  # noqa: E402
                                 sentences)
from asc.gamelog.world import chapter_timeline, derive_timeline  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
import probe_surface_variants  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-stageb-v11-t01"
INPUTS = BUNDLE / "inputs"
ARMS = {
    "log-backed": BUNDLE / "relay" / "responses",
    "direct": REPO_ROOT / "experiments" / "2026-10-l1-pair-t01" / "relay" / "responses",
    "log-backed-v10": REPO_ROOT / "experiments" / "2026-10-full-t01" / "relay" / "responses",
}


@pytest.fixture(scope="module")
def context():
    canon = load_canon(INPUTS / "canon")
    log = load_game_log(INPUTS / "game_log.json")
    return {"canon": canon, "timeline": derive_timeline(log, canon)}


def row(context, chapter: str) -> dict:
    return chapter_timeline(context["timeline"], chapter)


def test_a_duration_before_the_place_is_not_part_of_the_name(context):
    # Real text (the v1.0 chapter 1) reads 「三日かけて王都へ着いた」; the leading
    # duration used to be carried into the destination.
    claims = movement_claims("三日かけて王都へ着いた。")
    assert [claim.destination for claim in claims] == ["王都"]
    assert place_findings("三日かけて王都へ着いた。", row(context, "ch01"),
                          context["canon"]) == []


def test_a_clause_before_the_place_is_trimmed(context):
    claims = movement_claims("一行は山を越えて村に着いた。")
    assert [claim.destination for claim in claims] == ["村"]
    findings = place_findings("一行は山を越えて村に着いた。", row(context, "ch01"),
                              context["canon"])
    assert [item["evidence"]["destination"] for item in findings] == ["村"]


def test_paraphrases_of_an_off_log_trip_all_fire(context):
    chapter_row = row(context, "ch01")
    for sentence, destination in (
            ("アリアは船で対岸の島へ渡り、知らない港町を歩いた。", "対岸の島"),
            ("その夜、アリアは対岸の島に向かった。", "対岸の島"),
            ("明け方には、北の港に着いた。", "北の港"),
            ("アリアは隣町へ戻った。", "隣町")):
        findings = place_findings(sentence, chapter_row, context["canon"])
        assert [item["evidence"]["destination"] for item in findings] == [destination]


def test_lookalikes_stay_silent(context):
    chapter_row = row(context, "ch01")
    for sentence in ("父は灯りの話に戻った。", "記憶の底へ沈んだ。",
                     "アリアは台所へ行った。", "島が見えた。", "風が沖へ向かった。",
                     "話は振り出しに戻った。", "マーサは手紙を胸に戻した。"):
        assert place_findings(sentence, chapter_row, context["canon"]) == [], sentence


def test_a_declared_move_is_allowed_and_an_undeclared_one_is_not(context):
    # ch01 declares 灯台→王都; ch03 declares nothing.
    assert place_findings("アリアは王都へ発った。", row(context, "ch01"),
                          context["canon"]) == []
    findings = place_findings("アリアは港へ向かった。", row(context, "ch03"),
                              context["canon"])
    assert [item["evidence"]["destination"] for item in findings] == ["港"]
    assert "宣言されていない" in findings[0]["message_ja"]


def test_known_misses_stay_misses(context):
    # Kept as a table entry, so the limit is visible rather than absent.
    chapter_row = row(context, "ch01")
    for sentence in ("アリアは王都の市場を目指して歩いた。", "対岸の島が霞んで見えた。"):
        assert place_findings(sentence, chapter_row, context["canon"]) == [], sentence


def test_the_variant_probe_records_recall_and_precision(tmp_path):
    out = tmp_path / "variants.json"
    completed = probe_surface_variants.main([
        "--game-log", str(INPUTS / "game_log.json"),
        "--canon", str(INPUTS / "canon"),
        *[item for name, path in ARMS.items() for item in ("--arm", f"{name}={path}")],
        "--out", str(out)])
    assert completed == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == "surface-variants-v1"
    summary = report["summary"]
    assert summary["clean_chapters"] == 9
    assert summary["clean_chapters_with_findings"] == 0
    assert summary["recall"]["missed"] == []
    assert summary["precision"]["false_positives"] == []
    assert report["limits"]
