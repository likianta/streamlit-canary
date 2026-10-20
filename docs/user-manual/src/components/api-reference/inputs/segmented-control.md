# SegmentedControl and SelectSlider

Both widgets choose one value from a fixed list, but present it
differently.

## `SegmentedControl`

A row of pills inside one rounded track.

```python
with sc.SegmentedControl(
    'View',
    options=('List', 'Grid', 'Tree'),
    value='List',
) as control:
    @control.on_switch
    def _(value):
        change_view(value)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence \| Property | Choices |
| `index` | `int` | Selected position |
| `value` | any | Selected value |
| `format` | callable or sequence | Labels |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `index`, `value`.

Signals: `on_switch` (the new value), `value.on_change`.

`on_switch` fires only for a user click. A programmatic `value.set` or
`index.set` stays silent, so a listener can tell a click apart from a
refresh.

The track hugs its options by default (`width='content'`). Pass
`width='stretch'` to fill the parent.

Only single selection is implemented.

## `SelectSlider`

A slider whose ticks are a fixed set of options.

```python
with sc.SelectSlider(
    'Start level',
    options=range(15, 0, -1),
    value=15,
    format=lambda x: 'Lv.{}'.format(x),
) as slider:
    @slider.value.on_change
    def _():
        start_level.set(slider.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence \| Property | Discrete choices |
| `index` | `int` | Selected position |
| `value` | any | Selected value |
| `format` | callable or sequence | Labels |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `index`, `value`.

Signals: `value.on_change`.

Every option is a tick on one track. Clicking or dragging to a tick
selects it; the interaction is client-side and the result comes back as a
change event. The slider fills its parent by default.
