# Bottom

A container that is pushed to the bottom of its parent layout.

```python
with v3.Container(height=320):
    v3.Text('Content')
    with v3.BottomContainer():
        v3.Button('Close')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `width`, `height`, ... | size keywords | See `Container` |
| `visible` | `bool \| Property` | Whether it is shown |

Properties: `border_title`, `visible`.

`Bottom` is an alias of `BottomContainer`.

## Inside a container

The parent pushes the bottom container down, so a card can keep its
actions at the bottom and a dialog can pin a button to its base.

## At the app root

At the app root, a bottom container becomes a **dock**:

- it hangs 16px above the window's bottom edge;
- it stays there while the page scrolls;
- the page reserves the dock's height at its end, so the last content can
  still be scrolled clear of it.

This is the same idea as `st.bottom`, but a canary `BottomContainer` is
allowed in any layout, not only at the root.
