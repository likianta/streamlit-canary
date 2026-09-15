"""
PropertyHost — shared base for any object that declares `Property` fields.

Both `StateV2` (application state) and `Component` (UI components) use the
same property model: a `Property` lives on the instance and exposes
`.get()` / `.set()` / `.on_change`, plus `__getitem__` / `__setitem__` sugar
(`obj['name']` reads the value, `obj['name'] = value` writes it,
`obj['on_name']` returns the change Signal).

Extracting this into `PropertyHost` keeps the read/write style uniform across
state and components.
"""

import typing as tp

from .property import Property


class PropertyHost:
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

    A `Property` may also be declared at class level; that is only safe when
    the state class has a single instance, because class-level properties are
    shared between instances.

    `__version__` (or `version=N` passed to `__init__`) tracks schema version.
    """

    def __init__(self, version: tp.Optional[int] = None) -> None:
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
