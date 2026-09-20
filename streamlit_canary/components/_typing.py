import typing as tp

if tp.TYPE_CHECKING:
    import streamlit as st

    AnyComponent = st.delta_generator.DeltaGenerator
    AnyContainer = st.delta_generator.DeltaGenerator
else:
    # `streamlit` is an optional dependency (see `_streamlit.py`). These two
    # aliases are only ever read by the type checker, so they fall back to
    # `Any` at runtime instead of forcing the import.
    AnyComponent = tp.Any
    AnyContainer = tp.Any
