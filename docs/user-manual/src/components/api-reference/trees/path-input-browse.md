# PathInputBrowse

A path box paired with one of the tree panels.

```python
with sc.PathInputBrowse(
    'Select a file',
    'data/sample',
    filter='.txt',
) as browse:
    ...

path = browse.value.get()
```

## Arguments

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str` | Path box label |
| `start_directory` | `str` | Path shown and folder opened |
| `panel_style` | `'popup' \| 'fold' \| 'inline'` | Where the panel lives |
| `expanded` | `bool` | Whether a foldable panel starts open |
| `tree_style` | `'single_list' \| 'tree_view' \| 'dual_pane' \| 'column_view'` | Which panel |
| `filter` | `str` or tuple | Suffixes to keep |
| `initial_mode` | `str` | Mode to open in |
| `selection_mode` | `str` or tuple | Modes offered |
| `input_history` | sequence, Property, or `None` | Seed for the box's history |
| `node_type` | `'file' \| 'folder'` | Dual-pane only |
| `panel_height` | `int` | Cap on the panel height |
| `width` | size keyword | Width |

Properties: `value`, `mode`, `directory`, `input_history`.

## `start_directory`

- `'.'` (the default): the cwd for both the box and the panel.
- `''`: the panel opens on the cwd, but the box is blank ("nothing picked
  yet").
- Any other value: shown in the box. If it names a file, the panel opens
  on its folder; otherwise on the value itself.

## Panel styles

### `'popup'` (default)

The panel lives in a `Browse` popover with its own toolbar and a Confirm
button.

- Confirm closes the popover and writes the choice into the box.
- The choice is the panel's pick, or, with nothing ticked, the folder the
  panel ended on.
- The choice also joins the selection, so `value` carries it.

Only this style accepts `tree_style='dual_pane'`, because the dual-pane
panel has its own toolbar and is not a good fit for the inline toolbar.

### `'fold'`

The panel sits under the box and is unfolded by a fold button.

- No popover, no Confirm.
- The fold button shows and hides the rows.
- The box follows the panel's pick live.

### `'inline'`

The panel sits under the box and is always on show.

## Toolbar takeover

In the fold and inline styles, the path box leads the panel's toolbar row
and the fold button (fold style only) trails it. The panel's own location
bar is turned off, because the box carries the ladder. `home`, `refresh`,
the bucket, and the mode control sit between them.

The box used here is a [`PathSelect`](./path-input.md), so clicking it
opens the navigation ladder and clicking the caret opens its history.

## `tree_style`

| Value | Panel |
| --- | --- |
| `'single_list'` | `SingleTreeSelect` |
| `'tree_view'` | `FileTreeView` |
| `'dual_pane'` | `DualTreeSelect` (popup only) |
| `'column_view'` | `ColumnView` |

## Typed paths

A path typed into the box and submitted moves the panel onto the folder
that holds it, and joins the panel's selection. A path that does not exist
names no folder, so the panel is left where it was.

Writes made by the wrapper itself are silenced, so a pick in the panel
does not echo back as a typed path and pull the panel away.
