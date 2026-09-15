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

import os
import typing as tp

from ..kernel import Property

if tp.TYPE_CHECKING:
    from ..components_v3.base import Component
    from .server import WebSocketClient


def _display_path(path: str) -> str:
    """Prefer a path relative to the working directory, for readability."""
    try:
        return os.path.relpath(path, os.getcwd()).replace('\\', '/')
    except ValueError:  # different drive on Windows
        return path.replace('\\', '/')


class Runtime:
    def __init__(self, app_func: tp.Callable[[], None]) -> None:
        self._app_func = app_func
        self._components: dict[str, Component] = {}
        self._roots: list[Component] = []
        self._ws_clients: set[WebSocketClient] = set()
        self._source_changed: set[str] = set()
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

        Built-in events:
            click  — emit `on_click` (Button)
            change — set the `value` Property (Selectbox / Radio / TextInput
                     / NumberInput), which in turn emits `on_value`
                     (= `value.on_change`).

        A component may also handle an event itself by defining an
        `_on_<event>` method, which receives the raw client value. That is
        how Tabs consumes `change` and Selectbox consumes `new_option`.
        """
        comp = self._components.get(component_id)
        if comp is None:
            return
        if event == 'click' and hasattr(comp, 'on_click'):
            comp.on_click.emit()
            return
        hook = getattr(comp, f'_on_{event}', None)
        if callable(hook):
            hook(value)
            return
        if event == 'change':
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

    # -- source watching / rerun -----------------------------------------

    @property
    def app_file(self) -> str | None:
        """The file the app function was defined in (watched by default)."""
        code = getattr(self._app_func, '__code__', None)
        filename = getattr(code, 'co_filename', None)
        return filename or None

    @property
    def source_changed(self) -> tuple[str, ...]:
        return tuple(sorted(self._source_changed))

    def mark_source_changed(self, paths: tp.Iterable[str]) -> None:
        """Record changed source files and notify the browsers."""
        self._source_changed.update(str(p) for p in paths)
        self._notify_source_changed()

    def send_source_state(self, client: WebSocketClient) -> None:
        """Replay the current notice to a freshly connected client."""
        client.send_json(self._source_message())

    def _source_message(self) -> dict:
        return {
            'type': 'source_changed',
            'files': [_display_path(p) for p in self.source_changed],
        }

    def _notify_source_changed(self) -> None:
        self._broadcast(self._source_message())

    # -- tree access (for rendering) -------------------------------------

    @property
    def roots(self) -> tuple[Component, ...]:
        return tuple(self._roots)

    @property
    def components(self) -> dict[str, Component]:
        return self._components
