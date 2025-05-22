import os
import sys
import typing as t

import psutil
import pyapp_window
import streamlit as st
from lk_utils import fs
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen


def run(
    target: str,
    port: int = 3001,
    subthread: bool = False,
    show_window: bool = False,
    extra_args: t.Sequence[str] = (),
    **kwargs
) -> t.Optional[t.Union[str, Popen]]:
    """
    params:
        target: a script path or something like `[path, '--', *args]`.
        show_window: if true, will open a native window.
            if this argument is set to true, `subthread` will be ignored.
        **kwargs:
            popen options:
                cwd: str
                env: dict
                shell: bool
            if show_window is true, the following are also available:
                icon: str
                pos: str | tuple[int | str, int | str]
                size: str | tuple[int | str, int | str]
                title: str
    """
    if show_window:
        title = kwargs.pop('title', 'Streamlit Canary App')
        icon = kwargs.pop('icon', None)
        size = kwargs.pop('size', (1200, 900))
        pos = kwargs.pop('pos', 'center')
        os.environ['SC_WINDOW_PID_FOR_PORT_{}'.format(port)] = str(os.getpid())
    proc = run_cmd_args(
        (sys.executable, '-m', 'streamlit', 'run'),
        ('--browser.gatherUsageStats', 'false'),
        ('--global.developmentMode', 'false'),
        ('--runner.magicEnabled', 'false'),
        ('--server.headless', 'true'),
        ('--server.port', port),
        target,
        ('--', *extra_args) if extra_args else (),
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
        pyapp_window.open_window(
            title=title, icon=icon, port=port, size=size, pos=pos
        )
    else:
        return proc


# TODO: rename to "kill_current_app"?
def kill(port: int = None) -> None:
    """ kill current app. if window is shown, also close the window. """
    if port is None:
        port = st.get_option('server.port')
    
    app_pid = os.getpid()
    if x := os.getenv('SC_WINDOW_PID_FOR_PORT_{}'.format(port)):
        win_pid = int(x)
    else:
        win_pid = None
    
    def kill_window_process(pid: int) -> None:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            if child.pid == app_pid:
                continue
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            pass
    
    def kill_app_process(pid: int) -> None:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            pass
    
    if win_pid:
        kill_window_process(win_pid)
    kill_app_process(app_pid)


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
