"""Starlette-based web server for the event-driven runtime.

Routes:
    GET  /                        → render the component tree as HTML
    GET  /fonts/source-sans.woff2 → the bundled "Source Sans" UI font
    GET  /fonts/source-code.woff2 → the bundled "Source Code Pro" code font
    GET  /fonts/material-symbols.woff2 → the bundled Material Symbols font
    WS   /ws                      → bidirectional channel for client events
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse
from starlette.responses import HTMLResponse
from starlette.responses import Response
from starlette.routing import Route
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from starlette.websockets import WebSocketDisconnect

from .reload import restart_process
from .render import render_page
from .runtime import Runtime
from .watcher import SourceWatcher
from .watcher import default_folders
from .watcher import extra_files
from .watcher import extra_folders

# 'Source Sans' is Streamlit's UI font and 'Source Code Pro' its code font.
# The same variable fonts are bundled here (copied from the Streamlit
# package) so text metrics match exactly.
_FONT_PATH = (
    Path(__file__).resolve().parent / 'static' / 'SourceSansVF-Upright.woff2'
)
_CODE_FONT_PATH = (
    Path(__file__).resolve().parent / 'static' / 'SourceCodeVF-Upright.woff2'
)
# 'Material Symbols Rounded' draws every `:material/..:` icon, exactly as it
# does in Streamlit (see `page.css` and the markdown renderer in `page.js`).
_ICON_FONT_PATH = (
    Path(__file__).resolve().parent / 'static' / 'MaterialSymbols-Rounded.woff2'
)
# Bundled markdown renderer (MIT). Streamlit renders markdown in the
# browser too; serving it separately keeps the page HTML lean and lets the
# browser cache it across reloads.
_MARKDOWN_PATH = (
    Path(__file__).resolve().parent / 'static' / 'markdown-it.min.js'
)


class WebSocketClient:
    """Thin wrapper around a Starlette WebSocket used by the Runtime.

    ``send_json`` must be callable from *any* thread — signal handlers may
    run in a worker thread (see ``ws_endpoint`` below), so we capture the
    event loop at construction time and use ``run_coroutine_threadsafe``
    to schedule the send back on the loop thread.
    """

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._loop = asyncio.get_running_loop()

    def send_json(self, message: dict) -> None:
        asyncio.run_coroutine_threadsafe(
            self._ws.send_json(message), self._loop
        )


def create_app(runtime: Runtime) -> Starlette:
    # Import here to avoid circular import.
    from . import get_page_config

    async def homepage(request: Request) -> HTMLResponse:
        cfg = get_page_config()
        return HTMLResponse(
            render_page(
                runtime.roots,
                title=cfg['title'],
                default_theme=cfg.get('default_theme', 'dark'),
                layout=cfg.get('layout', 'centered'),
            )
        )

    async def font_endpoint(request: Request) -> Response:
        if not _FONT_PATH.is_file():
            return Response(status_code=404)
        return FileResponse(_FONT_PATH, media_type='font/woff2')

    async def code_font_endpoint(request: Request) -> Response:
        if not _CODE_FONT_PATH.is_file():
            return Response(status_code=404)
        return FileResponse(_CODE_FONT_PATH, media_type='font/woff2')

    async def icon_font_endpoint(request: Request) -> Response:
        if not _ICON_FONT_PATH.is_file():
            return Response(status_code=404)
        return FileResponse(_ICON_FONT_PATH, media_type='font/woff2')

    async def markdown_endpoint(request: Request) -> Response:
        if not _MARKDOWN_PATH.is_file():
            return Response(status_code=404)
        return FileResponse(_MARKDOWN_PATH, media_type='text/javascript')

    async def healthz(request: Request) -> Response:
        # Polled by the browser while a rerun is in flight; the response
        # lets the page know the process is back and it can reload.
        return Response('ok')

    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        client = WebSocketClient(ws)
        runtime.add_ws_client(client)
        runtime.send_source_state(client)
        try:
            while True:
                data = await ws.receive_text()
                message = json.loads(data)
                msg_type = message.get('type')
                if msg_type == 'event':
                    # Run the handler in a worker thread so that blocking
                    # calls (e.g. ``time.sleep``) don't block the event
                    # loop.  Delta patches produced during the handler
                    # are scheduled back on the loop via
                    # ``run_coroutine_threadsafe`` and reach the client
                    # immediately.
                    await asyncio.to_thread(
                        runtime.on_event,
                        message['id'],
                        message['event'],
                        message.get('value'),
                    )
                elif msg_type == 'rerun':
                    # Re-execute the whole process (see reload.py); the
                    # page polls /healthz and reloads once we're back.
                    client.send_json({'type': 'reloading'})
                    restart_process()
        except WebSocketDisconnect:
            pass
        finally:
            runtime.remove_ws_client(client)

    return Starlette(
        routes=[
            Route('/', homepage),
            Route('/healthz', healthz),
            Route('/fonts/source-sans.woff2', font_endpoint),
            Route('/fonts/source-code.woff2', code_font_endpoint),
            Route('/fonts/material-symbols.woff2', icon_font_endpoint),
            Route('/static/markdown-it.js', markdown_endpoint),
            WebSocketRoute('/ws', ws_endpoint),
        ]
    )


def serve(runtime: Runtime, port: int = 3001) -> None:
    """Build the runtime and start the uvicorn server (blocking)."""
    import uvicorn

    runtime.build()
    app = create_app(runtime)
    start_source_watcher(runtime)
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


def _log(message: str) -> None:
    """Write a diagnostics line straight to stderr.

    `print` is monkey-patched by neoprint in this package (it rejects
    `flush=...` and decorates the output), so status lines go to stderr,
    which is also where uvicorn writes.
    """
    sys.stderr.write(message + '\n')
    sys.stderr.flush()


def start_source_watcher(runtime: Runtime) -> SourceWatcher | None:
    """Watch the app folder, the `sys.path` entries, and registered folders.

    Watched by default:
        * the folder the app function was defined in (recursively),
        * every existing `sys.path` / `$PYTHONPATH` entry that is not part
          of the Python installation (see `watcher.default_folders`),
        * anything registered via `streamlit_canary.add_watch_folder(...)`
          or `add_watch_file(...)`.

    Returns the running watcher, or None when watching is unavailable.
    """
    watcher = SourceWatcher(runtime.mark_source_changed)
    if not watcher.available:
        _log(
            '[streamlit-canary] watchdog is not installed - source watching '
            'is disabled (run: uv add watchdog).'
        )
        return None

    folders: list[Path] = []
    app_file = runtime.app_file
    if app_file:
        folders.append(Path(app_file).parent)
    folders.extend(default_folders())
    folders.extend(extra_folders())

    unique: list[Path] = []
    seen: set[str] = set()
    for folder in folders:
        # Dedupe by the *resolved* path: `asa_gui_copy` is a symlink, so
        # the symlink path (from `app_file`) and its target (from
        # `sys.path`, which `default_folders` resolves) both show up and
        # would otherwise report every change twice. The first spelling
        # wins, which keeps the symlink path in the log.
        key = os.path.normcase(os.path.realpath(folder))
        if key in seen:
            continue
        seen.add(key)
        unique.append(folder)

    if not watcher.start(unique, extra_files()):
        _log('[streamlit-canary] nothing to watch.')
        return None

    _log(f'[streamlit-canary] watching {len(unique)} folder(s) for changes:')
    for folder in unique:
        _log(f'  - {folder}')
    return watcher
