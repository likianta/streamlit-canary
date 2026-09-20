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

import hashlib
import os
import sys
import traceback
import typing as tp

from ..kernel import Property

if tp.TYPE_CHECKING:
    from .server import WebSocketClient
    from ..components_v3.base import Component
else:
    Component = tp.Any
    WebSocketClient = tp.Any

_MAX_MEDIA = 64
"""How many published media bodies the runtime holds (see `publish_media`).
A `PdfViewer` document is a few hundred KB, so the cap keeps a handful of MB
around -- far more than any one page can point at."""


def _display_path(path: str) -> str:
    """Prefer a path relative to the working directory, for readability."""
    try:
        return os.path.relpath(path, os.getcwd()).replace('\\', '/')
    except ValueError:  # different drive on Windows
        return path.replace('\\', '/')


def _log_error(text: str) -> None:
    """Echo a traceback to stderr, where uvicorn's own logging goes.

    `print` is monkey-patched by neoprint in this package (it rejects
    `flush=...` and decorates the output), so the traceback would come out
    mangled; stderr keeps it byte-for-byte.
    """
    sys.stderr.write(text if text.endswith('\n') else text + '\n')
    sys.stderr.flush()


class _LogTee:
    """A stand-in for `sys.stdout` / `sys.stderr` that feeds the log panels.

    Every write goes on to the real stream first -- the terminal keeps
    working -- and then into a line buffer, because `print(a, b)` lays its
    pieces down one `write` at a time while a sink wants whole lines.
    """

    def __init__(self, stream: tp.Any, emit: tp.Callable[[str], None]) -> None:
        self._stream = stream
        self._emit = emit
        self._pending = ''

    def write(self, text: str) -> int:
        self._stream.write(text)
        self._pending += text
        while '\n' in self._pending:
            line, self._pending = self._pending.split('\n', 1)
            self._emit(line)
        return len(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str) -> tp.Any:
        # everything else (`columns`, `encoding`, `isatty`, ...) is the real
        # stream's; the guard keeps a half-built tee from recursing
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._stream, name)


