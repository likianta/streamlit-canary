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

| | Streamlit | Streamlit Canary (V3) |
| --- | --- | --- |
| Execution model | The script reruns on every interaction | The app function runs once |
| UI updates | A new render tree is diffed on every rerun | A delta patch updates the affected DOM nodes |
| State | `st.session_state` is rebuilt on each rerun | `StateV2` holds `Property` objects for the session |
| Widgets | Return values from the last run | Expose reactive `Property` fields and `Signal`s |
| Cost of one click | Proportional to the whole script | Proportional to the handlers that listen to it |

## Installation

```bash
pip install streamlit-canary
```

Python 3.11 or newer is required.

The manual tracks the `0.4.x` line. The latest published release may lag
behind the repository while a version is being prepared.

## Hello world

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
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))

        with sc.v3.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state['count'] += 1


if __name__ == '__main__':
    sc.run(app, port=2201)
```

Save the file and run it with `python app.py`. Open
`http://localhost:2201`, then click the button. The text changes without a
page reload, and `app()` is not called again.

## How this manual is organized

- **Components V3** explains the runtime model, session state, and every
  component in the V3 library.
- **Components V1 (Legacy)** documents the original Streamlit-based API
  that still ships with the package.
- **Components V2 (Broken)** describes an abandoned transitional
  implementation. It is kept only for historical reference.
- **Roadmap** lists the work that is planned next.

If you are starting a new app, read
[The Event Driven System](./components-v3/event-driven-system.md) and
[Session State](./components-v3/session-state.md) first, then use the
[API Reference](./components-v3/api-reference/index.md) as a lookup.
