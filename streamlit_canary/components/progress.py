"""
example:
    import openpyxl
    book = openpyxl.load_workbook('test.xlsx')
    with progress('Processing sheets...', len(book.sheets)) as prog:
        for sheet in book.sheets:
            # you can put this before or after item processing.
            prog.update(sheet.title)
            ...
"""

import streamlit as st
import typing as tp
from contextlib import contextmanager
from time import sleep


@contextmanager
def progress(
    label: str = 'Working...',
    total: int = 0,
    auto_close: bool = True,
) -> tp.Generator['Progress', None, None]:
    with Progress(label, total, auto_close) as prog:
        yield prog


class Progress:
    def __init__(
        self, label: str, total: int = 0, auto_close: bool = True
    ) -> None:
        self._prog = st.progress(0, label)
        self.total = total
        self.index = 0
        self._auto_close = auto_close

    def __enter__(self) -> 'Progress':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._auto_close:
            sleep(0.2)
            self.close()

    def update(self, text: str = '') -> None:
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

    def close(self) -> None:
        self._prog.empty()
