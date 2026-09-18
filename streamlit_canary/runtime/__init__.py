"""
Event-driven runtime package.

Exposes:
    Runtime    — owns the component tree and routes events
    create_app — build a Starlette app from a Runtime
    serve      — build + start the uvicorn server
    run_app    — convenience: app function + port → running server
"""

import typing as tp

from .render import render_page
from .render import render_tree
from .runtime import Runtime
from .server import create_app
from .server import serve
from .server import WebSocketClient
from .watcher import add_watch_file
from .watcher import add_watch_folder

# ---------------------------------------------------------------------------
# page config (stored globally, consumed by `render_page`)
# ---------------------------------------------------------------------------

_page_config: dict[str, tp.Any] = {
    'title': 'Streamlit Canary',
    'layout': 'centered',
}


def set_page_config(
    title: str, *, layout: str = 'centered', **kwargs: tp.Any
) -> None:
    """
    Set the page title, layout, and theme.

    Call this at the top of the app function.

    Supported kwargs:
        layout: "centered" (default) | "wide"
        default_theme: "dark" (default) | "light"
    """
    _page_config['title'] = title
    _page_config['layout'] = layout
    _page_config.update(kwargs)


def get_page_config() -> dict[str, tp.Any]:
    return dict(_page_config)
