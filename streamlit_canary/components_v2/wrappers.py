import streamlit as st
import typing as tp
from lk_utils import uuid
from functools import partial


class Binding:
    key: str
    value: tp.Any
    _listeners: tp.List[tp.Tuple[object, str]]

    def __init__(self, key: str) -> None:
        self.key = key
        self._listeners = []

    def trigger(self) -> None:
        for obj, attr in self._listeners:
            setattr(obj, attr, st.session_state[self.key])

    def bind(self, obj: object, attr: str) -> tp.Self:
        self._listeners.append((obj, attr))
        return self


def _generate_key(*factors) -> str:
    return uuid(':'.join(map(str, factors)))


def _generic_component_wrapper(component_name, *args, **kwargs) -> Binding:
    key_factors = []
    if len(args) == 0:
        key_factors.extend(tuple(kwargs.values())[:2])
    elif len(args) == 1:
        key_factors.append(args[0])
        if kwargs:
            key_factors.append(tuple(kwargs.values())[0])
        else:
            key_factors.append('')
    else:
        key_factors.extend(args[:2])
    assert len(key_factors) == 2
    key = _generate_key(*key_factors)
    binding = Binding(key)
    binding.value = getattr(st, component_name)(
        *args, **kwargs, key=key, on_change=binding.trigger
    )
    return binding


selectbox = partial(_generic_component_wrapper, 'selectbox')
text_input = partial(_generic_component_wrapper, 'text_input')
