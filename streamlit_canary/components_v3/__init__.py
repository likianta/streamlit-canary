"""
Event-driven (v3) component model.

Pure-Python components used by the event-driven runtime. No Streamlit
dependency here — the frontend bridge is added in a later phase.
"""

from .base import Component
from .widgets import Button
from .widgets import Row
from .widgets import Text

__all__ = ['Button', 'Component', 'Row', 'Text']