class Runtime:
    def __init__(self, app_func: tp.Callable[[], None]) -> None:
        self._app_func = app_func
        self._components: dict[str, Component] = {}
        self._roots: list[Component] = []
        self._ws_clients: set[WebSocketClient] = set()
        self._source_changed: set[str] = set()
        self._log_sinks: dict[str, list[tp.Callable[[str], None]]] = {}
        self._media: dict[str, tuple[str, bytes]] = {}
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
            change — set the `value` Property (Selectbox / RadioGroup / TextInput
                     / NumberInput), which in turn emits `on_value`
                     (= `value.on_change`).

        A component may also handle an event itself by defining an
        `_on_<event>` method, which receives the raw client value. That is
        how Tabs consumes `change` and Selectbox consumes `new_option`.

        An exception raised by a handler is *caught* and reported to the
        browsers (`_report_error`). Letting it escape would tear the
        websocket down (Starlette closes it), so the client would lose every
        later patch -- while the built tree stays perfectly valid. The error
        is therefore shown instead, and the user decides when to rerun.
        """
        try:
            self._dispatch_event(component_id, event, value)
        except Exception as exc:
            self._report_error(exc)

    def _dispatch_event(
        self, component_id: str, event: str, value: tp.Any = None
    ) -> None:
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
            # Selectbox / RadioGroup / TextInput / NumberInput: set the value
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
        # For Selectbox / RadioGroup `options` patch, the frontend needs the
        # formatted labels (via `format_func`) because the raw values are
        # keys, not human-readable text. Without this, the JS rebuilds
        # radio items with raw keys instead of formatted labels.
        if prop_name == 'options':
            fmt = getattr(comp, 'format_func', None) or str
            message['formatted'] = [fmt(o) for o in (value or [])]
            # RadioGroup / CheckGroup: which rows draw a frozen box (see
            # their `box_disabled`) -- the JS rebuilt rows need the indices
            # because it cannot evaluate the predicate.
            box_disabled = getattr(comp, '_box_disabled', None)
            if callable(box_disabled):
                message['box_disabled'] = [
                    i for i, o in enumerate(value or []) if box_disabled(o)
                ]
            # ... and which rows carry the "enter" button (`_navigable`, which
            # only `TreeSelect`'s private navigation groups set) -- same
            # reason.
            navigable = getattr(comp, '_navigable', None)
            if callable(navigable):
                message['navigable'] = [
                    i for i, o in enumerate(value or []) if navigable(o)
                ]
            # ... and which rows walk in on their *own* click instead
            # (`_body_opens`: `..` has no arrow and no tick, so the click is
            # free) -- the JS row needs the same handler the server drew.
            body_opens = getattr(comp, '_body_opens', None)
            if callable(body_opens):
                message['body_opens'] = [
                    i for i, o in enumerate(value or []) if body_opens(o)
                ]
            # CheckGroup in flag mode keeps `value` as a list of booleans
            # parallel to `options` (`options` was a `dict`), so a rebuilt row
            # set also needs those flags to know which rows are ticked.
            if getattr(comp, '_flags', False):
                message['flags'] = list(comp.value.get() or ())
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

    # -- log capture -------------------------------------------------------

    def add_log_sink(self, source: str, sink: tp.Callable[[str], None]) -> None:
        """Feed every complete line written to `source` to `sink`.

        `source` is `'stdout'` or `'stderr'`, and a sink is what a `LogPanel`
        registers while it is being built. The stream is wrapped the first
        time a sink asks for it and stays wrapped for the life of the
        process. Sinks receive lines rather than raw writes: `print(a, b)`
        lays its pieces down one `write` at a time.
        """
        self._log_sinks.setdefault(source, []).append(sink)
        self._wrap_log_stream(source)

    def _wrap_log_stream(self, source: str) -> None:
        """Put a `_LogTee` in front of `source` (once)."""
        stream = getattr(sys, source)
        if isinstance(stream, _LogTee):
            # a second panel on the same stream rides the first tee
            return
        tee = _LogTee(stream, lambda line: self._emit_log(source, line))
        setattr(sys, source, tee)
        if source != 'stdout':
            return
        # neoprint wrote its own handle on the stream down at import time
        # (`neoprint.console._stdout`, read by `Console.print`), so anything
        # printed from inside this package -- which neoprint decorates
        # instead of handing to `builtins.print` -- would keep writing to the
        # original object and slip past the tee. Point that handle at the tee
        # too. Nothing is double-counted: the tee forwards to the stream it
        # wrapped, which is that same original object. (Note that the
        # `neoprint.console` *attribute* is the `Console` instance the package
        # re-exports -- `_stdout` lives on the module, hence `sys.modules`.)
        neoprint_console = sys.modules.get('neoprint.console')
        if neoprint_console is not None and not isinstance(
            neoprint_console._stdout, _LogTee
        ):
            neoprint_console._stdout = tee

    def _emit_log(self, source: str, line: str) -> None:
        for sink in tuple(self._log_sinks.get(source, ())):
            try:
                sink(line)
            except Exception:
                # a panel that cannot take the line must not take the app
                # down with it -- the line has reached the terminal already
                pass

    # -- media -------------------------------------------------------------

    def publish_media(self, data: bytes, media_type: str) -> str:
        """Publish `data` and return the URL the client can fetch it from.

        `PdfViewer` hands a document over this way rather than inlining it as
        a `data:` URL: the page HTML stays small (a PDF is often megabytes,
        and base64 adds a third on top of that), and the client can cache the
        address across reloads.

        The token is the content hash, so the same bytes always come back
        under the same URL -- re-publishing is free, and the client may cache
        it forever. The oldest entries are dropped past `_MAX_MEDIA`.
        """
        token = hashlib.sha256(data).hexdigest()[:32]
        self._media.pop(token, None)  # re-insert, so it counts as fresh
        self._media[token] = (media_type, data)
        while len(self._media) > _MAX_MEDIA:
            self._media.pop(next(iter(self._media)))
        return '/media/{}'.format(token)

    def get_media(self, token: str) -> tp.Optional[tuple[str, bytes]]:
        """The `(media type, body)` published under `token`, if still held."""
        return self._media.get(token)

    # TODO or DELETE: file watcher & reload banner needs to be refactored or
    # be deleted. Nothing reaches these any more: the watcher is not started
    # (see server.serve) and the frontend ignores `source_changed`.
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

    # -- error reporting --------------------------------------------------

    def _report_error(self, exc: BaseException) -> None:
        """Send a handler's traceback to the browsers (and to the terminal).

        The whole traceback goes out as one `format_exception` string --
        `str(exc)` alone would only carry the last line, and the source
        excerpts plus the frame list are exactly what makes an error
        actionable. The frontend renders it in a panel whose Rerun button
        restarts the process, which is how the error is dismissed.
        """
        message = ''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        _log_error(message)
        self._broadcast({'type': 'error', 'message': message})

    # -- tree access (for rendering) -------------------------------------

    @property
    def roots(self) -> tuple[Component, ...]:
        return tuple(self._roots)

    @property
    def components(self) -> dict[str, Component]:
        return self._components
