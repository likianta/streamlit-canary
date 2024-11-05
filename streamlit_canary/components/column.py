import streamlit as st


def columns(count: int, **kwargs) -> '_Columns':
    return _Columns(count, **kwargs)


class _Columns:
    def __init__(self, count: int, **kwargs) -> None:
        self._cols = st.columns(count, **kwargs)
        self._idx = -1
    
    def next(self) -> st.delta_generator.DeltaGenerator:
        self._idx += 1
        return self._cols[self._idx]
