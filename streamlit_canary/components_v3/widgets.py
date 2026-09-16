"""
v3 widgets: the built-in component library.

Public widgets (in alphabetical order):
    AltairChart, Button, Caption, Cell, Checkbox, Code, Column, Container,
    Dialog, Expander, Grid, IconButton, Info, Multiselect, NumberInput,
    Popover, Progress, Radio, Row, SelectSlider, Selectbox, Spinner, Success,
    Table, Tabs, Text, TextArea, TextInput, Title, Toggle, Warning.

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

import textwrap
import typing as tp

from ..kernel import Property
from ..kernel import Signal
from ..kernel import _undefined
from .base import Component
from .base import Height
from .base import Width
from .base import _validate_size

_T = tp.TypeVar('_T')

# Streamlit's semantic dialog sizes (`DialogWidth`), mapped to their maximum
# pixel widths (see `st.dialog`: small=500, medium=750, large=1280).
DialogWidth: tp.TypeAlias = tp.Literal['small', 'medium', 'large']
_DIALOG_WIDTHS: dict[str, int] = {'small': 500, 'medium': 750, 'large': 1280}


def _resolve_number(value: tp.Any) -> int | float:
    """The plain number behind a NumberInput `value` argument.

    A bound `Property` is inspected through its current value (falling back
    to `default` while it is still unset), so the widget's numeric type can
    be decided even when the caller passes `sc.bind(...)` / `sc.bbind(...)`.
    """
    if isinstance(value, Property):
        current = value.get()
        value = current if current is not _undefined else value.default
    if value is _undefined or value is None:
        return 0
    if isinstance(value, (int, float)):
        return value
    raise TypeError(
        'NumberInput expects an int or float value, got '
        f'{type(value).__name__}: {value!r}'
    )


def _check_number_arg(arg: tp.Any, is_float: bool, name: str) -> int | float:
    """Validate a `min_value` / `max_value` / `step` argument.

    An int widget only accepts ints; a float widget also accepts ints and
    converts them to float.
    """
    if not isinstance(arg, (int, float)):
        raise TypeError(f'NumberInput {name} must be a number, got {arg!r}')
    if is_float:
        return float(arg)
    if isinstance(arg, float):
        raise TypeError(
            f'NumberInput {name} must be an int for an int widget, got {arg!r}'
        )
    return arg


def _as_list(source: tp.Any) -> tp.Any:
    """`_prop` takes a list or a Property; accept any sequence as well."""
    if isinstance(source, Property):
        return source
    return list(source or ())


def _prop(default: _T, source: _T | Property[_T]) -> Property[_T]:
    """Create a `Property` seeded with `default`, then `set_or_bind(source)`.

    Collapses the usual two-step setup into one line, so a field can be
    declared as either a plain value or a bound `Property`:

        self.text = _prop('', text)
    """
    prop = Property(default)
    prop.set_or_bind(source)
    return prop


def _dedent_help(value: tp.Any) -> str:
    """Strip the common indentation from a `help` text.

    Help is normally written as an indented triple-quoted literal. Markdown
    reads four leading spaces as a code block, so the indent has to go before
    the text is ever handed to the parser -- Streamlit dedents for the same
    reason. Deeper indentation (an intentional code block) is left alone,
    since only the *common* prefix is removed.
    """
    if value is None:
        return ''
    return textwrap.dedent(str(value))


def _help_prop(help: str | Property) -> Property[str]:
    """Declare a `help` Property, dedenting its text on the way in.

    The dedent has to happen on the property itself (rather than while
    rendering) so that a `help` reachable through a `Property` is dedented too
    -- the frontend receives its value as a delta patch.
    """
    prop: Property[str] = Property('')
    if isinstance(help, Property):
        prop.bind(help, _dedent_help)
    else:
        prop.set(_dedent_help(help))
    return prop


def _inline_datasets(node: tp.Any, datasets: dict) -> None:
    """Replace `{"name": "<key>"}` data references with inline values.

    Altair's default data transformer keeps the rows in a top-level
    `datasets` map and leaves `{"name": ...}` references behind — a
    Jupyter-only convention that plain Vega-Lite (and therefore
    `vega-embed`) does not understand. Resolving the references here keeps
    the emitted spec self-contained. The walk covers layered / concatenated
    specs too, since every nested `data` is visited.
    """
    if isinstance(node, dict):
        data = node.get('data')
        if (
            isinstance(data, dict)
            and set(data) == {'name'}
            and data['name'] in datasets
        ):
            node['data'] = {'values': datasets[data['name']]}
        for value in node.values():
            _inline_datasets(value, datasets)
    elif isinstance(node, list):
        for value in node:
            _inline_datasets(value, datasets)


def _to_vega_lite_spec(chart: tp.Any) -> dict:
    """Normalize an Altair chart (or an already-built spec) to a spec dict.

    Altair's own `to_dict()` is used when available, which keeps `altair`
    out of `streamlit_canary`'s dependencies — the chart object is the only
    thing that needs altair installed. Named datasets are inlined so the
    result renders with a plain `vega-embed` call.
    """
    to_dict = getattr(chart, 'to_dict', None)
    if callable(to_dict):
        spec = tp.cast(dict, to_dict())
        datasets = spec.pop('datasets', None)
        if datasets:
            _inline_datasets(spec, datasets)
        return spec
    if isinstance(chart, dict):
        return chart
    raise TypeError(
        'AltairChart expects an altair.Chart or a Vega-Lite spec dict, '
        f'got {type(chart).__name__}: {chart!r}'
    )


# -- shared bases ----------------------------------------------------------


class _HasText(Component):
    """Shared base for components carrying a single bindable `text` field.

    Used by Button, Code and Popover, and (through `_HelpText`) by Caption,
    Text and Title. The text is the first positional argument and accepts a
    plain value or a `Property`.
    """

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.text = _prop('', text)


class _HelpText(_HasText):
    """Shared base for text elements that also carry a `help` tooltip.

    Mirrors Streamlit, whose text and heading elements (`st.text`,
    `st.caption`, `st.title`) all accept `help`. Used by Caption, Text and
    Title.

    Fields:
        text: Property[str] — the displayed text (bindable).
        help: Property[str] — markdown tooltip shown next to the text
            (bindable; bind it when the text depends on state).

    `width` defaults to `'auto'` (mirroring Streamlit's markdown family): the
    text stretches inside a vertical container and shrinks to its content
    inside a horizontal one. Pass an explicit `width` to override.
    """

    _default_width = 'auto'

    def __init__(
        self,
        text: str | Property = '',
        *,
        help: str | Property = '',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, **kwargs)
        self.help = _help_prop(help)


class _Labeled(Component):
    """Shared base for widgets that render a `label` above the control.

    Fields:
        label: Property[str]   — the widget label (bindable).
        _label_visibility: str — "visible" | "hidden" | "collapsed".
        help: Property[str]    — markdown tooltip shown next to the label
            (bindable; bind it when the text depends on state).
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        label_visibility: str = 'visible',
        help: str | Property = '',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        self._label_visibility = label_visibility
        self.help = _help_prop(help)


class _OptionsWidget(_Labeled):
    """Shared base for Selectbox / Radio.

    Fields:
        options: Property[list] — the raw choices (bindable).
        index:   Property[int]  — the selected position (bindable).
        value:   Property[any]  — the raw selected value (bindable).
        enabled: Property[bool] — whether the widget accepts input (bindable).
        format_func: Callable[[Any], str] — raw value → display string.

    `index` and `value` mirror each other, so either one may be set: `index`
    is the position of `value` in `options`, and setting `index` selects
    `options[index]`. When `options` change and the current `value` is no
    longer among them, `value` falls back to the first option.
    """

    def __init__(
        self,
        label: str | Property = '',
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        index: int | Property | None = None,
        value: tp.Any = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        enabled: bool | Property = True,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = Property([])
        self.index = Property(0)
        self.value = Property('')
        self.enabled = _prop(True, enabled)
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

    def _coerce_value(self, raw: tp.Any) -> tp.Any:
        """Recover an option's real type from the client-sent string.

        The DOM only carries strings, so clicking an option sends `'48'`
        even when the option itself is the int `48`. This maps the text back
        onto the matching entry of `options`; an unknown value is passed
        through unchanged (it may be a `new_option` mid-flight).
        """
        for option in self.options.get() or []:
            if str(option) == str(raw):
                return option
        return raw


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


class AltairChart(Component):
    """A chart drawn from an Altair (Vega-Lite) specification.

    Args:
        chart: an `altair.Chart` — more precisely, anything exposing
            `to_dict()` — or an already-built Vega-Lite spec (`dict`).
            Bindable. `None` renders nothing until a spec is set.
        width: "stretch" (default; fills the parent) | "content" | int px.

    Properties:
        chart: dict | None — the Vega-Lite spec (JSON-serializable). The
            client renders it with `vega-embed` and re-renders whenever the
            spec changes.

    `streamlit_canary` never imports altair itself; a chart object is
    converted through its own `to_dict()`, so altair stays optional:

        v3.AltairChart(chart)
        v3.AltairChart(state.spec)  # a Property holding a spec dict
    """

    _default_width = 'stretch'

    def __init__(
        self,
        chart: tp.Any = None,
        *,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)
        self.chart: Property[dict | None] = Property(None)
        if isinstance(chart, Property):
            self.chart.set_or_bind(chart)
        elif chart is not None:
            self.set_chart(chart)

    def set_chart(self, chart: tp.Any) -> None:
        """Set the chart from an Altair object or a Vega-Lite spec dict."""
        spec = _to_vega_lite_spec(chart)
        if spec is not None and self._width == 'stretch':
            # The spec usually carries its own pixel `width`; make it follow
            # the widget instead, otherwise a wide chart overflows a narrower
            # parent (Streamlit does the same for `width='stretch'`).
            spec['width'] = 'container'
            spec['autosize'] = {'type': 'fit', 'contains': 'padding'}
        self.chart.set(spec)


class Button(_HasText):
    """A clickable button.

    Args:
        label:   button text (stored in the reactive `text` Property).
        type:    "secondary" (default) | "primary".
        width:   "content" (default) | "stretch" — stretch fills parent width.
        help:    markdown tooltip text; a plain string or a bound value
            (`sc.bind(...)`) when the text depends on state.
        enabled: bool (default True) | bound value (`sc.bind(...)`).

    Signals:
        on_click: emitted when the user clicks the button. A handler may
            also be attached at construction time via `on_click=...`.
    """

    _default_width = 'content'

    def __init__(
        self,
        label: str | Property = '',
        *,
        type: str = 'secondary',
        help: str | Property | None = None,
        width: Width | None = None,
        enabled: bool | Property = True,
        on_click: tp.Callable[[], None] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, width=width, **kwargs)
        # `enabled` is reactive so a button can be disabled dynamically,
        # e.g. `btn.enabled.bind(state.dep, lambda x: not x['is_latest'])`.
        self.enabled = _prop(True, enabled)
        # `help` is reactive too: Streamlit recomputes it on every rerun, so
        # a no-rerun port needs a bound Property to reach the same effect.
        self.help = _help_prop('' if help is None else help)
        # `type` is static config, not a reactive Property (`width` is
        # collected by the base class).
        self._type = type
        # `Signal(owner_factory=...)` mirrors `Property.on_change`, so
        # `@btn.on_click.partial(sc._self)` hands the handler this button.
        self.on_click: Signal = Signal(owner_factory=lambda: self)
        if on_click is not None:
            self.on_click.connect(on_click)


class Caption(_HelpText):
    """A small caption / helper text (mirrors Streamlit's `st.caption`).

    Args:
        text: the caption content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """


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

    _default_width = 'stretch'

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

    _default_width = 'stretch'

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
        width:  `int` (px) | 'stretch' | 'content' | None (fill parent).
        weight: flex-grow ratio when laid out inside a `Row`, e.g. a
            `(5, 2)` split is `Column(weight=5)` + `Column(weight=2)`;
            None keeps the default equal share.
        border: whether to draw a bordered container around the children.
        height: fixed height in px; the content scrolls when it overflows
            (mirrors `st.container(height=...)`).
        visible: bool (default True, bindable) — hidden containers keep their
            place in the tree but are not rendered.
        animated: transition the height when `visible` flips, instead of
            appearing/disappearing instantly (mirrors an expander body). Use
            it for blocks that a button reveals, e.g.
            `Column(visible=state.show, animated=True)`.
    """

    def __init__(
        self,
        *,
        width: Width | None = None,
        weight: float | None = None,
        border: bool = False,
        height: Height | None = None,
        visible: bool | Property = True,
        animated: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, height=height, **kwargs)
        self._weight = weight
        self._border = border
        self._animated = animated
        self.visible = _prop(True, visible)


Container = Column
#   alias of `Column`, mirroring Streamlit's `st.container`.


class Dialog(Component):
    """A modal dialog (mirrors Streamlit's `st.dialog`).

        with v3.Dialog('Select a file', visible=state.browsing):
            ...

    `st.dialog` decorates a function that Streamlit re-runs every time the
    dialog opens.  A v3 dialog is an ordinary container built once, so its
    `visible` Property is what opens and closes it.  The client can also
    dismiss it (the close button, a click on the backdrop, or Esc), which
    sets `visible` back to False and emits `on_close`.

    Args:
        text:    the dialog title.
        visible: bool (default True, bindable) — whether it is open.
        width:   `'small'` (default, 500px) | `'medium'` (750px) |
            `'large'` (1280px); an int px value is accepted as an escape
            hatch. Mirrors Streamlit's semantic `DialogWidth`.

    Properties:
        text: str  — the title.
        visible: bool — open/closed.

    Signals:
        on_close: emitted when the client dismisses the dialog.
    """

    def __init__(
        self,
        text: str | Property = '',
        *,
        visible: bool | Property = True,
        width: DialogWidth | int = 'small',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = _prop('', text)
        self.visible = _prop(True, visible)
        # Resolve the semantic size to px up front so the renderer stays thin
        # (and `comp._width` is always an int).
        if isinstance(width, str):
            if width not in _DIALOG_WIDTHS:
                raise ValueError(
                    f'Dialog width must be one of '
                    f'{tuple(_DIALOG_WIDTHS)} or an int, got {width!r}'
                )
            self._width = _DIALOG_WIDTHS[width]
        else:
            _validate_size(width, 'width')
            self._width = width
        self.on_close: Signal = Signal(owner_factory=lambda: self)

    def _on_close(self, _value: tp.Any = None) -> None:
        """Handle a client-side dismissal (✕ / backdrop / Esc)."""
        self.visible.set(False)
        self.on_close.emit()


class Expander(Component):
    """A collapsible container (mirrors Streamlit's `st.expander`).

    Args:
        label: the header text (bindable).
        expanded: whether the body starts open.
        visible: whether the expander is shown (default True, bindable).

    Children render inside the body:

        with v3.Expander('Configurations', expanded=True):
            v3.Button('Force refresh')

    Expanding / collapsing is handled entirely on the client, so it never
    reruns.

    Properties:
        label: str — the header text.
        visible: bool — whether the expander is shown.
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        expanded: bool = False,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        self.visible = _prop(True, visible)
        # Initial state only; the client owns it from then on.
        self._expanded = expanded


class Grid(Component):
    """A grid layout container.

    Args:
        rows: number of rows (default 1).
        cols: number of columns (default 2), or a sequence of column weights
            — `cols=(5, 2)` mirrors `st.columns((5, 2))`.
        columns: alias of `cols` (kept for backwards compatibility).
        vertical_alignment: "top" (default) | "center" | "bottom" — how a
            cell's content aligns inside its row when the columns differ in
            height (mirrors `st.columns(vertical_alignment=...)`).

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
        cols: int | tp.Sequence[float] = 2,
        columns: int | tp.Sequence[float] | None = None,
        vertical_alignment: tp.Literal['top', 'center', 'bottom'] = 'top',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        if columns is not None:
            cols = columns
        # An int means "N equal columns"; a sequence is taken as explicit
        # weights, so `cols=(5, 2)` mirrors `st.columns((5, 2))`.
        weights = (
            (1.0,) * cols
            if isinstance(cols, int)
            else tuple(float(w) for w in cols)
        )
        if not weights:
            raise ValueError('Grid needs at least one column.')
        self._rows = rows
        self._weights = weights
        self._columns = len(weights)
        self._vertical_alignment = vertical_alignment
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


class IconButton(Button):
    """An icon-only button — a `Button` with a square, icon-sized frame.

        v3.IconButton('refresh', help='Refresh tree')

    Args:
        icon: a material icon name (e.g. "refresh"), or any short label;
            a bare name is wrapped as `:material/<name>:`.
        help: tooltip text — recommended, since an icon alone is cryptic.
        type / width / enabled / on_click: see `Button`.
    """

    def __init__(
        self, icon: str = '', *, help: str | None = None, **kwargs: tp.Any
    ) -> None:
        if icon and not icon.startswith(':'):
            icon = ':material/{}:'.format(icon)
        super().__init__(icon, help=help, **kwargs)
        self._icon_only = True


class Info(_TextVisible):
    """A blue informational alert box (mirrors Streamlit's `st.info`).

    Properties:
        text:    str  — the message (bindable; `:color[..]` markup allowed)
        visible: bool — whether the alert is shown (bindable)
    """

    _kind = 'info'


class Markdown(_HelpText):
    """A markdown block (mirrors Streamlit's `st.markdown`).

        v3.Markdown('Press :material/play_arrow: to **start**.')

    The source is parsed in the browser, just like Streamlit's, so the
    Streamlit-only extensions (`:material/..:` icons, `:color[..]` spans) work
    here as well. A blank line starts a new paragraph.

    Args:
        text: the markdown source (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """


class Multiselect(_Labeled):
    """A dropdown for choosing several options (mirrors `st.multiselect`).

        with v3.Multiselect(
            'Select chart results',
            options=('Droop', 'PSD', 'SNDR'),
            value=('Droop', 'PSD'),
        ):
            pass

    The trigger summarises the selection; opening it shows every option with
    a tick box. Each toggle reports the whole selection back to the server.

    Args:
        label: the widget label (bindable).
        options: the choices (bindable).
        value: the initial selection, a list drawn from `options` (bindable).
        format: callable (value -> text) or a label sequence parallel to
            `options`.
        format_func: raw option value -> display string.
        placeholder: shown on the trigger while nothing is selected.

    Properties:
        label: str — the widget label.
        options: list — the choices.
        value: list — the selected options; the client sends the whole list
            on each toggle.

    Signals:
        on_value (via `ms['on_value']` or `ms.value.on_change`)
    """

    format_func: tp.Callable[[tp.Any], str]

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        value: tp.Sequence[tp.Any] | Property | None = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        placeholder: str = 'Choose an option',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = _prop([], _as_list(options))
        self.value = _prop([], _as_list(value))
        if format is not None:
            if callable(format):
                self.format_func = tp.cast(tp.Callable[[tp.Any], str], format)
            else:
                labels = list(format)

                def _by_index(x: tp.Any) -> str:
                    return labels[list(self.options.get()).index(x)]

                self.format_func = _by_index
        elif format_func is not None:
            self.format_func = format_func
        else:
            self.format_func = lambda x: str(x)
        self._placeholder = placeholder

    def _coerce_value(self, values: tp.Any) -> list:
        """Map the client's raw strings back onto the real options."""
        options = list(self.options.get())
        out = []
        for raw in values or ():
            for option in options:
                if str(option) == str(raw):
                    out.append(option)
                    break
        return out


class NumberInput(_Labeled):
    """A numeric input box (mirrors Streamlit's `st.number_input`).

    Args:
        label: the widget label.
        value: the number (bindable). It alone decides whether this is an
            int widget or a float widget.
        min_value / max_value: optional inclusive bounds. An int widget
            requires ints; a float widget also accepts ints and converts
            them to float.
        step: increment used by the stepper (+/-) gadgets. `0` (the
            default) shows **no stepper at all** — pass a positive number to
            get one. An int widget requires an int step; a float widget
            accepts int or float (converted to float). Must be >= 0.
            A stepper that does not fit the widget's width degrades: it turns
            into a vertical (+ above, - below) gadget, and is dropped when
            even that does not fit (see `page.css`).
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

    Raises:
        TypeError: `value` is not a number, or `min_value` / `max_value` /
            `step` do not match the widget's numeric type.
        ValueError: `value` falls outside `[min_value, max_value]`, or
            `step` is negative.
    """

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        value: int | float | Property = 0,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        step: int | float = 0,
        *,
        format: tp.Callable[[tp.Any], str] | None = None,
        width: Width | None = None,
        placeholder: str = '',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label, label_visibility=label_visibility, width=width, **kwargs
        )
        number = _resolve_number(value)
        is_float = isinstance(number, float)
        self._num_type = float if is_float else int

        if min_value is not None:
            min_value = _check_number_arg(min_value, is_float, 'min_value')
        if max_value is not None:
            max_value = _check_number_arg(max_value, is_float, 'max_value')
        if min_value is not None and number < min_value:
            raise ValueError(
                f'NumberInput value {number!r} is below min_value '
                f'{min_value!r}.'
            )
        if max_value is not None and number > max_value:
            raise ValueError(
                f'NumberInput value {number!r} is above max_value '
                f'{max_value!r}.'
            )
        step = _check_number_arg(step, is_float, 'step')
        if step < 0:
            raise ValueError(f'NumberInput step must be >= 0, got {step!r}.')

        # `0` keeps `_step` falsy: no stepper is rendered in that case.
        self.value = _prop(tp.cast(tp.Any, number), tp.cast(tp.Any, value))
        self.format = format
        self._min = min_value
        self._max = max_value
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

    Args:
        label: the trigger label (bindable).
        width: `int` (px) | 'content' | 'stretch' | None (default) — width
            of the trigger button.
        visible: whether the popover is shown (default True, bindable).
        help: markdown tooltip text shown on the trigger button; a plain
            string or a bound value (`sc.bind(...)`).
        panel_align: `'trigger'` (default) anchors the panel under the
            trigger; `'row'` stretches it across the surrounding `Row`,
            from that row's text input's left edge to the row's right edge.
        panel_max_height: optional max height (px) of the panel; content
            taller than this scrolls (bindable is not supported).

    Properties:
        text: str — the trigger label (bindable).
        visible: bool — whether the popover is shown.

    Note:
        The trigger's chevron is *swapped* between `expand_more` and
        `expand_less` on open/close (see `render._POPOVER_CHEVRON_*` and
        `scSwapChevron` in `page.js`), which is what Streamlit does. The
        selectbox chevron, on the other hand, rotates (a canary-only touch,
        listed in `.trae/documents/pixel_fidelity_caveats.md`). The two may be
        unified on the rotation later on, so keep the swap isolated here.
    """

    _default_width = 'content'

    def __init__(
        self,
        label: str | Property = '',
        *,
        width: Width | None = None,
        visible: bool | Property = True,
        help: str | Property = '',
        panel_align: tp.Literal['trigger', 'row'] = 'trigger',
        panel_max_height: int | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, width=width, **kwargs)
        self.visible = _prop(True, visible)
        self.help = _help_prop(help)
        self._panel_align = panel_align
        self._panel_max_height = panel_max_height


class Progress(_HasText):
    """A progress bar (mirrors Streamlit's `st.progress`).

    Args:
        value: completion percentage — an int between 0 and 100, or `None`
            for an indeterminate (animated) bar. Bindable.
        text:  an optional caption shown under the bar (bindable).
        visible: whether the bar is shown (default False, bindable), so a
            long-running step can toggle it like a spinner.

    Properties:
        value:   int | None — the completion percentage.
        text:    str — the caption.
        visible: bool — whether the bar is shown.
    """

    def __init__(
        self,
        value: int | None | Property = None,
        *,
        text: str | Property = '',
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, **kwargs)
        self.value: Property[int | None] = Property(None)
        if isinstance(value, Property):
            self.value.bind(value)
        elif value is not None:
            self.value.set(value)
        self.visible = _prop(False, visible)


class Radio(_OptionsWidget):
    """A radio button group (mirrors Streamlit's `st.radio`).

    Args:
        label:     the widget label (bindable).
        horizontal: lay the options out in a row instead of a column.
        max_height: cap the list height in px and scroll past it (useful for
            long option lists such as a folder listing).

    Properties:
        label, options, value — see `_OptionsWidget`.

    Attributes:
        format_func: Callable[[Any], str] — raw option value → display string
        (default `str`; reassign it to change formatting).

    Signals:
        on_value (via `radio['on_value']` or `radio.value.on_change`)
        on_options (via `radio['on_options']` or `radio.options.on_change`)
    """

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        *,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        label_visibility: str = 'visible',
        horizontal: bool = False,
        max_height: int | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            format_func=format_func,
            label_visibility=label_visibility,
            **kwargs,
        )
        self._horizontal = horizontal
        self._max_height = max_height


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


class SelectSlider(_OptionsWidget):
    """A slider over a fixed set of options (mirrors `st.select_slider`).

        with v3.SelectSlider(
            'Start level',
            options=range(15, 0, -1),
            value=15,
            format_func=lambda x: 'Lv.{}'.format(x),
        ):
            pass

    Every option is a tick on one track; clicking or dragging to a tick
    selects it. The interaction is client-side; the result is reported back
    as a `change` event.

    Args:
        label: the widget label (bindable).
        options: the discrete choices, laid out left to right (bindable).
        index / value: the initial selection (defaults to the first option).
        format: callable (value -> text) or a label sequence parallel to
            `options`.
        format_func: raw option value -> display string.

    Properties:
        label, options, index, value — see `_OptionsWidget`.

    Signals:
        on_value (via `slider['on_value']` or `slider.value.on_change`)
    """

    _default_width = 'stretch'


class Selectbox(_OptionsWidget):
    """A dropdown select component (mirrors Streamlit's `st.selectbox`).

    Args:
        accept_new_options: allow typing a value that is not among
            `options` yet — an input row appears at the top of the dropdown.
        format_new_option: converts the typed text into an option value,
            e.g. `lambda x: int(x, 0)` for `'0x30'` / `'48'`. Required when
            `accept_new_options` is on.

    Properties:
        label, options, index, value — see `_OptionsWidget`.

    Attributes:
        format_func: Callable[[Any], str] — raw option value → display string
        (default `str`; reassign it to change formatting).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
        on_options (via `sel['on_options']` or `sel.options.on_change`)
    """

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        index: int | Property | None = None,
        value: tp.Any = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        format_func: tp.Callable[[tp.Any], str] | None = None,
        accept_new_options: bool = False,
        format_new_option: tp.Callable[[str], tp.Any] | None = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            options,
            index=index,
            value=value,
            format=format,
            format_func=format_func,
            label_visibility=label_visibility,
            **kwargs,
        )
        if accept_new_options and format_new_option is None:
            raise TypeError(
                'Selectbox(accept_new_options=True) needs a '
                '`format_new_option` callable to convert the typed text.'
            )
        self._accept_new_options = accept_new_options
        self._format_new_option = format_new_option

    def _on_new_option(self, text: str) -> None:
        """The client typed a value that is not among `options` yet.

        `format_new_option` turns the raw text (e.g. `'0x30'`) into a value,
        which is appended to `options` (when new) and then selected. Input
        the converter rejects leaves the widget untouched and is reported on
        the server console.
        """
        convert = self._format_new_option
        try:
            new_value = convert(text) if convert is not None else text
        except Exception as exc:
            print(f'[streamlit-canary] ignored new option {text!r}: {exc}')
            return
        options = list(self.options.get() or [])
        if new_value not in options:
            options.append(new_value)
            self.options.set(options)
        # `_sync_index` mirrors the new position into `index`.
        self.value.set(new_value)


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

    _kind = 'success'


class Table(Component):
    """A static table (mirrors Streamlit's `st.table`).

    Args:
        rows: an iterable of `(key, value)` pairs. Both cells accept the
            same `:color[..]` markup as `v3.Text`. Bindable.
        width: "stretch" (Streamlit's default) fills the parent column;
            "content" hugs the cell contents; an int is a pixel width.

    Properties:
        rows: list[tuple[str, str]] — the table body.
    """

    _default_width = 'stretch'

    def __init__(
        self,
        rows: tp.Iterable[tp.Tuple[str, str]] | Property | None = None,
        *,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)
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

    Panels may also be walked in label order with `next(tabs)` (mirroring
    `next(grid)`):

        with v3.Tabs(('a', 'b')) as tabs:
            with next(tabs):
                v3.Text('...')
            with next(tabs):
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
        self._cursor = 0
        if active is None:
            active = self._labels[0]
        self.active = _prop(self._labels[0], tp.cast(tp.Any, active))

    def __getitem__(self, key: tp.Any) -> tp.Any:
        if isinstance(key, str) and key in self._labels:
            return self._panel(key)
        return super().__getitem__(key)

    # -- panel iteration (in label order) ---------------------------------

    def __iter__(self) -> 'Tabs':
        self._cursor = 0
        return self

    def __next__(self) -> '_TabPanel':
        if self._cursor >= len(self._labels):
            raise StopIteration
        label = self._labels[self._cursor]
        self._cursor += 1
        return self._panel(label)

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

    def _on_change(self, value: tp.Any) -> None:
        """A tab click reports the label that became visible."""
        label = str(value)
        if label in self._labels:
            self.active.set(label)


class Text(_HelpText):
    """A text display component (mirrors Streamlit's `st.text`).

    Args:
        text: the text content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """


class TextArea(_Labeled):
    """A multi-line text box (mirrors Streamlit's `st.text_area`).

    Args:
        label: the widget label.
        value: initial text (bindable).
        placeholder: hint shown while the box is empty.
        height: box height — `int` px (default 200) | 'stretch' | 'content';
            the text scrolls once it overflows.
        enabled: bool (default True, bindable) — a disabled box is greyed
            out and cannot be edited.
        width: `int` px | 'stretch' | 'content' | None (fill parent).
        help: optional tooltip shown next to the label.

    Properties:
        label: str — rendered above the box.
        value: str — the current text; the client sends a `change` event
            (fired on blur), which sets this property.
        enabled: bool — whether the box accepts input.

    Signals:
        on_value: emitted when `value` changes.
    """

    _default_width = 'stretch'
    _default_height = 200

    def __init__(
        self,
        label: str | Property = '',
        *,
        value: str | Property = '',
        placeholder: str = '',
        height: Height | None = None,
        enabled: bool | Property = True,
        width: Width | None = None,
        help: str = '',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            help=help,
            label_visibility=label_visibility,
            width=width,
            height=height,
            **kwargs,
        )
        self.value = _prop('', value)
        self.enabled = _prop(True, enabled)
        self._placeholder = placeholder


class TextInput(_Labeled):
    """A single-line text input (mirrors Streamlit's `st.text_input`).

    Args:
        label: the widget label.
        value: initial text (bindable).
        placeholder: hint shown while the box is empty.
        enabled: bool (default True, bindable) — a disabled box is greyed
            out and cannot be edited.
        width: `int` px | 'stretch' | 'content' | None (fill parent).
        help: optional tooltip shown next to the label.

    Properties:
        label: str — rendered above the box.
        value: str — the current text; the client sends a `change` event
            (fired on blur / Enter), which sets this property.
        enabled: bool — whether the box accepts input.

    Signals:
        on_value: emitted when `value` changes.
    """

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        value: str | Property = '',
        *,
        placeholder: str = '',
        enabled: bool | Property = True,
        width: Width | None = None,
        help: str = '',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            help=help,
            label_visibility=label_visibility,
            width=width,
            **kwargs,
        )
        self.value = _prop('', value)
        self.enabled = _prop(True, enabled)
        self._placeholder = placeholder


class Title(_HelpText):
    """A title (heading) component (mirrors Streamlit's `st.title`).

    Args:
        text: the title content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """


class Toggle(_Labeled):
    """An on/off switch (mirrors Streamlit's `st.toggle`).

    Same fields as `Checkbox`; only the visual differs (a sliding switch
    instead of a tick box).

    Args:
        label: the widget label (bindable).
        value: the switch state (default False, bindable).

    Properties:
        label: str  — the widget label.
        value: bool — the switch state; the client sends a `change` event
            (boolean), which sets this property.

    Signals:
        on_value (via `tg['on_value']` or `tg.value.on_change`)
    """

    _default_width = 'stretch'

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


class Warning(_TextVisible):
    """A yellow warning alert box (mirrors Streamlit's `st.warning`).

    Properties:
        text:    str  — the message (bindable; `:color[..]` markup allowed)
        visible: bool — whether the alert is shown (bindable)
    """

    _kind = 'warning'
