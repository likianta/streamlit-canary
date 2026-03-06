import streamlit as st
from collections import namedtuple

ProgressItem = namedtuple('ProgressItem', 'data label')


def progress(
    iterable,
    label: str = 'Working...',
    auto_close: bool = True,
):
    prog = st.progress(0, label)
    total = len(iterable)
    for i, x in enumerate(iterable, 1):
        if isinstance(x, ProgressItem):
            prog.progress(i / total, '[{}/{}] {}'.format(i, total, x.label))
            yield x.data
        else:
            prog.progress(i / total, '{:.2%}'.format(i / total))
            yield x
    if auto_close:
        prog.empty()
