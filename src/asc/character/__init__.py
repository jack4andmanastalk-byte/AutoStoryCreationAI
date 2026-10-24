"""Character cores: pressure-tested models of who chooses what.

A character file declares WANT/NEED, fears, principles, separated views,
a fixed voice sample and a decided arc. The checker verifies the design
document and its cross-references against the canon; whether a character
feels alive on the page is an L2/L3 question.
"""
from .check import check_characters, render_markdown
from .schema import CharacterDoc, CharacterDocError, load_characters

__all__ = ["CharacterDoc", "CharacterDocError", "check_characters",
           "load_characters", "render_markdown"]
