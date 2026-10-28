"""スキルレジストリ。

configs/skills.yaml で定義したスキル情報を機械可読に扱い、
story_project.py やパイプラインからスキルを動的参照できるようにする。

新スキル追加時は configs/skills.yaml に1エントリ追加するだけで、
このモジュールを経由して実装モジュール・チェッカー・プロンプト
テンプレートを参照できる。手動配線を減らし、スキルの追加・削除
を安全に行うための仕組みである。
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "configs" / "skills.yaml"


@dataclass(frozen=True)
class SkillEntry:
    """1スキルの登録情報。"""

    id: str
    name: str
    description: str
    skill_md: str
    impl_module: str
    impl_package: str
    checker_script: Optional[str]
    prompt_template: Optional[str]
    schema_ref: Optional[str]
    measurement_ref: Optional[str]
    techniques_ref: Optional[str]
    seed: Optional[str]
    version: Optional[str]
    catalog: Optional[str]
    executability: Optional[str]
    license: str
    compatibility: str
    in_pipeline_design: bool
    design_doc: Optional[str]

    @property
    def skill_md_path(self) -> Path:
        return REPO_ROOT / self.skill_md

    @property
    def impl_package_path(self) -> Path:
        return REPO_ROOT / self.impl_package

    @property
    def checker_script_path(self) -> Optional[Path]:
        return (REPO_ROOT / self.checker_script) if self.checker_script else None

    @property
    def prompt_template_path(self) -> Optional[Path]:
        return (REPO_ROOT / self.prompt_template) if self.prompt_template else None


@dataclass(frozen=True)
class SkillRegistry:
    """スキルレジストリ全体。"""

    skills: tuple[SkillEntry, ...]
    registry_version: str
    skill_count: int

    def by_id(self, skill_id: str) -> Optional[SkillEntry]:
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None

    def design_skills(self) -> tuple[SkillEntry, ...]:
        """パイプライン設計段階で使うスキル（依存順）を返す。"""
        return tuple(
            s for s in self.skills if s.in_pipeline_design and s.design_doc is not None
        )

    def non_design_skills(self) -> tuple[SkillEntry, ...]:
        """設計段階以外の単独利用スキルを返す。"""
        return tuple(s for s in self.skills if not s.in_pipeline_design)

    def import_impl_module(self, skill: SkillEntry):
        """スキルの実装モジュールを動的にインポートして返す。"""
        return importlib.import_module(skill.impl_module)

    def run_checker(self, skill: SkillEntry, *args: str) -> subprocess.CompletedProcess:
        """スキルのチェッカースクリプトを実行して結果を返す。"""
        if skill.checker_script_path is None:
            raise ValueError(f"skill {skill.id} has no checker script")
        script = skill.checker_script_path
        cmd = [sys.executable, str(script), *args]
        return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)


def load_registry(path: str | Path | None = None) -> SkillRegistry:
    """skills.yaml を読み込んで SkillRegistry を構築する。"""
    registry_path = Path(path) if path else REGISTRY_PATH
    if not registry_path.exists():
        raise FileNotFoundError(f"skill registry not found: {registry_path}")

    with registry_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    skills_data = data.get("skills") or []
    skills: list[SkillEntry] = []
    for entry in skills_data:
        skills.append(
            SkillEntry(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                description=entry.get("description", ""),
                skill_md=entry["skill_md"],
                impl_module=entry["impl_module"],
                impl_package=entry["impl_package"],
                checker_script=entry.get("checker_script"),
                prompt_template=entry.get("prompt_template"),
                schema_ref=entry.get("schema_ref"),
                measurement_ref=entry.get("measurement_ref"),
                techniques_ref=entry.get("techniques_ref"),
                seed=entry.get("seed"),
                version=entry.get("version"),
                catalog=entry.get("catalog"),
                executability=entry.get("executability"),
                license=entry.get("license", "MIT"),
                compatibility=entry.get("compatibility", ""),
                in_pipeline_design=bool(entry.get("in_pipeline_design", False)),
                design_doc=entry.get("design_doc"),
            )
        )

    return SkillRegistry(
        skills=tuple(skills),
        registry_version=data.get("registry_version", "unknown"),
        skill_count=int(data.get("skill_count", len(skills))),
    )


__all__ = ["SkillEntry", "SkillRegistry", "load_registry", "REGISTRY_PATH"]
