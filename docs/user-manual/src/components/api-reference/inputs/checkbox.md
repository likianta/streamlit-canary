# Checkbox and Group

## `Checkbox`

A single tick box.

```python
with sc.Checkbox('Enable caching', value=True) as box:
    @box.value.on_change
    def _():
        cache_enabled.set(box.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `value` | `bool \| Property` | Checked state, default `False` |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `value`.

Signals: `value.on_change` (`box['on_value']`).

## `CheckGroup`

A group of tick boxes for choosing several values.

```python
with sc.CheckGroup(
    'Extras',
    options=('Deps', 'Docs', 'Tests'),
    value=('Deps', 'Tests'),
) as group:
    @group.on_change
    def _():
        print(group.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence, dict, or Property | Choices |
| `value` | sequence \| Property | Ticked values |
| `format` | callable or sequence | Labels |
| `horizontal` | `bool` | Lay out in a row |
| `max_height` | `int` | Cap and scroll the list |
| `enabled` | `bool \| Property` | Whether input is accepted |
| `box_disabled` | callable | Predicate for rows that cannot be ticked |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `value`, `focused_index`.

Signals: `on_change` (same as `value.on_change`), `options.on_change`.

### Dictionary form

Passing a dictionary spells each option's starting state:

```python
sc.CheckGroup('Extras', options={'Deps': True, 'Docs': False})
```

The keys become `options`, and `value` becomes a list of booleans parallel
to `options`, not a subset of them. This is useful when a caller wants to
keep the flags in a fixed order.

### Focused row

`focused_index` is the row the client last clicked, or `-1`. It can drive
an action that applies to the highlighted row:

```python
sc.Button(
    'Open',
    enabled=sc.bind(group.focused_index, lambda i: i >= 0),
)
```
