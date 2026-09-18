import typing as tp

from contextlib import AbstractContextManager
from contextlib import contextmanager

if tp.TYPE_CHECKING:
    from .property import Property


class _PendingUpdates:
    queue: tp.Dict[int, tp.Tuple['Property', int]]
    stage: tp.Literal['idle', 'pending', 'resolving']
    _transaction_order: int

    def __init__(self) -> None:
        self.queue = {}  # {id: (source, order), ...}
        self.stage = 'idle'
        self._transaction_order = 0

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
        changed is notified once, in the order it was first set.

        Blocks nest: an inner one joins the outer transaction (the sets are
        still batched as a whole) rather than committing on its own.
        """
        return self._transaction()

    @contextmanager
    def _transaction(self) -> tp.Iterator[None]:
        if self.stage == 'idle':
            self.stage = 'pending'
            try:
                yield
            finally:
                if self.queue:
                    self.stage = 'resolving'
                    # A source is popped the moment it is notified, so while
                    # the batch runs "in the queue" means "still to be
                    # notified". `Property.bind` relies on that to tell
                    # "a later source will sync" apart from "a later source
                    # has already had its turn".
                    for source, _ in sorted(
                        self.queue.values(), key=lambda x: x[1]
                    ):
                        self.queue.pop(id(source), None)
                        # One misbehaving listener must not stop the rest of
                        # the batch from being notified.
                        try:
                            source.on_change.emit()
                        except Exception:
                            continue
                    self.queue.clear()
                self.stage = 'idle'
        elif self.stage == 'pending':
            yield
        else:
            raise RuntimeError(
                'cannot open a transaction while one is being resolved'
            )

    # def __contains__(self, source_id: int) -> bool:
    #     return source_id in self.queue

    def add_to_queue(self, source: 'Property') -> None:
        self._transaction_order += 1
        self.queue[id(source)] = (source, self._transaction_order)

    def get_order(self, source: 'Property') -> int:
        return self.queue[id(source)][1]


pending_updates = _PendingUpdates()
