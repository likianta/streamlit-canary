import streamlit as st


def hint(text: str) -> None:
    # assert '\n' not in text
    # st.write(':gray[{}]'.format(text.replace('[', '\\[')))
    st.markdown(
        f'<div style="color: gray;">{text}\n</div>',
        unsafe_allow_html=True
    )
