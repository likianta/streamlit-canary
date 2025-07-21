import typing as t
import streamlit as st


def radio(
    label: str,
    options: t.Union[t.Dict[t.Any, str], t.Iterable[t.Tuple[t.Any, str]]],
    index: int = 0,
    horizontal: bool = True,
    **kwargs
) -> t.Union[int, str]:
    frozen = tuple(options)
    indexes = tuple(range(len(frozen)))
    keys = (
        frozen if isinstance(options, dict) else
        tuple(x if isinstance(x, str) else x[0] for x in frozen)
    )
    values = (
        tuple(options.values()) if isinstance(options, dict) else
        tuple(x if isinstance(x, str) else x[1] for x in frozen)
    )
    
    idx = st.radio(
        label,
        indexes,
        format_func=lambda i: values[i],
        horizontal=horizontal,
        index=index,
        **kwargs
    )
    return keys[idx]
