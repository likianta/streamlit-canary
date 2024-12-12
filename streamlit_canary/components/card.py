import typing as t
from contextlib import contextmanager
from functools import partial

import streamlit as st

bordered_container = partial(st.container, border=True)


@contextmanager
def card(label: str = None) -> t.ContextManager:
    with st.container(border=True):
        if label:
            st.write(':blue[**{}**]'.format(label))
        yield
