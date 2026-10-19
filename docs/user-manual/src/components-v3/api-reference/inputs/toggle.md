# Toggle

A sliding on / off switch.

```python
with v3.Toggle('Auto refresh', value=True) as toggle:
    @toggle.value.on_change
    def _():
        auto_refresh.set(toggle.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `value` | `bool \| Property` | On / off state, default `False` |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `value`.

Signals: `value.on_change` (`toggle['on_value']`).

`Toggle` is an alias of `ToggleBox`. Its fields match `Checkbox`; only the
visual differs.

## `Toggle` versus `ToggleButton`

- `ToggleBox` (`Toggle`) is an input widget: it belongs among other form
  controls and has a label above it.
- [`ToggleButton`](../buttons.md) is a button that stays lit. It belongs
  in a toolbar, and its `type` is derived from its state.
