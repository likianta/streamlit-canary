"""Shared private bases and helpers for the v3 component modules.

Nothing here is public API: the per-category modules import these bases, and
`components_v3/__init__.py` re-exports only the components themselves.
"""

import textwrap
import typing as tp

from .base import Component
from ..kernel import Property
from ..kernel import Signal

_T = tp.TypeVar('_T')


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


def _is_blank(value: tp.Any) -> bool:
    """Whether a data source draws nothing.

    `None`, an empty string and an empty sequence all count, and so does a
    string of nothing but whitespace -- with a single exception, the lone
    space. `' '` is how an element keeps its place while showing nothing
    (`v3.Title(' ')`), the way `st.title('')` still occupies a line. Every
    other whitespace-only string (`'\\t'`, `'\\n'`, `'  '`) is blank, so a
    component that tidies its input first (`Markdown` dedents and trims)
    leaves nothing behind instead of an invisible row -- see
    `_visible_when_filled`.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value != ' ' and not value.strip()
    return not value


def _visible_when_filled(
    data: Property, explicit: bool | Property = True
) -> Property[bool]:
    """A `visible` flag that follows whether `data` holds anything.

    `Table` / `Code` / `Markdown` have nothing to draw while their data is
    blank, so rather than leaving an empty frame behind they hide -- and come
    back as soon as the (possibly bound) value fills in.

    "Blank" means `None` or empty (`_is_blank`); the lone space is content,
    so `Title(' ')` keeps its line while showing nothing -- the way to ask
    for `st.title('')`'s empty row. Any other whitespace-only string counts
    as blank, and a component that tidies its input runs that tidying before
    this test (so `Markdown('\\n')` is blank too).

    `explicit` is the caller's own `visible` (the base-class argument) ANDed
    in, so the widget hides either because there is nothing to draw or because
    the caller switched it off, and a bound flag keeps working: both sources
    are watched.

    `data` must already hold its value when this is called.
    """
    visible = Property(True)

    def sync() -> None:
        on = (
            bool(explicit.get())
            if isinstance(explicit, Property)
            else bool(explicit)
        )
        visible.set(not _is_blank(data.get()) and on)

    data.on_change.connect(sync)
    if isinstance(explicit, Property):
        explicit.on_change.connect(sync)
    sync()
    return visible


class _ReadOnlyProperty(Property):
    """A `Property` a caller may read (and watch) but not write.

    `set` -- what `prop.set(...)` and `comp['x'] = ...` call -- is refused, so
    a derived field cannot be forced out of step with what it derives from.
    The owning component updates it through `_write` (see `_derive`).
    """

    def set(self, value: tp.Any, notify: tp.Optional[bool] = None) -> None:
        raise AttributeError(
            'this is a derived, read-only property; change the value it is '
            'derived from instead'
        )

    def _write(self, value: tp.Any, notify: tp.Optional[bool] = None) -> None:
        super().set(value, notify)


def _derive(
    source: Property, transform: tp.Callable[[tp.Any], tp.Any]
) -> Property:
    """A read-only `Property` mirroring `transform(source.get())`.

    Used for a field the component owns and the caller only reads, e.g.
    `ToggleButton.type` (on -> "primary", off -> "secondary"). Writing it
    raises, so it can never disagree with `source`.
    """
    out = _ReadOnlyProperty()
    out._write(transform(source.get()))
    source.on_change.connect(lambda: out._write(transform(source.get())))
    return out


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


# -- shared bases ----------------------------------------------------------


class _HasPlaceholder:
    """Mixin for widgets that show a hint while nothing is picked.

    Fields:
        placeholder: Property[str] — drawn while the widget holds nothing: an
            empty box for the three text-like widgets (`TextInput` /
            `TextArea` / `NumberInput`), an empty selection for the two option
            triggers (`Selectbox` / `Multiselect`). Bindable, so a hint can
            follow the state it hints at (see
            `test/pixel_fidelity/ui_scene_sc.py`).

    A mixin rather than a base: these widgets already meet through `_Labeled`
    (or `_OptionsWidget`), so there is no single `super()` to chain into and
    each `__init__` calls `_init_placeholder` directly -- the same
    arrangement as `_RowGestures._init_rows`.
    """

    def _init_placeholder(self, placeholder: str | Property = '') -> None:
        self.placeholder = _prop('', placeholder)


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
    `st.caption`, `st.title`) all accept `help`. Used by Caption, Markdown,
    Text and Title.

    Fields:
        text: Property[str] — the displayed text (bindable).
        help: Property[str] — markdown tooltip shown next to the text
            (bindable; bind it when the text depends on state).
        visible: Property[bool] — whether the text is drawn (bindable). A
            blank `text` has nothing to draw, so this is the caller's flag
            ANDed with the content test (see `_visible_when_filled`): the
            element hides either because there is nothing to show or because
            the caller switched it off.
        font_family: str — the CSS `font-family` to draw the text in (static,
            not bindable). Empty means inherit, i.e. the page's own font;
            `sc.MONOSPACED` is the stack to reach for when the text has to
            line up in columns (a log, an ASCII table).
        font_size: str — a CSS length to draw the text at (static). Empty
            leaves it to the stylesheet, i.e. the shared body size -- with one
            exception: `font_family=sc.MONOSPACED` brings `0.875em` along,
            because a monospace face reads a size larger at the same pixels
            (see `MONOSPACED_SIZE`). Pass a length here to override that.

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
        visible: bool | Property = True,
        font_family: str = '',
        font_size: str = '',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, visible=visible, **kwargs)
        self.help = _help_prop(help)
        self._font_family = font_family
        self._font_size = font_size
        self.visible = _visible_when_filled(self.text, visible)


class _Labeled(Component):
    """Shared base for widgets that render a `label` above the control.

    Fields:
        label: Property[str]   — the widget label (bindable).
        _label_visibility: str — "auto" | "visible" | "hidden" | "collapsed";
            see `inputs.T.LabelVisibility` for all four. "auto" is the
            default: the row follows the label, showing when it draws
            something and collapsing when it draws nothing.
        help: Property[str]    — markdown tooltip shown next to the label
            (bindable; bind it when the text depends on state).
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        label_visibility: str = 'auto',
        help: str | Property = '',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = _prop('', label)
        self._label_visibility = label_visibility
        self.help = _help_prop(help)


