"""
Event-driven kernel: pure-Python Property / Signal / StateV2.

This package is the foundation of the event-driven Streamlit framework. It is
intentionally free of Streamlit and Qt dependencies so it can be developed and
tested in isolation.
"""

from .pending_updates import pending_updates
from .property import Property
from .property import bbind
from .property import bind
from .signal import Signal
from .special_value import _self
from .special_value import _undefined
from .special_value import _value
from .state import PropertyHost
from .state import StateV2
