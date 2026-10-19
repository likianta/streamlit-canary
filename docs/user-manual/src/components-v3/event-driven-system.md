# The Event Driven System

Streamlit Canary replaces Streamlit's rerun loop with a persistent
component tree and a small event protocol.

## The old model

In Streamlit, a widget interaction triggers a full script rerun:

```
click -> rerun script -> rebuild the UI -> diff -> send the page
```

The cost grows with the size of the script, not with the size of the
change. A large app pays the whole price for one checkbox.

## The V3 model

In V3, the app function runs once:

```
start -> run app() once -> build the component tree -> render HTML
click -> WebSocket event -> find the handler -> update properties
      -> send delta patches -> patch the DOM
```

The app function is never called again for that session. A handler runs
only the code registered on the signal that fired.

## The pieces

### Runtime

`sc.run(app_function, port=2201)` starts a Starlette + Uvicorn server. The
runtime keeps one component tree per session and owns the WebSocket
endpoint. It is a no-rerun runtime: there is no script re-execution path.

### Component tree

Components are nested with context managers:

```python
with sc.v3.Row('center'):
    sc.v3.Text('Left')
    sc.v3.Button('Right')
```

Each component has an `id`, a `parent`, and `children`. The tree is built
once and kept for the life of the session.

### Properties

A `Property` is a reactive value container:

```python
count = sc.Property(0)
count.set(1)
print(count.get())     # 1
```

Setting a value emits `on_change` only when the value actually changes.
Pass `notify=True` to force a notification when something outside the
value changed but the rendered result still needs a refresh.

### Signals

A `Signal` is a publish / subscribe primitive with no value:

```python
clicked = sc.Signal()

@clicked
def handler():
    print('clicked')

clicked.emit()
```

Signals may declare payload types:

```python
changed = sc.Signal(int)
changed.emit(42)
```

### Handlers

A component exposes named signals:

```python
with sc.v3.Button('Save') as button:
    @button.on_click
    def _():
        ...
```

`on_click`, `on_change`, `on_submit`, and the other signals are ordinary
`Signal` objects. A handler runs on a daemon worker thread, so a long
operation does not block the WebSocket loop.

### Delta patches

When a property changes, the runtime serializes the new value and sends a
patch naming the component and the field. The browser updates that field
in place. No HTML page is reloaded.

Some elements own client-side state that never reaches the server:
expanding an `Expander`, switching a `Tabs` panel, opening a `Popover`.
Those interactions are handled entirely in the browser.

## Binding values

`sc.bind` derives a property from one or more sources:

```python
label = sc.bind(state.count, lambda n: 'Count: {}'.format(n))
```

The derived property updates when a source changes. A `Signal` may be
listed beside the value sources as a trigger: it forces a recomputation
even when the value comes out the same, which is useful when the rendered
result depends on more than the value.

```python
label = sc.bind(
    (state.items, state.reloaded),
    lambda pair: ', '.join(pair[0]),
)
```

`sc.bbind` binds in both directions:

```python
v3.NumberInput('Channel', sc.bbind(state.channel))
```

The widget mirrors the state, and a user edit writes back into it.

## What a handler should do

A handler is the equivalent of the body of an `if st.button(...)` branch,
but it runs only when that event happens. It should:

- update one or more properties;
- keep the work short;
- avoid touching the component tree (create components in `app()`, not in
  a handler).

```python
with sc.v3.Button('Load') as button:
    @button.on_click
    def _():
        state.status.set('loading')
        data = load_data()
        state.rows.set(data)
        state.status.set('ready')
```

Reading a property gives its current value. Writing it schedules a patch.

## Ordering and batching

During a single event, property writes are staged and flushed together.
A derived property that depends on several sources is recomputed once,
after the last declared source has settled. This keeps a multi-field
update from producing a chain of intermediate renders.

## Client-side interactions

Not every interaction needs the server. The following are local to the
browser:

- opening and closing an `Expander`;
- switching `Tabs`;
- opening and closing a `Popover` (the server can still call `close()`);
- folding a folder row in a tree;
- highlighting a row.

The server is told only about the results it needs: a new `value`, a
submitted path, a closed dialog.

## Summary

| Concept | Role |
| --- | --- |
| `sc.run` | Starts the persistent runtime |
| Component tree | The UI, built once per session |
| `Property` | A reactive value |
| `Signal` | An event with no value |
| Handler | The code that reacts to one event |
| Delta patch | The small update sent to the browser |
| `sc.bind` / `sc.bbind` | Derived and two-way values |
