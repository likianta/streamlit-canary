# Floating

A container that sticks to a corner of its parent's visible area.

```python
with v3.Popover('Browse', panel_max_height=420):
    with v3.FloatingContainer('top-right'):
        v3.IconButton('refresh')
    v3.RadioGroup('Folder contents', options=('a.txt', 'b.txt'))
    with v3.FloatingContainer('bottom-right'):
        v3.Button('Confirm', type='primary')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `position` | `'top-left'`, `'top-center'`, `'top-right'`, `'bottom-left'`, `'bottom-center'`, `'bottom-right'` | Required |
| `width`, `height`, ... | size keywords | See `Container` |

Properties: `border_title`, `visible`.

`Floating` is an alias of `FloatingContainer`.

## How it behaves

- Children lay out in a row; the cluster hugs them.
- The box sticks to its corner of the parent's visible area, so content
  scrolls underneath while the box stays put.
- It keeps its place in the layout (`position: sticky`, not an overlay),
  so the parent needs no extra padding.

## Where it may go

A floating cluster must sit directly in a vertical layout:

- a `Container`,
- a `Popover`,
- a `Dialog`,
- or the app root.

Anything else raises `ValueError`. A `Row` cannot hold one, because the
corner's horizontal half comes from `align-self`, which a row would fight.

## Authoring order

Sticky positioning can only offset a box from its own flow position:

- author a `top-*` cluster as the parent's **first** child;
- author a `bottom-*` cluster as the parent's **last** child.

A bottom cluster also receives `margin-top: auto`, so it drops to the end
of the remaining room.
