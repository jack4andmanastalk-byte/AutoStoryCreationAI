"""Interactive branches: graphs, conditions, merges, endings.

A branch file declares the nodes (scene/choice/ending), the edges with
conditions and flag updates, the flag table and the start. The checker runs
graph checks (reachability, termination, dead ends) and a bounded
state-space search for dead conditions; whether choices feel meaningful is
an L2/L3 question.
"""
from .check import check_branches, render_markdown
from .schema import BranchDoc, BranchDocError, load_branches

__all__ = ["BranchDoc", "BranchDocError", "check_branches", "load_branches",
           "render_markdown"]
