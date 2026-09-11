"""
v3 widgets: Row, Text, Button.

These are the components used by `test/demo_click_counter.py`. They are pure
Python (no Streamlit dependency) and expose the event-driven API:
    * `with sc.v3.Row() as row:`          — horizontal layout container
    * `with sc.v3.Text('...') as txt:`    — text display; `txt.text.set(...)`
    * `with sc.v3.Button('...') as btn:`  — button; `btn.on_click` signal

Component visual fields are `Property` instances, so they share the same
read/write style as state: `txt.text.get()`, `txt.text.set(...)`,
`txt.text.on_change`, `txt['text']`, `txt['on_text']`.
"""

from __future__ import annotations

from ..kernel import Property
from ..kernel import Signal
from .base import Component


class Row(Component):
    """Horizontal layout container."""


class Text(Component):
    """A text display component."""

    text = Property('')

    def __init__(self, text: str = '', **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.text.set(text)


class Button(Component):
    """A clickable button."""

    label = Property('')

    def __init__(
        self, label: str = '', *, type: str = 'default', **kwargs: object
    ) -> None:
        super().__init__(**kwargs)
        self.label.set(label)
        # `type` is a static config, not a reactive Property.
        self._type = type
        self.on_click: Signal = Signal()
