import typing as tp

from ._shared import _HasText
from ._shared import _help_prop
from ._shared import _prop
from .base import Component
from .base import Height
from .base import Width
from .base import _validate_size
from ..kernel import Property
from ..kernel import Signal

# Streamlit's semantic dialog sizes (`DialogWidth`), mapped to their maximum
# pixel widths (see `st.dialog`: small=500, medium=750, large=1280).
DialogWidth: tp.TypeAlias = tp.Literal['small', 'medium', 'large']
_DIALOG_WIDTHS: dict[str, int] = {'small': 500, 'medium': 750, 'large': 1280}


class Cell(Component):
    """A single cell inside a `Grid`, used as `with grid[row, col]:`."""

    def __init__(self, *, row: int = 0, col: int = 0, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self._row = row
        self._col = col


class Container(Component):
    """Vertical layout container.

    Args:
        width:  `int` (px) | 'stretch' | 'content' | None (fill parent).
        weight: flex-grow ratio when laid out inside a `Row`, e.g. a
            `(5, 2)` split is `Container(weight=5)` + `Container(weight=2)`;
            None keeps the default equal share.
        border: whether to draw a bordered container around the children.
        height: fixed height in px; the content scrolls when it overflows
            (mirrors `st.container(height=...)`).
        max_height, min_height: optional pixel cap / floor on the container's
            height; a cap makes the container scroll rather than letting its
            content spill past it. Canary-only -- see `Component`.
        visible: bool (default True, bindable) — hidden containers keep their
            place in the tree but are not rendered.
        animated: transition the height when `visible` flips, instead of
            appearing/disappearing instantly (mirrors an expander body). Use
            it for blocks that a button reveals, e.g.
            `Container(visible=state.show, animated=True)`.
    """

    def __init__(
        self,
        *,
        width: Width | None = None,
        weight: float | None = None,
        border: bool = False,
        height: Height | None = None,
        animated: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, height=height, **kwargs)
        self._weight = weight
        self._border = border
        self._animated = animated


Column = Container  # alias


class BottomContainer(Container):
    """A container that sticks to the bottom of its parent layout.

    Used exactly like `Container`, except that the layout pushes it down, so a 
    card can keep its actions at the bottom and a dialog can pin a button to 
    its base:

        with v3.Container(height=320):
            v3.Text('...')
            with v3.BottomContainer():
                v3.Button('Close')

    Streamlit's `st.bottom` is only allowed at the root; this one works in
    any layout (a canary-only difference, see
    `.trae/documents/pixel_fidelity_caveats.md`).
    """

    def __init__(self, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)


Bottom = BottomContainer  # alias


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
        max_height, min_height: optional pixel cap / floor on the panel's
            height; a cap makes the panel scroll as a whole. See `Component`.

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
        width: DialogWidth | int = 'small',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = _prop('', text)
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
        self.on_close: Signal = Signal(_owner_factory=lambda: self)

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
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        # Initial state only; the client owns it from then on.
        self._expanded = expanded


_FLOAT_POSITIONS = (
    'top-left',
    'top-center',
    'top-right',
    'bottom-left',
    'bottom-center',
    'bottom-right',
)


class FloatingContainer(Container):
    """A container that sticks to a corner of the layout it sits in.

        with v3.Popover('Browse', panel_max_height=420):
            with v3.FloatingContainer('top-right'):
                v3.IconButton('refresh')
            v3.RadioGroup('Folder contents', options=...)
            with v3.FloatingContainer('bottom-right'):
                v3.Button('Confirm', type='primary')

    Children lay out in a row -- a floating cluster is nearly always a few
    buttons -- and the box hugs them.  It sticks to its corner of the parent's
    *visible* area, so the parent's content scrolls underneath while the box
    stays put: a toolbar that never scrolls away.  Because it keeps its place
    in the layout as well (`position: sticky`, not an overlay), the parent
    needs no compensating padding -- content can always be scrolled clear
    of it.

    Placement matters, because sticky can only offset a box *from its own
    flow position*: author a `top-*` cluster as the parent's first child and a
    `bottom-*` one as its last, so there is somewhere for the corner to be.
    (A bottom cluster also gets `margin-top: auto`, so it drops to the end of
    whatever room the parent has to spare.)  Between the two, everything else
    the parent holds is reachable by scrolling.

    Only a vertical layout may hold one -- a `Popover`, a `Dialog`, or the app 
    root -- since the corner's horizontal half comes from `align-self`, which a 
    `Row` would fight.  Anything else raises `ValueError`.

    Args:
        position: the corner to stick to (required) -- `'top-left'`,
            `'top-center'`, `'top-right'`, `'bottom-left'`,
            `'bottom-center'`, or `'bottom-right'`.
        **kwargs: see `Container`.

    A floating box *is* a `Container` underneath, so `width` / `visible` and the
    other container keywords still apply.
    """

    def __init__(self, position: str, **kwargs: tp.Any) -> None:
        if position not in _FLOAT_POSITIONS:
            raise ValueError(
                'position must be one of {}, got {!r}'.format(
                    ', '.join(repr(p) for p in _FLOAT_POSITIONS), position
                )
            )
        super().__init__(**kwargs)
        parent = self._parent
        if parent is not None and not isinstance(
            parent, (Container, Popover, Dialog)
        ):
            raise ValueError(
                'FloatingContainer must sit in a Container, Popover, Dialog or '
                'the app root, not in {}'.format(type(parent).__name__)
            )
        self._position = position


Floating = FloatingContainer
"""Alias of `FloatingContainer`."""


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


class Popover(_HasText):
    """A popover: a trigger button that reveals a floating panel.

    Children render inside the panel (hidden until the trigger is clicked):

        with v3.Popover('Export requirements'):
            v3.RadioGroup('Mirror source', ...)
            v3.Checkbox('Lock self', value=True)

    Opening/closing is handled entirely on the client, so it never reruns.
    What does reach the server are the two ends of it: `close()` asks the
    client to fold the panel away while leaving the trigger in place, which a
    widget such as `TreeSelect` uses to dismiss its own panel once the user
    confirms; and `on_open` / `on_close` report a panel that came up or went
    away -- which is how a caller does its work only while the panel is up
    (drawing a preview, say) instead of on every change of whatever the panel
    is about.

    Args:
        label: the trigger label (bindable).
        width: `int` (px) | 'content' | 'stretch' | None (default) — width
            of the trigger button.
        visible: whether the popover is shown (default True, bindable).
        help: markdown tooltip text shown on the trigger button; a plain
            string or a bound value (`sc.bind(...)`).
        enabled: whether the trigger accepts clicks (default True, bindable);
            a disabled trigger is greyed out and inert.
        panel_align: `'trigger'` (default) anchors the panel under the
            trigger; `'row'` stretches it across the surrounding `Row`,
            from that row's text input's left edge to the row's right edge;
            `'above'` anchors it *above* the trigger instead, which is what a
            trigger sitting at the bottom of a scrollable panel needs -- a
            downward panel would be clipped by that panel's `overflow`.
        panel_max_height: optional max height (px) of the panel; content
            taller than this scrolls (bindable is not supported).

    Properties:
        text: str — the trigger label (bindable).
        visible: bool — whether the popover is shown.

    Signals:
        on_open: the panel was unfolded (no payload).
        on_close: the panel was folded away (no payload) -- by any means: the
            trigger, a click outside, Escape, or `close()`.

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
        help: str | Property = '',
        enabled: bool | Property = True,
        panel_align: tp.Literal['trigger', 'row', 'above'] = 'trigger',
        panel_max_height: int | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, width=width, **kwargs)
        self.enabled = _prop(True, enabled)
        self.help = _help_prop(help)
        self._panel_align = panel_align
        self._panel_max_height = panel_max_height
        # The open/closed state lives in the browser -- the trigger toggles it
        # and an outside click closes it -- so the server cannot read it. This
        # counter is how it asks for a close instead: `close()` bumps it and
        # the client folds the panel away on the patch.
        self._close = Property(0)
        # The other direction: the client tells us when the panel came up or
        # went away, so a caller can wait for that instead of guessing (see the
        # class docstring).
        self.on_open: Signal = Signal()
        self.on_close: Signal = Signal()

    def _on_close(self, _value: tp.Any = None) -> None:
        """The client folded the panel away."""
        self.on_close.emit()

    def _on_open(self, _value: tp.Any = None) -> None:
        """The client unfolded the panel."""
        self.on_open.emit()

    def close(self) -> None:
        """Fold the panel shut, the way an outside click would.

        The trigger stays put; only the panel closes.
        """
        self._close.set(self._close.get() + 1)


class Row(Component):
    """Horizontal layout container.

    Args:
        vertical_alignment: "top" (default) | "center" | "bottom" — how
            children align on the cross axis.
        hide_when_empty: whether the row also counts as hidden while every
            child of it is hidden (default `False`). A row that exists only
            to be filled in later -- a bar handed out for a caller to add
            its own widgets to -- would otherwise still cost its parent one
            gap, because a zero-height box is a box all the same.

            This is decided per render, so the row is back as soon as
            anything inside it is there when the render happens. A child
            that a *patch* turns visible later does not bring the row back:
            patches reach the elements they name, not their parent.
    """

    def __init__(
        self,
        vertical_alignment: tp.Literal['top', 'center', 'bottom'] = 'top',
        *,
        hide_when_empty: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._vertical_alignment = vertical_alignment
        self._hide_when_empty = hide_when_empty

    def is_hidden(self) -> bool:
        if super().is_hidden():
            return True
        if not self._hide_when_empty:
            return False
        return not any(not child.is_hidden() for child in self.children)


class Space(Component):
    """A flexible spacer (mirrors Streamlit's internal `st.space`).

    Inside a `Row` it absorbs the leftover width, so whatever is laid out
    after it is pushed to the right edge:

        with v3.Row():
            v3.IconButton('home')
            v3.Space(width='stretch')
            v3.Popover(':material/bucket_check: 0')

    A vertical container has no leftover width to absorb, so there it simply
    renders nothing.
    """

    _default_width = 'stretch'


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
