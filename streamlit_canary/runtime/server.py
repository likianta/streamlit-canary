"""
Starlette-based web server for the event-driven runtime.

Routes:
    GET  /                        → render the component tree as HTML
    GET  /fonts/source-sans.woff2 → the bundled "Source Sans" UI font
    WS   /ws                      → bidirectional channel for client events
"""

from __future__ import annotations

import asyncio
import json
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

from .render import render_page
from .runtime import Runtime

# 'Source Sans' is Streamlit's UI font. The same variable font is bundled
# here (copied from the Streamlit package) so text metrics match exactly.
_FONT_PATH = (
    Path(__file__).resolve().parent / 'static' / 'SourceSansVF-Upright.woff2'
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
            )
        )

    async def font_endpoint(request: Request) -> Response:
        if not _FONT_PATH.is_file():
            return Response(status_code=404)
        return FileResponse(_FONT_PATH, media_type='font/woff2')

    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        client = WebSocketClient(ws)
        runtime.add_ws_client(client)
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
        except WebSocketDisconnect:
            pass
        finally:
            runtime.remove_ws_client(client)

    return Starlette(
        routes=[
            Route('/', homepage),
            Route('/fonts/source-sans.woff2', font_endpoint),
            WebSocketRoute('/ws', ws_endpoint),
        ]
    )


def serve(runtime: Runtime, port: int = 3001) -> None:
    """Build the runtime and start the uvicorn server (blocking)."""
    import uvicorn

    runtime.build()
    app = create_app(runtime)
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')
