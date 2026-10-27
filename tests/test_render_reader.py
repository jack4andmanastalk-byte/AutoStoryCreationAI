"""The reading copy: chapter headings, no audit markers (U-08, F-17).

The rendered manuscript is the checked text: it carries ``{{time: …}}`` and
``{{foreshadow: …}}`` markers because the audit reads them, and its SHA-256 is
the recorded identity of the draft.  That makes it a poor thing to read: three
chapters run together with machine annotations inside sentences.

``render --reader`` writes the same work as a reading copy — one heading per
chapter and the markers dropped — while the default output stays byte for byte
what it was.  These tests pin both halves: the reading copy is readable, and
the checked text is untouched.

The draft text is the repository's scripted fixture, so this is a wiring check,
not model output and not a claim about quality.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "story_project.py"
FIXTURE = ROOT / "benchmarks" / "protocol-v1" / "fixtures" / "plan-demo.json"

sys.path.insert(0, str(ROOT / "src"))

from asc.pipeline import ScriptedProvider, load_scripted_responses  # noqa: E402
from asc.story.text import without_markers  # noqa: E402
from asc.project import ProjectComposer, ProjectRunner, ProjectStore, WorkSpec  # noqa: E402


def project_responses() -> dict[str, str]:
    responses = {}
    for key, text in load_scripted_responses(FIXTURE).items():
        parts = key.split(":")
        if parts[-1] == "t01":
            responses[":".join(parts[:-1])] = text
    return responses


def completed_store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path)
    store.create_project(
        WorkSpec(
            title="灯台の鍵",
            premise="灯台守の娘が、父の残した鍵を届ける。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        project_id="prj-reader",
    )
    ProjectRunner(store).run("prj-reader", ScriptedProvider(project_responses()))
    return store


def test_the_checked_text_keeps_its_markers_and_has_no_chapter_headings(tmp_path: Path):
    store = completed_store(tmp_path)
    checked = ProjectComposer(store).render("prj-reader").text

    assert "{{time:" in checked
    assert "## 第1章" not in checked
    # The markers are the reason the text is audited; their count is stable.
    assert checked.count("{{") == checked.count("}}") > 0


def test_the_reader_copy_adds_headings_and_drops_markers(tmp_path: Path):
    store = completed_store(tmp_path)
    reader = ProjectComposer(store).render("prj-reader", reader=True).text

    assert "{{" not in reader and "}}" not in reader
    assert reader.count("## 第") == 3
    assert "## 第1章" in reader and "## 第3章" in reader
    # The chapter ID survives in a comment, so a passage can still be traced.
    assert "<!-- asc-chapter: ch01 -->" in reader
    # Dropping a marker-only line must not leave an empty paragraph behind.
    assert "\n\n\n" not in reader


def test_the_reader_copy_keeps_the_prose_of_every_chapter(tmp_path: Path):
    store = completed_store(tmp_path)
    composer = ProjectComposer(store)
    checked = composer.render("prj-reader").text
    reader = composer.render("prj-reader", reader=True).text

    scripted = project_responses()
    for chapter_id in ("ch01", "ch02", "ch03"):
        first_line = scripted[f"draft:{chapter_id}"].splitlines()[1]
        assert first_line in checked
        # The reading copy is the same prose with the markers taken out.
        assert without_markers(first_line) in reader


def test_the_cli_writes_the_reader_copy_and_says_what_it_is(tmp_path: Path):
    completed_store(tmp_path)
    out = tmp_path / "reader.md"
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--root", str(tmp_path),
            "render", "prj-reader", "--reader", "--out", str(out), "--json",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sha256"]
    text = out.read_text(encoding="utf-8")
    assert "## 第1章" in text and "{{" not in text


def test_compose_reader_adds_nested_headings_and_drops_markers_from_all_works(tmp_path: Path):
    """U-06 / U-08: ``compose --reader`` formats the parent and every child."""
    store = completed_store(tmp_path)
    link = store.create_child(
        "prj-reader",
        WorkSpec(
            title="王都の預かり物",
            premise="鍵屋がアリアの父から予備の鍵を預かった日。",
            chapter_count=3,
            target_chars_per_chapter=1200,
        ),
        child_node_id="node-child",
        link_id="link-child",
    )
    ProjectRunner(store).run(
        "prj-reader", ScriptedProvider(project_responses()), node_id="node-child",
    )
    store.adopt_child("prj-reader", link.id)

    composer = ProjectComposer(store)
    checked = composer.compose("prj-reader").text
    reader = composer.compose("prj-reader", reader=True).text

    assert "{{time:" in checked
    assert "{{" not in reader and "}}" not in reader
    # Parent is H1 with H2 chapters; child is H2 with H3 chapters.
    assert "# 灯台の鍵" in reader
    assert "## 第1章" in reader
    assert "## 王都の預かり物" in reader
    assert "### 第1章" in reader

