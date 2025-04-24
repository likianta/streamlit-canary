import streamlit as st


def hint(text: str) -> None:
    st.markdown(
        f'<p style="color: gray;">{text}\n</p>',
        unsafe_allow_html=True
    )
