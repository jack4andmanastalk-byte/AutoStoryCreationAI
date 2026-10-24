from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.style import VoiceError, check_voice, load_voice  # noqa: E402

DEMO = REPO_ROOT / "harness" / "cases" / "voice-demo"


def test_demo_detects_every_seeded_defect():
    """EXPECTED.md の 4 件が、その検査・行で検出されること。"""
    report = check_voice(load_voice(DEMO / "voice.yaml"), DEMO / "text")
    found = {(f["check"], f["evidence"]["line"]) for f in report["findings"]}
    assert ("viewpoint_slip", 2) in found
    assert ("pronoun_drift", 3) in found
    assert ("banned_voice", 4) in found
    assert ("banned_voice", 5) in found


def test_no_high_severity_is_ever_reported():
    report = check_voice(load_voice(DEMO / "voice.yaml"), DEMO / "text")
    assert all(f["severity"] in {"medium", "low"} for f in report["findings"])


def test_clean_chapter_passes(tmp_path):
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text(
        (DEMO / "text" / "ch01.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = check_voice(load_voice(DEMO / "voice.yaml"), text)
    assert report["findings"] == []


def test_missing_sample_is_skipped_not_failed(tmp_path):
    voice = tmp_path / "voice.yaml"
    voice.write_text(
        "viewpoint: {person: first, character: 凪, pronouns: [私]}\n"
        "narrator: {knows_ja: 凪が見たことだけ。}\n",
        encoding="utf-8")
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("私は歩いた。\n", encoding="utf-8")
    report = check_voice(load_voice(voice), text)
    skipped = {c["id"] for c in report["checks"] if c["status"] == "skipped"}
    assert {"banned_voice", "sample_drift"} <= skipped


def test_third_person_skips_pronoun_check(tmp_path):
    voice = tmp_path / "voice.yaml"
    voice.write_text(
        "viewpoint: {person: third, character: 凪}\n"
        "narrator: {knows_ja: 凪の視点。}\n",
        encoding="utf-8")
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("凪は歩いた。僕も歩いた。\n", encoding="utf-8")
    report = check_voice(load_voice(voice), text)
    pronoun = [c for c in report["checks"] if c["id"] == "pronoun_drift"][0]
    assert pronoun["status"] == "skipped"


def test_dialogue_is_not_judged(tmp_path):
    voice = tmp_path / "voice.yaml"
    voice.write_text(
        "viewpoint: {person: first, character: 凪, pronouns: [私]}\n"
        "narrator: {knows_ja: 凪が見たことだけ。}\n",
        encoding="utf-8")
    text = tmp_path / "text"
    text.mkdir()
    (text / "ch01.md").write_text("「彼は悟ったよ」と私は言った。\n", encoding="utf-8")
    report = check_voice(load_voice(voice), text)
    assert report["findings"] == []


def test_missing_character_is_an_input_error(tmp_path):
    voice = tmp_path / "voice.yaml"
    voice.write_text(
        "viewpoint: {person: first}\n"
        "narrator: {knows_ja: 何か。}\n",
        encoding="utf-8")
    with pytest.raises(VoiceError):
        load_voice(voice)


def test_cli_exit_codes():
    ok = subprocess.run(
        [sys.executable, "scripts/check_voice.py",
         "--voice", str(DEMO / "voice.yaml"), "--text", str(DEMO / "text"),
         "--fail-on", "none", "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, "scripts/check_voice.py",
         "--voice", str(DEMO / "voice.yaml"), "--text", str(DEMO / "text"),
         "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert bad.returncode == 1
