"""
Event-driven runtime package.

Exposes:
    Runtime     — owns the component tree and routes events
    create_app  — build a Starlette app from a Runtime
    serve       — build + start the uvicorn server (blocking)
    serve_async — the same, on a background thread (for a native window)
    run_app     — convenience: app function + port → running server
    set_page_config — page title / layout / theme
    toast       — push a toast onto the page's shared stack
"""

import typing as tp

from .render import render_page
from .render import render_tree
from .runtime import Runtime
from .runtime import get_current_runtime
from .server import create_app
from .server import serve
from .server import serve_async
from .server import WebSocketClient
from .watcher import add_watch_file
from .watcher import add_watch_folder

# ---------------------------------------------------------------------------
# page config (stored globally, consumed by `render_page`)
# ---------------------------------------------------------------------------

_page_config: dict[str, tp.Any] = {
    'title': 'Streamlit Canary',
    'layout': 'centered',
    'dunder_literal': False,
}


def set_page_config(
    title: str,
    *,
    layout: str = 'centered',
    dunder_literal: bool = False,
    **kwargs: tp.Any,
) -> None:
    """
    Set the page title, layout, and theme.

    Call this at the top of the app function.

    Supported kwargs:
        layout: "centered" (default) | "wide"
        default_theme: "dark" (default) | "light"
        dunder_literal: experimental, off by default. Keep `__x__` as plain
            text instead of letting markdown read it as bold, so a `__init__`
            or `__name__` in prose survives; `**x**` and `:bold[x]` are then
            the only ways to bold. Handy for an app whose text is full of
            Python names. Read by the markdown setup in page.js, which is
            what renders markdown in the browser.
    """
    _page_config['title'] = title
    _page_config['layout'] = layout
    _page_config['dunder_literal'] = dunder_literal
    _page_config.update(kwargs)


def get_page_config() -> dict[str, tp.Any]:
    return dict(_page_config)


# ---------------------------------------------------------------------------
# toast
# ---------------------------------------------------------------------------


def toast(text: str, *, icon: str = '', duration: str | int = 'short') -> None:
    """
    Show a toast in the top-right corner of the page (mirrors `st.toast`).

    Call it from anywhere -- an event handler, a helper, or the app function
    itself. There is no element to declare first: every call writes to the
    page's single toast stack, which the runtime brings into being on its own.

    ```python
    with v3.Button('Make toast') as btn:

        @btn.on_click
        def _() -> None:
            sc.toast('Saved!', icon=':material/check:')
    ```

    Args:
        text: The message. It is rendered as markdown, so `:material/..:`
            icons and the `:color[..]` spans all work.
        icon: An optional icon drawn before the text.
        duration: `'short'` (4 seconds) | `'long'` (10 seconds) |
            `'infinite'` | a positive number of seconds. Hovering the stack
            pauses the countdown. A toast can also be dismissed with its ✕.
    """
    runtime = get_current_runtime()
    if runtime is None:
        raise RuntimeError(
            'sc.toast() needs a running app, but no runtime has come up in '
            'this process yet.'
        )
    runtime.toast(text, icon=icon, duration=duration)
