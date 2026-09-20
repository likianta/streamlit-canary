import os
import socket
import sys
import typing as tp

import psutil
import pyapp_window
from lk_utils import fs
from lk_utils import now
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen

from ._streamlit import st
from .runtime import Runtime
from .runtime import serve


def run(
    target: tp.Union[str, tp.Callable[[], None]],
    port: int = 3001,
    *,
    blocking: bool = True,
    extra_args: tp.Sequence[str] = (),
    show_window: bool = False,
    window_icon: tp.Optional[str] = None,
    window_pos: pyapp_window.opener.T.AnyPos = 'center',
    window_size: pyapp_window.opener.T.AnySize = (1200, 900),
    window_title: tp.Optional[str] = None,
    # ---
    icon: tp.Optional[str] = None,  # alias of window_icon
    title: tp.Optional[str] = None,  # alias of window_title
    _v3: tp.Optional[tp.Literal[True]] = None,  # experimental
    **kwargs,
) -> tp.Optional[tp.Tuple[tp.Optional[Popen], tp.Optional[Popen]]]:
    """
    params:
        target: a script path.
        show_window: if true, will open a native window.
    returns:
        (streamlit_process, window_process)
    """
    if _v3 or callable(target):  # v3 entrance
        if isinstance(target, str):
            proc_v3 = tp.cast(
                Popen,
                run_cmd_args(
                    (sys.executable, target, *extra_args),
                    blocking=False if show_window else blocking,
                    verbose=True,
                    force_term_color=True,
                ),
            )
        else:  # callable
            if blocking:
                print(':dsv', now('h:n:s'))
                print(
                    'application is running at:\n  - {}\n  - {}'.format(
                        'http://localhost:{}'.format(port),
                        'http://{}:{}'.format(_get_local_ip(), port),
                    ),
                    ':v4p',
                )
                runtime = Runtime(target)
                serve(runtime, port=port)  # blocking
                return
            else:
                raise NotImplementedError

        if show_window:
            proc_win = tp.cast(  # TODO  # noqa
                Popen,
                pyapp_window.open_window(
                    port=port,
                    blocking=blocking,
                    title=window_title
                    or title
                    or 'Streamlit Canary Application',
                    icon=window_icon or icon or '',
                    oversize_scheme='crop',
                    pos=window_pos,
                    size=window_size,
                ),
            )
            return proc_v3, proc_win
        else:
            return proc_v3, None
    else:
        return _legacy_run(
            target,
            port,
            blocking=blocking,
            extra_args=extra_args,
            show_window=show_window,
            window_icon=window_icon or icon,
            window_pos=window_pos,
            window_size=window_size,
            window_title=window_title or title,
            **kwargs,
        )


def _get_local_ip() -> str:
    """
    Ref:
    - `[lib] airmise : /util.py : get_local_ip_address`
    - `[lib] streamlit : /net_util.py : get_internal_ip`
    - https://stackoverflow.com/a/28950776
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # doesn't even have to be reachable
            s.connect(('8.8.8.8', 1))
            return s.getsockname()[0]
        except Exception:
            return '127.0.0.1'


def _legacy_run(
    target: str,
    port: int = 3001,
    *,
    blocking: bool = True,
    extra_args: tp.Sequence[str] = (),
    show_error_details_on_ui: bool = True,
    show_window: bool = False,
    window_icon: tp.Optional[str] = None,
    window_pos: pyapp_window.opener.T.AnyPos = 'center',
    window_size: pyapp_window.opener.T.AnySize = (1200, 900),
    window_title: tp.Optional[str] = None,
    # -- alias
    icon: tp.Optional[str] = None,
    title: tp.Optional[str] = None,
) -> tp.Tuple[tp.Optional[Popen], tp.Optional[Popen]]:
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
            (
                (sys.executable, '-m', 'streamlit', 'run'),
                ('--browser.gatherUsageStats', 'false'),
                (
                    '--client.showErrorDetails',
                    'full' if show_error_details_on_ui else 'type',
                ),
                ('--global.developmentMode', 'false'),
                ('--runner.magicEnabled', 'false'),
                ('--server.headless', 'true'),
                ('--server.port', str(port)),
                target,
                ('--', *extra_args) if extra_args else (),
            ),
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
