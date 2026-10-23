"""The relay is a human step, so the failure modes are human ones.

Copy-paste loses tags, repeats a block, or pastes an answer under the wrong key.
The tests pin what must happen then: refuse, say which tag, and never attach an
answer to a prompt it was not written for.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "relay_prompts.py"


def make_operator(tmp_path: Path, keys: tuple[str, ...] = ("s1-t01-s1-plan-a1",
                                                          "s0-t01-s1-draft-ch01-a1")) -> Path:
    root = tmp_path / "op"
    (root / "requests").mkdir(parents=True)
    for number, key in enumerate(keys, start=1):
        (root / "requests" / f"{key}.json").write_text(json.dumps({
            "key": key, "purpose": "plan" if "plan" in key else "draft:ch01",
            "system": "s1" if key.startswith("s1") else "s0",
            "task_id": "t01", "seed": number, "attempt": 1,
            "prompt_hash": f"{number:016x}",
            "prompt": f"{number} 番目のリクエスト本文。1000〜1400 字で。",
        }, ensure_ascii=False), encoding="utf-8")
    return root


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def export(root: Path) -> dict:
    result = cli("export", "--dir", str(root))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_export_writes_a_block_per_pending_request(tmp_path):
    root = make_operator(tmp_path)
    summary = export(root)
    assert summary["pending"] == 2 and summary["done"] == 0
    prompts = (root / "relay" / "PROMPTS.md").read_text(encoding="utf-8")
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))

    assert len(index["pending"]) == 2
    for item in index["pending"]:
        assert f"<<<ANSWER {item['tag']}>>>" in prompts
        # The tag is opaque: it must not spell out the run key it stands for.
        assert item["key"] not in prompts
        assert item["key"] not in item["tag"]
    assert "モデル役" in prompts, "the preamble has to be sent first"


def test_tags_are_stable_across_exports(tmp_path):
    root = make_operator(tmp_path)
    first = export(root)
    second = export(root)
    assert first == second
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    tags = {item["key"]: item["tag"] for item in index["pending"]}
    assert len(set(tags.values())) == len(tags), "two requests must not share a tag"


def test_ingest_writes_the_answer_under_the_pinned_hash(tmp_path):
    root = make_operator(tmp_path)
    export(root)
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    tag = index["pending"][0]["tag"]
    answers = tmp_path / "answers.txt"
    answers.write_text(
        f"はい、承知しました。\n\n<<<ANSWER {tag}>>>\n本文です。\n二行目。\n<<<END {tag}>>>\n",
        encoding="utf-8")

    result = cli("ingest", "--dir", str(root), "--file", str(answers))
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["written"] == [index["pending"][0]["key"]]
    assert summary["still_pending"] == 1

    stored = json.loads((root / "responses" /
                         f"{index['pending'][0]['key']}.json").read_text(encoding="utf-8"))
    assert stored["text"] == "本文です。\n二行目。"
    assert stored["prompt_hash"] == index["pending"][0]["prompt_hash"]
    assert stored["model"] == "arena-chat-worker"
    assert stored["model_version"].startswith("unversioned-")


def test_an_unknown_tag_is_rejected_not_guessed(tmp_path):
    root = make_operator(tmp_path)
    answers = tmp_path / "answers.txt"
    answers.write_text("<<<ANSWER ZZZZ>>>\n本文。\n<<<END ZZZZ>>>\n", encoding="utf-8")
    result = cli("ingest", "--dir", str(root), "--file", str(answers))
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary["written"] == []
    assert summary["rejected"][0]["reason"] == "unknown tag"
    assert not (root / "responses").exists()


def test_a_repeated_block_is_rejected(tmp_path):
    root = make_operator(tmp_path)
    export(root)
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    tag = index["pending"][0]["tag"]
    answers = tmp_path / "answers.txt"
    answers.write_text(
        f"<<<ANSWER {tag}>>>\n一つ目。\n<<<END {tag}>>>\n\n"
        f"<<<ANSWER {tag}>>>\n二つ目。\n<<<END {tag}>>>\n", encoding="utf-8")
    result = cli("ingest", "--dir", str(root), "--file", str(answers))
    summary = json.loads(result.stdout)
    assert summary["rejected"][0]["reason"] == "duplicate tag in the same file"
    stored = json.loads((root / "responses" /
                         f"{index['pending'][0]['key']}.json").read_text(encoding="utf-8"))
    assert stored["text"] == "一つ目。"


def test_an_error_block_is_reported_and_not_stored(tmp_path):
    root = make_operator(tmp_path)
    export(root)
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    tag = index["pending"][0]["tag"]
    answers = tmp_path / "answers.txt"
    answers.write_text(f"<<<ERROR {tag}>>>\n文字数が足りません\n<<<END {tag}>>>\n",
                       encoding="utf-8")
    result = cli("ingest", "--dir", str(root), "--file", str(answers))
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary["errors"] == [{"tag": tag, "reason": "文字数が足りません"}]
    assert not (root / "responses").exists()


def test_answered_requests_drop_out_of_the_next_export(tmp_path):
    root = make_operator(tmp_path)
    export(root)
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    tag = index["pending"][0]["tag"]
    answers = tmp_path / "answers.txt"
    answers.write_text(f"<<<ANSWER {tag}>>>\n本文。\n<<<END {tag}>>>\n", encoding="utf-8")
    cli("ingest", "--dir", str(root), "--file", str(answers))

    summary = export(root)
    assert summary == {"pending": 1, "done": 1, "out": str(root / "relay")}
    prompts = (root / "relay" / "PROMPTS.md").read_text(encoding="utf-8")
    assert f"<<<ANSWER {tag}>>>" not in prompts


def test_a_mistyped_tag_is_accepted_only_when_mapped(tmp_path):
    """A chat sometimes tags the answer 'ch01' instead of the given tag.

    Guessing would defeat the point, so the mapping has to be explicit; when it
    is, the answer is stored under the right key and the remap is reported.
    """
    root = make_operator(tmp_path)
    export(root)
    index = json.loads((root / "relay" / "index.json").read_text(encoding="utf-8"))
    target = index["pending"][0]

    answers = tmp_path / "answers.txt"
    answers.write_text("<<<ANSWER ch01>>>\n本文です。\n<<<END ch01>>>\n", encoding="utf-8")

    without = cli("ingest", "--dir", str(root), "--file", str(answers))
    assert without.returncode == 1
    assert json.loads(without.stdout)["rejected"][0]["reason"] == "unknown tag"

    with_map = cli("ingest", "--dir", str(root), "--file", str(answers),
                   "--map", f"ch01={target['tag']}")
    assert with_map.returncode == 0, with_map.stderr
    summary = json.loads(with_map.stdout)
    assert summary["remapped"] == [{"from": "ch01", "to": target["tag"]}]
    assert summary["written"] == [target["key"]]

    stored = json.loads((root / "responses" / f"{target['key']}.json").read_text(encoding="utf-8"))
    assert stored["text"] == "本文です。"
    assert stored["prompt_hash"] == target["prompt_hash"]


def test_a_map_without_an_equals_sign_is_a_usage_error(tmp_path):
    root = make_operator(tmp_path)
    answers = tmp_path / "answers.txt"
    answers.write_text("<<<ANSWER ch01>>>\n本文。\n<<<END ch01>>>\n", encoding="utf-8")
    result = cli("ingest", "--dir", str(root), "--file", str(answers), "--map", "ch01")
    assert result.returncode == 2
    assert "FROM=TO" in result.stderr
