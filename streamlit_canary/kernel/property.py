"""
Property descriptor for event-driven state.

Usage: See `test/on_property_test.py` and
`test/event_driven_system/demo_click_counter.py`.
"""

import typing as tp

from .signal import Signal
from .special_value import _undefined
from .special_value import _Undefined

_T = tp.TypeVar('_T')
_S = tp.TypeVar('_S')


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
        self.on_change = Signal(owner_factory=lambda: self)

    def __bool__(self) -> bool:
        return bool(self.value)

    def get(self) -> _T:
        return tp.cast(_T, self.value)

    def set(self, value: _T, notify: bool = True) -> None:
        if self.value != value:
            self.value = value
            if notify:
                self.on_change.emit()

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
        """
        if isinstance(value, Property):
            self.bind(value)
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
