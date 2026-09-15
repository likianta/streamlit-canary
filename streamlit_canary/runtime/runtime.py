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

from ..kernel import Property

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
        # Observe every Property *after* the tree is fully built: components
        # create their Property fields inside `__init__`, i.e. after they have
        # already registered themselves. Changes made during the build are
        # reflected in the initial render, so only later changes need patches.
        for comp in self._components.values():
            for name, prop in comp._iter_properties():
                prop.on_change.connect(
                    lambda c=comp, n=name: self._on_prop_change(c, n)
                )
        self._built = True

    # -- component registration ------------------------------------------

    def _register_component(self, comp: Component) -> None:
        self._components[comp.id] = comp

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
            # Selectbox / Radio / TextInput / NumberInput: set the value
            # property, which triggers `on_value` and any bound handlers.
            # A component may expose `_coerce_value` to normalize the raw
            # client string (e.g. NumberInput parses `'0x29'` into an int).
            prop = getattr(comp, 'value', None)
            if isinstance(prop, Property):
                coerce = getattr(comp, '_coerce_value', None)
                prop.set(coerce(value) if callable(coerce) else value)

    # -- property change → delta -----------------------------------------

    def _on_prop_change(self, comp: Component, prop_name: str) -> None:
        prop = getattr(comp, prop_name)
        value = prop.get()
        message: dict = {
            'type': 'patch',
            'id': comp.id,
            'prop': prop_name,
            'value': value,
        }
        # For Selectbox / Radio `options` patch, the frontend needs the
        # formatted labels (via `format_func`) because the raw values are
        # keys, not human-readable text. Without this, the JS rebuilds
        # radio items with raw keys instead of formatted labels.
        if prop_name == 'options':
            fmt = getattr(comp, 'format_func', None) or str
            message['formatted'] = [fmt(o) for o in (value or [])]
        elif prop_name == 'value':
            # NumberInput: the display text may differ from the raw value
            # (e.g. `hex`), so send it along for the frontend to patch.
            fmt = getattr(comp, 'format', None)
            if callable(fmt):
                message['formatted'] = fmt(value)
        self._broadcast(message)

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
