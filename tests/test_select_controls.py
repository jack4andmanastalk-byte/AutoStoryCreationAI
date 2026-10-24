"""Control-group selection must be deterministic, rights-safe and strict.

The fixtures are synthetic: ten tiny metadata records and three tiny texts.
Nothing here touches the real 17,840-work catalog or the network.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import select_controls as controls  # noqa: E402
from asc.pipeline.tasks import load_tasks  # noqa: E402

TASKS = REPO_ROOT / "benchmarks" / "protocol-v1" / "tasks.yaml"


def work(work_id: str, title: str, code: str | None = "913",
         expired: bool = True) -> dict:
    return {
        "id": work_id, "title": title,
        "authors": [{"name": "誰か", "role": "author"}],
        "url": f"https://example.invalid/{work_id}",
        "text_url": f"https://example.invalid/{work_id}.zip",
        "genre": {"code": code, "label": "小説・物語", "taxonomy": "NDC"},
        "rights": {"copyright_flag": not expired, "source": "test"},
    }


def write_works(tmp_path: Path, works: list[dict]) -> Path:
    path = tmp_path / "works.jsonl"
    path.write_text("\n".join(json.dumps(w, ensure_ascii=False) for w in works)
                    + "\n", encoding="utf-8")
    return path


def test_genre_rules_keep_novels_and_drop_the_rest():
    assert controls.genre_allowed(work("a", "X", "913"))[0]
    assert controls.genre_allowed(work("a", "X", "933"))[0]
    assert not controls.genre_allowed(work("a", "X", "911"))[0]  # poetry
    assert not controls.genre_allowed(work("a", "X", "914"))[0]  # essays
    assert not controls.genre_allowed(work("a", "X", "912"))[0]  # plays
    assert not controls.genre_allowed(work("a", "X", "K913"))[0]  # children
    assert not controls.genre_allowed(work("a", "X", None))[0]  # unknown


def test_copyrighted_and_unknown_works_are_excluded():
    assert controls.rights_ok(work("a", "X", expired=True))[0]
    assert not controls.rights_ok(work("a", "X", expired=False))[0]
    assert not controls.rights_ok({"id": "a"})[0]


def test_propose_is_deterministic(tmp_path):
    works = [work(f"aozora:{i:06d}", f"昔話{i}") for i in range(10)]
    path = write_works(tmp_path, works)
    tasks = load_tasks(TASKS)
    first = controls.propose_candidates(works, tasks, tmp_path / "texts", 5, 0)
    second = controls.propose_candidates(works, tasks, tmp_path / "texts", 5, 0)
    assert first == second
    assert set(first["by_task"]) == {t.id for t in tasks.tasks}
    assert all(v["shortfall"] == 3 for v in first["by_task"].values())


def test_keyword_hits_rank_first_for_fantasy(tmp_path):
    works = [work("aozora:000001", "雪女"),
             work("aozora:000002", "何の変哲もない話")]
    tasks = load_tasks(TASKS)
    result = controls.propose_candidates(works, tasks, tmp_path / "texts", 5, 0)
    top = result["by_task"]["t01"]["candidates"][0]
    assert top["work_id"] == "aozora:000001"
    assert "雪女" in top["keywords"]


def test_cut_head_stays_inside_the_window():
    paras = ["あ" * 1000, "い" * 1000, "う" * 1000, "え" * 1000, "お" * 1000]
    body, span = controls.cut_head("\n\n".join(paras), (3000, 4200))
    assert 3000 <= controls.count_chars(body) <= 4200
    assert span["method"].startswith("head-cut")
    assert span["paragraphs"] == 4


def test_cut_head_refuses_an_impossible_window():
    with pytest.raises(ValueError, match="cannot cut"):
        controls.cut_head("あ" * 5000, (3000, 4200))


def test_freeze_validates_everything(tmp_path):
    body = "\n\n".join(["あ" * 1000] * 4)
    for i in range(1, 4):
        (tmp_path / f"texts").mkdir(exist_ok=True)
        (tmp_path / "texts" / f"{i:06d}.txt").write_text(body, encoding="utf-8")
    works = [work(f"aozora:{i:06d}", f"昔話{i}") for i in range(1, 4)]
    for i in range(4, 8):
        works.append(work(f"aozora:{i:06d}", f"昔話{i}"))
    for i in range(8, 12):
        works.append(work(f"aozora:{i:06d}", f"昔話{i}"))
    works += [work(f"aozora:{i:06d}", f"昔話{i}") for i in range(12, 31)]
    works_path = write_works(tmp_path, works)
    # texts for the first 30 only come in one size: reuse the same body
    for i in range(1, 31):
        (tmp_path / "texts" / f"{i:06d}.txt").write_text(body, encoding="utf-8")
    tasks = load_tasks(TASKS)
    ids = [f"aozora:{i:06d}" for i in range(1, 31)]
    approved = {"approved_by": "test", "approved_at": "2026-10-24",
                "picks": {t.id: ids[k * 3:k * 3 + 3]
                          for k, t in enumerate(tasks.tasks)}}
    approved_path = tmp_path / "approved.json"
    approved_path.write_text(json.dumps(approved, ensure_ascii=False),
                             encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "scripts/select_controls.py", "freeze",
         "--approved", str(approved_path), "--works", str(works_path),
         "--texts", str(tmp_path / "texts"), "--out", str(tmp_path / "controls.json"),
         "--emit-dir", str(tmp_path / "emitted"), "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    frozen = json.loads((tmp_path / "controls.json").read_text(encoding="utf-8"))
    assert len(frozen["works"]) == 30
    assert frozen["rules"] == controls.RULES_VERSION
    assert all(3000 <= w["chars"] <= 4200 for w in frozen["works"])
    assert len(list((tmp_path / "emitted").glob("*.txt"))) == 30


def test_freeze_rejects_duplicates_and_short_lists(tmp_path):
    works_path = write_works(tmp_path, [work("aozora:000001", "雪女")])
    bad = {"approved_by": "test",
           "picks": {"t01": ["aozora:000001", "aozora:000001", "aozora:000001"]}}
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "scripts/select_controls.py", "freeze",
         "--approved", str(bad_path), "--works", str(works_path),
         "--texts", str(tmp_path), "--out", str(tmp_path / "controls.json"),
         "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 2
    assert "exactly once" in completed.stderr or "exactly 3" in completed.stderr


def test_pool_keeps_only_expired_novels_and_labels_exclusions(tmp_path):
    works = [work("aozora:000001", "雪女", "913", True),
             work("aozora:000002", "詩集", "911", True),
             work("aozora:000003", "新作", "913", False),
             work("aozora:000004", "不明", None, True)]
    tasks = load_tasks(TASKS)
    result = controls.propose_candidates(works, tasks, tmp_path / "texts", 5, 0)
    assert result["pool"] == 1
    assert "copyright expired" not in result["excluded"]
    assert result["excluded"].get("copyright not expired") == 1
    assert sum(result["excluded"].values()) == 3


def test_freeze_requires_an_approver(tmp_path):
    works_path = write_works(tmp_path, [])
    unsigned = tmp_path / "unsigned.json"
    unsigned.write_text(json.dumps({"picks": {}}), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "scripts/select_controls.py", "freeze",
         "--approved", str(unsigned), "--works", str(works_path),
         "--texts", str(tmp_path), "--out", str(tmp_path / "controls.json"),
         "--quiet"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 2
    assert "approved_by" in completed.stderr
