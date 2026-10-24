"""Voice and style: who narrates, what they can know, how it sounds.

The checker verifies the *mechanical* side only: viewpoint slips detectable
by pattern, pronoun drift, voice-local banned phrases, and drift against a
fixed sample. Whether the prose is beautiful is an L2/L3 question.
"""
from .schema import Voice, VoiceError, load_voice
from .voice import check_voice, render_markdown

__all__ = ["Voice", "VoiceError", "check_voice", "load_voice", "render_markdown"]
