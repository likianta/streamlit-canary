import os
import sys
import typing as t

import pyapp_window
from lk_utils import fs
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen


def run(
    target: t.Union[str, t.Tuple[str, ...], t.List[str]],
    port: int = 3001,
    subthread: bool = False,
    show_window: bool = False,
    **kwargs
) -> t.Optional[t.Union[str, Popen]]:
    """
    params:
        target: a script path or something like `[path, '--', *args]`.
        show_window: if true, will open a native window.
            if this argument is set to true, `subthread` will be ignored.
            window options (by `kwargs`): title, size, pos.
    """
    if not isinstance(target, str):
        assert target[1] == '--'
    if show_window:
        title = kwargs.pop('title', 'Streamlit Canary App')
        size = kwargs.pop('size', (1200, 900))
        pos = kwargs.pop('pos', 'center')
    proc = run_cmd_args(
        (sys.executable, '-m', 'streamlit', 'run'),
        ('--browser.gatherUsageStats', 'false'),
        ('--global.developmentMode', 'false'),
        ('--runner.magicEnabled', 'false'),
        ('--server.headless', 'true'),
        ('--server.port', port),
        target,
        verbose=True,
        blocking=False if show_window else not subthread,
        force_term_color=True,
        # cwd=_get_entrance(
        #     fs.parent(caller_file),
        #     caller_frame.f_globals['__package__']
        # ),
        **kwargs,
    )
    if show_window:
        # noinspection PyUnboundLocalVariable
        pyapp_window.open_window(title=title, port=port, size=size, pos=pos)
    else:
        return proc


# DELETE
def _check_package_definition_in_source(source_file: str) -> None:
    """
    if source has imported relative module, it must have defined `__package__` -
    in first of lines.
    """
    source_code = fs.load(source_file, 'plain')
    temp = []
    for i, line in enumerate(source_code.splitlines()):
        line = line.lstrip()
        if line.startswith((
            'if __name__ == "__main__"', "if __name__ == '__main__'"
        )):
            temp.append(line)
        if line.startswith(('from .', 'import .')):
            assert any(x.startswith('__package__ = ') for x in temp), (temp, i)
            return
        if temp:
            temp.append(line)


def _get_entrance(caller_dir: str, package_info: str) -> str:
    if (x := fs.normpath(os.getcwd())) != caller_dir:
        return x
    else:
        assert caller_dir.endswith(x := package_info.replace('.', '/'))
        return caller_dir[:-len(x)]
