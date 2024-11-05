import typing as t


class Compositor:
    item: t.Any = None
    value: t.Any = None
    
    def __init__(self, *args, **kwargs) -> None:
        self.compose(*args, **kwargs)
    
    def compose(self, *args, **kwargs) -> None:
        pass
    
    def __enter__(self) -> t.Self:
        if self.item:
            self.item.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> t.Any:
        if self.item:
            return self.item.__exit__(exc_type, exc_val, exc_tb)
