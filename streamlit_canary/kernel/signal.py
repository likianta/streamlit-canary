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
    def __init__(
        self, owner_factory: tp.Callable[[], tuple] | None = None
    ) -> None:
        self._handlers: list[tp.Callable] = []
        # When non-None, `emit_now` calls `self.emit(*owner_factory())` so that
        # the registered handler receives the right argument (e.g. the Property
        # handle that owns this Signal).
        self._owner_factory = owner_factory

    # -- connection -------------------------------------------------------

    def connect(self, handler: tp.Callable) -> tp.Callable:
        self._handlers.append(handler)
        return handler

    def disconnect(self, handler: tp.Callable) -> None:
        self._handlers = [h for h in self._handlers if h is not handler]

    # -- emit ------------------------------------------------------------

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

    # -- register + emit immediately --------------------------------------

    @property
    def emit_now(self) -> tp.Callable[[_H], _H]:
        """
        Decorator: register the handler and immediately emit once.

        Usage:
            @signal.emit_now
            def handler(...): ...

        If the Signal was created with `owner_factory`, the immediate emit
        passes the owner as the argument (e.g. the Property handle for a
        Property.on_change signal).
        """

        def decorator(func: _H) -> _H:
            self.connect(func)
            if self._owner_factory is not None:
                self.emit(*self._owner_factory())
            else:
                self.emit()
            return func

        return decorator

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
