# Streamlit Canary

## Usage

### Session State

There are two code styles for accessing session data. The first is short but
the IDE may not be able to autocomplete its keys; the second is more verbose
but make IDE's autocomplete work:

Style 1:

```python
import streamlit_canary as sc
if not (state := sc.session.get_state(<target_version>)):
    state.update({'key1': 'value1', 'key2': 'value2'})
```

Style 2:

```python
import streamlit_canary as sc
if not (x := sc.session.get_state( < target_version >)):
    x.update(state := {'key1': 'value1', 'key2': 'value2'})
else:
    state = x
```
