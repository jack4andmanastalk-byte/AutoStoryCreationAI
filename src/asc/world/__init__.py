"""World rules: the world as a system of constraints, not atmosphere.

A world file declares axioms, rules with costs, institutions, geography and
the order of disclosure. The checker verifies structure and cross-references
against the canon; whether the world is fascinating is an L2/L3 question.
"""
from .check import check_world, render_markdown
from .schema import World, WorldError, load_world

__all__ = ["World", "WorldError", "check_world", "load_world", "render_markdown"]
