"""Plot architecture: acts, turning points, subplots, endings, debts.

A plot file divides the work into acts, places the turning points on
protagonist choices, allocates beats to the A/B plots, designs the ending
and lists the unresolved items. The checker verifies the design and its
cross-references against the canon; whether the plot grips is an L2/L3
question.
"""
from .check import check_plot, render_markdown
from .schema import PlotDoc, PlotDocError, load_plot

__all__ = ["PlotDoc", "PlotDocError", "check_plot", "load_plot",
           "render_markdown"]
