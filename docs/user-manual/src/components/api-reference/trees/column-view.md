# ColumnView

A Finder-style stack of columns, one level per column.

```python
with sc.ColumnView('Pick a file', 'data/sample') as tree:
    ...

path = tree.value.get()
```

Layout:

```
[ /current/folder v ] [home] [refresh]        <- toolbar
+---------+ +---------+ +---------+
| alpha/  | | one.py  | | a.txt   |
| beta/   | | two.py  | | b.txt   |
+---------+ +---------+ +---------+
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `start_directory` | `str` | Folder the first column opens on |
| `filter` | `str` or tuple | Suffixes to keep |
| `height` | `int` | Height of every column, default `500` |
| `max_columns` | `int` | Columns on show at once, default `4` |
| `home_directory` | `str` | Where `home` returns |
| `accept_new_option` | `bool` | Offer a typed path in the location bar |
| `show_location` | `bool` | Draw the location ladder |
| `show_confirm_button` | `bool` | Default `True` |
| `rows_visible` | `bool \| Property` | Whether the columns are drawn |
| `label_visibility` | `str` | See [Inputs](../inputs/index.md) |
| `help` | `str \| Property` | Tooltip |

Properties: `value`, `mode` (always `'single'`), `directory` (the folder
the rightmost column shows).

Signals: `on_navigate(directory)`, `on_submit(paths)`.

Methods: `reload()`, `select(path)`, `clear()`, `resolve()`.

## Interaction

- Clicking a folder opens its contents in a new column to the right.
- Clicking a file marks it.
- Clicking a folder in a column further left replaces everything to its
  right, so the whole trail stays on show.
- The panel needs no "go up" row; the trail is the way back.

## `value`

Single-select. It names the node picked in the rightmost column, or that
column's folder while nothing inside is picked. A column view always has a
current folder, so `value` is never empty.

## Windowing

At most `max_columns` columns are on show. Walking deeper scrolls the
earlier ones out; the window keeps the last `max_columns` folders, so the
column just opened stays visible. The location ladder and `home` still
reach any ancestor in one pick.

## Toolbar

The toolbar holds the location ladder, `home`, and `refresh`. With
`leading` / `trailing`, a wrapper can add its own widgets around them.
