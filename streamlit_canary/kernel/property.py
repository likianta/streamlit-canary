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
    Source = tp.Union['Property[P]', Signal]
    SourceOrMany = tp.Union[Source, tp.Sequence[Source]]
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
        # True while a notification that carries no change is being delivered
        # (see `set` / `_emit`), which is what a bound target re-renders on.
        self._forced_emit = False

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
                True: force notify. Use it when the value is unchanged but what
                    is *rendered* from it moved -- a dict (or other object)
                    mutated in place never compares unequal, and a widget's
                    `format` may read state that is not part of the value. A
                    bound property downstream re-renders in turn, however many
                    hops away it is (see `bind`).
                False: do not notify.
        """
        changed = self.value != value
        # An explicit `True` is not merely "notify anyway": it says a forced
        # notification -- something outside the value moved, so bound
        # properties downstream re-render too, however many hops away. That is
        # why the flag is read off the argument here and not off `changed`: a
        # hop whose own value does come out different would otherwise deliver
        # the notification as an ordinary change and drop the force.
        forced = notify is True
        if changed:
            self.value = value
            if notify is None:
                notify = True
        if notify:
            if pending_updates.stage == 'pending':
                pending_updates.add_to_queue(self, forced)
            else:
                pending_updates.notify(self, forced)

    def _emit(self, force: bool = False) -> None:
        """Deliver `on_change`. `force` marks a notification with no change.

        The flag is only readable while the emission is in flight (a bound
        target reads it to decide whether to re-render), so it is cleared as
        soon as the handlers return.
        """
        self._forced_emit = force
        try:
            self.on_change.emit()
        finally:
            self._forced_emit = False

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

        A source may also be a `Signal` -- a *trigger* rather than a value:

            sc.bind(
                (state.name_to_project, state.project_revamped),
                lambda x: list(x[0].keys()),
            )

        A Signal carries no value, so its only possible meaning is "recompute
        and re-render now": the sync it asks for is **forced**, i.e. `self`
        notifies even when the recomputed value is the same as the current one.
        That is what a renderer needs when it reads something the value does not
        hold -- a `format` that renders `x['version']`, say, where the dict was
        mutated in place and so never compares unequal. `transform` is handed
        the values of the `Property` sources only, in declared order, so a
        Signal slot does not shift the indices.
        """

        if isinstance(any_source, Property):
            source: Property = any_source

            def sync() -> None:
                if transform is None:
                    value = tp.cast(T.Q, source.get())
                else:
                    value = transform(source.get())
                # a forced notification means "re-render, nothing changed", so
                # pass it on rather than letting the value comparison eat it.
                self.set(value, notify=True if source._forced_emit else None)

            source.on_change.connect(sync)
            # immediate sync so the bound property starts with the right value.
            if source.get() is not _undefined:
                sync()

        else:
            assert transform is not None
            if isinstance(any_source, Signal):
                raise TypeError(
                    'a Signal source must be declared beside a Property, e.g. '
                    'sc.bind((state.items, state.reloaded), lambda x: ...)'
                )
            declared = tuple(any_source)
            # see the docstring: Signals trigger, they do not carry a value.
            triggers = declared
            values = tuple(x for x in declared if isinstance(x, Property))
            if not values:
                raise TypeError(
                    'a bind needs at least one Property source to take its '
                    'value from'
                )

            class SourceAccessor:
                def __init__(
                    self,
                    triggers: tp.Sequence[tp.Any],
                    values: tp.Sequence[Property[T.P]],
                    target: Property[T.Q],
                    transform: T.Transform,
                ) -> None:
                    self._triggers = tuple(triggers)
                    self._trigger_ids = tuple(id(x) for x in triggers)
                    self._values = tuple(values)
                    self._target = target
                    self._transform = transform
                    self._forced = False

                    for trigger in self._triggers:
                        # a Property is watched through its `on_change`; a
                        # Signal is already the thing to watch.
                        watched: Signal = (
                            trigger.on_change
                            if isinstance(trigger, Property)
                            else trigger
                        )
                        watched.connect(partial(self._lazy_sync, trigger))

                def __getitem__(self, index: int) -> T.P:
                    return self._values[index].get()  # type: ignore

                def _lazy_sync(
                    self, trigger: tp.Any, *_payload: tp.Any
                ) -> None:
                    # A Signal carries no value, so every emission of one is a
                    # forced sync; so is a forced *Property* notification.
                    # `_payload` swallows whatever a Signal declares -- a
                    # trigger is interested in the fact, not in the argument.
                    # Either way the flag is taken now -- before the batch check
                    # below -- so the force still lands when this sync is held
                    # back for a later-declared trigger to have its turn.
                    if isinstance(trigger, Signal):
                        self._forced = True
                    else:
                        self._forced = self._forced or trigger._forced_emit
                    if pending_updates.stage == 'resolving':
                        # inside a batch: hold the sync until the
                        # *last declared* source that changed has had its turn,
                        # so a transaction syncs a multi-source target once
                        # rather than once per `source` itself need not be part
                        # of the batch -- a derived property moves during the
                        # flush without being queued (one of the queued ones
                        # moved it), and for the rule below only the declared
                        # order matters.
                        src_index = self._trigger_ids.index(id(trigger))
                        for following_id in self._trigger_ids[src_index + 1 :]:
                            if following_id in pending_updates.queue:
                                # a source declared *after* this one is still
                                # waiting for its turn in this batch, so it is
                                # the one that will ask to sync.
                                return
                    self.sync()

                def sync(self) -> None:
                    forced, self._forced = self._forced, False
                    self._target.set(
                        self._transform(tp.cast(tp.Sequence[T.P], self)),
                        notify=True if forced else None,
                    )

            accessor = SourceAccessor(triggers, values, self, transform)
            _weakrefs.append(accessor)
            if all(x.get() is not _undefined for x in values):
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

    A `Signal` may sit beside a `Property` as a trigger -- it makes the derived
    property notify again even when its value comes out the same, which is what
    a widget needs when its `format` renders more than the value holds:

        v3.Radio(
            options=sc.bind(
                (state.projects, state.projects_reloaded),
                lambda x: list(x[0]),
            )
        )
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
