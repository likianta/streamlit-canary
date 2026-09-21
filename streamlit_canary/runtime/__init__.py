"""
Event-driven runtime package.

Exposes:
    Runtime     — owns the component tree and routes events
    create_app  — build a Starlette app from a Runtime
    serve       — build + start the uvicorn server (blocking)
    serve_async — the same, on a background thread (for a native window)
    run_app     — convenience: app function + port → running server
"""

import typing as tp

from .render import render_page
from .render import render_tree
from .runtime import Runtime
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
