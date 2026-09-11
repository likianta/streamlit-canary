"""
Pure-Python signal implementation (no Qt dependency).

A Signal is a publish/subscribe primitive:
    sig = Signal()
    sig.connect(handler)
    sig.emit(42)            # calls handler(42)

It can also be used as a decorator to register a handler:
    @sig
    def handler(x): ...

For binding extra static arguments, use `.partial(...)`:
    @sig.partial('prefix')
    def handler(prefix, x): ...
"""

from __future__ import annotations

import typing as tp

_H = tp.TypeVar('_H', bound=tp.Callable)


class Signal:
    def __init__(self) -> None:
        self._handlers: list[tp.Callable] = []

    # -- connection -------------------------------------------------------

    def connect(self, handler: tp.Callable) -> tp.Callable:
        self._handlers.append(handler)
        return handler

    def disconnect(self, handler: tp.Callable) -> None:
        self._handlers = [h for h in self._handlers if h is not handler]

    # -- emit -------------------------------------------------------------

    def emit(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        # iterate over a copy so handlers that disconnect themselves during
        # emission do not break the loop.
        for handler in list(self._handlers):
            handler(*args, **kwargs)

    # -- decorator support ------------------------------------------------

    def __call__(self, func: _H) -> _H:
        """Allow `@signal` to register a handler."""
        self.connect(func)
        return func

    # -- partial binding --------------------------------------------------

    def partial(self, *args: tp.Any, **kwargs: tp.Any) -> tp.Callable[[_H], _H]:
        """
        Return a decorator that binds `args`/`kwargs` in front of whatever the
        signal emits. Unlike `functools.partial`, the bound function is also
        connected to this signal automatically.
        """

        def decorator(func: _H) -> _H:
            def wrapper(*emit_args: tp.Any, **emit_kwargs: tp.Any) -> tp.Any:
                return func(*args, *emit_args, **{**kwargs, **emit_kwargs})

            self.connect(wrapper)
            return func

        return decorator
