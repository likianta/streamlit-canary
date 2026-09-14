"""
See `test/on_property_test.py`.
"""

import typing as tp


class _Self:
    """Marker: resolve to the Signal's owner at emit time."""

    __slots__ = ()

    def __repr__(self) -> str:
        return 'sc._self'


class _Undefined:
    pass


class _Value:
    """Marker: resolve to the owner's current value at emit time."""

    __slots__ = ()

    def __repr__(self) -> str:
        return 'sc._value'


_self: tp.Final[_Self] = _Self()
_undefined: tp.Final[_Undefined] = _Undefined()
_value: tp.Final[_Value] = _Value()
