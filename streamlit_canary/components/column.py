import typing as t

import streamlit as st

from ._typing import AnyContainer


def columns(count: t.Union[int, t.Tuple[int, ...]], **kwargs) -> '_Columns':
    return _Columns(count, **kwargs)


class _Columns:
    def __init__(
        self, count: t.Union[int, t.Tuple[int, ...]], **kwargs
    ) -> None:
        self._cols = st.columns(count, **kwargs)
        self._idx = -1
        self._length = count if isinstance(count, int) else len(count)
    
    def __getitem__(self, item: int) -> AnyContainer:
        return self._cols[item]
    
    def next(self) -> AnyContainer:
        self._idx += 1
        if self._idx >= self._length:
            self._idx = 0
        return self._cols[self._idx]
