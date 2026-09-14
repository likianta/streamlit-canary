"""
v3 widgets: Row, Column, Text, Title, Caption, Button, Spinner, Grid,
Selectbox, Radio.

Component visual fields are `Property` instances living on the component
instance, so they share the same read/write style as state: `txt.text.get()`,
`txt.text.set(...)`, `txt.text.on_change`, `txt['text']`, `txt['on_text']`.

Constructor arguments that represent a visual value accept either a plain
value or a bound `Property` (see `sc.bind`); the latter makes the field
reactive, e.g. `v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))`.
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

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.text.set_or_bind(text)


class Title(Component):
    """A title (heading) component."""

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.text.set_or_bind(text)


class Caption(Component):
    """A small caption / helper text."""

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.text.set_or_bind(text)


class Button(Component):
    """A clickable button.

    Matches Streamlit's ``st.button`` API:
        label:   button text (stored in the reactive `text` Property)
        type:    "secondary" (default) | "primary"
        width:   "content" (default) | "stretch" — stretch fills parent width
        help:    tooltip text
        enabled: bool (default True) | bound value (`sc.bind(...)`)

    Signals:
        on_click: emitted when the user clicks the button.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        type: str = 'secondary',
        help: str | None = None,
        width: str = 'content',
        enabled: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.text.set_or_bind(label)
        # `enabled` is reactive so a button can be disabled dynamically,
        # e.g. `btn.enabled.bind(state.dep, lambda x: not x['is_latest'])`.
        self.enabled = Property(True)
        self.enabled.set_or_bind(enabled)
        # `type` / `help` / `width` are static config, not reactive Property.
        self._type = type
        self._help = help
        self._width = width
        self.on_click: Signal = Signal()


class Spinner(Component):
    """A spinner indicator.

    Args:
        visible: whether the spinner is shown (default False).

    The spinner is both a containment context manager (like every Component)
    and a visibility toggle:

        spinner = v3.Spinner(visible=False)
        ...
        with spinner('Syncing...'):
            # __call__ sets the text, __enter__ shows the spinner, and
            # __exit__ restores the visibility it had before.
            ...
    """

    def __init__(self, visible: bool = False, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.visible = Property(False)
        self.visible.set(visible)
        self._prev_visible = False

    def __call__(self, text: str = '') -> 'Spinner':
        """Set the spinner text and return `self` (chainable)."""
        if text:
            self.text.set(text)
        return self

    def __enter__(self) -> 'Spinner':
        self._prev_visible = bool(self.visible.get())
        self.visible.set(True)
        return super().__enter__()

    def __exit__(self, *exc: tp.Any) -> bool:
        self.visible.set(self._prev_visible)
        return super().__exit__(*exc)


class Success(Component):
    """A green success alert box (mirrors Streamlit's `st.success`).

    Properties:
        text:    str  — the message (bindable; `:color[..]` markup allowed)
        visible: bool — whether the alert is shown (bindable)
    """

    def __init__(
        self,
        text: str | Property = '',
        *,
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = Property('')
        self.text.set_or_bind(text)
        self.visible = Property(False)
        self.visible.set_or_bind(visible)


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
        label:   str        — widget label (bindable)
        options: list       — available choices (raw values)
        value:   any        — currently selected value (raw)

    Attributes:
        format_func: Callable[[Any], str] — converts a raw option value to
        its display string. Default: `str`. Reassign it to change formatting.

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
        on_options (via `sel['on_options']` or `sel.options.on_change`)

    When options change, if the current value is not in the new options,
    the value is automatically set to the first option.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = Property('')
        self.label.set_or_bind(label)
        self.options = Property([])
        self.value = Property('')
        self.format_func: tp.Callable[[tp.Any], str] = format_func or str
        self._label_visibility = label_visibility
        self.options.on_change.connect(self._auto_select)

    def _auto_select(self) -> None:
        opts = self.options.get()
        if opts and self.value.get() not in opts:
            self.value.set(opts[0])


class Radio(Component):
    """A radio button group.

    Properties:
        label:   str        — widget label (bindable)
        options: list       — available choices (raw values)
        value:   any        — currently selected value (raw)

    Attributes:
        format_func: Callable[[Any], str] — converts a raw option value to
        its display string. Default: `str`. Reassign it to change formatting.

    Signals:
        on_value (via `radio['on_value']` or `radio.value.on_change`)
        on_options (via `radio['on_options']` or `radio.options.on_change`)

    Same auto-select behavior as Selectbox.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = Property('')
        self.label.set_or_bind(label)
        self.options = Property([])
        self.value = Property('')
        self.format_func: tp.Callable[[tp.Any], str] = format_func or str
        self._label_visibility = label_visibility
        self.options.on_change.connect(self._auto_select)

    def _auto_select(self) -> None:
        opts = self.options.get()
        if opts and self.value.get() not in opts:
            self.value.set(opts[0])
