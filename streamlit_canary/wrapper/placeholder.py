import typing as t

import streamlit as st

from .base import T
from ..compositor import Compositor


class Placeholder(Compositor):
    _delegate0: t.Optional[t.Union[t.Callable[[], T.Item], T.Item]]
    _delegate1: t.Optional[T.Item]
    
    def __init__(
        self, delegaet: t.Optional[t.Union[t.Callable[[], T.Item], T.Item]] = None
    ):
        self._delegate0 = delegaet
        self._delegate1 = None
        super().__init__()
    
    def __call__(self, *args, **kwargs) -> t.Self:
        self._delegate1 = self._delegate0(*args, **kwargs)
        return self
    
    def compose(self) -> None:
        self.item = st.empty()
    
    def __enter__(self) -> t.Any:
        self.item.__enter__()
        if self._delegate1:
            self._delegate1.__enter__()
        # elif self._delegate0:
        #     self._delegate0.__enter__()
        return self
    
    def __exit__(self, *args):
        self.item.__exit__(*args)
        if self._delegate1:
            self._delegate1.__exit__(*args)
            # self._delegate1 = None
        # elif self._delegate0:
        #     self._delegate0.__exit__(*args)
