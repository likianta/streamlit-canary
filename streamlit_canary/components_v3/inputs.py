"""Value inputs: the second half of Streamlit's "Input widgets"
(`api-reference/widgets`), which we split in two.

`CheckGroup`, `Checkbox`, `Multiselect`, `NumberInput`, `Radio` (an alias of
`RadioGroup`), `RadioGroup`, `ReducibleGroup`, `SegmentedControl`,
`SelectSlider`, `Selectbox`, `TextArea`, `TextInput`, `Toggle`. The buttons
live in `buttons.py`.
"""

import typing as tp

from ._shared import _as_list
from ._shared import _Labeled
from ._shared import _OptionsWidget
from ._shared import _prop
from ._shared import _RowGestures
from .base import Height
from .base import Width
from ..kernel import Property
from ..kernel import Signal
from ..kernel import _undefined


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


class CheckGroup(_RowGestures, _Labeled):
    """A group of tick boxes for choosing several options at once.

    It is `RadioGroup`'s twin: same label handling, same option spacing, same
    `format` / `horizontal` / `max_height` / `enabled` arguments, same hover
    highlight, same material / markdown text rendering. It differs in exactly
    two ways:

    * every option draws a *square* box (RadioGroup draws a circle);
    * clicking an option ticks / unticks it, so any number may be selected.

        with v3.CheckGroup(
            'Extras',
            options=('Deps', 'Docs', 'Tests'),
            value=('Deps', 'Tests'),
        ):
            pass

    Spell the starting state next to each option with a `dict`: the keys
    become the options, and `value` then mirrors them as a parallel list of
    booleans (see `value` below):

        v3.CheckGroup('Extras', options={'Deps': True, 'Docs': False})

    Args:
        label: the widget label (bindable).
        options: the choices, laid out top to bottom (bindable). A `dict` is
            accepted as a shorthand: the keys become the options, and each
            value says whether that option starts ticked.
        value: the initial selection, a list drawn from `options` (bindable)
            -- or, for the `dict` form, a list of booleans parallel to
            `options`.
        format: callable (value -> text) or a label sequence parallel to
            `options`.
        horizontal: lay the options out in a row instead of a column.
        max_height: cap the list height in px and scroll past it.
        enabled: whether the widget accepts input (bindable).
        box_disabled: a predicate marking options whose box may never be
            ticked; those are drawn dimmed and their field is inert.
            `TreeSelect` uses it for the `..` row, which is a navigation
            target rather than a node.

    Properties:
        label, options — see `_Labeled` / the fields below.
        value: list — the ticked options; the client sends the whole list on
            every toggle. When `options` was given as a `dict`, this is
            instead a list of booleans parallel to `options` -- the form the
            client's report gets translated into, and the form it is read
            back as.
        focused_index: int — the position of the row the client last clicked
            (a click on a row body highlights that row -- see
            `scHighlightChoice`), or -1 while none is. Handy for a "go into
            the focused node" button:
            `btn.enabled = sc.bind(cg.focused_index, lambda i: i >= 0)`.

    Attributes:
        format_func: Callable[[Any], str] — raw option value -> display string
        (default `str`; reassign it to change formatting).

    Signals:
        on_change (also `cg['on_value']` / `cg.value.on_change`): `value`
            changed, i.e. a row was ticked or unticked.
        on_options (via `cg['on_options']` or `cg.options.on_change`)
    """

    format_func: tp.Callable[[tp.Any], str]

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        options: (
            tp.Sequence[tp.Any] | tp.Mapping[str, bool] | Property | None
        ) = None,
        *,
        value: tp.Sequence[tp.Any] | Property | None = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        enabled: bool | Property = True,
        label_visibility: str = 'visible',
        horizontal: bool = False,
        max_height: int | None = None,
        box_disabled: tp.Callable[[tp.Any], bool] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        # A `dict[str, bool]` spells each option's text together with whether
        # it starts ticked: the keys become `options` and the flags become
        # `value`. That value is then a list of booleans *parallel* to
        # `options` rather than a subset of it -- `_flags` marks the widget
        # as that odd one out, and the renderer and `_coerce_value` branch on
        # it.
        if isinstance(options, dict):
            self._flags = True
            flags = [bool(on) for on in options.values()]
            options = list(options)
            if value is None:
                value = flags
        else:
            self._flags = False
        self.options = _prop([], _as_list(options))
        self.value = _prop([], _as_list(value))
        self.enabled = _prop(True, enabled)
        self._init_rows(box_disabled)
        if format is None:
            self.format_func = lambda x: str(x)
        elif callable(format):
            self.format_func = tp.cast(tp.Callable[[tp.Any], str], format)
        else:
            labels = list(format)

            def _by_index(x: tp.Any) -> str:
                return labels[list(self.options.get()).index(x)]

            self.format_func = _by_index
        self._horizontal = horizontal
        self._max_height = max_height

    @property
    def on_change(self) -> Signal:
        """Shorthand for the `value` Property's `on_change` Signal.

        A `CheckGroup` carries several properties, but a row being ticked or
        unticked is nearly always what a caller wants to hear about, so
        `cg.on_change` reads as `cg.value.on_change` (equivalently
        `cg['on_value']`).
        """
        return self.value.on_change

    def _coerce_value(self, values: tp.Any) -> list:
        """Map the client's raw strings back onto the real options.

        In flag mode the client still reports the ticked *texts*, but the
        value is the parallel list of booleans, so every option is tested
        against that report instead of being looked up in it.
        """
        options = list(self.options.get())
        if self._flags:
            texts = {str(value) for value in (values or ())}
            return [str(option) in texts for option in options]
        out = []
        for raw in values or ():
            for option in options:
                if str(option) == str(raw):
                    out.append(option)
                    break
        return out


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
        placeholder: str = 'Choose an option',
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = _prop([], _as_list(options))
        self.value = _prop([], _as_list(value))
        if format is None:
            self.format_func = lambda x: str(x)
        elif callable(format):
            self.format_func = tp.cast(tp.Callable[[tp.Any], str], format)
        else:
            labels = list(format)

            def _by_index(x: tp.Any) -> str:
                return labels[list(self.options.get()).index(x)]

            self.format_func = _by_index
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


