"""
Pure-Python signal implementation (no Qt dependency).

A Signal is a publish/subscribe primitive. Its parameters are declared up
front, as the types of whatever `emit()` will carry:

    sig = Signal(int)
    sig.connect(handler)
    sig.emit(42)            # calls handler(42)

`*args` declares positional-only parameters, `**kwargs` named ones. A named
parameter is also accepted in position order, so a signal can be emitted in
whichever form reads better:

    state_changed = Signal(bool, reason=str)
    state_changed.emit(True, reason='User clicks connect button.')
    state_changed.emit(True, 'User clicks connect button.')   # same thing

Declaring no parameter leaves the signal free-form: `emit()` hands whatever it
is given over untouched. That is what the payload-less signals the framework
defines itself (`Property.on_change`, `Button.on_click`, ...) rely on, and it
is also the fastest path.

It can also be used as a decorator to register a handler:
    @sig
    def handler(x): ...

A Signal does **not** pass its owner to handlers by default. Use
`.partial(...)` to bind extra arguments in front of whatever `emit()`
provides; the `_self` / `_value` markers resolve to the owner at emit time:

    @sig.partial('prefix')
    def handler(prefix, x): ...      # static args are bound in front

    @sig.partial(_self)              # the owner (e.g. a Property handle)
    def handler(prop): ...

    @sig.partial(_value)             # the owner's current value
    def handler(value): ...
"""

import inspect
import typing as tp

from .special_value import _self
from .special_value import _value

_H = tp.TypeVar('_H', bound=tp.Callable)


def _type_name(annotation: tp.Any) -> str:
    """Readable name of a declared parameter type, for `repr()`."""
    return getattr(annotation, '__name__', None) or repr(annotation)


def _build_signature(
    args: tuple[tp.Any, ...], kwargs: dict[str, tp.Any]
) -> inspect.Signature | None:
    """Turn declared parameter types into something `emit()` can bind.

    Positional types become positional-only parameters (they have no name, so
    there is nothing to pass them by), while the named ones stay
    positional-or-keyword -- which is exactly what makes `emit(v, 'why')` and
    `emit(v, why='...')` the same call. A signal that declares nothing returns
    None, and is then left free-form.
    """
    if not args and not kwargs:
        return None
    parameters = [
        inspect.Parameter(
            'arg{}'.format(index),
            inspect.Parameter.POSITIONAL_ONLY,
            annotation=annotation,
        )
        for index, annotation in enumerate(args)
    ]
    parameters += [
        inspect.Parameter(
            name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation
        )
        for name, annotation in kwargs.items()
    ]
    return inspect.Signature(parameters)


class _Partial:
    """
    Decorator returned by `Signal.partial(...)`.

    Supports two forms:

        @sig.partial(_self)              # register the handler
        def handler(prop): ...

        @sig.partial(_self).emit_now     # register + emit immediately
        def handler(prop): ...

    Any `_self` / `_value` marker in the bound arguments is resolved to the
    Signal's owner (and its current value) at emit time.
    """

    def __init__(
        self,
        signal: 'Signal',
        args: tuple[tp.Any, ...],
        kwargs: dict[str, tp.Any],
    ) -> None:
        self._signal = signal
        self._args = args
        self._kwargs = kwargs

    def _wrap(self, func: tp.Callable) -> tp.Callable:
        signal = self._signal
        args = self._args
        kwargs = self._kwargs

        def wrapper(*emit_args: tp.Any, **emit_kwargs: tp.Any) -> tp.Any:
            bound_args = tuple(signal._resolve(a) for a in args)
            bound_kwargs = {k: signal._resolve(v) for k, v in kwargs.items()}
            return func(
                *bound_args, *emit_args, **{**bound_kwargs, **emit_kwargs}
            )

        return wrapper

    def __call__(self, func: _H) -> _H:
        self._signal.connect(self._wrap(func))
        return func

    @property
    def emit_now(self) -> tp.Callable[[_H], _H]:
        def decorator(func: _H) -> _H:
            self._signal.connect(self._wrap(func))
            self._signal.emit()
            return func

        return decorator


class Signal:
    def __init__(
        self,
        *args: type,
        _owner_factory: tp.Callable[[], tp.Any] | None = None,
        **kwargs: type,
    ) -> None:
        self._args = args
        self._kwargs = kwargs
        self._signature = _build_signature(args, kwargs)
        self._handlers: list[tp.Callable] = []
        # Optional owner provider. When set, `_resolve(_self)` returns the
        # owner and `_resolve(_value)` returns `owner.get()`. Only used by
        # `.partial(...)`; `emit()` never passes the owner automatically.
        self._owner_factory = _owner_factory

    def __repr__(self) -> str:
        declared = [_type_name(annotation) for annotation in self._args]
        declared += [
            '{}: {}'.format(name, _type_name(annotation))
            for name, annotation in self._kwargs.items()
        ]
        return 'sc.Signal({})'.format(', '.join(declared))

    # -- connection -------------------------------------------------------

    def connect(self, handler: tp.Callable) -> tp.Callable:
        self._handlers.append(handler)
        return handler

    def disconnect(self, handler: tp.Callable) -> None:
        self._handlers = [h for h in self._handlers if h is not handler]

    # -- emit ------------------------------------------------------------

    def emit(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        if self._signature is None:
            # No declared parameter: free-form, hand the payload over as given.
            payload_args, payload_kwargs = args, kwargs
        else:
            try:
                bound = self._signature.bind(*args, **kwargs)
            except TypeError as exc:
                raise TypeError('{!r}: {}'.format(self, exc)) from None
            # Binding up front is what lets a named parameter be passed by name
            # or in position order; handlers always receive one positional
            # payload, in declaration order.
            payload_args, payload_kwargs = bound.args, bound.kwargs
        # iterate over a copy so handlers that disconnect themselves during
        # emission do not break the loop.
        for handler in list(self._handlers):
            handler(*payload_args, **payload_kwargs)

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
            def handler(): ...

        The immediate emit passes no arguments (the owner is not injected).
        To receive the owner or its value, use `.partial(...).emit_now`.
        Only a signal that declares no parameter can be emitted this way --
        for the others there would be nothing to pass.
        """

        def decorator(func: _H) -> _H:
            self.connect(func)
            self.emit()
            return func

        return decorator

    # -- partial binding --------------------------------------------------

    def partial(self, *args: tp.Any, **kwargs: tp.Any) -> _Partial:
        """
        Return a decorator that binds `args`/`kwargs` in front of whatever the
        signal emits. Unlike `functools.partial`, the bound function is also
        connected to this signal automatically.

        The `_self` / `_value` markers are resolved at emit time to the
        owner (from `owner_factory`) and the owner's current `.get()` value.
        """
        return _Partial(self, args, kwargs)

    # -- special-value resolution -----------------------------------------

    def _owner(self) -> tp.Any:
        if self._owner_factory is None:
            return None
        return self._owner_factory()

    def _resolve(self, token: tp.Any) -> tp.Any:
        if token is _self:
            return self._owner()
        if token is _value:
            owner = self._owner()
            getter = getattr(owner, 'get', None)
            return getter() if getter is not None else None
        return token
