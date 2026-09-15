"""
v3 widgets: the built-in component library.

Public widgets (in alphabetical order):
    Button, Caption, Cell, Checkbox, Code, Column, Grid, Popover, Radio,
    Row, Selectbox, Spinner, Success, Table, Text, TextInput, Title.

They are built on a few shared private bases (defined first):
    _HasText       — a single bindable `text` field.
    _Labeled       — a `label` field plus `label_visibility`.
    _OptionsWidget — `_Labeled` + `options` / `value` / `format_func`.
    _TextVisible   — `_HasText` + a bindable `visible` flag.

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

_T = tp.TypeVar('_T')


def _prop(default: _T, source: _T | Property[_T]) -> Property[_T]:
    """Create a `Property` seeded with `default`, then `set_or_bind(source)`.

    Collapses the usual two-step setup into one line, so a field can be
    declared as either a plain value or a bound `Property`:

        self.text = _prop('', text)
    """
    prop = Property(default)
    prop.set_or_bind(source)
    return prop


# -- shared bases ----------------------------------------------------------


class _HasText(Component):
    """Shared base for components carrying a single bindable `text` field.

    Used by Button, Caption, Code, Popover, Text and Title. The text is the
    first positional argument and accepts a plain value or a `Property`.
    """

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = _prop('', text)


class _Labeled(Component):
    """Shared base for widgets that render a `label` above the control.

    Fields:
        label: Property[str]   — the widget label (bindable).
        _label_visibility: str — "visible" | "hidden" | "collapsed".
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        self._label_visibility = label_visibility


class _OptionsWidget(_Labeled):
    """Shared base for Selectbox / Radio.

    Fields:
        options: Property[list] — the raw choices (bindable).
        value:   Property[any]  — the raw selected value (bindable).
        format_func: Callable[[Any], str] — raw value → display string.

    When `options` change and the current `value` is no longer among them,
    `value` falls back to the first option.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = Property([])
        self.value = Property('')
        self.format_func: tp.Callable[[tp.Any], str] = format_func or str
        self.options.on_change.connect(self._auto_select)

    def _auto_select(self) -> None:
        options = self.options.get()
        if options and self.value.get() not in options:
            self.value.set(options[0])


class _TextVisible(_HasText):
    """Shared base for status boxes: a `text` plus a bindable `visible`.

    Used by Spinner and Success.
    """

    def __init__(
        self,
        text: str | Property = '',
        *,
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, **kwargs)
        self.visible = _prop(False, visible)


# -- widgets (alphabetical) ------------------------------------------------


class Button(_HasText):
    """A clickable button.

    Args:
        label:   button text (stored in the reactive `text` Property).
        type:    "secondary" (default) | "primary".
        width:   "content" (default) | "stretch" — stretch fills parent width.
        help:    tooltip text.
        enabled: bool (default True) | bound value (`sc.bind(...)`).

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
        super().__init__(label, **kwargs)
        # `enabled` is reactive so a button can be disabled dynamically,
        # e.g. `btn.enabled.bind(state.dep, lambda x: not x['is_latest'])`.
        self.enabled = _prop(True, enabled)
        # `type` / `help` / `width` are static config, not reactive Property.
        self._type = type
        self._help = help
        self._width = width
        # `Signal(owner_factory=...)` mirrors `Property.on_change`, so
        # `@btn.on_click.partial(sc._self)` hands the handler this button.
        self.on_click: Signal = Signal(owner_factory=lambda: self)


class Caption(_HasText):
    """A small caption / helper text."""


