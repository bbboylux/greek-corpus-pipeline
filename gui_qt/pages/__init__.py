"""One module per step of the workflow.

Each page is a self-contained widget that knows how to render itself from the
state object the main window hands it, and nothing about the other pages. Adding
a step means writing one module and adding one line to the rail.
"""
from .base import Page, AppState

__all__ = ["Page", "AppState"]
