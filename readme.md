# Streamlit Canary

Streamlit-flavored components with an **event-driven (no-rerun)** runtime.

The app function runs **once** to build a persistent component tree. Later
interactions run only the handlers registered on signals, and the browser
patches the DOM in place. There is no page reload and no script re-run.

## Highlights

- **Performant by design.** The app function runs once. An interaction
  executes only the handlers attached to it, then patches the DOM. The
  script never re-runs.
- **Reactive, polished event-driven syntax.** `sc.bind` and `sc.bbind`
  build derived and two-way values, `on_change` and component signals
  attach handlers, and a forced notification (`set(value, notify=True)`)
  refreshes output when the value itself did not change.
- **Desktop windows.** `sc.run(..., show_window=True)` serves the app and
  opens it in a native `pyapp-window` window, sized in CSS pixels.
- **Custom components included.** Folder trees, `PathInputBrowse`, a PDF
  viewer, a live log panel, animated toasts, and the rest of the V3
  library ship with the package.
- **`dunder_literal`.** `PageConfig(dunder_literal=True)` keeps names such
  as `__init__` and `__name__` from turning into bold text.
- **Fewer dependencies.** The V3 core runs without Streamlit, pandas,
  NumPy, SciPy, pyarrow, or Altair. Altair is needed only if you use
  `AltairChart`.

## Install

```bash
pip install streamlit-canary
```

Python 3.11 or newer is required.

## Quick start

```python
import streamlit_canary as sc


class State(sc.StateV2):
    count = sc.Property(0)


state = State()


def app():
    sc.v3.PageTitle('Click Counter')

    with sc.v3.Row('center'):
        with sc.v3.Text('Click count: 0') as txt:
            @state.count.on_change.partial(sc._self)
            def _(cnt):
                txt.text.set('Click count: {}'.format(cnt.get()))

        with sc.v3.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state['count'] += 1


if __name__ == '__main__':
    sc.run(app, port=2201)
```

Save it as `app.py`, run `python app.py`, and open
`http://localhost:2201`. Clicking the button updates the text in place;
`app()` is not called again.

## Native window

```python
sc.run(
    app,
    show_window=True,
    window_size=(980, 760),
    window_title='My App',
)
```

`window_size` is the page viewport in CSS pixels, so the layout receives
exactly the size requested, independent of the display scale factor.
`'maximized'` and `'fullscreen'` are also accepted.

## Examples

- [`examples/click_counter.py`](examples/click_counter.py) — the minimal
  event-driven app.
- [`examples/bind_multi_source.py`](examples/bind_multi_source.py) —
  single-source and multi-source `sc.bind`, plus batched updates with
  `sc.pending_updates()`.
- [`examples/tree_select_multicross.py`](examples/tree_select_multicross.py)
  — folder trees with single, multiple, and cross-folder selection.

Run any of them directly:

```bash
python examples/click_counter.py
```

## Documentation

The full user manual lives in
[`docs/user-manual/src/index.md`](docs/user-manual/src/index.md).

To preview it locally:

```bash
cd docs/user-manual
mdbook serve
```

## Components and namespaces

- `sc.v3.*` — the event-driven components. This is the recommended API.
- `sc.*` — the legacy V1 components, built on Streamlit and the rerun
  model. They will be removed in a future version.
- `sc.v2` — an abandoned transitional implementation. It is broken and
  will be removed.

The V3 library currently keeps the `v3` prefix to avoid colliding with the
legacy namespace. The prefix is planned to be dropped once V1 and V2 are
gone.
