import typing as t
from contextlib import contextmanager
from functools import partial

import streamlit as st

bordered_container = partial(st.container, border=True)


@contextmanager
def card(title: str = None) -> t.Iterator:
    with st.container(border=True):
        if title:
            st.write(':blue[**{}**]'.format(title))
        yield
