import streamlit as st


def long_button(text: str, **kwargs) -> bool:
    return st.button(text, width='stretch', **kwargs)
