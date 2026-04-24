"""
example:
    import openpyxl
    book = openpyxl.load_workbook('test.xlsx')
    with progress('Processing sheets...', len(book.sheets)) as prog:
        for sheet in book.sheets:
            prog.update(sheet.name)
            ...
"""
import streamlit as st
import typing as tp
from contextlib import contextmanager


@contextmanager
def progress(
    label: str = 'Working...',
    total: int = 0,
    auto_close: bool = True,
) -> tp.Generator['_Progress']:
    prog = _Progress(label, total)
    yield prog
    if auto_close:
        prog.close()


class _Progress:
    def __init__(self, label: str, total: int = 0):
        self.index = 0
        self._prog = st.progress(0, label)
    
    def update(self, text: str = ''):
        self.index += 1
        if text:
            self._prog.progress(
                self.index / self.total,
                '[{}/{}] {}'.format(self.index, self.total, text),
            )
        else:
            self._prog.progress(
                self.index / self.total,
                '{:.2%}'.format(self.index / self.total),
            )
    
    def close(self):
        self._prog.empty()
