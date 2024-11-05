import streamlit as st


def anynum_input(label: str, value: int) -> int:
    r = st.text_input(label, placeholder=hex(value))
    if r:
        try:
            out = eval(r)
            assert isinstance(out, (int, float))
            return out
        except ValueError:
            st.error('Invalid input')
            return value
    else:
        return value


def hex_input(label: str, value: int) -> int:
    r = st.text_input(label, placeholder=hex(value))
    if r:
        try:
            return int(r, 16)
        except ValueError:
            st.error('Invalid input')
            return value
    else:
        return value
