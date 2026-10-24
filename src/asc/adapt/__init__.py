"""Adaptation: functions, mappings, deletions, rights.

An adaptation file lists the functions of the source (information, emotion,
relation, tempo), maps each to the target medium's means, splits the
treatment for newcomers and existing readers, records deletions with their
substitutes, and logs the rights. The checker verifies the design; whether
the adaptation works is an L2/L3 question.
"""
from .check import check_adaptation, render_markdown
from .schema import AdaptationDoc, AdaptationDocError, load_adaptation

__all__ = ["AdaptationDoc", "AdaptationDocError", "check_adaptation",
           "load_adaptation", "render_markdown"]
