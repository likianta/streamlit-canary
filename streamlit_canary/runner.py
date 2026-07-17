import os
import sys
import typing as tp

import psutil
import pyapp_window
import streamlit as st
from lk_utils import fs
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen


def run(
    target: str,
    port: int = 3001,
    *,
    extra_args: tp.Sequence[str] = (),
    show_error_details_on_ui: bool = True,
    show_window: bool = False,
    # subthread: bool = False,
    window_icon: tp.Optional[str] = None,
    window_pos: pyapp_window.opener.T.AnyPos = 'center',
    window_size: pyapp_window.opener.T.AnySize = (1200, 900),
    window_title: tp.Optional[str] = None,
    # -- alias
    blocking: bool = True,
    icon: tp.Optional[str] = None,
    title: tp.Optional[str] = None,
) -> tp.Tuple[tp.Optional[Popen], tp.Optional[Popen]]:
    """
    params:
        target: a script path.
        show_window: if true, will open a native window.
            if this argument is set to true, `subthread` will be ignored.
    returns:
        (streamlit_process, window_process)
    """
    # popen_options = {}
    # for k in ('cwd', 'env', 'shell'):
    #     if k in kwargs:
    #         popen_options[k] = kwargs[k]
    window_options = {}
    if show_window:
        window_options.update(
            {
                'title': window_title
                or title
                or 'Streamlit Canary Application',
                'icon': window_icon or icon,
                'oversize_scheme': 'crop',
                'pos': window_pos,
                'size': window_size,
            }
        )
        os.environ['SC_WINDOW_PID_AT_PORT_{}'.format(port)] = str(os.getpid())

    proc_st = tp.cast(
        tp.Optional[Popen],
        run_cmd_args(
            (sys.executable, '-m', 'streamlit', 'run'),
            ('--browser.gatherUsageStats', 'false'),
            (
                '--client.showErrorDetails',
                'full' if show_error_details_on_ui else 'type',
            ),
            ('--global.developmentMode', 'false'),
            ('--runner.magicEnabled', 'false'),
            ('--server.headless', 'true'),
            ('--server.port', port),
            target,
            ('--', *extra_args) if extra_args else (),
            verbose=True,
            blocking=False if show_window else blocking,
            force_term_color=True,
            # **popen_options,
        ),
    )
    if show_window:
        proc_win = pyapp_window.open_window(
            port=port, blocking=blocking, **window_options
        )
        return proc_st, proc_win
    else:
        return proc_st, None


# TODO: rename to "kill_current_app"?
def kill(
    port: tp.Optional[int] = None, except_pids: tp.Sequence[int] = ()
) -> None:
    """kill current app. if window is shown, also close the window."""
    if port is None:
        port = st.get_option('server.port')

    app_pid = os.getpid()
    if x := os.getenv('SC_WINDOW_PID_AT_PORT_{}'.format(port)):
        win_pid = int(x)
    else:
        win_pid = None
    if except_pids:
        assert app_pid not in except_pids and win_pid not in except_pids

    def kill_window_process(pid: int) -> None:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            if child.pid == app_pid or child.pid in except_pids:
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
            if child.pid in except_pids:
                continue
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
        if line.startswith(
            ('if __name__ == "__main__"', "if __name__ == '__main__'")
        ):
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
        return caller_dir[: -len(x)]
