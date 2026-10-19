# DualTreeSelect

A two-column browser: subfolders on the left, files on the right.

```python
with v3.DualTreeSelect('data/sample', filter='.txt') as tree:
    @tree.on_confirm
    def _():
        path = tree.value.get()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `start_directory` | `str` | Folder to open, default the cwd |
| `filter` | `str` or tuple | Suffixes to keep |
| `height` | `int` | Height of both columns, default `500` |
| `node_type` | `'file' \| 'folder'` | What may be selected, default `'file'` |
| `preview_subfolders` | `bool` | Also list the highlighted subfolder's contents |
| `show_confirm_button` | `bool` | Default `True` |
| `width` | size keyword | Panel width |

Properties: `value` (the highlighted path), `directory` (the folder the
left column is on).

Signals: `on_confirm`.

Methods: `reload()`.

## Left column

The left column navigates subfolders:

- back;
- forward (enter the highlighted subfolder);
- refresh;
- create a new folder.

The "Current location" bar at the top lists every ancestor, so any parent
is one pick away.

## Right column

The right column lists the files of the current folder, or the files of
the highlighted subfolder when `preview_subfolders=True`. A single click on
a subfolder previews it.

`value` follows the highlighted row, so it is live rather than waiting for
Confirm.

## Confirm

With `show_confirm_button=True`, the Confirm button is disabled while
nothing is selected. Clicking it emits `on_confirm`.

## Differences from the other panels

- It is single-select only; there are no modes.
- It has no `selection_mode`, `label`, or `help` arguments.
- Its toolbar is its own (back / forward / refresh / new folder), so
  `PathInputBrowse` uses it only in the popup style.
