# SingleTreeSelect

The single-pane folder browser: one folder on show at a time, with `..` to
walk up.

```python
with v3.Popover('Browse', panel_align='row', panel_max_height=500):
    tree = v3.SingleTreeSelect(filter='.txt')

path = tree.value.get()
```

Layout:

```
[ /current/folder v ] [home] [refresh] [bucket] [mode]   <- toolbar
..   (go to parent)
subfolder/                                        ->
another-file.txt
[                    Confirm                    ]
```

## Arguments

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label above the panel |
| `start_directory` | `str` | Folder to open, default the cwd |
| `home_directory` | `str` | Where `home` returns; defaults to `start_directory` |
| `filter` | `str` or tuple | Suffixes to keep |
| `height` | `int` | Cap the listing height and scroll |
| `width` | size keyword | Panel width |
| `selection_mode` | `str` or tuple | `'single'`, `'multiple'`, `'multicross'`, `'none'` |
| `initial_mode` | `str` | Which offered mode opens |
| `show_confirm_button` | `bool` | Default `True` |
| `border` | `bool` | Draw a frame; defaults to standalone |
| `label_visibility` | `str` | See [Inputs](../inputs/index.md) |
| `help` | `str \| Property` | Tooltip |

`leading` and `trailing` are builders run at the head and tail of the
toolbar row. They are used by wrappers to put their own widgets around the
actions, not usually by an app.

## Properties

- `value`: the selection.
  - `'single'`: one path, or `''`.
  - Multi modes: a list of paths.
- `mode`: the active mode.
- `directory`: the folder on show (read-only).
- `rows_visible`: whether the listing is drawn.

Prefer `select()` and `clear()` over writing `value` directly; those keep
the listing in step.

## Signals

- `value.on_change`: the selection changed.
- `on_navigate(directory)`: the listing moved to a new folder.
- `on_submit(paths)`: Confirm was clicked; carries the resolved paths.

## Methods

- `reload()`: re-read the current folder from disk.
- `select(path)`: add a path that is not in the listing.
- `clear()`: drop the selection.
- `resolve()`: the paths Confirm reports.
- `open_path(path)`: move the panel onto what a path names.

## Widgets

`tree.widgets` exposes two sub-components:

- `bottom_bar`: the `Row` under the listing. Enter it to append actions
  after the Confirm button.
- `confirm_button`: the button itself, reachable even when hidden.

```python
with tree.widgets['bottom_bar']:
    v3.Button('Open input folder')
```

## Selection modes

- `'single'` picks one node.
- `'multiple'` holds picks within the folder being browsed. Walking away
  drops them.
- `'multicross'` gathers picks into a bucket across folders. Only a mode
  set containing it draws the bucket.
- `'none'` draws no boxes; the rows are read-only.

A tuple draws a mode switch, but only when it contains more than one mode.
