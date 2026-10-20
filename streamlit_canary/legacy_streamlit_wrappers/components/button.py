from .._streamlit import st


def long_button(*args, **kwargs):
    """A `st.button` that stretches to the width of its container."""
    return st.button(*args, width='stretch', **kwargs)
