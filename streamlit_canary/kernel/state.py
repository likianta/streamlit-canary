"""
PropertyHost — shared base for any object that declares `Property` fields.

Both `StateV2` (application state) and `Component` (UI components) use the
same property model: a class-level `Property` descriptor compiles into a bound
handle with `.get()` / `.set()` / `.on_change`, plus `__getitem__` /
`__setitem__` sugar (`obj['name']`, `obj['name'] = value`, `obj['on_name']`).

Extracting this into `PropertyHost` keeps the read/write style uniform across
state and components.
"""

from __future__ import annotations

import typing as tp

from .property import Property


class PropertyHost:
    # cached per-subclass: {name: Property descriptor}
    _properties: tp.ClassVar[dict[str, Property]] = {}

    def __init_subclass__(cls, **kwargs: tp.Any) -> None:
        # No metaclass needed: `__init_subclass__` scans the MRO for Property
        # descriptors once per subclass definition and caches them.
        super().__init_subclass__(**kwargs)
        props: dict[str, Property] = {}
        for klass in reversed(cls.__mro__):
            for name, attr in vars(klass).items():
                if isinstance(attr, Property) and not name.startswith('_'):
                    props[name] = attr
        cls._properties = props

    def __init__(self, **_kwargs: tp.Any) -> None:
        # raw value store: name -> value
        self._values: dict[str, tp.Any] = {}
        # bound handles: name -> Property (bound)
        self._handles: dict[str, Property] = {}

        for name, prop in self._properties.items():
            self._values[name] = prop.default
            self._handles[name] = Property(
                prop.default, _bound=True, _instance=self, _name=name
            )

    # -- dict-like access ------------------------------------------------

    def __getitem__(self, key: str) -> tp.Any:
        if key.startswith('on_'):
            name = key[3:]
            if name in self._handles:
                return self._handles[name].on_change
            raise KeyError(key)
        if key in self._values:
            return self._values[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: tp.Any) -> None:
        if key.startswith('on_'):
            raise TypeError(f'{key!r} is a signal and cannot be assigned to')
        if key in self._handles:
            self._handles[key].set(value)
            return
        raise KeyError(key)


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

    def __init__(self, version: int | None = None, **kwargs: tp.Any) -> None:
        super().__init__(**kwargs)
        # schema version: explicit kwarg wins, else class-level __version__
        if version is None:
            version = getattr(type(self), '__version__', 0)
        self._version = version

    # -- version ---------------------------------------------------------

    @property
    def version(self) -> int:
        return self._version

    # -- introspection ---------------------------------------------------

    def __repr__(self) -> str:
        fields = ', '.join(f'{n}={self._values[n]!r}' for n in self._properties)
        return f'<{type(self).__name__} v{self._version} {fields}>'
