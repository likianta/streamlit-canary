import streamlit as st
import typing as t
from streamlit.navigation.page import StreamlitPage


def pages(
    elements: t.Dict[str, t.Callable[[], t.Any]]
) -> StreamlitPage:
    normalized_elements = []
    for k, v in elements.items():
        normalized_elements.append(st.Page(
            v,
            title=k,
            url_path=k.lower().replace(' ', '-'),
        ))
    return st.navigation(normalized_elements)
