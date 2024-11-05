import streamlit as st


def hint(text: str) -> None:
    st.markdown(
        f'<div style="color: gray;">{text}</div>',
        unsafe_allow_html=True
    )
