"""AutoStoryCreationAI - research toolkit for AI-assisted creative activities.

The package currently focuses on *dataset setup*: downloading research material
(public-domain Japanese literature from Aozora Bunko and web novels from
Syosetsuka ni Narou), normalising the bibliographic metadata into a single
JSONL schema and rendering human readable PDFs for inspection.

Layout
------
``asc.config``      configuration loading (YAML + dataclasses)
``asc.http``        small HTTP client with retries / rate limiting / cache
``asc.jsonl``       JSONL helpers
``asc.schema``      unified record schema shared by every source
``asc.sources``     per-source acquisition logic (aozora, narou)
``asc.text``        text normalisation (Aozora ruby notation, Narou HTML)
``asc.render``      PDF rendering (fpdf2 based, Japanese font aware)
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
