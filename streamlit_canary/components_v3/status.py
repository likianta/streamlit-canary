"""Status elements: Streamlit's "Status elements" (`api-reference/status`).

`Callout` (the base of `Error`, `Info`, `Success`, `Warning`), `LogPanel`,
`Progress`, `Spinner`, `Toast`.
"""

import re
import typing as tp
from time import sleep

from ._shared import _HasText
from ._shared import _TextVisible
from ._shared import _visible_when_filled
from .base import Component
from ..kernel import Property


class Callout(_TextVisible):
    """A coloured alert box -- the base of `Error` / `Info` / `Success` /
    `Warning`.

    Those four are one box in four palettes, the way `st.error` / `st.info` /
    `st.success` / `st.warning` are, so a subclass only names its palette
    through `_kind`; `render.py` turns that into the `st-alert-<kind>` class
    and `runtime/static/css/11-status.css` pairs each kind with its
    `--st-<name>-background-color` / `--st-<name>-text-color`.

    The base itself carries the success palette, because that is what the
    shared `.st-alert-container` rule holds -- the variants only override it.

    Args:
        text: the message (bindable; `:color[..]` markup allowed).
        visible: whether the alert is shown (default True, bindable). A blank
            `text` has nothing to draw, so this is the caller's flag ANDed
            with the content test (see `_visible_when_filled`): the box hides
            either because there is nothing to show or because the caller
            switched it off.

    Properties:
        text:    str  — the message (bindable; `:color[..]` markup allowed)
        visible: bool — whether the alert is shown (bindable).
    """

    _kind = 'success'

    def __init__(
        self,
        text: str | Property = '',
        *,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, visible=visible, **kwargs)
        self.visible = _visible_when_filled(self.text, visible)


class Error(Callout):
    """A red error alert box (mirrors Streamlit's `st.error`)."""

    _kind = 'error'


class Info(Callout):
    """A blue informational alert box (mirrors Streamlit's `st.info`)."""

    _kind = 'info'


# Terminal control sequences: CSI (`\x1b[` + params + final byte) and the
# short two-character escapes. Enough for neoprint's colours and styles.
_ANSI_RE = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])')


def _strip_ansi(text: str) -> str:
    """Drop terminal colour codes from an emitted line.

    The browser has no terminal to interpret them, so the panel would
    otherwise show the escape sequences as garbage. Most lines carry none, so
    the escape character is checked before the pattern runs.
    """
    return _ANSI_RE.sub('', text) if '\x1b' in text else text


