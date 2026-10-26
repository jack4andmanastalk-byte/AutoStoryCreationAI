"""Stage A structured game log and Stage B rewrite checks.

This package is the first vertical slice of the two-stage
"pseudo-TRPG log -> novelisation" pipeline. It is deliberately small:
a strict schema, a deterministic checker, a marker derivation, and a
rewrite checker. It does not implement a general game engine, branching,
dice, or in-story death events.
"""
from .check import (
    CHECKS as GAMELOG_CHECKS, check_game_log, check_game_log_files,
    needs_repair as gamelog_needs_repair, render_markdown as render_gamelog_markdown,
)
from .markers import derive_markers, chapter_markers, owner_markers
from .rewrite import (
    CHECKS as REWRITE_CHECKS, check_rewrite,
    needs_repair as rewrite_needs_repair,
    render_markdown as render_rewrite_markdown,
)
from .schema import (
    ACTION_TYPES, PRESENT_TENSE_TYPES, REFERENCE_TYPES, SCHEMA_VERSION,
    Action, Chapter, FactUse, ForeshadowEvent, GameLog, GameLogError,
    LocationMove, Scene, StateDelta, load_game_log, parse_game_log,
)

__all__ = [
    "SCHEMA_VERSION", "ACTION_TYPES", "PRESENT_TENSE_TYPES", "REFERENCE_TYPES",
    "Action", "Chapter", "FactUse", "ForeshadowEvent", "GameLog", "GameLogError",
    "LocationMove", "Scene", "StateDelta", "load_game_log", "parse_game_log",
    "derive_markers", "chapter_markers", "owner_markers",
    "GAMELOG_CHECKS", "check_game_log", "check_game_log_files",
    "gamelog_needs_repair", "render_gamelog_markdown",
    "REWRITE_CHECKS", "check_rewrite", "rewrite_needs_repair",
    "render_rewrite_markdown",
]
