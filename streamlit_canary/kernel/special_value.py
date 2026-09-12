"""
Special marker objects that extend `Signal.partial(...)`.

A `Signal` does **not** pass its owner to handlers by default. To opt in to
receiving the owner, or the owner's current value, bind one of these markers
when registering a handler:

    # plain handler: receives only what `emit()` passes (usually nothing)
    @prop.on_change
    def on_change():
        ...

    # `sc._self` → the owner (e.g. the Property handle that changed)
    @prop.on_change.partial(sc._self)
    def on_change(prop):
        assert isinstance(prop, sc.Property)

    # `sc._value` → the owner's current value at emit time
    @prop.on_change.partial(sc._value)
    def on_change(value):
        ...

Markers can be mixed with ordinary bound arguments, in any position:

    @sig.partial('prefix', sc._value)
    def handler(prefix, value):
        ...
"""

from __future__ import annotations

import typing as tp


class _Self:
    """Marker: resolve to the Signal's owner at emit time."""

    __slots__ = ()

    def __repr__(self) -> str:
        return 'sc._self'


class _Value:
    """Marker: resolve to the owner's current value at emit time."""

    __slots__ = ()

    def __repr__(self) -> str:
        return 'sc._value'


_self: tp.Final[_Self] = _Self()
_value: tp.Final[_Value] = _Value()