class LogPanel(Component):
    """A live view of what the app prints to the terminal.

        with v3.BottomContainer():
            v3.LogPanel(source='stdout')

    Everything the app writes to `source` lands here, one row per line, the
    newest at the bottom -- which stays in view as lines arrive. The panel
    hides itself while nothing has been written, so an app that never prints
    does not pay for an empty frame.

    `print` is monkey-patched by neoprint in this package, and neoprint keeps
    its own handle on the stream it writes to, so the capture has to wrap
    that handle as well as `sys.stdout` / `sys.stderr` -- see
    `Runtime.add_log_sink`. ANSI colour codes (neoprint decorates its output)
    are dropped.

    Args:
        source: the stream to follow -- `'stdout'` (the default, where
            `print` goes) or `'stderr'`.
        height: see the size scheme; 200px by default, past which the log
            scrolls.
        width: see the size scheme; stretches by default.

    Properties:
        lines: list[str] -- the buffered lines, oldest first, capped at
            `_max_lines` (the oldest are dropped).
    """

    _default_width = 'stretch'
    _default_height = 200
    _max_lines = 500

    def __init__(
        self,
        source: str = 'stdout',
        *,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(visible=visible, **kwargs)
        if source not in ('stdout', 'stderr'):
            raise ValueError(
                "source must be 'stdout' or 'stderr', got {!r}".format(source)
            )
        self._source = source
        self.lines = Property([])
        self.visible = _visible_when_filled(self.lines, visible)
        # Ask the runtime to tee the stream into us. The active runtime is
        # the one building this tree, and the capture has to outlive the
        # build: the app prints from its own event handlers, long after
        # `main()` has returned.
        runtime = Component._active_runtime
        if runtime is not None:
            runtime.add_log_sink(source, self._append)

    def _append(self, line: str) -> None:
        """Take one line from the stream tee (the runtime's log sink)."""
        lines = list(self.lines.get() or [])
        lines.append(_strip_ansi(line))
        del lines[: -self._max_lines]
        self.lines.set(lines)


class Progress(_HasText):
    """A progress bar (mirrors Streamlit's `st.progress`).

    Args:
        value: completion percentage — an int between 0 and 100, or `None`
            for an indeterminate (animated) bar. Bindable.
        text:  an optional caption shown under the bar (bindable).
        visible: whether the bar is shown (default False, bindable), so a
            long-running step can toggle it like a spinner.
        total: how many steps the bar is driven through (see `update`).
        auto_close: hide the bar when a `with` block ends.

    Properties:
        value:   int | None — the completion percentage.
        text:    str — the caption.
        visible: bool — whether the bar is shown.

    A bar can also be *stepped*, which is how a loop-driven bar is usually
    written (this mirrors `streamlit_canary.progress`, the design the
    original applications use):

        with v3.Progress(total=len(sheets)) as prog:
            for sheet in sheets:
                prog.update(sheet.title)

    `update` advances `index` by one and moves `value` to
    `index / total * 100`. A caller is free to set `total` itself once it is
    known -- that is what `emei_kit_r6p0`'s collector does on its first step,
    so a bare `v3.Progress()` can be handed to vendor code as-is.

    Use the `with` form *inside* a handler (the block then spans the work).
    At build time the block is the build itself, so it would close the bar
    immediately -- construct the component plainly there instead.
    """

    def __init__(
        self,
        value: int | None | Property = None,
        *,
        text: str | Property = '',
        visible: bool | Property = False,
        total: int = 0,
        auto_close: bool = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, visible=visible, **kwargs)
        self.value: Property[int | None] = Property(None)
        if isinstance(value, Property):
            self.value.bind(value)
        elif value is not None:
            self.value.set(value)
        # `total` / `index` are plain attributes on purpose: `update` runs in
        # the worker thread that executes a handler, and vendor code (the
        # collector) assigns `total` directly before its first `update`.
        self.total = total
        self._auto_close = auto_close

    @property
    def total(self) -> int:
        """How many steps the bar is driven through (see `update`)."""
        return self._total

    @total.setter
    def total(self, value: int) -> None:
        """Re-initialise the step count; `index` restarts together with it.

        Vendor code assigns this on the first step of a run, so the second
        run must not carry on counting where the first one stopped -- the v1
        shim got that for free, because every run built a fresh object.
        """
        self._total = value
        self.index = 0

    def __enter__(self) -> 'Progress':
        # the base class keeps the component-tree protocol here (it pushes
        # this component onto the build stack, like `with v3.Row():`), so it
        # has to run first; on top of that, entering shows the bar.
        super().__enter__()
        self['visible'] = True
        return self

    def __exit__(self, *exc_info: tp.Any) -> bool:
        if self._auto_close:
            # let the browser paint the finished bar before it is hidden
            sleep(0.2)
            self.close()
        return super().__exit__(*exc_info)

    def update(self, item: tp.Any = None) -> None:
        """Advance one step: move the bar, and caption the step."""
        self.index += 1
        if self.total:
            # a caller may step past `total` (a retry, a count that grows),
            # so the percentage is capped rather than overshooting 100
            self['value'] = min(100, round(self.index / self.total * 100))
        if item is not None:
            self['text'] = '[{}/{}] {}'.format(self.index, self.total, item)
        elif self.total:
            self['text'] = '{:.2%}'.format(self.index / self.total)

    def close(self) -> None:
        """Hide the bar (the value stays, so it can be shown again)."""
        self['visible'] = False


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

    def __init__(
        self,
        text: str | Property = '',
        *,
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, visible=visible, **kwargs)

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


class Success(Callout):
    """A green success alert box (mirrors Streamlit's `st.success`)."""

    _kind = 'success'


_TOAST_DURATIONS: dict[str, int | None] = {
    'short': 4,
    'long': 10,
    'infinite': None,
}


def _toast_duration(value: tp.Any) -> int | None:
    """Normalise a `Toast.show(duration=...)` value (mirrors `st.toast`)."""
    if isinstance(value, str) and value in _TOAST_DURATIONS:
        return _TOAST_DURATIONS[value]
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ValueError(
        'duration must be "short", "long", "infinite" or a positive '
        'integer, got {!r}'.format(value)
    )


class Toast(Component):
    """A stack of transient notifications, pinned to the page's top-right.

    You rarely declare one yourself: `sc.toast(...)` reaches the page's single
    stack on its own, and that stack is a `Toast` the runtime creates for the
    page if the app did not. Declare it only when you want the element to sit
    at a particular spot in the tree, or to drive the stack by hand.

        toast = v3.Toast()
        ...
        toast.show('Saved!', icon=':material/check:')

    Messages accumulate (oldest first, capped at `_max_visible`). Collapsed,
    the stack piles up: the newest sits in front and on top, and every older
    toast is scaled down and tucked behind it, so only its bottom edge peeks
    out. Hovering the pile fans it out into an evenly spaced, readable list
    (a canary-only touch, modelled on the "Pines" toast; Streamlit shows a
    single toast at a time).

    Each message auto-dismisses after its `duration` (mirroring `st.toast`:
    `'short'` 4s, `'long'` 10s, `'infinite'`, or a positive second count);
    hovering the stack pauses the countdown. A toast can also be dismissed
    early with its ✕.

    Properties:
        messages: list[dict] — the visible stack, oldest first. Each entry is
            `{'id': int, 'text': str, 'icon': str, 'duration': int | None}`.
            Bindable.
    """

    _max_visible = 5

    def __init__(self, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        self.messages = Property([])

    def show(
        self, text: str, *, icon: str = '', duration: str | int = 'short'
    ) -> None:
        """Push a message (the oldest is dropped once the cap is reached)."""
        messages = list(self.messages.get() or [])
        next_id = 1 + max((m.get('id', 0) for m in messages), default=0)
        messages.append(
            {
                'id': next_id,
                'text': str(text),
                'icon': str(icon),
                'duration': _toast_duration(duration),
            }
        )
        self.messages.set(messages[-self._max_visible :])

    def clear(self) -> None:
        """Drop every message (the stack disappears)."""
        self.messages.set([])

    def _on_dismiss(self, value: tp.Any) -> None:
        """Handle a client ✕ (or an elapsed duration): drop that message."""
        target = str(value)
        messages = [
            m for m in (self.messages.get() or []) if str(m.get('id')) != target
        ]
        self.messages.set(messages)


class Warning(Callout):
    """A yellow warning alert box (mirrors Streamlit's `st.warning`)."""

    _kind = 'warning'
