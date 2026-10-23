"""Revision loop: critique, patch, re-audit, compare.

The loop turns deterministic findings (continuity violations, voice findings)
into critique notes with templated fix directions, applies explicit patches,
and compares before/after reports. Prose rewriting itself is done by a human
or a model; this package only makes the round-trip checkable.
"""
from .loop import (
    apply_patches,
    compare_reports,
    detect_repeats,
    load_json,
    plan_round,
    render_markdown,
)

__all__ = ["apply_patches", "compare_reports", "detect_repeats", "load_json",
           "plan_round", "render_markdown"]
