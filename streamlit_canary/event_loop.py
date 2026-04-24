import typing as tp


class EventLoop:
    def __init__(self) -> None:
        # print('init event loop', ':pv')
        self.events = []

    def run(self):
        for name, call in self.events:
            print('trigger event', name)
            call()
        self.events.clear()

    def register(self, event: str, callback: tp.Callable[[], tp.Any]):
        self.events.append((event, callback))


event_loop = EventLoop()
