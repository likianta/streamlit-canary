# Session State

`State` is the base class for application state. It is a
`PropertyHost`: a plain object whose fields are reactive `Property` and
`Signal` handles.

## Declaring state

The simplest form declares fields inside `__init__`:

```python
import streamlit_canary as sc


class State(sc.State):
    def __init__(self):
        super().__init__()
        self.count = sc.Property(0)
        self.name = sc.Property('')


state = State()
```

A field may also be declared by annotation. `PropertyHost` builds one
handle per instance:

```python
class State(sc.State):
    count: sc.Property[int] = 0
    name: sc.Property[str]
    reloaded: sc.Signal
```

- `Property[int]` with a class-body value uses that value as the default.
- Without a class-body value, a primitive type starts from its zero value
  (`int` -> `0`, `str` -> `''`, `list` -> `[]`, ...; each instance gets its
  own), while any other type -- a class of your own, a union such as
  `bool | None` -- starts as `sc._undefined` (see
  [Special markers](./event-driven-system.md#special-markers)).
- `Signal` declares no payload; `Signal[int]` declares one positional
  payload.

Do not declare a `Property` instance at class level unless the state class
has a single instance. Class-level properties are shared between
instances.

## Reading and writing

```python
state.count.get()        # 0
state.count.set(1)       # 1, emits state.count.on_change
state['count']           # 1
state['count'] = 2       # 2
state['on_count']        # state.count.on_change
```

`state.count += 1` is not supported by the property object itself. Use
the subscript form, which the runtime maps to `get` and `set`:

```python
state['count'] += 1
```

## Reacting to changes

```python
@state.count.on_change
def _():
    print('count is now', state.count.get())
```

A handler may receive the property handle or its current value:

```python
@state.count.on_change.partial(sc._self)
def _(prop):
    print(prop.get())

@state.count.on_change.partial(sc._value)
def _(value):
    print(value)
```

## Binding

A derived value is created with `sc.bind`:

```python
double = sc.bind(state.count, lambda n: n * 2)
```

A two-way binding is created with `sc.bbind`:

```python
sc.NumberInput('Count', sc.bbind(state.count))
```

See [The Event Driven System](./event-driven-system.md) for the full
explanation of triggers, multiple sources, and the `default=` / `fallback=`
starting values.

## Versioning

`State` tracks a schema version:

```python
class State(sc.State):
    __version__ = 2
    ...
```

or pass it explicitly:

```python
state = State(version=2)
```

The version is currently metadata (`state.version`). It gives the app a
place to detect an incompatible state layout and rebuild it.

## Lifetime

State lives in the server process for the life of a session. Because the
app function does not rerun, a value written in one handler is still there
in the next handler.

This also means that state is **not** rebuilt from the script. If you need
a value to reset, reset it explicitly:

```python
state.count.set(0)
```

## Relationship to Streamlit's `session_state`

`State` replaces `st.session_state` for V3 apps. The two are not
synchronized. A V3 app should keep its state in `State` and pass it to
handlers by closure, or store it on the app object.
