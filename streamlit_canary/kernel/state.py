"""
PropertyHost — shared base for any object that declares `Property` fields.

Both `StateV2` (application state) and `Component` (UI components) use the
same property model: a `Property` lives on the instance and exposes
`.get()` / `.set()` / `.on_change`, plus `__getitem__` / `__setitem__` sugar
(`obj['name']` reads the value, `obj['name'] = value` writes it,
`obj['on_name']` returns the change Signal).

Extracting this into `PropertyHost` keeps the read/write style uniform across
state and components.

A field can also be declared by annotation, which makes the host build the
handle for you -- one per instance, just like a hand-written one:

    class _State(sc.StateV2):
        name: sc.Property[str]
        age: sc.Property[int] = 0

    state = _State()
    state.name.get()         # sc._undefined, until something sets it
    state.age.get()          # 0

Only `Property` / `Property[T]` annotations are picked up (a plain
`current_scope: str` is left to the `__init__` body), a class-body value of
the same name becomes the default, and a class-level `Property` contributes
its default. Subclasses have to call `super().__init__()` for this to run.
"""

import functools
import typing as tp

from .property import Property
from .special_value import _undefined


def _is_property_annotation(annotation: tp.Any) -> bool:
    """Whether an annotation declares a `Property` field.

    `Property` and `Property[T]` both count. The annotation is expected to be
    the object itself: a string one (a module that opted into
    `from __future__ import annotations`, which this project does not use) is
    deliberately not recognised.
    """
    return annotation is Property or tp.get_origin(annotation) is Property


@functools.lru_cache(maxsize=None)
def _annotated_fields(cls: type) -> tuple[tuple[str, tp.Any], ...]:
    """`(name, default)` for every field `cls` annotates as a `Property`.

    Annotations are collected per class along the MRO, so a subclass may add
    or re-declare a field. Memoised, because every instance asks the same
    question and components are created by the hundred.
    """
    names: list[str] = []
    for base in reversed(cls.__mro__):
        # `__annotations__` is a descriptor that computes them on access (PEP
        # 649), so it is read with `getattr`: a class `__dict__` only holds
        # `__annotate_func__`, and a class without annotations answers `{}`.
        annotations = getattr(base, '__annotations__', None) or {}
        for name, annotation in annotations.items():
            if name not in names and _is_property_annotation(annotation):
                names.append(name)
    fields = []
    for name in names:
        declared = getattr(cls, name, _undefined)
        if isinstance(declared, Property):
            # A class-level handle is shared between instances, so only its
            # default is carried over -- the instance needs a handle of its own.
            declared = declared.default
        fields.append((name, declared))
    return tuple(fields)


class PropertyHost:
    def __init__(self) -> None:
        """Build a `Property` for every field declared by annotation.

        A handle the instance already carries is left alone, so an `__init__`
        body that assigns before calling `super().__init__()` keeps its own.
        """
        for name, default in _annotated_fields(type(self)):
            if name not in vars(self):
                setattr(self, name, Property(default))

    def __getitem__(self, key: str) -> tp.Any:
        if key.startswith('on_'):
            name = key[3:]
            prop = getattr(self, name)
            assert isinstance(prop, Property)
            return prop.on_change
        else:
            prop = getattr(self, key)
            assert isinstance(prop, Property)
            return prop.get()

    def __setitem__(self, key: str, value: tp.Any) -> None:
        assert not key.startswith('on_')
        prop = getattr(self, key)
        assert isinstance(prop, Property)
        prop.set(value)

    def _iter_properties(self) -> tp.Iterator[tuple[str, Property]]:
        """Yield `(name, Property)` for every Property field on this host."""
        for name, value in list(vars(self).items()):
            if isinstance(value, Property):
                yield name, value


class StateV2(PropertyHost):
    """
    Base class for event-driven state.

    Subclasses declare `Property` fields, typically inside `__init__`:

        class _State(sc.StateV2):
            __version__ = 0

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.count = sc.Property(0)

        state = _State()
        state.count.get()        # 0
        state.count.set(1)       # emits state.count.on_change
        state['count']           # 1          (alias of .get())
        state['count'] = 2       #            (alias of .set())
        state['on_count']        # the change Signal

    A field may also be declared by annotation, in which case
    `super().__init__()` already builds the handle (see the module docstring):

        class _State(sc.StateV2):
            name: sc.Property[str]
            age: sc.Property[int] = 0

    A `Property` may also be declared at class level; that is only safe when
    the state class has a single instance, because class-level properties are
    shared between instances.

    `__version__` (or `version=N` passed to `__init__`) tracks schema version.
    """

    def __init__(self, version: tp.Optional[int] = None) -> None:
        super().__init__()
        # schema version: explicit kwarg wins, else class-level __version__
        if version is None:
            version = getattr(type(self), '__version__', 0)
        self._version = version  # TODO

    def __repr__(self) -> str:
        fields = ', '.join(
            f'{name}={prop.get()!r}' for name, prop in self._iter_properties()
        )
        return f'<{type(self).__name__} v{self._version} {fields}>'

    @property
    def version(self) -> int:
        return self._version
