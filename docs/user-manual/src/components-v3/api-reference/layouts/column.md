# Column

A vertical layout container inside a `Row`. `Column` is an alias of
`Container`, so it takes every `Container` argument plus `weight`.

```python
with v3.Row():
    with v3.Column(weight=5):
        v3.Text('Main pane')
    with v3.Column(weight=2):
        v3.Text('Side pane')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `weight` | `float` | Flex-grow ratio inside a `Row` |
| `width`, `height`, ... | size keywords | The column's own size |
| `border` | `bool` | Draw a border |
| `border_title` | `str \| Property` | Title in the border |
| `animated` | `bool` | Animate height when `visible` flips |

Properties: `border_title`, `visible`.

## Weights

`weight` decides how the leftover width is shared. A `(5, 2)` split is two
columns with `weight=5` and `weight=2`. Without weights, columns share the
width equally.

```python
with v3.Row():
    v3.Column(weight=3)
    v3.Column(weight=1)
```

A column is a full `Container`; see [Container](./container.md) for
borders, fixed heights, and scrolling.
