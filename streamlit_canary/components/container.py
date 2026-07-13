import typing as tp
from contextlib import contextmanager

import streamlit as st


def row(
    vertical_alignment: tp.Literal['top', 'center', 'bottom'] = 'top',
    border: bool = False,
):
    return st.container(
        border=border, horizontal=True, vertical_alignment=vertical_alignment
    )


column = st.container


@contextmanager
def columns(
    segment: tp.Union[int, tp.Tuple[tp.Union[int, float], ...]], **kwargs
) -> tp.Generator[tp.List[tp.Any], None, None]:
    """
    usage:
        with columns((7, 3)) as cols:
            host = cols[0].text_input('Host')
            port = cols[1].number_input('Port')
    """
    cols = st.columns(segment, **kwargs)
    yield cols


@contextmanager
def void_container():
    """
    just sustain a `with` statement to help organizing fluent layout.
    """
    yield


# TODO: rename to `horizontal_flow` and `vertical_flow`?
void_row = void_container
void_column = void_container
