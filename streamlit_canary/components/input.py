import os
import streamlit as st
import typing as t
from lk_utils import fs


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


def path_input(
    label: str,
    path: str = '',
    parent: str = '',
    check: t.Union[bool, int] = False,
    **kwargs
) -> str:
    """
    check: True | False | 0 | 1 | 2
        True: check existence
        False: no check
        0: no check
        1: check if file
        2: check if directory
    """
    x = st.text_input(
        label,
        placeholder=kwargs.pop('placeholder', path),
        **kwargs
    ) or path
    if x and check:
        # if not fs.exist(x):
        #     st.warning('Path does not exist')
        # elif
        try:
            assert fs.exist(x)
            if check == 1:
                assert fs.isfile(x)
            elif check == 2:
                assert fs.isdir(x)
        except AssertionError as e:
            e.add_note(x)
            raise e
    if x:
        if os.path.isabs(x):
            return fs.normpath(x)
        else:
            if parent:
                return fs.normpath('{}/{}'.format(parent, x))
            else:
                return fs.abspath(x)
    else:
        return ''
