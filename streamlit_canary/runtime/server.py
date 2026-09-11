"""
Starlette-based web server for the event-driven runtime.

Routes:
    GET  /    → render the component tree as HTML
    WS   /ws  → bidirectional channel for client events and server deltas
"""

from __future__ import annotations

import asyncio
import json

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from starlette.websockets import WebSocketDisconnect

from .render import render_page
from .runtime import Runtime


class WebSocketClient:
    """Thin wrapper around a Starlette WebSocket used by the Runtime."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    def send_json(self, message: dict) -> None:
        # `WebSocket.send_json` is a coroutine. Signal handlers run
        # synchronously from within the async websocket loop, so there is a
        # running event loop we can schedule the send on.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._ws.send_json(message))


def create_app(runtime: Runtime) -> Starlette:
    # Import here to avoid circular import.
    from . import get_page_config

    async def homepage(request: Request) -> HTMLResponse:
        cfg = get_page_config()
        return HTMLResponse(render_page(runtime.roots, title=cfg['title']))

    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        client = WebSocketClient(ws)
        runtime.add_ws_client(client)
        try:
            while True:
                data = await ws.receive_text()
                message = json.loads(data)
                if message.get('type') == 'event':
                    runtime.on_event(
                        message['id'],
                        message['event'],
                        value=message.get('value'),
                    )
        except WebSocketDisconnect:
            pass
        finally:
            runtime.remove_ws_client(client)

    return Starlette(
        routes=[Route('/', homepage), WebSocketRoute('/ws', ws_endpoint)]
    )


def serve(runtime: Runtime, port: int = 3001) -> None:
    """Build the runtime and start the uvicorn server (blocking)."""
    import uvicorn

    runtime.build()
    app = create_app(runtime)
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')
