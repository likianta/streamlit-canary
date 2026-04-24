import streamlit as st
import typing as tp
from functools import partial
from ..session import init_state


@init_state
class State:
    button_states: tp.Dict[str, bool] = {}


def toggled_button(label: str, value: bool = False, **kwargs) -> bool:
    if label not in State.button_states:
        State.button_states[label] = value
    curr_value = State.button_states[label]
    st.button(
        label,
        type='primary' if curr_value else 'secondary',
        on_click=partial(_invert_state, label),
        **kwargs,
    )
    return curr_value


def _invert_state(key: str) -> None:
    State.button_states[key] = not State.button_states[key]
