# Popover

A trigger button that reveals a floating panel.

```python
with sc.Popover('Export requirements'):
    sc.RadioGroup('Mirror source', options=('PyPI', 'Local'))
    sc.Checkbox('Lock self', value=True)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Trigger label |
| `width` | size keyword | Trigger width, default `'content'` |
| `help` | `str \| Property` | Tooltip on the trigger |
| `enabled` | `bool \| Property` | Whether the trigger accepts clicks |
| `panel_align` | `'trigger' \| 'row' \| 'above'` | Panel placement |
| `panel_max_height` | `int` | Cap the panel height; it scrolls |
| `visible` | `bool \| Property` | Whether the trigger is shown |

Properties: `text`, `visible`.

Signals: `on_open`, `on_close`.

## Placement

- `'trigger'` (default): the panel opens under the trigger.
- `'row'`: the panel stretches across the surrounding `Row`.
- `'above'`: the panel opens above the trigger. Use this when the trigger
  sits at the bottom of a scrollable box, where a downward panel would be
  clipped.

## Opening and closing

Open and close are handled in the browser and do not reach the server.
Two signals report the ends:

```python
@popover.on_open
def _():
    refresh_preview()

@popover.on_close
def _():
    clear_preview()
```

Calling `popover.close()` asks the client to fold the panel away while
leaving the trigger in place. This is how a widget such as
`SingleTreeSelect` dismisses its own panel after a Confirm.

## Server-side state

The open / closed state lives in the browser; the server cannot read it.
Use `on_open` and `on_close` when work should happen only while the panel
is up.
