"""
v3 widgets: the built-in component library.

Public widgets (in alphabetical order):
    Button, Caption, Cell, Checkbox, Code, Column, Container, Expander,
    Grid, NumberInput, Popover, Radio, Row, Selectbox, Spinner, Success,
    Table, Tabs, Text, TextInput, Title.

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
from ..kernel import _undefined
from .base import Component

_T = tp.TypeVar('_T')


def _number_type(*candidates: tp.Any) -> type:
    """Decide whether a NumberInput behaves as an int or a float widget.

    `value` / `min_value` / `max_value` must agree — mixing ints and floats
    is a programming error, so it is reported where the widget is built
    rather than producing a confusing comparison later on. Property
    arguments are inspected through their `default`, and unset ones
    (`sc._undefined`) are skipped.
    """
    kinds: set[type] = set()
    for candidate in candidates:
        if isinstance(candidate, Property):
            candidate = candidate.default
        if candidate is None or candidate is _undefined:
            continue
        if not isinstance(candidate, (int, float)):
            raise TypeError(
                'NumberInput expects int or float values, got '
                f'{type(candidate).__name__}: {candidate!r}'
            )
        kinds.add(float if isinstance(candidate, float) else int)
    if len(kinds) > 1:
        raise TypeError(
            'NumberInput value / min_value / max_value must be all ints or '
            'all floats, got a mix.'
        )
    return kinds.pop() if kinds else int


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
        index:   Property[int]  — the selected position (bindable).
        value:   Property[any]  — the raw selected value (bindable).
        format_func: Callable[[Any], str] — raw value → display string.

    `index` and `value` mirror each other, so either one may be set: `index`
    is the position of `value` in `options`, and setting `index` selects
    `options[index]`. When `options` change and the current `value` is no
    longer among them, `value` falls back to the first option.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        options: tp.Sequence[tp.Any] | Property | None = None,
        index: int | Property | None = None,
        value: tp.Any = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = Property([])
        self.index = Property(0)
        self.value = Property('')
        self._format = format
        self.format_func: tp.Callable[[tp.Any], str] = self._make_format(
            format, format_func
        )
        self.options.on_change.connect(self._auto_select)
        self.value.on_change.connect(self._sync_index)
        self.index.on_change.connect(self._sync_value)
        if options is not None:
            self.options.set_or_bind(tp.cast(tp.Any, options))
        if value is not None:
            self.value.set_or_bind(value)
        elif index is not None:
            self.index.set_or_bind(tp.cast(tp.Any, index))

    def _make_format(
        self,
        format: tp.Callable[[tp.Any], str] | tp.Sequence[str] | None,
        format_func: tp.Callable[[tp.Any], str] | None,
    ) -> tp.Callable[[tp.Any], str]:
        """Resolve the display formatter from `format_func` / `format`.

        `format_func` wins when given. Otherwise `format` may be either a
        callable (raw value -> display string) or a sequence parallel to
        `options` (index -> display string). `format` is resolved lazily
        against the *current* options, so it stays correct after
        `options` changes.
        """
        if format_func is not None:
            return format_func
        if format is None:
            return str
        if callable(format):
            return tp.cast(tp.Callable[[tp.Any], str], format)
        labels = list(format)

        def _fmt(v: tp.Any) -> str:
            options = list(self.options.get() or [])
            try:
                i = options.index(v)
            except ValueError:
                return str(v)
            return str(labels[i]) if i < len(labels) else str(v)

        return _fmt

    def _auto_select(self) -> None:
        options = self.options.get()
        if options and self.value.get() not in options:
            self.value.set(options[0])

    def _sync_index(self) -> None:
        """Mirror `value` into `index` (its position in `options`)."""
        options = list(self.options.get() or [])
        value = self.value.get()
        if value in options:
            self.index.set(options.index(value))

    def _sync_value(self) -> None:
        """Mirror `index` into `value`."""
        options = list(self.options.get() or [])
        i = self.index.get()
        if isinstance(i, int) and 0 <= i < len(options):
            self.value.set(options[i])


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
        on_click: emitted when the user clicks the button. A handler may
            also be attached at construction time via `on_click=...`.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        type: str = 'secondary',
        help: str | None = None,
        width: str = 'content',
        enabled: bool | Property = True,
        on_click: tp.Callable[[], None] | None = None,
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
        if on_click is not None:
            self.on_click.connect(on_click)


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


Container = Column
#   alias of `Column`, mirroring Streamlit's `st.container`.


class Expander(Component):
    """A collapsible container (mirrors Streamlit's `st.expander`).

    Args:
        label: the header text (bindable).
        expanded: whether the body starts open.

    Children render inside the body:

        with v3.Expander('Configurations', expanded=True):
            v3.Button('Force refresh')

    Expanding / collapsing is handled entirely on the client, so it never
    reruns.

    Properties:
        label: str — the header text.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        expanded: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        # Initial state only; the client owns it from then on.
        self._expanded = expanded


class Grid(Component):
    """A grid layout container.

    Args:
        rows: number of rows (default 1).
        cols: number of columns (default 2).
        columns: alias of `cols` (kept for backwards compatibility).

    Cells are addressed with `next(grid)` or `(row, col)`, and are used as
    context managers:

        with v3.Grid(rows=1, cols=2) as grid:
            with next(grid):
                v3.Button('a')
            with next(grid):
                v3.Button('b')

    `next(grid)` — and `for cell in grid:` — walks the cells left to right,
    then top to bottom. `grid[row, col]` returns a stable `Cell`, created on
    first access and reused afterwards, so a cell may also be re-entered.
    """

    def __init__(
        self,
        *,
        rows: int = 1,
        cols: int = 2,
        columns: int | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        if columns is not None:
            cols = columns
        self._rows = rows
        self._columns = cols
        self._cells: dict[tuple[int, int], Cell] = {}
        self._cursor = 0

    # -- cell iteration (left to right, then top to bottom) ---------------

    def __iter__(self) -> 'Grid':
        self._cursor = 0
        return self

    def __next__(self) -> 'Cell':
        if self._cursor >= self._rows * self._columns:
            raise StopIteration
        index = self._cursor
        self._cursor += 1
        return self[index // self._columns, index % self._columns]

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


class NumberInput(_Labeled):
    """A numeric input box (mirrors Streamlit's `st.number_input`).

    Args:
        label: the widget label.
        value: the number (bindable). Together with `min_value` / `max_value`
            it also decides whether this is an int or a float widget.
        min_value / max_value: optional bounds. `value`, `min_value` and
            `max_value` must be all ints or all floats.
        step: increment used by the stepper (+/-) gadgets. `None` means
            "decide from the type of `value`": an int widget steps by 1,
            while a float widget shows *no* stepper (a float step cannot be
            guessed, so it has to be set explicitly).
        format: optional display formatter, e.g. `hex` (int widgets only).
        width: `int` (px) | 'content' | 'stretch' | None (default).
        placeholder: hint shown while the box is empty.

    Properties:
        label: str — rendered above the box.
        value: int | float — the current number. The client sends a `change`
            event (fired on blur / Enter, or by the stepper); the incoming
            text is parsed with the widget's numeric type, so both `'41'`
            and `'0x29'` are accepted for an int widget.

    Signals:
        on_value: emitted when `value` changes.
    """

    def __init__(
        self,
        label: str | Property = '',
        value: int | float | Property = 0,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        *,
        step: int | float | None = None,
        format: tp.Callable[[tp.Any], str] | None = None,
        width: int | tp.Literal['content', 'stretch'] | None = None,
        placeholder: str = '',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self._num_type = _number_type(value, min_value, max_value)
        self.value = _prop(0, tp.cast(tp.Any, value))
        self.format = format
        self._width = width
        self._min = min_value
        self._max = max_value
        if step is None and self._num_type is int:
            step = 1
        # `step is None` now means "a float widget without a stepper".
        self._step = step
        self._placeholder = placeholder

    def _coerce_value(self, raw: tp.Any) -> int | float:
        """Parse a client-sent string back with the widget's numeric type."""
        text = str(raw).strip()
        try:
            if self._num_type is float:
                return float(text)
            return int(text, 0)
        except ValueError:
            return self.value.get()


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


class _TabPanel(Component):
    """The content holder of one `Tabs` label (internal to `Tabs`)."""

    def __init__(self, *, label: str = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self._label = label


class Tabs(Component):
    """A tab bar with one panel per label (mirrors Streamlit's `st.tabs`).

        with v3.Tabs(('Eye Diagram', 'Batchtub Curve')) as tabs:
            with tabs['Eye Diagram']:
                v3.Text('...')
            with tabs['Batchtub Curve']:
                v3.Text('...')

    Every panel is built up front; switching tabs happens entirely on the
    client, so it never reruns. `tabs[label]` returns that label's panel
    (created on first access and reused afterwards).

    A label wins over property access, so a tab named after a property
    (e.g. 'active') is not reachable as `tabs['active']`; read the property
    through `tabs.active` instead.

    Properties:
        active: str — the visible tab's label.

    Signals:
        on_active (via `tabs['on_active']` or `tabs.active.on_change`)
    """

    def __init__(
        self,
        labels: tp.Sequence[str],
        *,
        active: str | Property | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._labels = tuple(labels)
        if not self._labels:
            raise ValueError('Tabs needs at least one label.')
        self._panels: dict[str, _TabPanel] = {}
        if active is None:
            active = self._labels[0]
        self.active = _prop(self._labels[0], tp.cast(tp.Any, active))

    def __getitem__(self, key: tp.Any) -> tp.Any:
        if isinstance(key, str) and key in self._labels:
            return self._panel(key)
        return super().__getitem__(key)

    def _panel(self, label: str) -> _TabPanel:
        panel = self._panels.get(label)
        if panel is None:
            # Create the panel with this Tabs as its parent, regardless of
            # what is currently on the context stack.
            stack = Component._context_stack
            stack.append(self)
            try:
                panel = _TabPanel(label=label)
            finally:
                stack.pop()
            self._panels[label] = panel
        return panel

    def _on_client_change(self, value: tp.Any) -> None:
        """A tab click reports the label that became visible."""
        label = str(value)
        if label in self._labels:
            self.active.set(label)


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
