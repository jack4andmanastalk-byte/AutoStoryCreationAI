"""Relationship webs: conflicting goals, knowledge states, change events.

A relation file declares each pair's public face and real stakes, the
knowledge table, the change events and the silences. The checker verifies the
design and its cross-references against the canon; whether the dynamics move
a reader is an L2/L3 question.
"""
from .check import check_relations, render_markdown
from .schema import RelationDoc, RelationDocError, load_relations

__all__ = ["RelationDoc", "RelationDocError", "check_relations",
           "load_relations", "render_markdown"]