class _OptionsWidget(_Labeled):
    """Shared base for the option-picking widgets (Selectbox / RadioGroup /
    SegmentedControl / SelectSlider).

    Fields:
        options: Property[list] — the raw choices (bindable).
        index:   Property[int]  — the selected position (bindable).
        value:   Property[any]  — the raw selected value (bindable).
        enabled: Property[bool] — whether the widget accepts input (bindable).
        format:  Callable[[Any], str] | Sequence[str] — how an option is
            rendered: a callable (raw value → display string), or a label
            sequence parallel to `options`. The resolved callable is kept on
            `format_func`.

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
        enabled: bool | Property = True,
        label_visibility: str = 'auto',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = Property([])
        self.index = Property(0)
        self.value = Property('')
        self.enabled = _prop(True, enabled)
        self.format_func: tp.Callable[[tp.Any], str] = self._make_format(format)
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
        self, format: tp.Callable[[tp.Any], str] | tp.Sequence[str] | None
    ) -> tp.Callable[[tp.Any], str]:
        """Resolve the display formatter from `format`.

        `format` may be either a callable (raw value -> display string) or a
        sequence parallel to `options` (index -> display string). A sequence
        is resolved lazily against the *current* options, so it stays correct
        after `options` changes.
        """
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


class _RowGestures:
    """Mixin for the two option lists whose rows carry a click highlight.

    `RadioGroup` and `CheckGroup` both draw rows a client can click *beside*
    the box: such a click highlights the row and reports it back through a
    `focus` event. That highlight and the state behind it live here so the
    widgets stay thin; `_init_rows` is called from each `__init__` (the two
    meet through `_Labeled`, so there is no single `super()` to chain into).

    Fields:
        focused_index: Property[int] — the row the client last clicked, or -1
            while none is. Dropped whenever `options` change: the rows are
            rebuilt, so a remembered index would point at the wrong one.
        _box_disabled: Callable[[Any], bool] | None — marks options whose box
            may never be ticked. They are drawn dimmed and their field is
            inert, so only the row's other half still acts.
    """

    def _init_rows(
        self, box_disabled: tp.Callable[[tp.Any], bool] | None
    ) -> None:
        self.focused_index = Property(-1)
        self._box_disabled = box_disabled
        self.options.on_change.connect(self._reset_focus)

    def _on_focus(self, value: tp.Any) -> None:
        """Record the option row the client just clicked.

        Fired by a `focus` event (see `scHighlightChoice`); the payload is the
        row's index.
        """
        try:
            index = int(value)
        except (TypeError, ValueError):
            index = -1
        self.focused_index.set(index)

    def _reset_focus(self) -> None:
        """Drop the highlight when the options are rebuilt (indices shift)."""
        self.focused_index.set(-1)


class _Submittable:
    """Mixin for input widgets whose text is committed as a separate act.

    Signals:
        on_submit: `Signal(str)` — the text was committed on purpose: Enter
            in a `TextInput` / `NumberInput`, Ctrl+Enter in a `TextArea`, or
            Enter (equivalently, the "Add" row) in a `Selectbox`'s
            `accept_new_option` box. Carries the raw text as typed.
        on_editing_finished: `Signal(str)` — the editing session ended,
            whether by a submit or by the box losing focus. Carries the text
            as it stood then. A submit emits both, `on_submit` first.

    The pair is declared together because it describes one act from two
    angles: `on_submit` is the deliberate commit, `on_editing_finished` the
    end of the session it belongs to.

    A mixin, like `_HasPlaceholder`: these widgets already meet through
    `_Labeled`, so there is no single `super()` to chain into and each
    `__init__` calls `_init_submittable` directly. `Multiselect` carries the
    pair for symmetry with its siblings, but nothing fires them until it
    grows an `accept_new_option` box of its own.
    """

    def _init_submittable(self) -> None:
        # `_owner_factory` mirrors `on_click`, so a handler can ask for the
        # widget itself through `@sig.partial(sc._self)`.
        self.on_submit: Signal = Signal(str, _owner_factory=lambda: self)
        self.on_editing_finished: Signal = Signal(
            str, _owner_factory=lambda: self
        )


class _TextVisible(_HasText):
    """Shared base for status boxes: a `text` plus a bindable `visible`.

    The flag itself lives on `Component` (default `True`); this base leaves
    the default to its users, because the two families want opposite things.
    `Spinner` starts it *off*, so it stays out of the way until it is
    entered. The `Callout` family starts it *on*, and hides only while its
    message is blank (see `_visible_when_filled`).
    """

    def __init__(self, text: str | Property = '', **kwargs: tp.Any) -> None:
        super().__init__(text, **kwargs)
