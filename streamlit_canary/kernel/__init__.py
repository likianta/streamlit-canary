"""
Event-driven kernel: pure-Python Property / Signal / StateV2.

This package is the foundation of the event-driven Streamlit framework. It is
intentionally free of Streamlit and Qt dependencies so it can be developed and
tested in isolation.
"""

from .property import Property
from .signal import Signal
from .state import StateV2
