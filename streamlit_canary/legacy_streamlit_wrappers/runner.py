import sys
import typing as tp

import pyapp_window
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen


def run(
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
    """
    params:
        target: a script path.
        show_window: if true, will open a native window.
            if this argument is set to true, `subthread` will be ignored.
    returns:
        (streamlit_process, window_process)
    """
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
            host='localhost', port=port, blocking=blocking, **window_options
        )
        return proc_st, proc_win
    else:
        return proc_st, None
