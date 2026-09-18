import typing as tp

from contextlib import AbstractContextManager
from contextlib import contextmanager

if tp.TYPE_CHECKING:
    from .property import Property


class _PendingUpdates:
    queue: tp.Dict[int, tp.Tuple['Property', int]]
    forced: tp.Dict[int, tp.Tuple['Property', int]]
    stage: tp.Literal['idle', 'pending', 'resolving']
    _transaction_order: int
    _notified: tp.Set[int]

    def __init__(self) -> None:
        self.queue = {}  # {id: (source, order), ...}
        self.forced = {}  # {id: (source, order), ...}
        self.stage = 'idle'
        self._transaction_order = 0
        self._notified = set()  # what the running flush has already told

    def __call__(self) -> AbstractContextManager[None]:
        """Open a transaction: batch the `set()`s made inside the block.

        Usage:
            with sc.pending_updates():
                count.set(1)
                count.set(2)
                count.set(3)
            # the value is 3, and its listeners ran once -- on one settled
            # state -- instead of once per set.

        Every `set()` inside the block still writes its value straight away;
        only the `on_change` notification waits, and each property that
        changed is notified once, in the order it was first set. A property
        that was *forced* without changing (`set(v, notify=True)` with `v`
        already held) is a re-render request rather than a change, so it is
        delivered *after* the changes -- it reports what the whole batch
        settled on -- and it is dropped if the change pass reached that
        property already.

        Blocks nest: an inner one joins the outer transaction (the sets are
        still batched as a whole) rather than committing on its own.

        A listener that raises does not stop the batch: the error is held
        until every property has been told, and only then raised, so one
        broken listener cannot starve the rest (see `_flush`).
        """
        return self._transaction()

    @contextmanager
    def _transaction(self) -> tp.Iterator[None]:
        if self.stage == 'idle':
            self.stage = 'pending'
            errors: tp.List[Exception] = []
            try:
                yield
            except BaseException as body_error:
                # The block itself failed. Its batch still has to settle --
                # otherwise a property would sit on a notification that is
                # never delivered -- but the batch's own errors are only
                # noted here, so they cannot hide the error that got us out.
                for error in self._flush():
                    body_error.add_note(
                        'also raised while notifying the batch: {0!r}'.format(
                            error
                        )
                    )
                raise
            else:
                errors = self._flush()
            finally:
                self.stage = 'idle'
            if errors:
                if len(errors) == 1:
                    raise errors[0]
                raise ExceptionGroup(
                    'errors while notifying a batch of property changes', errors
                )
        elif self.stage == 'pending':
            yield
        else:
            raise RuntimeError(
                'cannot open a transaction while one is being resolved'
            )

    def _flush(self) -> tp.List[Exception]:
        """Deliver the batch: the changes first, then the re-render requests.

        A listener that raises must not stop the others from being told, so
        the errors are collected and handed back rather than raised here --
        the caller raises them once the batch has settled. Several listeners
        may raise, hence a list.
        """
        if not self.queue and not self.forced:
            return []
        errors: tp.List[Exception] = []
        self.stage = 'resolving'
        self._notified.clear()
        # A source is popped the moment it is notified, so while the batch
        # runs "in the queue" means "still to be notified". `Property.bind`
        # relies on that to tell "a later source will sync" apart from "a
        # later source has already had its turn".
        for source, _ in sorted(self.queue.values(), key=lambda x: x[1]):
            self.queue.pop(id(source), None)
            self._notify_collecting(errors, source, False)
        self.queue.clear()
        # Then the re-render requests: they care about the state the batch
        # settles on, not about the value they carried when they were made.
        for source, _ in sorted(self.forced.values(), key=lambda x: x[1]):
            self.forced.pop(id(source), None)
            self._notify_collecting(errors, source, True)
        self.forced.clear()
        self._notified.clear()
        return errors

    # def __contains__(self, source_id: int) -> bool:
    #     return source_id in self.queue

    def add_to_queue(self, source: 'Property', forced: bool = False) -> None:
        """Queue a notification for the flush.

        A plain change joins the change pass, in the order it was last set. A
        `forced` one (`set(v, notify=True)`) asks for a re-render, so it joins
        the second pass instead -- whether or not its value moved, because it
        has to be reported once everything has settled, and only once. A
        property in both is reported by the change pass, forced.
        """
        self._transaction_order += 1
        if forced:
            self.forced[id(source)] = (source, self._transaction_order)
            return
        self.queue[id(source)] = (source, self._transaction_order)

    def notify(self, source: 'Property', force: bool = False) -> None:
        """Deliver one notification, the way `Property._emit` would.

        During a flush a property is told at most once: a re-render request
        for a property the change pass has already reached is dropped (that
        telling carried the settled value), while a change is never dropped --
        several sources may move one property, and each move has to be
        reported -- though it does inherit the force of a request still
        waiting for it.
        """
        if self.stage != 'resolving':
            source._emit(force)
            return
        if force and id(source) in self._notified:
            return
        self._notified.add(id(source))
        source._emit(force or id(source) in self.forced)

    def _notify_collecting(
        self, errors: tp.List[Exception], source: 'Property', force: bool
    ) -> None:
        # One misbehaving listener must not stop the rest of the batch, so its
        # error is set aside for the caller to raise once everyone was told.
        try:
            self.notify(source, force)
        except Exception as error:
            errors.append(error)

    def get_order(self, source: 'Property') -> int:
        return self.queue[id(source)][1]


pending_updates = _PendingUpdates()
