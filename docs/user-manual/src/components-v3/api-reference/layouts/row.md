# Row

A horizontal layout container.

```python
with v3.Row('center'):
    v3.IconButton('home')
    v3.Space()
    v3.Button('Save')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `vertical_alignment` | `'top' \| 'center' \| 'bottom'` | Cross-axis alignment, default `'top'` |
| `hide_when_empty` | `bool` | Hide the row when every child is hidden |
| `width`, `height`, ... | size keywords | The row's own size |

Properties: `visible`.

## Alignment

`vertical_alignment` decides how children line up when they differ in
height:

```python
with v3.Row('bottom'):
    v3.Text('Label')
    v3.TextInput('Value')
```

## Wrapping

A `Row` lays children out left to right and wraps when there is not enough
width. The horizontal gap is used between items on one line; the vertical
gap is used between wrapped lines.

## `hide_when_empty`

A row that exists only to be filled later still costs its parent one gap,
because a zero-height box is still a box. Set `hide_when_empty=True` to
hide the row while all of its children are hidden:

```python
with v3.Row(hide_when_empty=True):
    v3.Button('Retry', visible=state.failed)
```

This is decided at render time. A child that a later patch turns visible
does not bring the row back, because patches reach the child, not its
parent.
