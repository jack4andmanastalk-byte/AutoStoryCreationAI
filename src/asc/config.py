"""Configuration loading.

The dataset setup is driven by ``configs/dataset.yaml``.  The file is parsed
into plain dataclasses so that every module receives typed values instead of
diving into dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "dataset.yaml"


@dataclass
class PathsConfig:
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    dataset_dir: Path = REPO_ROOT / "data" / "datasets"
    cache_dir: Path = REPO_ROOT / "data" / "cache"
    font_dir: Path = REPO_ROOT / "data" / "cache" / "fonts"


@dataclass
class HttpConfig:
    user_agent: str = "AutoStoryCreationAI-dataset-builder/0.1 (+research; contact via repository issues)"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_seconds: float = 2.0
    request_interval_seconds: float = 1.0
    cache_dir: Optional[Path] = None
    cache_ttl_seconds: int = 60 * 60 * 24 * 7


@dataclass
class AozoraConfig:
    enabled: bool = True
    card_list_urls: List[str] = field(default_factory=list)
    card_list_mirrors: List[str] = field(default_factory=list)
    text_mirror_tarball: Optional[str] = None
    metadata_mirror_tarball: Optional[str] = None
    sample_works: int = 200
    sample_seed: int = 20240101
    min_chars: int = 1000
    ndc_map_url: Optional[str] = None


@dataclass
class NarouConfig:
    enabled: bool = True
    api_base: str = "https://api.syosetu.com/novelapi/api/"
    web_base: str = "https://ncode.syosetu.com"
    genres: List[int] = field(default_factory=list)
    orders: List[str] = field(default_factory=list)
    per_query: int = 200
    max_start: int = 2000
    download_works: int = 100
    min_chars: int = 5000
    include_r15: bool = True
    #: Only download texts/PDFs of commercialised Narou works (free web edition).
    commercialized_only: bool = True
    #: Require external bibliographic/media catalog proof (CiNii Books ISBN /
    #: Wikipedia franchise entry / official Syosetu anime-syuppan registry)
    #: across books, manga, anime, and games rather than self-reported text.
    strict_external_verification: bool = True
    #: Attempt legacy /txtdownload/ endpoint before HTML chapter pages.
    use_txtdownload: bool = False
    #: Local JSON files with raw API responses (offline import).
    api_response_files: List[str] = field(default_factory=list)
    #: Directory with already downloaded novel texts (``<ncode>/<index>.txt``).
    local_text_dir: Optional[str] = None
    #: ``auto`` downloads what is missing, ``download`` always downloads,
    #: ``local`` only uses :attr:`local_text_dir`.
    text_source: str = "auto"


@dataclass
class Config:
    paths: PathsConfig = field(default_factory=PathsConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    aozora: AozoraConfig = field(default_factory=AozoraConfig)
    narou: NarouConfig = field(default_factory=NarouConfig)
    raw: Dict[str, Any] = field(default_factory=dict)


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (REPO_ROOT / path)


def _build(cls, data: Dict[str, Any]):
    """Instantiate a dataclass, ignoring unknown keys (forward compatibility)."""
    if not data:
        return cls()
    fields = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in data.items() if k in fields}
    return cls(**kwargs)  # type: ignore[arg-type]


def load_config(path: str | Path | None = None) -> Config:
    """Load the dataset configuration (YAML) and return typed objects."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"configuration file not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    config = Config(raw=raw)
    paths_data = raw.get("paths") or {}
    paths = _build(PathsConfig, paths_data)
    for attr in ("raw_dir", "dataset_dir", "cache_dir", "font_dir"):
        setattr(paths, attr, _resolve(str(getattr(paths, attr))))
    config.paths = paths

    http = _build(HttpConfig, raw.get("http") or {})
    if http.cache_dir:
        http.cache_dir = _resolve(str(http.cache_dir))
    config.http = http

    config.aozora = _build(AozoraConfig, raw.get("aozora") or {})
    config.narou = _build(NarouConfig, raw.get("narou") or {})
    config.pdf = _build(PdfConfig, raw.get("pdf") or {})
    return config
