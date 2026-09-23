"""Button-style widgets: the first half of Streamlit's "Input widgets"
(`api-reference/widgets`), which we split in two.

`Button`, `IconButton`, `MenuButton`, `ToggleButton`. The value inputs live
in `inputs.py`.
"""

import typing as tp

from ._shared import _as_list
from ._shared import _derive
from ._shared import _HasText
from ._shared import _help_prop
from ._shared import _prop
from .base import Width
from .layouts import Popover
from ..kernel import Property
from ..kernel import Signal


class Button(_HasText):
    """A clickable button.

    Args:
        label:   button text (stored in the reactive `text` Property).
        type:    "secondary" (default) | "primary" (bindable).
        width:   "content" (default) | "stretch" — stretch fills parent width.
        help:    markdown tooltip text; a plain string or a bound value
            (`sc.bind(...)`) when the text depends on state.
        enabled: bool (default True) | bound value (`sc.bind(...)`).

    Properties:
        text:    str  — the label (bindable).
        type:    str  — "secondary" | "primary" (bindable).
        enabled: bool — whether the button can be clicked (bindable).
        help:    str  — markdown tooltip (bindable).

    Signals:
        on_click: emitted when the user clicks the button. A handler may
            also be attached at construction time via `on_click=...`.
    """

    _default_width = 'content'

    def __init__(
        self,
        label: str | Property = '',
        *,
        type: str | Property = 'secondary',
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
        # `type` is reactive as well (`width` is collected by the base class):
        # binding it lets a button turn primary / secondary at runtime, e.g.
        # a step that becomes the "confirm" action.
        self.type = _prop('secondary', type)
        # `Signal(_owner_factory=...)` mirrors `Property.on_change`, so
        # `@btn.on_click.partial(sc._self)` hands the handler this button.
        self.on_click: Signal = Signal(_owner_factory=lambda: self)
        if on_click is not None:
            self.on_click.connect(on_click)


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


# Alphabetically this belongs before `Multiselect`, but it subclasses
# `Popover`, so it has to follow it.
class MenuButton(Popover):
    """A button that unfolds a menu of options (mirrors `st.menu_button`).

    The trigger shows the label plus a chevron; the panel lists `options` as
    menu rows. Picking one sets `value` and closes the menu -- a client-side
    affair, so it never reruns.

        menu = v3.MenuButton('Export', options=('CSV', 'JSON'))
        @menu.value.on_change
        def _picked(): ...

    The panel is `position: fixed` with a z-index above every panel, so it may
    spill past the edges of a scrollable ancestor -- a plain `Popover` panel
    would be clipped by one.

    Args:
        label: the trigger label (bindable).
        options: the choices (bindable).
        value: the picked option (bindable; empty until something is picked).
        format: callable (value -> text) or a label sequence parallel to
            `options`.
        width: `int` (px) | 'content' | 'stretch' | None (default) — width of
            the trigger button.
        visible / enabled: whether the button is shown / clickable (bindable).
        help: markdown tooltip text shown on the trigger button.
        panel_max_height: optional max height (px) of the menu; content taller
            than this scrolls (bindable is not supported).

    Properties:
        text: str — the trigger label (bindable).
        options: list — the choices.
        value: the picked option; clicking a row sets it.

    Signals:
        on_value (via `mb['on_value']` or `mb.value.on_change`)
    """

    format_func: tp.Callable[[tp.Any], str]

    def __init__(
        self,
        label: str | Property = '',
        options: tp.Sequence[tp.Any] | Property | None = None,
        *,
        value: tp.Any = '',
        format: (tp.Callable[[tp.Any], str] | tp.Sequence[str] | None) = None,
        width: Width | None = None,
        enabled: bool | Property = True,
        help: str | Property = '',
        panel_max_height: int | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            width=width,
            enabled=enabled,
            help=help,
            panel_max_height=panel_max_height,
            **kwargs,
        )
        self.options = _prop([], _as_list(options))
        self.value = _prop('', value)
        if format is None:
            self.format_func = lambda x: str(x)
        elif callable(format):
            self.format_func = tp.cast(tp.Callable[[tp.Any], str], format)
        else:
            labels = list(format)

            def _by_index(x: tp.Any) -> str:
                return labels[list(self.options.get()).index(x)]

            self.format_func = _by_index
        # `_render_popover` turns this into `st-popover-panel--menu`, which
        # `scPositionPanel` places like a menu and `scMenuPick` drives.
        self._panel_align = 'menu'

    def _coerce_value(self, value: tp.Any) -> tp.Any:
        """Map the client's raw string back onto the real option."""
        for option in self.options.get() or ():
            if str(option) == str(value):
                return option
        return value


# Alphabetically last, but that is fine: it subclasses `Button`, defined
# first (the same reason `_shared.py`'s private bases sit up front).
class ToggleButton(Button):
    """A button that stays lit while its `value` is on (a canary extra).

        with v3.ToggleButton('Bold') as bold:
            @bold.value.on_change
            def _(): ...

    Clicking flips `value`; the button draws with `type="primary"` while it
    is true and `"secondary"` while false. There is no `type` argument: that
    field is *derived* from `value` and read-only, so the two can never
    disagree (writing it raises).

    Args:
        label: the button text (bindable).
        value: the initial on / off state (bindable -- pass a `Property` to
            follow the state it toggles).
        help / width / enabled: see `Button`.
        on_click: extra handler, run *after* `value` has flipped, so it sees
            the new state (also attachable with `@tb.on_click`).

    Properties:
        value: bool — the toggle state (bindable; a click flips it).
        type: str — derived & read-only: "primary" while on, else
            "secondary".

    Signals:
        on_click, and `value.on_change` (via `tb.value.on_change` /
        `tb['on_value']`).
    """

    def __init__(
        self,
        label: str | Property = '',
        *,
        value: bool | Property = False,
        on_click: tp.Callable[[], None] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        # `Button` has a `type` argument; a toggle's follows `value`, so
        # refuse it here rather than letting the base swallow it silently.
        if 'type' in kwargs:
            raise TypeError(
                'ToggleButton takes no `type`: it follows `value` (primary '
                'while on, secondary while off)'
            )
        # `super().__init__` gets `on_click=None`: the caller's handler is
        # wired below, after `_flip`, so it observes the state the click just
        # produced rather than the one before it.
        super().__init__(label, on_click=None, **kwargs)
        self.value = _prop(False, value)
        # The look follows the state; `_derive` makes it read-only so a
        # caller cannot force the two apart.
        self.type = _derive(
            self.value, lambda on: 'primary' if on else 'secondary'
        )
        self.on_click.connect(self._flip)
        if on_click is not None:
            self.on_click.connect(on_click)

    def _flip(self) -> None:
        self.value.set(not self.value.get())