class Cell(Component):
    """A single cell inside a `Grid`, used as `with grid[row, col]:`."""

    def __init__(self, *, row: int = 0, col: int = 0, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self._row = row
        self._col = col


class Checkbox(_Labeled):
    """A checkbox (mirrors Streamlit's `st.checkbox`).

    Args:
        label: the widget label (bindable).
        value: the checked state (default False, bindable).

    Properties:
        label: str  — the widget label.
        value: bool — the checked state; the client sends a `change` event
            (boolean), which sets this property.

    Signals:
        on_value (via `cb['on_value']` or `cb.value.on_change`)
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        value: bool | Property = False,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.value = _prop(False, value)


class Code(_HasText):
    """A code block with a hover-revealed "copy to clipboard" button.

    Args:
        text: the code content (bindable).
        language: kept for parity with Streamlit's `st.code`; this
            implementation does not syntax-highlight.

    Properties:
        text: str — the code content.
    """

    def __init__(
        self,
        text: str | Property = '',
        *,
        language: str = 'python',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, **kwargs)
        self._language = language


class Column(Component):
    """Vertical layout container.

    Args:
        width:  fixed width (int px or CSS length) | None (fill parent).
        border: whether to draw a bordered container around the children.
    """

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


class Popover(_HasText):
    """A popover: a trigger button that reveals a floating panel.

    Children render inside the panel (hidden until the trigger is clicked):

        with v3.Popover('Export requirements'):
            v3.Radio('Mirror source', ...)
            v3.Checkbox('Lock self', value=True)

    Opening/closing is handled entirely on the client, so it never reruns.

    Properties:
        text: str — the trigger label (bindable).
    """

    def __init__(self, label: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(label, **kwargs)


class Radio(_OptionsWidget):
    """A radio button group (mirrors Streamlit's `st.radio`).

    Args:
        label:     the widget label (bindable).
        horizontal: lay the options out in a row instead of a column.

    Properties:
        label, options, value — see `_OptionsWidget`.

    Attributes:
        format_func: Callable[[Any], str] — raw option value → display string
        (default `str`; reassign it to change formatting).

    Signals:
        on_value (via `radio['on_value']` or `radio.value.on_change`)
        on_options (via `radio['on_options']` or `radio.options.on_change`)
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        horizontal: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            format_func=format_func,
            label_visibility=label_visibility,
            **kwargs,
        )
        self._horizontal = horizontal


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


class Selectbox(_OptionsWidget):
    """A dropdown select component (mirrors Streamlit's `st.selectbox`).

    Properties:
        label, options, value — see `_OptionsWidget`.

    Attributes:
        format_func: Callable[[Any], str] — raw option value → display string
        (default `str`; reassign it to change formatting).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
        on_options (via `sel['on_options']` or `sel.options.on_change`)
    """


class Spinner(_TextVisible):
    """A spinner indicator.

    Args:
        text: the label shown next to the ring (bindable).
        visible: whether the spinner is shown (default False, bindable).

    The spinner is both a containment context manager (like every Component)
    and a visibility toggle:

        spinner = v3.Spinner(visible=False)
        ...
        with spinner('Syncing...'):
            # __call__ sets the text, __enter__ shows the spinner, and
            # __exit__ restores the visibility it had before.
            ...

    Or drive it entirely from state:

        v3.Spinner(state.busy_text, visible=sc.bind(state.busy_text, bool))
    """

    # Visibility remembered by `__enter__` and restored by `__exit__`; a
    # class-level default keeps subclasses from re-declaring the signature.
    _prev_visible = False

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


class Success(_TextVisible):
    """A green success alert box (mirrors Streamlit's `st.success`).

    Properties:
        text:    str  — the message (bindable; `:color[..]` markup allowed)
        visible: bool — whether the alert is shown (bindable)
    """


class Table(Component):
    """A static table (mirrors Streamlit's `st.table`).

    Args:
        rows: an iterable of `(key, value)` pairs. Both cells accept the
            same `:color[..]` markup as `v3.Text`. Bindable.

    Properties:
        rows: list[tuple[str, str]] — the table body.
    """

    def __init__(
        self,
        rows: tp.Iterable[tp.Tuple[str, str]] | Property | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rows = Property([])
        if isinstance(rows, Property):
            self.rows.bind(rows)
        elif rows is not None:
            self.rows.set(list(rows))


class Text(_HasText):
    """A text display component."""


class TextInput(_Labeled):
    """A single-line text input (mirrors Streamlit's `st.text_input`).

    Args:
        label: the widget label.
        value: initial text (bindable).
        placeholder: hint shown while the box is empty.

    Properties:
        label: str — rendered above the box.
        value: str — the current text; the client sends a `change` event
            (fired on blur / Enter), which sets this property.

    Signals:
        on_value: emitted when `value` changes.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        value: str | Property = '',
        placeholder: str = '',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.value = _prop('', value)
        self._placeholder = placeholder


class Title(_HasText):
    """A title (heading) component."""