class RadioGroup(_RowGestures, _OptionsWidget):
    """A radio button group (mirrors Streamlit's `st.radio`).

    Args:
        label:     the widget label (bindable).
        options:   the choices, laid out top to bottom (bindable).
        index / value: the initial selection (defaults to the first option).
        format:    callable (value -> text) or a label sequence parallel to
            `options`.
        horizontal: lay the options out in a row instead of a column.
        max_height: cap the list height in px and scroll past it (useful for
            long option lists such as a folder listing).
        box_disabled: a predicate marking options whose circle may never be
            selected; those are drawn dimmed and their field is inert.
            `TreeSelect` uses it for the `..` row, which is a navigation
            target rather than a node.

    Properties:
        label, options, value — see `_OptionsWidget`.
        focused_index: int — the row the client last clicked, or -1 while none
            is (see `CheckGroup`).

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
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        index: int | Property | None = None,
        value: tp.Any = None,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        label_visibility: str = 'visible',
        horizontal: bool = False,
        max_height: int | None = None,
        box_disabled: tp.Callable[[tp.Any], bool] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            options,
            index=index,
            value=value,
            format=format,
            label_visibility=label_visibility,
            **kwargs,
        )
        self._horizontal = horizontal
        self._max_height = max_height
        self._init_rows(box_disabled)


Radio = RadioGroup  # alias


class ReducibleGroup(_Labeled):
    """A list of items, each droppable from its own trailing `x`.

    The rows are laid out exactly like a `MenuButton`'s options; hovering one
    reveals an `x` on its right, and clicking that `x` drops the item from the
    group and emits `on_reduce`, so the owner can keep its own list in sync.

        group = v3.ReducibleGroup(options=('a.txt', 'b.txt'))
        @group.on_reduce
        def _dropped(item): ...

    Args:
        label: optional label above the list.
        options: the items (bindable).
        format: callable (value -> text) or a label sequence parallel to
            `options`.
        label_visibility: 'visible' (default) | 'collapsed' | 'hidden'.

    Properties:
        label: str — the widget label.
        options: list — the items still shown.

    Signals:
        on_reduce: emitted with the dropped item.
        on_options (via `rg['on_options']` or `rg.options.on_change`)
    """

    format_func: tp.Callable[[tp.Any], str]

    _default_width = 'stretch'

    def __init__(
        self,
        label: str | Property = '',
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.options = _prop([], _as_list(options))
        if format is None:
            self.format_func = lambda x: str(x)
        elif callable(format):
            self.format_func = tp.cast(tp.Callable[[tp.Any], str], format)
        else:
            labels = list(format)

            def _by_index(x: tp.Any) -> str:
                return labels[list(self.options.get()).index(x)]

            self.format_func = _by_index
        self.on_reduce: Signal = Signal(tp.Any)

    def _on_reduce(self, value: tp.Any) -> None:
        """Drop the option whose key the client sent (an `x` click)."""
        options = list(self.options.get() or ())
        kept = [o for o in options if str(o) != str(value)]
        if len(kept) == len(options):
            return
        dropped = [o for o in options if str(o) == str(value)][0]
        self.options.set(kept)
        self.on_reduce.emit(dropped)


class SegmentedControl(_OptionsWidget):
    """A segmented control (mirrors Streamlit's `st.segmented_control`).

    The options lay out as pills inside one rounded track; the selected pill
    is raised. Only single selection is implemented (Streamlit's
    `selection_mode='multi'` is not).

    Args:
        label: the widget label (bindable).
        options: the choices, laid out left to right (bindable).
        index / value: the initial selection (defaults to the first option).
        format: callable (value -> text) or a label sequence parallel to
            `options`.

    Properties:
        label, options, value — see `_OptionsWidget`.

    The track hugs its options by default (the `content` sizing keyword emits
    `flex: 0 1 auto`, so a `Row[Space(width='stretch'), SegmentedControl]`
    parks it against the right edge). Pass `width='stretch'` to fill instead.
    """

    _default_width = 'content'


class SelectSlider(_OptionsWidget):
    """A slider over a fixed set of options (mirrors `st.select_slider`).

        with v3.SelectSlider(
            'Start level',
            options=range(15, 0, -1),
            value=15,
            format=lambda x: 'Lv.{}'.format(x),
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
        candidates: optional suggestions (bindable), offered by a caret that
            opens a Selectbox-styled panel; picking one fills the box in. The
            text stays freely editable either way, so this is our take on
            `st.selectbox(..., accept_new_options=True)`. `None` draws a plain
            box with no caret, an empty sequence keeps the caret but disables
            it, and a non-empty one opens a working panel. Whether the caret
            exists is a build-time choice -- a later patch only swaps the
            contents (any `None` sent afterwards reads as an empty list).

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
        candidates: tp.Iterable[str] | Property | None = None,
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
        if candidates is None or isinstance(candidates, Property):
            source = tp.cast(tp.Optional[tp.List[str]], candidates)
        else:
            # materialize, so a one-shot iterable does not go stale
            source = list(candidates)
        self.candidates = _prop(
            tp.cast(tp.Optional[tp.List[str]], None), source
        )


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
        value: bool | Property = False,
        *,
        label_visibility: str = 'visible',
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, label_visibility=label_visibility, **kwargs)
        self.value = _prop(False, value)
