import typing as t
from contextlib import contextmanager

import streamlit as st


class Scope:
    
    def __init__(self) -> None:
        self.key = ''
    
    def __bool__(self) -> bool:
        return bool(self.key)
    
    def __str__(self) -> str:
        return self.key
    
    @contextmanager
    def __call__(self, main_key: str) -> t.Iterator:
        old, new = self.key, main_key
        self.key = new
        yield
        self.key = old


class ScopedComponent:
    def __init__(self, type: str) -> None:
        self.type = type
    
    def __call__(self, *args, **kwargs) -> t.Any:
        if scope:
            subkey = kwargs.pop('key', args[0])
            kwargs['key'] = f'{scope}:{subkey}'
            return getattr(st, self.type)(*args, **kwargs)
        else:
            return getattr(st, self.type)(*args, **kwargs)


scope = Scope()

if __name__ == '__main__':  # fraud ide typing analysis
    button = st.button
    checkbox = st.checkbox
    number_input = st.number_input
    radio = st.radio
    text_input = st.text_input
else:
    globals().update({
        'button'      : ScopedComponent('button'),
        'checkbox'    : ScopedComponent('checkbox'),
        'number_input': ScopedComponent('number_input'),
        'radio'       : ScopedComponent('radio'),
        'text_input'  : ScopedComponent('text_input'),
    })

__all__ = [
    'scope',
    'button',
    'checkbox',
    'number_input',
    'radio',
    'text_input',
]
