"""The frozen task set (``benchmarks/protocol-v1/tasks.yaml``).

Tasks are read-only inputs: a run may not invent its own premise, because the
comparison between systems only holds when every system answers the same task.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROTOCOL_VERSION = "protocol-v1"


class TaskError(ValueError):
    """Raised when the task file is malformed or a task is unknown."""


@dataclass(frozen=True)
class Task:
    id: str
    title_ja: str
    genre: str
    logline: str
    must_include: tuple[str, ...]
    avoid: tuple[str, ...]
    control: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title_ja": self.title_ja,
            "genre": self.genre,
            "logline": self.logline,
            "must_include": list(self.must_include),
            "avoid": list(self.avoid),
            "control": self.control,
        }


@dataclass(frozen=True)
class TaskSet:
    protocol: str
    path: Path
    chapters: int
    target_chars: tuple[int, int]
    tasks: tuple[Task, ...]

    def get(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise TaskError(
            f"unknown task {task_id!r}; known: {', '.join(t.id for t in self.tasks)}")


def load_tasks(path: str | Path) -> TaskSet:
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - declared dependency
        raise TaskError("loading tasks requires PyYAML") from exc

    path = Path(path)
    if not path.is_file():
        raise TaskError(f"task file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise TaskError(f"{path.name}: expected a 'tasks' list")

    tasks: list[Task] = []
    for entry in data["tasks"]:
        if not isinstance(entry, dict):
            raise TaskError(f"{path.name}: each task must be a mapping")
        for key in ("id", "title_ja", "genre", "logline", "control"):
            if not entry.get(key):
                raise TaskError(f"{path.name}: task {entry.get('id', '?')} lacks {key}")
        must = tuple(entry.get("must_include") or ())
        avoid = tuple(entry.get("avoid") or ())
        if not must:
            raise TaskError(f"{path.name}: task {entry['id']} has no must_include")
        if set(must) & set(avoid):
            raise TaskError(
                f"{path.name}: task {entry['id']} requires and avoids {set(must) & set(avoid)}")
        tasks.append(Task(
            id=str(entry["id"]), title_ja=str(entry["title_ja"]),
            genre=str(entry["genre"]), logline=str(entry["logline"]),
            must_include=must, avoid=avoid, control=str(entry["control"]),
        ))

    if not tasks:
        raise TaskError(f"{path.name}: no tasks")
    ids = [task.id for task in tasks]
    if len(ids) != len(set(ids)):
        raise TaskError(f"{path.name}: duplicate task ids")

    chapters = int(data.get("chapters", 3))
    target = data.get("target_chars") or [3000, 4200]
    if not (isinstance(target, list) and len(target) == 2):
        raise TaskError(f"{path.name}: target_chars must be [min, max]")
    return TaskSet(
        protocol=str(data.get("protocol", PROTOCOL_VERSION)),
        path=path, chapters=chapters,
        target_chars=(int(target[0]), int(target[1])), tasks=tuple(tasks),
    )
