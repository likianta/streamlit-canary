"""
Event-driven runtime package.

Exposes:
    Runtime    — owns the component tree and routes events
    create_app — build a Starlette app from a Runtime
    serve      — build + start the uvicorn server
    run_app    — convenience: app function + port → running server
"""

from __future__ import annotations

import typing as tp

from .render import render_page
from .render import render_tree
from .runtime import Runtime
from .server import create_app
from .server import serve
from .server import WebSocketClient

__all__ = [
    'Runtime',
    'WebSocketClient',
    'create_app',
    'render_page',
    'render_tree',
    'run_app',
    'serve',
    'set_page_config',
]


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


def run_app(
    app_func: tp.Callable[[], None], port: int = 3001
) -> None:  # pragma: no cover - thin wrapper
    """Build the runtime for `app_func` and serve it on `port` (blocking)."""
    runtime = Runtime(app_func)
    serve(runtime, port=port)


def run(
    target: tp.Union[str, tp.Callable[[], None]],
    port: int = 3001,
    **kwargs: tp.Any,
) -> tp.Any:
    """
    Unified entry point.

    If `target` is a callable (app function), run it with the event-driven
    runtime (no rerun, Starlette+Uvicorn). If it is a string (script path),
    fall back to the legacy Streamlit subprocess runner.
    """
    if callable(target):
        return run_app(tp.cast(tp.Callable[[], None], target), port=port)
    from ..runner import run as _legacy_run

    return _legacy_run(target, port=port, **kwargs)
