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
    """Horizontal layout container.

    Args:
        vertical_alignment: "top" (default) | "center" | "bottom" — how
            children align on the cross axis.
    """

    def __init__(
        self,
        *,
        vertical_alignment: tp.Literal['top', 'center', 'bottom'] = 'top',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._vertical_alignment = vertical_alignment


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
        label: button text (stored in the reactive `text` Property)
        type: "secondary" (default) | "primary"
        width: "content" (default) | "stretch" — stretch fills parent width
        help: tooltip text
    """

    text = Property('')

    def __init__(
        self,
        label: str = '',
        *,
        type: str = 'secondary',
        help: str | None = None,
        width: str = 'content',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text.set(label)
        # `type` / `help` / `width` are static config, not reactive Property.
        self._type = type
        self._help = help
        self._width = width
        self.on_click: Signal = Signal()


class Grid(Component):
    """A grid layout container.

    Args:
        columns: number of columns (rows grow as needed).

    Cells are addressed by `(row, col)` and used as context managers:

        with v3.Grid(columns=2) as grid:
            with grid[0, 0]:
                v3.Button('a')
            with grid[0, 1]:
                v3.Button('b')

    Each `grid[row, col]` returns a stable `Cell` component (created on first
    access and reused afterwards).
    """

    def __init__(self, *, columns: int = 2, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self._columns = columns
        self._cells: dict[tuple[int, int], Cell] = {}

    def __getitem__(self, key: tp.Any) -> tp.Any:
        # Keep compatibility with `PropertyHost.__getitem__` (str keys) and
        # additionally accept `(row, col)` tuples to address cells.
        if isinstance(key, str):
            return super().__getitem__(key)
        row, col = key
        cell = self._cells.get((row, col))
        if cell is None:
            # Create the Cell with this grid as its parent, regardless of
            # what is currently on the context stack.
            stack = Component._context_stack
            stack.append(self)
            try:
                cell = Cell(row=row, col=col)
            finally:
                stack.pop()
            self._cells[(row, col)] = cell
        return cell


class Cell(Component):
    """A single cell inside a `Grid`, used as `with grid[row, col]:`."""

    def __init__(self, *, row: int = 0, col: int = 0, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self._row = row
        self._col = col


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

    def _auto_select(self) -> None:
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

    def _auto_select(self) -> None:
        opts = self.options.get()
        if opts and self.value.get() not in opts:
            self.value.set(opts[0])
