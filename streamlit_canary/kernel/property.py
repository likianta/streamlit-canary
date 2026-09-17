"""
Property descriptor for event-driven state.

Usage: See `test/on_property_test.py` and
`test/event_driven_system/demo_click_counter.py`.
"""

import contextlib
import contextvars
import typing as tp

from .signal import Signal
from .special_value import _undefined
from .special_value import _Undefined

_T = tp.TypeVar('_T')
_S = tp.TypeVar('_S')

# Properties whose notification was deferred by an `updating()` block. A
# ContextVar (rather than a thread-local) scopes the transaction to the
# logical context, which also covers handlers run via `asyncio.to_thread`.
_pending_updates: contextvars.ContextVar = contextvars.ContextVar(
    'sc_pending_updates', default=None
)


class Property(tp.Generic[_T]):
    """A reactive value container.

    The type parameter describes the value the property *holds*, so a type
    checker can follow `get()` / `set()`:

        dependency: sc.Property[T.Dependency]          # convenient form
        dependency: sc.Property[T.Dependency | None]   # rigorous form, use
        #   when the property may still hold nothing (`sc._undefined`).

    Note: `value` itself is kept as `tp.Any` on purpose, because a property
    starts out as `sc._undefined` until the first `set()`. The declared `_T`
    is what callers see through `get()`.
    """

    default: tp.Any
    on_change: Signal
    value: tp.Any

    def __init__(self, default: _T | _Undefined = _undefined) -> None:
        self.default = default
        self.value = default
        self.on_change = Signal(_owner_factory=lambda: self)

    def __bool__(self) -> bool:
        return bool(self.value)

    def get(self) -> _T:
        return tp.cast(_T, self.value)

    def set(self, value: _T, notify: tp.Optional[bool] = None) -> None:
        """
        Args:
            notify:
                None: notify on demand (notify only if the value changes).
                True: force notify.
                False: do not notify.
        """
        if self.value != value:
            self.value = value
            if notify is None:
                notify = True
        if notify:
            pending = _pending_updates.get()
            if pending is None:
                self.on_change.emit()
            else:
                # Deferred: `updating()` emits once per property when the
                # block ends, with the final value.
                pending.add(self)

    def bind(
        self,
        source: 'Property[_S]',
        transform: tp.Callable[[_S], _T] | None = None,
    ) -> None:
        """
        Bind this property to a source property.
        When `source` changes, `transform(source.get())` is computed and set on
        this property. An immediate sync is also performed so that this property
        reflects the current source value right away.

        `transform` defaults to the identity function: `self` simply mirrors
        `source`. When the source still holds no initial value (`_undefined`),
        the immediate sync is skipped and we wait for the first change.
        """

        def sync() -> None:
            if transform is None:
                self.set(tp.cast(_T, source.get()))
            else:
                self.set(transform(source.get()))

        source.on_change.connect(sync)
        # immediate sync so the bound property starts with the right value.
        if source.get() is not _undefined:
            sync()

    def set_or_bind(self, value: '_T | Property[_T]') -> None:
        """
        `set(value)`, unless `value` is itself a `Property`, in which case
        `self` is bound to it instead (mirroring it from now on).

        This lets APIs accept either a plain value or a bound value, e.g.
        `Button('Go', enabled=sc.bind(state.busy, lambda x: not x))`.

        When the source comes from `sc.bbind`, the link is two-way: later
        changes of `self` are written back into the original property.
        """
        if isinstance(value, Property):
            self.bind(value)
            target = getattr(value, '_bidi_target', None)
            if target is not None:
                self.on_change.connect(lambda: target.set(self.get()))
        else:
            self.set(value)


def bind(
    source: Property[_S], transform: tp.Callable[[_S], _T] | None = None
) -> Property[_T]:
    """
    Create an anonymous `Property` bound to `source`.

    Usage:
        v3.Radio(sc.bind(state.project, lambda x: x['name']))
        v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))
    """
    prop = Property[_T]()
    prop.bind(source, transform)
    return prop


class _BidiProperty(Property[_T]):
    """The `Property` returned by `bbind`, carrying its reverse target.

    `Property.set_or_bind` looks for `_bidi_target` and wires the reverse
    direction, so a widget bound to this property writes its own changes
    back into the original one.
    """

    def __init__(self, target: Property[_T]) -> None:
        super().__init__()
        self._bidi_target: Property[_T] = target
        self.bind(target)


def bbind(source: Property[_T]) -> Property[_T]:
    """
    Create a property that binds *both ways* with `source`.

    The widget mirrors `source`, and the widget's own changes are written
    back into `source`:

        v3.NumberInput('Channel', sc.bbind(state.eye_channel))

    is equivalent to:

        with v3.NumberInput('Channel', sc.bind(state.eye_channel)) as inp:
            @inp.value.on_change.partial(sc._value)
            def _(new_channel):
                state.eye_channel.set(new_channel)
    """
    return _BidiProperty(source)


@contextlib.contextmanager
def updating() -> tp.Iterator[None]:
    """Batch property notifications until the block exits.

    Inside the block, `Property.set()` updates the value but does *not*
    emit `on_change`. Every property that changed then emits exactly once,
    carrying its final value, so a burst of intermediate updates collapses
    into a single notification per property:

        with sc.updating():
            state.count.set(1)
            state.count.set(2)
            state.count.set(3)
        # `on_change` fires once, with count == 3

    This matters for the delta protocol: each notification becomes a
    websocket frame pushed to the browser, so squashing them also trims
    traffic. `Property.set(notify=False)` still never notifies.

    Nested blocks join the outermost one, and an exception raised in the
    block still flushes whatever had already changed.
    """
    txn = _pending_updates.get()
    if txn is not None:
        yield  # join the enclosing transaction
        return
    txn = set()
    token = _pending_updates.set(txn)
    try:
        yield
    finally:
        # Reset first, so that a handler which `set()`s other properties
        # during the flush notifies normally instead of being deferred.
        _pending_updates.reset(token)
        for prop in list(txn):
            prop.on_change.emit()
