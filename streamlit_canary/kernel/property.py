"""
Property descriptor for event-driven state.

Usage: See `test/on_property_test.py` and
`test/event_driven_system/demo_click_counter.py`.
"""

import typing as tp
from functools import partial

from .pending_updates import pending_updates
from .signal import Signal
from .special_value import _undefined
from .special_value import _Undefined


class T:
    P = tp.TypeVar('P')
    Q = tp.TypeVar('Q')
    SourceOrMany = tp.Union['Property[P]', tp.Sequence['Property[P]']]
    Transform = tp.Union[tp.Callable[[P], Q], tp.Callable[[tp.Sequence[P]], Q]]


_weakrefs = []


class Property(tp.Generic[T.Q]):
    """A reactive value container.

    The type parameter describes the value the property *holds*, so a type
    checker can follow `get()` / `set()`:

        dependency: sc.Property[T.Dependency]          # convenient form
        dependency: sc.Property[T.Dependency | None]   # rigorous form, use
        #   when the property may still hold nothing (`sc._undefined`).

    Note: `value` itself is kept as `tp.Any` on purpose, because a property
    starts out as `sc._undefined` until the first `set()`. The declared `T.Q`
    is what callers see through `get()`.
    """

    default: tp.Any
    on_change: Signal
    value: tp.Any

    def __init__(self, default: T.Q | _Undefined = _undefined) -> None:
        self.default = default
        self.value = default
        self.on_change = Signal(_owner_factory=lambda: self)

    def __bool__(self) -> bool:
        return bool(self.value)

    # @property
    # def is_changed(self) -> bool:
    #     return pending_updates.is_pending and id(self) in pending_updates.queue

    def get(self) -> T.Q:
        return tp.cast(T.Q, self.value)

    def set(self, value: T.Q, notify: tp.Optional[bool] = None) -> None:
        """
        Args:
            notify:
                None: notify on demand (notify only if the value changes).
                True: force notify.
                False: do not notify.
        """
        if self.value != value:
            self.value = value
            if notify is None:
                notify = True
        if notify:
            if pending_updates.stage == 'pending':
                pending_updates.add_to_queue(self)
            else:
                self.on_change.emit()

    def bind(
        self,
        any_source: T.SourceOrMany,
        transform: tp.Optional[T.Transform] = None,
    ) -> None:
        """
        Bind this property to source property(s).
        When `source` changes, `transform(source.get())` is computed and set on
        this property. An immediate sync is also performed so that this property
        reflects the current source value right away.

        `transform` defaults to the identity function: `self` simply mirrors
        `source`. When the source still holds no initial value (`_undefined`),
        the immediate sync is skipped and we wait for the first change.
        """

        if isinstance(any_source, Property):
            source: Property = any_source

            def sync() -> None:
                if transform is None:
                    self.set(tp.cast(T.Q, source.get()))
                else:
                    self.set(transform(source.get()))

            source.on_change.connect(sync)
            # immediate sync so the bound property starts with the right value.
            if source.get() is not _undefined:
                sync()

        else:
            assert transform is not None
            sources: tp.Sequence[Property] = any_source

            class SourceAccessor:
                def __init__(
                    self,
                    sources: tp.Sequence[Property[T.P]],
                    target: Property[T.Q],
                    transform: T.Transform,
                ) -> None:
                    self._sources = tuple(sources)
                    self._source_ids = tuple(id(x) for x in sources)
                    self._target = target
                    self._transform = transform

                    for s in self._sources:
                        s.on_change.connect(partial(self._lazy_sync, s))

                def __getitem__(self, index: int) -> T.P:
                    return self._sources[index].get()  # type: ignore

                def _lazy_sync(self, source: Property) -> None:
                    if pending_updates.stage != 'resolving':
                        self.sync()
                        return
                    # Inside a batch: hold the sync until the *last declared*
                    # source that changed has had its turn, so a transaction
                    # syncs a multi-source target once rather than once per
                    # `source` itself need not be part of the batch -- a
                    # derived property moves during the flush without being
                    # queued (one of the queued ones moved it), and for the
                    # rule below only the declared order matters.
                    s_index = self._source_ids.index(id(source))
                    for fid in self._source_ids[s_index + 1 :]:
                        if fid in pending_updates.queue:
                            # A source declared *after* this one is still
                            # waiting for its turn in this batch, so it is the
                            # one that will ask to sync.
                            return
                    self.sync()

                def sync(self) -> None:
                    self._target.set(
                        self._transform(tp.cast(tp.Sequence[T.P], self))
                    )

            accessor = SourceAccessor(sources, self, transform)
            _weakrefs.append(accessor)
            if all(x.get() is not _undefined for x in sources):
                accessor.sync()

    def set_or_bind(self, value: 'T.Q | Property[T.Q]') -> None:
        """
        `set(value)`, unless `value` is itself a `Property`, in which case
        `self` is bound to it instead (mirroring it from now on).

        This lets APIs accept either a plain value or a bound value, e.g.
        `Button('Go', enabled=sc.bind(state.busy, lambda x: not x))`.

        When the source comes from `sc.bbind`, the link is two-way: later
        changes of `self` are written back into the original property.
        """
        if isinstance(value, Property):
            self.bind(value)
            target = getattr(value, '_bidi_target', None)
            if target is not None:
                self.on_change.connect(lambda: target.set(self.get()))
        else:
            self.set(value)


def bind(
    source: T.SourceOrMany, transform: tp.Optional[T.Transform] = None
) -> Property[T.Q]:
    """
    Create an anonymous `Property` bound to `source`.

    Usage:
        v3.Radio(sc.bind(state.project, lambda x: x['name']))
        v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))
    """
    prop = Property[T.Q]()
    prop.bind(source, transform)
    return prop


class _BidiProperty(Property[T.Q]):
    """The `Property` returned by `bbind`, carrying its reverse target.

    `Property.set_or_bind` looks for `_bidi_target` and wires the reverse
    direction, so a widget bound to this property writes its own changes
    back into the original one.
    """

    def __init__(self, target: Property[T.Q]) -> None:
        super().__init__()
        self._bidi_target: Property[T.Q] = target
        self.bind(target)


def bbind(source: Property[T.Q]) -> Property[T.Q]:
    """
    Create a property that binds *both ways* with `source`.

    The widget mirrors `source`, and the widget's own changes are written
    back into `source`:

        v3.NumberInput('Channel', sc.bbind(state.eye_channel))

    is equivalent to:

        with v3.NumberInput('Channel', sc.bind(state.eye_channel)) as inp:
            @inp.value.on_change.partial(sc._value)
            def _(new_channel):
                state.eye_channel.set(new_channel)
    """
    return _BidiProperty(source)
