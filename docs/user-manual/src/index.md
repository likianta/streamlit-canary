# Streamlit Canary User Manual

Streamlit Canary is a fork of Streamlit with an **event-driven runtime** and
a new component library called **Components V3**. It keeps Streamlit's
familiar look and feel, but removes the rerun cycle that makes large apps
slow.

The application function runs **once**. It builds a persistent component
tree, and every later interaction is routed to a signal handler on the
server. Only the values that actually changed are sent back to the browser
as small patches, and the page updates in place.

## What makes it different

|                   | Streamlit                                   | Streamlit Canary (V3)                              |
| ----------------- | ------------------------------------------- | -------------------------------------------------- |
| Execution model   | The script reruns on every interaction      | The app function runs once                         |
| UI updates        | A new render tree is diffed on every rerun  | A delta patch updates the affected DOM nodes       |
| State             | `st.session_state` is rebuilt on each rerun | `StateV2` holds `Property` objects for the session |
| Widgets           | Return values from the last run             | Expose reactive `Property` fields and `Signal`s    |
| Cost of one click | Proportional to the whole script            | Proportional to the handlers that listen to it     |

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
- **Fewer dependencies.** The core does not require pandas, NumPy, SciPy,
  pyarrow, or Altair. Altair is needed only if you use `AltairChart`.

## Installation

```bash
pip install streamlit-canary
```

Python 3.11 or newer is required.

> [!WARNING]
> Streamlit Canary evolves from 0.1.0 to 0.4.0 (the latest version), it contains three generation of implementations in one code base:
>
> - The components V1, which are wrappers of Streamlit components, not event-driven.
> - Components V2, broken, unable to use.
> - Components V3, the event-driven structure.
>
> We will remove V1 and V2, then strip V3 prefix and make it default in the future. Currently be noted they are all importable, by exclusive statements (e.g. `from streamlit_canary import components_v3 as v3`). Current codebase and examples follow the way, they will be updated once refactoring is done.

## Hello world

```python
import streamlit_canary as sc
from streamlit_canary import components_v3 as v3


class State(sc.StateV2):
    count = sc.Property(0)


state = State()


def app():
    v3.PageTitle('Click Counter')

    with v3.Row('center'):
        with v3.Text('Click count: 0') as txt:
            @state.count.on_change
            def _():
                txt.text.set('Click count: {}'.format(state.count.get()))

        with v3.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state.count.set(state.count.get() + 1)
                # or a shorthand form: state['count'] += 1


if __name__ == '__main__':
    sc.run(app, port=2201)
```

Save the file and run it with `python app.py`. Open
`http://localhost:2201`, then click the button. The text changes without a
page reload, and `app()` is not called again.

## How this manual is organized

- **Components V1 (Legacy)** documents the original Streamlit-based API
  that still ships with the package.
- **Components V2 (Broken)** describes an abandoned transitional
  implementation. It is kept only for historical reference.
- **Components V3** explains the runtime model, session state, and every
  component in the V3 library.
- **Roadmap** lists the work that is planned next.

If you are starting a new app, read
[Running Apps](./running-apps.md),
[The Event Driven System](./components-v3/event-driven-system.md), and
[Session State](./components-v3/session-state.md) first, then use the
[API Reference](./components-v3/api-reference/index.md) as a lookup.
