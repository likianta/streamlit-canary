import typing as t
from contextlib import contextmanager

import streamlit as st

column = st.container


@contextmanager
def columns(
    segment: t.Union[int, t.Tuple[t.Union[int, float], ...]], **kwargs
) -> t.Generator[t.List[t.Any], None, None]:
    """
    usage:
        with columns((7, 3)) as cols:
            host = cols[0].text_input('Host')
            port = cols[1].number_input('Port')
    """
    cols = st.columns(segment, **kwargs)
    yield cols


# class _Columns:
#     def __init__(
#         self, count: t.Union[int, t.Tuple[int, ...]], **kwargs
#     ) -> None:
#         self._cols = st.columns(count, **kwargs)
#         self._idx = -1
#         self._length = count if isinstance(count, int) else len(count)

#     def __getitem__(self, item: int) -> AnyContainer:
#         return self._cols[item]

#     def next(self) -> AnyContainer:
#         self._idx += 1
#         if self._idx >= self._length:
#             self._idx = 0
#         return self._cols[self._idx]
