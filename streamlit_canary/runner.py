import os
import socket
import sys
import time
import typing as tp
from urllib.request import Request
from urllib.request import urlopen

import pyapp_window
import uvicorn
from lk_utils import now
from lk_utils import run_cmd_args
from lk_utils import wait
from lk_utils.subproc import Popen

from .runtime import Runtime
from .runtime import serve
from .runtime import serve_async


def run(
    target: tp.Union[str, tp.Callable[[], None]],
    port: int = 3001,
    *,
    blocking: bool = True,
    extra_args: tp.Sequence[str] = (),
    host: tp.Optional[str] = None,
    #   '0.0.0.0': all interfaces.
    #   '127.0.0.1': localhost only.
    #   'localhost': localhost only. (plus ::1)
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
) -> tp.Tuple[tp.Optional[Popen], tp.Optional[Popen]]:
    """
    Args:
        target: A module path, a script path, or a callable.
        port: The port to listen on. It is also the key the `host` hand-down
            below is filed under, so both ends of a str target must agree.
        host: Which interface to bind. Left alone it follows `show_window`:
            `'localhost'` when a window is asked for, since a window is a
            desktop session and opening it on every interface would only
            earn a firewall prompt; `'0.0.0.0'` otherwise, so the app is
            reachable on the LAN as well as on localhost. Pass
            `'127.0.0.1'` to keep it to this machine.
        blocking: If true, `run()` stays until the app is done -- it serves
            in this thread. If false, it returns at once: a callable leaves
            the server on a background thread, so the caller has to keep
            the process alive; a str target's child process carries on.
        show_window: If true, will open a native window.
        window_size: The window's box, in css px -- the unit the page lays
            out in, and the size the page is then given to lay out in (a
            700x600 window shows 700x600 css px of the page, no matter the
            display's scale factor; `pyapp_window` asks its backend for a
            window in that unit and hands it to the page as-is). An app with
            a form to fill in works this out from the form's shape -- the
            argsense demo's `estimate_window_size` is the worked example.
            `'fullscreen'` / `'maximized'` are taken as `pyapp_window` means
            them.
    Returns:
        (streamlit_process, window_process)
    """
    if host is None:
        # a str target is served by a *child* process, which calls `run()`
        # again on its own, so `host` has to cross a process boundary; it
        # rides in the environment, filed under the port. A callable target
        # has no such hop, and the lookup simply misses.
        host = os.getenv(
            'STREAMLIT_CANARY_HOST_FOR_PORT_{}'.format(port),
            'localhost' if show_window else '0.0.0.0',
        )

    if _v3 or callable(target):  # v3 entrance
        if isinstance(target, str):
            env = os.environ.copy()
            env['STREAMLIT_CANARY_HOST_FOR_PORT_{}'.format(port)] = host
            result = run_cmd_args(
                _v3_argv(target, extra_args),
                blocking=False if show_window else blocking,
                verbose=True,
                ignore_return=not show_window,
                env=env,
            )
            # a Popen comes back only when the child was left running; when we
            # waited for it, what comes back is its output.
            proc_v3 = result if isinstance(result, Popen) else None

            if show_window:
                _wait_until_port_ready(port, host, proc_v3)
                proc_win = _open_window(
                    title=window_title or title,
                    host=host,
                    port=port,
                    icon=window_icon or icon,
                    pos=window_pos,
                    size=window_size,
                    blocking=blocking,
                )
                if blocking and proc_v3 is not None:
                    # the session is over; the server has no reason to outlive
                    # it.
                    _stop_server(proc_v3, port, host)
                return proc_v3, proc_win
            else:
                return proc_v3, None

        else:
            # callable: the server is this very process
            runtime = Runtime(target)
            _print_urls(port, host)

            if show_window:
                server = serve_async(runtime, port=port, host=host)
                _wait_until_server_started(server)
                proc_win = _open_window(
                    title=window_title or title,
                    host=host,
                    port=port,
                    icon=window_icon or icon,
                    pos=window_pos,
                    size=window_size,
                    blocking=blocking,
                )
                if blocking:
                    server.should_exit = True
                return None, proc_win

            else:
                if blocking:
                    serve(runtime, port=port, host=host)  # blocking
                else:
                    # the caller keeps the process; the server rides on a daemon
                    # thread and goes down with it
                    serve_async(runtime, port=port, host=host)
                return None, None
    else:
        return legacy_run(
            target,
            port,
            blocking=blocking,
            extra_args=extra_args,
            host=host,
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
    - `[lib] streamlit : /net_util.py : get_internal_ip`
    - https://stackoverflow.com/a/28950776
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # doesn't even have to be reachable
            s.connect(('8.8.8.8', 1))
            return s.getsockname()[0]
        except Exception:
            pass
    # no route out (an isolated LAN, say): take the first non-loopback ipv4 the
    # host name resolves to instead.
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            family, _type, _proto, _canon, sockaddr = info
            address = str(sockaddr[0])
            if family == socket.AF_INET and not address.startswith('127.'):
                return address
    except Exception:
        pass
    return '127.0.0.1'


def _open_window(
    *,
    blocking: bool,
    host: str,
    icon: tp.Optional[str],
    port: int,
    pos: pyapp_window.opener.T.AnyPos,
    size: pyapp_window.opener.T.AnySize,
    title: tp.Optional[str],
) -> tp.Optional[Popen]:
    """Show the app in a native window, aimed at the url it is served on.

    A host that only makes sense as a *bind* address -- `0.0.0.0` and its
    ipv6 twin -- is not something a browser can connect to, so the window
    asks for localhost in that case.

    The window always runs in a *child* process, even when the caller asked
    to block: hosting the webview here rather than in a child is the path
    that, on Windows, wants a .NET runtime `toga_winforms` may not find (10.0
    on the machine this was written on -- where the child, a plain
    `python -m pyapp_window`, opens a working window instead). So `blocking`
    here means "wait for the child", which is what `run()` wants either way:
    it has a server to shut down once the session ends.
    """
    proc = pyapp_window.open_window(
        title=title or 'Streamlit Canary Application',
        host='localhost' if host in ('0.0.0.0', '::') else host,
        port=port,
        icon=icon or '',
        oversize_scheme='crop',
        pos=pos,
        size=size,
        blocking=False,
        # `run()` cleans up around the window itself (there is a server behind
        # it to shut down), so the window must hand control back on close rather
        # than call `sys.exit()`.
        close_window_to_exit=False,
    )
    if blocking and proc is not None:
        proc.wait()
    return proc


def _print_urls(port: int, host: str) -> None:
    urls = ['http://localhost:{}'.format(port)]
    if host in ('0.0.0.0', '::'):
        urls.append('http://{}:{}'.format(_get_local_ip(), port))
    elif host not in ('localhost', '127.0.0.1', '::1'):
        urls.append('http://{}:{}'.format(host, port))
    print(':dsv', now('h:n:s'))  # divider line, dim color, shows timestamp.
    print(
        'application is running at:\n{}'.format(
            '\n'.join('  - {}'.format(x) for x in urls)
        ),
        ':v4p2',  # green color, grand parent source location.
    )


def _request_shutdown(port: int, host: str) -> bool:
    """Ask the server behind `port` to stop; say whether it took the request.

    `/shutdown` is the clean way out (see `server.create_app`): uvicorn stops,
    the app module returns, and the interpreter runs its `atexit` hooks on the
    way down. A server that is not there -- or is one from before the route
    existed -- answers with nothing, and the caller settles for the hard way.
    """
    address = '127.0.0.1' if host in ('0.0.0.0', '::', 'localhost') else host
    url = 'http://{}:{}/shutdown'.format(address, port)
    try:
        with urlopen(Request(url, method='POST'), timeout=2) as response:
            response.read()
    except OSError:
        # no server, a refused connection, a 4xx from a route we do not have:
        # all the same to us, and none of it worth a traceback.
        return False
    return True


def _stop_server(proc: Popen, port: int, host: str, timeout: float = 5) -> None:
    """Stop the serving child, gently when it takes the hint.

    Killing it is the last resort, not the first move: `Popen.terminate` is
    `TerminateProcess` on Windows, which skips the child's `atexit` hooks --
    so whatever a session saved on its way out (a memory file, say) would be
    lost. Ask first, and only take the process down by force if it will not go
    within `timeout`.
    """
    if not _request_shutdown(port, host):
        proc.terminate()
        return
    for _ in wait(timeout, 0.05):
        if proc.poll() is not None:
            return
    proc.terminate()


def _v3_argv(target: str, extra_args: tp.Sequence[str]) -> tp.Tuple[str, ...]:
    # note that target may be "xxx.yyy.zzz" or "xxx/yyy/zzz.py".
    if target.endswith('.py'):
        return (sys.executable, target, *extra_args)
    return (sys.executable, '-m', target, *extra_args)


def _wait_until_port_ready(
    port: int, host: str, proc: tp.Optional[Popen] = None, timeout: float = 10
) -> None:
    # a name or a wildcard is not something we can dial; the child, told the
    # same `host`, ends up listening on loopback either way.
    address = '127.0.0.1' if host in ('0.0.0.0', '::', 'localhost') else host
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            return  # the child is gone; its port will never open
        with socket.socket() as s:
            # a refused connect does not always fail fast -- it may sit on the
            # timeout instead -- so keep it short and let `deadline` pace us
            s.settimeout(0.2)
            if s.connect_ex((address, port)) == 0:
                return
        time.sleep(0.05)


def _wait_until_server_started(
    server: uvicorn.Server, timeout: float = 10
) -> None:
    for _ in wait(timeout, 0.05):
        if server.started:
            return


def legacy_run(
    target: str,
    port: int = 3001,
    *,
    blocking: bool = True,
    extra_args: tp.Sequence[str] = (),
    host: str = '0.0.0.0',
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
    result = run_cmd_args(
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
            ('--server.address', host),
            ('--server.port', str(port)),
            target,
            ('--', *extra_args) if extra_args else (),
        ),
        verbose=True,
        blocking=False if show_window else blocking,
        ignore_return=not show_window,
    )
    proc_st = result if isinstance(result, Popen) else None

    if show_window:
        _wait_until_port_ready(port, host, proc_st)
        proc_win = _open_window(
            title=window_title or title,
            host=host,
            port=port,
            icon=window_icon or icon,
            pos=window_pos,
            size=window_size,
            blocking=blocking,
        )
        if blocking and proc_st is not None:
            # the session is over; the server has no reason to outlive it
            proc_st.terminate()
        return proc_st, proc_win
    else:
        return proc_st, None
