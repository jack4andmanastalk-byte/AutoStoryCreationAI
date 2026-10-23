"""Premise briefs: the compressible core of a plan, before any prose exists.

A brief is the smallest artifact the later steps can check against: one
logline, one premise, one theme stated as a対立命題, the works it differs from
and the things it refuses to do. Everything here is structural — whether the
premise is *good* is an L2/L3 question this package never answers.
"""
from .check import check_brief, render_markdown
from .schema import Brief, BriefError, load_brief

__all__ = ["Brief", "BriefError", "check_brief", "load_brief", "render_markdown"]
