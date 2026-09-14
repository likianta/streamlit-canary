"""
Property descriptor for event-driven state.

Usage (standalone reactive value):
    count = sc.Property(0)
    count.get()            # 0
    count.set(1)           # sets value, emits count.on_change
    count.on_change        # the change Signal

Usage (declared on a `StateV2` / `Component`):
    class State(StateV2):
        count = Property(0)

    s = State()
    s.count.get()          # 0
    s.count.set(1)         # sets value, emits s.count.on_change

A `Property` declared at class level is a descriptor. When accessed on an
instance (`s.count`) it returns a *bound* Property handle that carries
`.get()`, `.set()` and `.on_change`. The bound handle is cached per instance
so identity is stable.

A `Property` created outside a class body (e.g. `count = sc.Property(0)`)
is self-contained: it owns its value directly.

This is a simplified, pure-Python reimplementation of the ideas in
`lib/qmlease/qtcore/property.py` — without Qt, without metaclass, and with the
API shape required by the event-driven demo (`state.count.get()`,
`state.count.on_change`, `state['count']`, `state['on_count']`).
"""

from __future__ import annotations

import typing as tp

from .signal import Signal
from .special_value import _undefined


class Property:
    # -- class-level descriptor attributes --------------------------------
    # (only meaningful on the unbound descriptor stored on the class)
    default: tp.Any
    name: str | None

    # -- bound-handle attributes ------------------------------------------
    # (only meaningful on the bound handle returned by `__get__`)
    _instance: tp.Any | None
    on_change: Signal

    def __init__(
        self,
        default: tp.Any = _undefined,
        *,
        _bound: bool = False,
        _instance: tp.Any = None,
        _name: str | None = None,
    ) -> None:
        self.default = default
        self.name = _name
        self._bound = _bound
        self._instance = _instance
        # Self-contained value store, used when this Property is not bound to
        # a `PropertyHost` instance (e.g. `count = sc.Property(0)` at module
        # level). Bound handles read/write the host's `_values` instead.
        self._value = default
        # `on_change` is always available. It does NOT pass the owner to
        # handlers by default; opt in with `.partial(sc._self / sc._value)`.
        # The owner_factory lets those markers resolve back to this handle.
        self.on_change = Signal(owner_factory=lambda: self)

    # -- descriptor protocol ---------------------------------------------

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(
        self, instance: tp.Any, owner: type | None = None
    ) -> 'Property':
        if instance is None:
            # class-level access: return the descriptor itself
            return self
        # instance-level access: return the cached bound handle
        return instance._handles[self.name]

    # -- value accessors --------------------------------------------------

    def get(self) -> tp.Any:
        if self._instance is None:
            return self._value
        return self._instance._values[self.name]

    def set(self, value: tp.Any, notify: bool = True) -> None:
        if self._instance is None:
            if self._value == value:
                return
            self._value = value
        else:
            old = self._instance._values.get(self.name)
            if old == value:
                return
            self._instance._values[self.name] = value
        if notify:
            self.on_change.emit()

    # -- sugar -----------------------------------------------------------

    def bind(
        self, source: 'Property', transform: tp.Callable[[tp.Any], tp.Any]
    ) -> None:
        """
        Bind this property to a source property.

        When `source` changes, `transform(source.get())` is computed and set
        on this property. An immediate sync is also performed so that this
        property reflects the current source value right away.

        Usage:
            sel.options.bind(state.projects, lambda this: list(this.keys()))
        """

        def sync() -> None:
            new_value = transform(source.get())
            self.set(new_value)

        source.on_change.connect(sync)
        # immediate sync so the bound property starts with the right value.
        if source.get() is not _undefined:
            sync()

    def __repr__(self) -> str:
        if self.name is None:
            return f'<Property(v={self._value!r})>'
        return f'<Property {self.name}={self.get()!r}>'
