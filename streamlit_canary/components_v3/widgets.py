"""
v3 widgets: Row, Column, Text, Title, Button, Selectbox, Radio.

Component visual fields are `Property` instances, so they share the same
read/write style as state: `txt.text.get()`, `txt.text.set(...)`,
`txt.text.on_change`, `txt['text']`, `txt['on_text']`.
"""

from __future__ import annotations

import typing as tp

from ..kernel import Property
from ..kernel import Signal
from .base import Component


class Row(Component):
    """Horizontal layout container."""


class Column(Component):
    """Vertical layout container."""

    def __init__(
        self,
        *,
        width: int | str | None = None,
        border: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._width = width
        self._border = border


class Text(Component):
    """A text display component."""

    text = Property('')

    def __init__(self, text: str = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text.set(text)


class Title(Component):
    """A title (heading) component."""

    text = Property('')

    def __init__(self, text: str = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text.set(text)


class Button(Component):
    """A clickable button.

    Matches Streamlit's ``st.button`` API:
        type: "secondary" (default) | "primary"
        use_container_width: bool — stretch to fill parent width
        help: tooltip text
    """

    label = Property('')

    def __init__(
        self,
        label: str = '',
        *,
        type: str = 'secondary',
        help: str | None = None,
        use_container_width: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label.set(label)
        # `type` / `help` / `use_container_width` are static config, not
        # reactive Property.
        self._type = type
        self._help = help
        self._use_container_width = use_container_width
        self.on_click: Signal = Signal()


class Selectbox(Component):
    """A dropdown select component.

    Properties:
        options: list       — available choices (raw values)
        value:   any        — currently selected value (raw)

    Constructor params:
        format_func: Callable[[Any], str] — converts raw option value to
        display string. Default: `str`.

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
        on_options (via `sel['on_options']` or `sel.options.on_change`)

    When options change, if the current value is not in the new options,
    the value is automatically set to the first option.
    """

    options = Property([])
    value = Property('')

    def __init__(
        self,
        label: str = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._format_func = format_func or str
        self.options.on_change.connect(self._auto_select)

    def _auto_select(self, _opts_prop: Property) -> None:
        opts = self.options.get()
        if opts and self.value.get() not in opts:
            self.value.set(opts[0])


class Radio(Component):
    """A radio button group.

    Properties:
        options: list       — available choices (raw values)
        value:   any        — currently selected value (raw)

    Constructor params:
        format_func: Callable[[Any], str] — converts raw option value to
        display string. Default: `str`.

    Signals:
        on_value (via `radio['on_value']` or `radio.value.on_change`)
        on_options (via `radio['on_options']` or `radio.options.on_change`)

    Same auto-select behavior as Selectbox.
    """

    options = Property([])
    value = Property('')

    def __init__(
        self,
        label: str = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._format_func = format_func or str
        self.options.on_change.connect(self._auto_select)

    def _auto_select(self, _opts_prop: Property) -> None:
        opts = self.options.get()
        if opts and self.value.get() not in opts:
            self.value.set(opts[0])
