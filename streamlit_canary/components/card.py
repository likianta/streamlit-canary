import streamlit as st
import typing as t
from contextlib import contextmanager


@contextmanager
def card(title: str = '') -> t.Generator:
    with st.container(border=True):
        if title:
            st.write(':blue[**{}**]'.format(title))
        yield
