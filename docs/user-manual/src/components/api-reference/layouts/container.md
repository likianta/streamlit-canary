# Container

A vertical box for grouping components. `Column` is an alias of
`Container`.

```python
with sc.Container(border=True, border_title='Settings', height=320):
    sc.Checkbox('Enable caching')
    sc.NumberInput('Workers', value=4)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `width` | size keyword | Width |
| `weight` | `float` | Flex-grow ratio inside a `Row` |
| `border` | `bool` | Draw a frame |
| `border_title` | `str \| Property` | Title drawn in the top border |
| `height` | size keyword | Fixed height; content scrolls |
| `animated` | `bool` | Animate the height when `visible` flips |
| `visible` | `bool \| Property` | Default `True` |

Properties: `border_title`, `visible`.

## Scrolling

A fixed `height` caps the box and makes it scroll:

```python
with sc.Container(height=240):
    for line in lines:
        sc.Text(line)
```

`max_height` has the same effect. `min_height` does not.

## Stretching inside a row

`height='stretch'` makes the container fill the parent's height. Inside a
`Row`, it spans the row's tallest sibling:

```python
with sc.Row():
    with sc.Container(height='stretch'):
        sc.Text('Left')
    with sc.Container(height='stretch'):
        sc.Text('Right')
```

## Showing and hiding

`visible` controls whether the container is rendered. `animated=True`
transitions the height instead of making it pop:

```python
with sc.Container(visible=state.show_advanced, animated=True):
    sc.Text('Advanced options')
```

The container stays in the tree either way, so a later patch can bring it
back.

## Border title

`border_title` is only honored with `border=True`. It is drawn inline in
the frame, the way a `<legend>` sits in a fieldset.
