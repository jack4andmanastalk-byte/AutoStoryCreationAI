"""The documented R15 default and PDF compatibility must match the code."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asc.config import NarouConfig, PathsConfig, load_config  # noqa: E402
from asc.schema import Work  # noqa: E402
from asc.sources.narou import NarouSource  # noqa: E402


def test_r15_default_and_explicit_exclusion_are_documented_and_effective():
    assert NarouConfig().include_r15 is True
    config = load_config()
    assert config.narou.include_r15 is True
    work = Work(id="narou:N1", source="syosetsuka_narou", title="example", url="", stats={"elements": ["R15"]})
    source = NarouSource(config.narou, PathsConfig(), None)
    assert source._accept_work(work) is True
    source.config.include_r15 = False
    assert source._accept_work(work) is False
    doc = (ROOT / "docs/legal_and_ethics.md").read_text(encoding="utf-8")
    assert "narou.include_r15: true" in doc
    assert "R15 フラグ付き作品を含みます" in doc


def test_pdf_generation_remains_an_explicit_compatibility_option():
    for command in ("aozora-texts", "narou-texts"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/setup_dataset.py"), command, "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--pdf" in result.stdout
    docs = (ROOT / "docs/data_setup.md").read_text(encoding="utf-8")
    assert "`make data` は最後に `purge-pdfs` を実行します" in docs
    assert "事前にバックアップ" in docs
