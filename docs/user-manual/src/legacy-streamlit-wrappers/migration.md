# Migrating to the default components

V1 and the event-driven components can live in the same process, but they do
not share a component tree. An app should use only `sc.*` components inside
its app function.

## The mental model

V1:

```python
import streamlit as st

count = st.session_state.get('count', 0)

if st.button('Increase'):
    count += 1
    st.session_state.count = count

st.text('Click count: {}'.format(count))
```

V3:

```python
import streamlit_canary as sc


class State(sc.StateV2):
    count = sc.Property(0)


state = State()


def app():
    with sc.Text('Click count: 0') as txt:
        @state.count.on_change.partial(sc._self)
        def _(cnt):
            txt.text.set('Click count: {}'.format(cnt.get()))

    with sc.Button('Increase') as btn:
        @btn.on_click
        def _():
            state['count'] += 1
```

The differences:

1. **The app function runs once.** There is no `if st.button(...)` branch
   that runs on the next rerun.
2. **State is explicit.** `StateV2` fields are `Property` objects, not
   dictionary entries.
3. **Widgets expose properties and signals.** You attach a handler with
   `@widget.on_click` or `@widget.value.on_change` instead of reading a
   return value.
4. **Updates are pushed.** Changing `txt.text` sends a patch; the browser
   replaces that text node.

## A practical checklist

- Replace `st.session_state` with a `StateV2` subclass.
- Replace `st.button(...)` plus an `if` branch with `sc.Button(...)` plus
  `@button.on_click`.
- Replace "read the widget's return value" with `widget.value.get()`.
- Replace "write a widget's value by assigning its return value" with
  `widget.value.set(...)`.
- Move conditional rendering into a `Container(visible=...)` or an
  `Expander`, rather than skipping code on a rerun.
- Replace `st.rerun()` with a state change. A rerun is neither needed nor
  available in the V3 runtime.

## Things that do not translate one to one

- A V3 component is created once. If a widget should not exist at all, keep
  it hidden with `visible=False` instead of not creating it.
- Layout is built with context managers (`with sc.Row(): ...`), not by
  assigning columns to variables.
- Server-side code inside a handler runs on a worker thread. Keep handlers
  short, and do not block the event loop for long periods.
