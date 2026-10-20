# Dialog

A modal dialog.

```python
with sc.Dialog('Select a file', visible=state.browsing) as dialog:
    sc.Text('...')
    sc.Button('Close', on_click=lambda: dialog.visible.set(False))
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Dialog title |
| `width` | `'small' \| 'medium' \| 'large' \| int` | Panel width |
| `visible` | `bool \| Property` | Whether the dialog is open |
| `max_height` | `int` | Cap the panel height; the panel scrolls |
| `min_height` | `int` | Floor the panel height |

Properties: `text`, `visible`.

Signals: `on_close`.

## Opening and closing

A V3 dialog is an ordinary component built once. Unlike `st.dialog`, it
does not decorate a function and it does not rerun when opened. Set
`visible` to open or close it:

```python
state.browsing.set(True)    # open
state.browsing.set(False)   # close
```

`visible` may be bound directly at construction, as in the example above.

## Width presets

| Value | Width |
| --- | --- |
| `'small'` | 500px (default) |
| `'medium'` | 750px |
| `'large'` | 1280px |
| `int` | Explicit pixels |

## Client dismissal

The close button, a click on the backdrop, and Escape all dismiss the
dialog. When that happens:

1. `visible` is set to `False`;
2. `on_close` is emitted.

```python
@dialog.on_close
def _():
    state.browsing.set(False)
```

The first step already closes the dialog; the signal lets your app clean
up or log the dismissal.

## Height

`max_height` and `min_height` apply to the panel, not to the full-screen
backdrop. A capped panel scrolls as a whole.
