# Running Apps

`sc.run` starts a Streamlit Canary app. It accepts either the app function
itself or a path to a script or module.

```python
import streamlit_canary as sc


def app():
    sc.PageTitle('Hello')
    sc.Text('This page has no rerun loop.')


if __name__ == '__main__':
    sc.run(app, port=2201)
```

## `sc.run`

```python
sc.run(
    target,
    port=3001,
    *,
    blocking=True,
    host=None,
    show_window=False,
    window_size=(1200, 900),
    window_pos='center',
    window_title=None,
    window_icon=None,
    icon=None,
    title=None,
    extra_args=(),
)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `target` | callable or `str` | The app function, a `.py` path, or a module path |
| `port` | `int` | Port to listen on, default `3001` |
| `blocking` | `bool` | Whether `run()` waits for the app to end |
| `host` | `str` or `None` | Interface to bind |
| `show_window` | `bool` | Open the app in a native window |
| `window_size` | tuple or keyword | Window size in CSS pixels |
| `window_pos` | position | Window position, default `'center'` |
| `window_title` | `str` | Window title |
| `window_icon` | `str` | Window icon path |
| `icon` / `title` | `str` | Aliases of `window_icon` / `window_title` |
| `extra_args` | sequence of `str` | Extra arguments for a path target |

It returns a pair:

```python
server_process, window_process = sc.run(app)
```

Either element may be `None` when that process does not exist.

### Callable targets

A callable is served in the current process:

```python
sc.run(app, port=2201)
```

With `blocking=True` (the default), `run()` does not return until the
server stops. With `blocking=False`, the server is started on a daemon
thread and `run()` returns at once; the caller must keep the process
alive.

### Path targets

A `.py` path is launched in a child process:

```python
sc.run('app.py', port=2201)
```

A module path is launched with `python -m`:

```python
sc.run('my_project.app', port=2201)
```

Arguments left over from the command line can be forwarded:

```python
sc.run('app.py', extra_args=('--debug',))
```

The child process calls `sc.run` again on its own. Return values therefore
describe the child process.

### Host

`host` chooses the interface to bind:

- `'0.0.0.0'`: all interfaces; the app is reachable on the LAN.
- `'127.0.0.1'`: this machine only.
- `'localhost'`: this machine only, including IPv6 loopback.

When `host` is omitted, it follows `show_window`:

- `show_window=True`: `'localhost'`, because a desktop window is a local
  session and binding every interface would only earn a firewall prompt;
- otherwise: `'0.0.0.0'`.

## Opening a native window

`show_window=True` serves the app and opens it in a desktop window through
`pyapp-window`:

```python
sc.run(
    app,
    port=2201,
    show_window=True,
    window_size=(980, 760),
    window_title='My App',
    window_icon='assets/app.ico',
)
```

The window is not a browser tab; it is a native webview. Closing it ends
the session. With `blocking=True`, the server is stopped as well.

### `window_size`

`window_size` is the **page viewport**, in CSS pixels. A 700x600 window
shows 700x600 CSS pixels of the page regardless of the display's scale
factor, so the layout sees exactly the size requested.

```python
window_size=(1200, 900)   # width, height
window_size='maximized'
window_size='fullscreen'
```

The window manager may crop the requested box when it does not fit the
screen. Size the window from the layout the app builds, not from a fixed
guess: a form with a known number of rows has a known height.

### `window_pos`

The default is `'center'`. A screen position can also be passed the way
`pyapp-window` accepts it. Leave it alone unless the app has a reason to
place itself.

### `window_title` and `window_icon`

`window_title` sets the OS window title. If omitted, the title is
`'Streamlit Canary Application'`.

`window_icon` points to an icon file for the window.

`title` and `icon` are shorter aliases:

```python
sc.run(app, show_window=True, title='My App', icon='app.ico')
```

### Platform note

The window backend is provided by `pyapp-window`. On Windows, its `toga`
backend requires .NET 10. If the runtime is installed outside the default
location, point `DOTNET_ROOT` at it before starting the app.

## Blocking behavior

| Target | `blocking=True` | `blocking=False` |
| --- | --- | --- |
| Callable | Serves in the current thread until stopped | Serves on a daemon thread and returns |
| Path / module | Waits for the child process | Leaves the child running and returns |

With `show_window=True` and `blocking=True`, `run()` waits for the window
to close and then stops the server.

## Stopping an app

- Press Ctrl+C in the terminal that started a blocking server.
- With a native window, close the window.
- With `blocking=False`, the caller owns the process (for a callable) or
  the returned child process (for a path target).

The server exposes a `/shutdown` endpoint, which is how a window session
asks the serving child to stop cleanly before falling back to terminating
it.

## Related pages

- [The Event Driven System](./components/event-driven-system.md)
- [Session State](./components/session-state.md)
