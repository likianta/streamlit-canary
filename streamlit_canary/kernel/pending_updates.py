import typing as tp

from contextlib import contextmanager

if tp.TYPE_CHECKING:
    from .property import Property


class _PendingUpdates:
    def __init__(self):
        self.queue = {}  # {id: (source, order), ...}
        self.is_pending = False
        self._transaction_order = 0

    def add_to_queue(self, source: 'Property') -> None:
        self._transaction_order += 1
        self.queue[id(source)] = (source, self._transaction_order)

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
            if self.is_pending:
                yield
            else:
                self.is_pending = True
                try:
                    yield
                finally:
                    if self.queue:
                        for source, _ in sorted(
                            self.queue.values(), key=lambda x: x[1]
                        ):
                            try:
                                source.on_change.emit()
                            except Exception:
                                continue
                        self.queue.clear()
                    self.is_pending = False

        return _pending


pending_updates = _PendingUpdates()
