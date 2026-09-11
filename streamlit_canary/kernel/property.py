"""
Property descriptor for event-driven state.

Usage:
    class State(StateV2):
        count = Property(0)

    s = State()
    s.count.get()          # 0
    s.count.set(1)         # sets value, emits s.count.on_change
    s.count.on_change      # the change Signal

A `Property` declared at class level is a descriptor. When accessed on an
instance (`s.count`) it returns a *bound* Property handle that carries
`.get()`, `.set()` and `.on_change`. The bound handle is cached per instance
so identity is stable.

This is a simplified, pure-Python reimplementation of the ideas in
`lib/qmlease/qtcore/property.py` — without Qt, without metaclass, and with the
API shape required by the event-driven demo (`state.count.get()`,
`state.count.on_change`, `state['count']`, `state['on_count']`).
"""

from __future__ import annotations

import typing as tp

from .signal import Signal


class Property:
    # -- class-level descriptor attributes --------------------------------
    # (only meaningful on the unbound descriptor stored on the class)
    default: tp.Any
    name: str | None

    # -- bound-handle attributes ------------------------------------------
    # (only meaningful on the bound handle returned by `__get__`)
    _instance: tp.Any | None
    on_change: Signal | None

    def __init__(
        self,
        default: tp.Any = None,
        *,
        _bound: bool = False,
        _instance: tp.Any = None,
        _name: str | None = None,
    ) -> None:
        self.default = default
        self.name = _name
        if _bound:
            # bound handle: per-instance, carries the value + change signal
            self._instance = _instance
            # `on_change` is emitted with this handle as the argument, so
            # handlers receive the Property that changed directly.
            self.on_change = Signal()
        else:
            # unbound descriptor: shared across all instances of the class
            self._instance = None
            self.on_change = None

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

    # -- value accessors (bound handle only) -----------------------------

    def get(self) -> tp.Any:
        assert self._instance is not None, (
            'Property.get() called on an unbound descriptor'
        )
        return self._instance._values[self.name]

    def set(self, value: tp.Any) -> None:
        assert self._instance is not None, (
            'Property.set() called on an unbound descriptor'
        )
        old = self._instance._values.get(self.name)
        if old == value:
            return
        self._instance._values[self.name] = value
        # notify subscribers, passing this handle so handlers can read the
        # new value via `cnt.get()`.
        assert self.on_change is not None
        self.on_change.emit(self)

    # -- sugar -----------------------------------------------------------

    def __repr__(self) -> str:
        if self._instance is None:
            return f'<Property(default={self.default!r})>'
        return f'<Property {self.name}={self.get()!r}>'
