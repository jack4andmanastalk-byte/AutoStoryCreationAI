"""Scene information: purpose, tension, knowledge flow, disclosure.

A scene file designs each scene's job (purpose, conflict, change), its
tension device, who learns what, what is disclosed or withheld from the
reader, and which foreshadowing it plants or pays. The checker verifies the
design and its cross-references against the canon; whether a scene moves is
an L2/L3 question.
"""
from .check import check_scenes, render_markdown
from .schema import SceneDoc, SceneDocError, load_scenes

__all__ = ["SceneDoc", "SceneDocError", "check_scenes", "load_scenes",
           "render_markdown"]
