"""
Event-driven runtime.

The Runtime owns the component tree and the application state. It:
  * runs the app function exactly once to build the tree,
  * routes incoming client events to the right component signal,
  * observes property changes and pushes delta messages to connected
    WebSocket clients so the frontend can patch the DOM in place.

This is the core of the "no rerun" model: after `build()`, the app function
never runs again — only signal handlers execute.
"""

from __future__ import annotations

import typing as tp

if tp.TYPE_CHECKING:
    from ..components_v3.base import Component
    from .server import WebSocketClient


class Runtime:
    def __init__(self, app_func: tp.Callable[[], None]) -> None:
        self._app_func = app_func
        self._components: dict[str, Component] = {}
        self._roots: list[Component] = []
        self._ws_clients: set[WebSocketClient] = set()
        self._built = False

    # -- lifecycle --------------------------------------------------------

    def build(self) -> None:
        """Run the app function once to construct the component tree."""
        if self._built:
            return
        # avoid circular import at module load time
        from ..components_v3.base import Component

        Component._active_runtime = self
        try:
            self._app_func()
        finally:
            Component._active_runtime = None
        # roots are the components created outside any `with` block.
        self._roots = [c for c in self._components.values() if c.parent is None]
        self._built = True

    # -- component registration ------------------------------------------

    def _register_component(self, comp: Component) -> None:
        self._components[comp.id] = comp
        # observe every Property so we can push a delta when it changes.
        for name in comp._properties:
            handle = comp._handles[name]
            handle.on_change.connect(
                lambda _h, c=comp, n=name: self._on_prop_change(c, n)
            )

    # -- event routing ----------------------------------------------------

    def on_event(
        self, component_id: str, event: str, value: tp.Any = None
    ) -> None:
        """Dispatch a client event to the component.

        Supported events:
            click  — emit `on_click` (Button)
            change — set `value` Property (Selectbox / Radio), which in turn
                     emits `on_value` (= `value.on_change`).
        """
        comp = self._components.get(component_id)
        if comp is None:
            return
        if event == 'click' and hasattr(comp, 'on_click'):
            comp.on_click.emit()
        elif event == 'change':
            # Selectbox / Radio: set the value property, which triggers
            # `on_value` and any handlers bound to it.
            if 'value' in comp._handles:
                comp._handles['value'].set(value)

    # -- property change → delta -----------------------------------------

    def _on_prop_change(self, comp: Component, prop_name: str) -> None:
        value = comp._values.get(prop_name)
        self._broadcast(
            {'type': 'patch', 'id': comp.id, 'prop': prop_name, 'value': value}
        )

    # -- websocket client management -------------------------------------

    def add_ws_client(self, client: WebSocketClient) -> None:
        self._ws_clients.add(client)

    def remove_ws_client(self, client: WebSocketClient) -> None:
        self._ws_clients.discard(client)

    def _broadcast(self, message: dict) -> None:
        for client in list(self._ws_clients):
            client.send_json(message)

    # -- tree access (for rendering) -------------------------------------

    @property
    def roots(self) -> tuple[Component, ...]:
        return tuple(self._roots)

    @property
    def components(self) -> dict[str, Component]:
        return self._components
