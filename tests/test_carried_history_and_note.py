"""Carried design history (F-31) and the operator's revision note (F-32).

A ``revise`` used to write every carried design document as
``attempts 0 / repairs 0``, so the human summary of a revised work claimed
nothing had been repaired.  A revise also had no way to say *why* a chapter was
regenerated; the note is now part of the prompt and of the revision record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.project import ProjectRunner, ProjectStore, WorkSpec  # noqa: E402
from asc.project.summary import ProjectSummary, _inherited_history  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"


def responses() -> dict[str, str]:
    out = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            out[":".join(parts[:-1])] = text
    return out


def revised_chapter(day: int = 4) -> str:
    return (
        f"{{{{time: day={day}}}}}{{{{location: 灯台}}}}\n"
        + "改訂された章の本文です。潮の記録を読み直し、灯台の窓を開ける。" * 30
    )


def spec() -> WorkSpec:
    return WorkSpec(
        title="潮の記憶", premise="潮の記憶の短い物語。", chapter_count=3,
        target_chars_per_chapter=1200,
    )


def completed_project(tmp_path: Path):
    store = ProjectStore(tmp_path)
    snapshot = store.create_project(spec(), project_id="prj-carried")
    ProjectRunner(store).run("prj-carried", ScriptedProvider(responses()))
    return store, snapshot


def design_run(store: ProjectStore, status: dict, project_id: str = "prj-carried") -> Path:
    return store.project_dir(project_id) / "runs" / status["checkpoints"]["design"]["run_id"]


def test_a_carried_design_document_keeps_its_attempt_history(tmp_path: Path):
    store, _ = completed_project(tmp_path)
    runner = ProjectRunner(store)
    before = store.status("prj-carried")
    before_rows = json.loads(
        (design_run(store, before) / "design.json").read_text(encoding="utf-8")
    )["docs"]
    assert before_rows["brief"]["attempts"] >= 1

    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    result = runner.revise("prj-carried", ScriptedProvider(scripted), chapters=("ch02",))
    after_rows = json.loads(
        (design_run(store, result.status) / "design.json").read_text(encoding="utf-8")
    )["docs"]

    assert after_rows["brief"]["status"] == "carried"
    assert after_rows["brief"]["attempts"] == before_rows["brief"]["attempts"]
    assert after_rows["brief"]["repairs"] == before_rows["brief"]["repairs"]
    # The inherited history must not carry run ids: a recorded-response replay
    # reproduces this file byte for byte.
    assert "carried_from" not in after_rows["brief"]

    summary = ProjectSummary(store).summarize("prj-carried")
    docs = {doc["doc"]: doc for doc in summary.design["documents"]}
    assert docs["brief"]["attempts"] == before_rows["brief"]["attempts"]
    assert summary.design["repairs_total"] == before_rows["brief"]["repairs"] + sum(
        int(row.get("repairs") or 0) for row in before_rows.values()
    )
    assert "元リビジョンの履歴を引き継ぎ" in summary.markdown
    assert "**設計の累計**" in summary.markdown


def test_older_zero_rows_fall_back_to_the_source_revision(tmp_path: Path):
    """Runs written before the fix stored zeros; the summary still finds the source."""
    rows_by_revision = {
        "rev-a": {"brief": {"attempts": 2, "repairs": 1, "findings": 0}},
        "rev-b": {"brief": {"attempts": 0, "repairs": 0, "findings": 0}},
    }
    inherited = _inherited_history(rows_by_revision, ["rev-b", "rev-a"], "brief")
    assert inherited == {"attempts": 2, "repairs": 1, "findings": 0, "run_id": "rev-a"}
    assert _inherited_history(rows_by_revision, ["rev-b"], "brief") is None


def test_revise_note_reaches_the_prompt_and_the_revision(tmp_path: Path):
    store, _ = completed_project(tmp_path)
    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    provider = ScriptedProvider(scripted)
    note = "同じ内容の台詞が二度出ているので、後半を一つに統合する。"
    result = ProjectRunner(store).revise(
        "prj-carried", provider, chapters=("ch02",), note=note,
    )

    prompt = provider.calls[0].prompt
    assert "## 改訂の意図" in prompt
    assert note in prompt
    assert result.status["derived"]["note"] == note

    revision = store.load_revision(
        "prj-carried", result.status["node_id"], result.status["current_revision_id"],
    )
    assert revision.derived["note"] == note

    summary = ProjectSummary(store).summarize("prj-carried")
    assert summary.info["revise_note"] == note
    assert f"**改訂の意図**: {note}" in summary.markdown
    assert summary.info["regenerated_chapters"] == ["ch02"]


def test_a_note_is_optional_and_bounded(tmp_path: Path):
    store, _ = completed_project(tmp_path)
    scripted = responses()
    scripted["draft:ch02"] = revised_chapter()
    provider = ScriptedProvider(scripted)
    result = ProjectRunner(store).revise("prj-carried", provider, chapters=("ch02",))
    assert "## 改訂の意図" not in provider.calls[0].prompt
    assert "note" not in result.status["derived"]


def test_a_continuation_carries_the_design_history_too(tmp_path: Path):
    """The continuation path carries brief/history/character/voice by design."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_project_continuation as continuation

    store = ProjectStore(tmp_path)
    snapshot = continuation.make_project(store, project_id="prj-cont-note")
    ProjectRunner(store).run(
        "prj-cont-note", ScriptedProvider(continuation.project_responses()),
    )
    before = store.status("prj-cont-note")
    before_rows = json.loads(
        (store.project_dir("prj-cont-note") / "runs"
         / before["checkpoints"]["design"]["run_id"] / "design.json").read_text(
            encoding="utf-8")
    )["docs"]

    result = ProjectRunner(store).continue_project(
        "prj-cont-note", ScriptedProvider(continuation.continuation_responses()),
    )
    after_rows = json.loads(
        (store.project_dir("prj-cont-note") / "runs"
         / result.stage_runs["design"] / "design.json").read_text(encoding="utf-8")
    )["docs"]
    carried = [name for name, row in after_rows.items() if row["status"] == "carried"]
    assert carried, "a continuation carries the chapter-independent documents"
    for name in carried:
        assert after_rows[name]["attempts"] == before_rows[name]["attempts"]
        assert after_rows[name]["repairs"] == before_rows[name]["repairs"]
