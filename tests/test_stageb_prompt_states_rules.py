"""The prompt must state the rules the checker enforces.

Batch A showed what happens when it does not: every sample's ch02 leaked
「三年前」 (a withheld term the premise itself uses) and two samples named the
dead without a medium in the same sentence. Both rules existed only inside
`check_rewrite`. These tests keep the prompt and the checker derived from the
same data, so the two cannot drift apart silently.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from asc.gamelog import load_game_log  # noqa: E402
from asc.gamelog.rewrite import check_rewrite, forbidden_terms  # noqa: E402
from asc.gamelog.world import build_world, derive_timeline  # noqa: E402
from asc.pipeline import load_prompt  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402
import export_stageb_prompts  # noqa: E402
import run_twostage  # noqa: E402

BUNDLE = REPO_ROOT / "experiments" / "2026-10-realrun-a-t01"
INPUTS = BUNDLE / "inputs"


@pytest.fixture(scope="module")
def context():
    canon = load_canon(INPUTS / "canon")
    scenes = load_scenes(INPUTS / "design" / "scene.json")
    log = load_game_log(INPUTS / "game_log.json")
    return {"canon": canon, "scenes": scenes, "log": log,
            "voice": load_voice(INPUTS / "design" / "voice.json"),
            "timeline": derive_timeline(log, canon, build_world(canon))}


def test_the_template_version_moved_past_the_run(context):
    template = load_prompt("stage-b-rewrite")
    assert template.version == "1.2"
    assert "$withheld" in template.text


def test_the_prompt_lists_the_terms_the_checker_flags(context):
    for chapter in ("ch01", "ch02", "ch03"):
        rendered = run_twostage.withheld_text(context["canon"],
                                              context["scenes"], chapter)
        terms = [item["term"] for item in forbidden_terms(
            context["canon"], context["scenes"], chapter)]
        for term in terms:
            assert f"「{term}」" in rendered, (chapter, term)
        if not terms:
            assert "なし" in rendered


def test_a_term_named_in_the_prompt_is_actually_refused(context):
    """Every word the prompt forbids is one the checker reports."""
    for chapter, term in (("ch02", "三年前"), ("ch01", "予備の鍵")):
        assert term in [item["term"] for item in
                        forbidden_terms(context["canon"], context["scenes"], chapter)]
        text = (f"{{{{time: day=1}}}}{{location: 灯台}}\n"
                f"アリアは{term}のことを考えた。灯台の灯りは消えなかった。\n")
        report = check_rewrite(text, chapter, context["log"], context["canon"],
                               timeline=context["timeline"])
        assert any(item["check"] == "fact_boundary" for item in report["findings"]), \
            (chapter, term)


def test_ch03_has_nothing_withheld(context):
    assert run_twostage.withheld_text(context["canon"], context["scenes"],
                                      "ch03").startswith("なし")


def test_the_rendered_prompt_carries_the_withheld_section(tmp_path):
    assert export_stageb_prompts.main(["--bundle", str(BUNDLE),
                                       "--out", str(tmp_path)]) == 0
    ch02 = (tmp_path / "ch02.prompt.md").read_text(encoding="utf-8")
    assert "## この章で書いてはいけない語" in ch02
    assert "「三年前」" in ch02
    assert "同じ文の中に媒体か参照の語" in ch02
    ch03 = (tmp_path / "ch03.prompt.md").read_text(encoding="utf-8")
    assert "なし（この章で伏せる語はない）" in ch03
