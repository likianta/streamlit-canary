"""
PropertyHost — shared base for any object that declares `Property` fields.

Both `StateV2` (application state) and `Component` (UI components) use the
same property model: a class-level `Property` descriptor compiles into a bound
handle with `.get()` / `.set()` / `.on_change`, plus `__getitem__` /
`__setitem__` sugar (`obj['name']`, `obj['name'] = value`, `obj['on_name']`).

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
            return getattr(self, key)

    def __setitem__(self, key: str, value: tp.Any) -> None:
        assert not key.startswith('on_')
        prop = getattr(self, key)
        assert isinstance(prop, Property)
        prop.set(value)


class StateV2(PropertyHost):
    """
    Base class for event-driven state.

    Subclasses declare `Property` fields at class level:

        class _State(sc.StateV2):
            count = sc.Property(0)
            __version__ = 0

        state = _State()
        state.count.get()        # 0
        state.count.set(1)       # emits state.count.on_change
        state['count']           # 1          (alias of .get())
        state['count'] = 2       #            (alias of .set())
        state['on_count']        # the change Signal

    `__version__` (or `version=N` passed to `__init__`) tracks schema version.
    The actual "rebuild state when version changes" persistence logic is added
    later when the runtime/persistence layer lands; for now the version is
    stored on the instance and exposed via `state.version`.
    """

    def __init__(
        self, version: tp.Optional[int] = None, **kwargs: tp.Any
    ) -> None:
        super().__init__(**kwargs)
        # schema version: explicit kwarg wins, else class-level __version__
        if version is None:
            version = getattr(type(self), '__version__', 0)
        self._version = version  # TODO

    def __repr__(self) -> str:
        fields = ', '.join(f'{n}={self._values[n]!r}' for n in self._properties)
        return f'<{type(self).__name__} v{self._version} {fields}>'

    @property
    def version(self) -> int:
        return self._version
