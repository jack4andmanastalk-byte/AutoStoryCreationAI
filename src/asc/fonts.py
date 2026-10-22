"""Font handling for the PDF renderer.

Japanese text needs a CJK font.  The renderer uses two families:

* a *mincho* (serif) face for the body text - close to the typography used by
  printed Japanese books,
* a *gothic* (sans-serif) face for titles and headers.

Fonts are downloaded on demand from the Google Fonts repository (SIL Open
Font License) and cached in ``data/cache/fonts``.  Any local ``.ttf``/``.otf``
file can be used instead by pointing the configuration at it.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

LOGGER = logging.getLogger(__name__)

GOOGLE_FONTS_REPO = "google/fonts"
GOOGLE_FONTS_API = "https://api.github.com/repos/{repo}/contents/{path}"

#: Mapping of the font files used by the renderer to their location in the
#: Google Fonts repository.
GOOGLE_FONT_PATHS: Dict[str, str] = {
    "ZenOldMincho-Regular.ttf": "ofl/zenoldmincho/ZenOldMincho-Regular.ttf",
    "ZenOldMincho-Bold.ttf": "ofl/zenoldmincho/ZenOldMincho-Bold.ttf",
    "ZenKakuGothicNew-Bold.ttf": "ofl/zenkakugothicnew/ZenKakuGothicNew-Bold.ttf",
    "ZenKakuGothicNew-Regular.ttf": "ofl/zenkakugothicnew/ZenKakuGothicNew-Regular.ttf",
    "NotoSerifJP-Regular.ttf": "ofl/notoserifjp/NotoSerifJP[wght].ttf",
}

FONT_LICENSE = "SIL Open Font License 1.1 (Google Fonts)"


class FontError(RuntimeError):
    pass


@dataclass
class FontSet:
    body: Path
    heading: Path
    body_bold: Optional[Path] = None

    def validate(self) -> None:
        for path in (self.body, self.heading):
            if not path.exists():
                raise FontError(f"font file not found: {path}")


def _github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AutoStoryCreationAI-dataset-builder/0.1",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=_github_headers())
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    destination.write_bytes(payload)


def download_google_font(font_file: str, cache_dir: Path, repo: str = GOOGLE_FONTS_REPO) -> Path:
    """Download a font from the Google Fonts GitHub repository (cached)."""
    relative = GOOGLE_FONT_PATHS.get(font_file)
    if relative is None:
        raise FontError(f"unknown Google Font: {font_file}")

    target = cache_dir / font_file
    if target.exists() and target.stat().st_size > 0:
        return target

    api_url = GOOGLE_FONTS_API.format(repo=repo, path=relative)
    LOGGER.info("downloading font %s from %s", font_file, repo)
    try:
        request = urllib.request.Request(api_url, headers=_github_headers())
        with urllib.request.urlopen(request, timeout=120) as response:
            meta = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FontError(f"cannot query GitHub for {font_file}: {exc}") from exc

    content = meta.get("content")
    if content:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(content))
        return target

    sha = meta.get("sha")
    if not sha:
        raise FontError(f"unexpected GitHub response for {font_file}")
    blob_url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    request = urllib.request.Request(blob_url, headers=_github_headers())
    with urllib.request.urlopen(request, timeout=300) as response:
        blob = json.loads(response.read().decode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(blob["content"]))
    return target


def resolve_font(
    font_file: str,
    cache_dir: Path,
    source: str = "google-fonts",
    repo: str = GOOGLE_FONTS_REPO,
) -> Path:
    """Resolve ``font_file`` to a local path.

    ``font_file`` may be an absolute/relative path (used as-is) or the name of
    a Google Font (downloaded on demand).
    """
    candidate = Path(font_file)
    if candidate.suffix.lower() in {".ttf", ".otf"} and candidate.exists():
        return candidate
    if source == "google-fonts" or font_file in GOOGLE_FONT_PATHS:
        return download_google_font(font_file, cache_dir, repo=repo)
    if candidate.exists():
        return candidate
    raise FontError(f"cannot resolve font: {font_file}")


def build_font_set(
    body_font: str,
    heading_font: str,
    body_bold_font: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    source: str = "google-fonts",
) -> FontSet:
    """Resolve all fonts required by the renderer."""
    cache = Path(cache_dir) if cache_dir else Path("data/cache/fonts")
    fonts = FontSet(
        body=resolve_font(body_font, cache, source),
        heading=resolve_font(heading_font, cache, source),
    )
    if body_bold_font:
        try:
            fonts.body_bold = resolve_font(body_bold_font, cache, source)
        except FontError:  # pragma: no cover - bold is optional
            fonts.body_bold = None
    fonts.validate()
    return fonts
