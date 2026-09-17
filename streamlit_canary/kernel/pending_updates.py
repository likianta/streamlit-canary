import typing as tp

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

    def __call__(self):
        """
        Usage:
            assert isinstance(sc.pending_updates, _PendingUpdates)
            with sc.pending_updates():  # `with` statement is allowed.
                count.set(1)
                count.set(2)
                count.set(3)
            # finally, only 3 is notified.
        """

        @contextmanager
        def _pending():
            if self.stage == 'idle':
                self.stage = 'pending'
                try:
                    yield
                finally:
                    if self.queue:
                        self.stage = 'resolving'
                        for source, _ in sorted(
                            self.queue.values(), key=lambda x: x[1]
                        ):
                            try:
                                source.on_change.emit()
                            except Exception:
                                continue
                        self.queue.clear()
                    self.stage = 'idle'
            elif self.stage == 'pending':
                yield
            else:
                raise Exception('Invalid state')

        return _pending

    # def __contains__(self, source_id: int) -> bool:
    #     return source_id in self.queue

    def add_to_queue(self, source: 'Property') -> None:
        self._transaction_order += 1
        self.queue[id(source)] = (source, self._transaction_order)

    def get_order(self, source: 'Property') -> int:
        return self.queue[id(source)][1]


pending_updates = _PendingUpdates()
