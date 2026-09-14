"""
Property descriptor for event-driven state.

Usage: See `test/on_property_test.py` and
`test/event_driven_structure/demo_click_counter.py`.
"""

import typing as tp

from .signal import Signal
from .special_value import _undefined


class Property:
    default: tp.Any
    on_change: Signal
    value: tp.Any

    def __init__(self, default: tp.Any = _undefined) -> None:
        self.default = default
        self.value = default
        self.on_change = Signal(owner_factory=lambda: self)

    def __bool__(self) -> bool:
        return bool(self.value)

    def get(self) -> tp.Any:
        return self.value

    def set(self, value: tp.Any, notify: bool = True) -> None:
        if self.value != value:
            self.value = value
            if notify:
                self.on_change.emit()

    def bind(
        self,
        source: 'Property',
        transform: tp.Optional[tp.Callable[[tp.Any], tp.Any]] = None,
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
            value = source.get()
            self.set(value if transform is None else transform(value))

        source.on_change.connect(sync)
        # immediate sync so the bound property starts with the right value.
        if source.get() is not _undefined:
            sync()

    def set_or_bind(self, value: tp.Any) -> None:
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
    source: Property,
    transform: tp.Optional[tp.Callable[[tp.Any], tp.Any]] = None,
) -> Property:
    """
    Create an anonymous `Property` bound to `source`.

    Usage:
        v3.Radio(sc.bind(state.project, lambda x: x['name']))
        v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))
    """
    prop = Property()
    prop.bind(source, transform)
    return prop
