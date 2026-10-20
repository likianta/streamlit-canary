# Radiobox and Group

## `RadioGroup`

A group of radio buttons for choosing exactly one value.

```python
with sc.RadioGroup(
    'Project scope',
    options=('All', 'Current', 'Selected'),
    value='Current',
) as radio:
    @radio.value.on_change
    def _():
        scope.set(radio.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence \| Property | Choices |
| `index` | `int` | Selected position |
| `value` | any | Selected value |
| `format` | callable or sequence | Labels |
| `horizontal` | `bool` | Lay out in a row |
| `max_height` | `int` | Cap and scroll the list |
| `enabled` | `bool \| Property` | Whether input is accepted |
| `box_disabled` | callable | Predicate for rows that cannot be selected |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `index`, `value`, `focused_index`.

Signals: `value.on_change` (`radio['on_value']`), `options.on_change`.

`Radio = RadioGroup` is an alias, matching the name used in some
Streamlit examples.

## Choosing between `RadioGroup` and `Selectbox`

Use `RadioGroup` when every option should be visible at once and the list
is short. Use [`Selectbox`](./selectbox.md) when the list is long or the
space is tight.

## Disabled rows

`box_disabled` marks rows that are visible but cannot be selected:

```python
sc.RadioGroup(
    'Target',
    options=('dev', 'prod'),
    box_disabled=lambda x: x == 'prod',
)
```

The tree panels use this for the `..` navigation row, which is a target
for a click but not a value.
