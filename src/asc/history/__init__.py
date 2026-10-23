"""History and timeline: the past as a chain of causes and evidence.

A history file declares eras, events with causes/effects/traces, sources,
the canon/apocrypha split and who knows what. The checker verifies order,
references and the separation of real sources from invention; whether the
history is compelling is an L2/L3 question.
"""
from .check import check_history, render_markdown
from .schema import History, HistoryError, load_history

__all__ = ["History", "HistoryError", "check_history", "load_history",
           "render_markdown"]
