"""A line-based reader/writer for a project's `pyproject.toml`.

The handler keeps the file's raw lines in memory, so a single dependency can
be rewritten in place (`set`) and flushed back to disk (`save`).
"""

import typing as tp
from functools import partial

from lk_utils import fs
from lk_utils import re


class PyProjTomlHandler:
    def __init__(self, toml_file: str) -> None:
        self._file = toml_file
        self._text = fs.load(toml_file, 'plain')
        self._lines = self._text.splitlines()

    def get_dependencies(self) -> tp.Iterator['_LineHandler']:
        def _get(text: str) -> str:
            return text

        def _set(text: str, index: int, cmt: str = '') -> None:
            self._lines[index] = '    "{}",{}'.format(text, cmt)

        flag = 'START'
        for i, line in enumerate(self._lines):
            try:
                if flag == 'START':
                    if line.startswith('dependencies'):
                        flag = 'DEPENDENCIES'
                    continue
                if flag == 'DEPENDENCIES':
                    if line.startswith(']'):
                        flag = 'END'
                        break
                    elif line.strip() == '' or line.lstrip().startswith('#'):
                        continue
                    else:
                        assert (m := re.fullmatch(r' {4}"(.+)",( +#.+)?', line))
                        # yield m.group(1)
                        yield _LineHandler(
                            partial(_get, m.group(1)),
                            partial(_set, index=i, cmt=m.group(2) or ''),
                        )
            except Exception as e:
                e.add_note(
                    str(
                        {
                            'file': self._file,
                            'line_number': i + 1,
                            'line_content': line,
                        }
                    )
                )
                raise
        assert flag == 'END'

    def reload(self) -> None:
        """Re-read the file from disk.

        Keeps `self._lines` in sync with edits made outside this handler
        (e.g. the project version bumped by `project_actions`), while the
        dependency line handlers keep writing into the fresh list.
        """
        self._text = fs.load(self._file, 'plain')
        self._lines = self._text.splitlines()

    def save(self) -> None:
        fs.dump(self._lines, self._file, 'plain')


class _LineHandler:
    def __init__(
        self, getter: tp.Callable[[], str], setter: tp.Callable[[str], None]
    ) -> None:
        self._getter = getter
        self._setter = setter

    @property
    def text(self) -> str:
        return self._getter()

    def get(self) -> str:
        return self._getter()

    def set(self, value: str) -> None:
        self._setter(value)
