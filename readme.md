# Streamlit Canary

LK-flavored Streamlit components, plus an **event-driven (no-rerun)** runtime.

## Event-driven (v3)

The app function runs **once** to build a component tree. Later interactions
only run the handlers registered on signals, and the frontend patches the DOM
in place (no page reload). See
`test/event_driven_system/demo_click_counter.py` for a runnable minimal
example.

## Usage

### Session State

`sc.init_state` returns state that survives Streamlit reruns. There are two 
code styles: the short one, where the IDE may not autocomplete the keys; and 
the verbose one, where it does.

Style 1 (short -- keys are plain strings):

```python
import streamlit_canary as sc
state = sc.init_state(
    lambda: {'name': '', 'code': 0, 'flag': False},
    version=0,
)
```

Style 2 (verbose -- declare the fields on a class):

```python
import streamlit_canary as sc

class _State:
    def __init__(self):
        self.name = ''
        self.code = 0
        self.flag = False

state = sc.init_state(_State, version=0)
```

`version` controls schema migration: when the stored version differs, the
state is rebuilt. Bump it (or set `__version__` on the class) whenever the
field layout changes.
