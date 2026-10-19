# FileTreeView

The classic cascading tree, backed by the real filesystem.

```python
with v3.FileTreeView('Source', start_directory='./data') as tree:
    ...

picked = tree.value.get()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `start_directory` | `str \| Property` | Folder to open; `'.'` and `''` mean the cwd |
| `root_directory` | `str \| Property` | Top the panel may not pass; default `'/'` |
| `home_directory` | `str` | Where `home` returns |
| `filter` | `str` or tuple | Suffixes to keep |
| `height`, `selection_mode`, ... | see `SingleTreeSelect` | |

Properties: `value`, `mode`, `directory`, `rows_visible`,
`start_directory`, `root_directory`.

Signals: `value.on_change`, `on_navigate`, `on_submit`.

Methods: `open_path(path)`, `reload()`, `select(path)`, `clear()`,
`resolve()`.

## `start_directory`

The folder the panel opens on. It is bindable: a caller that owns the
value can move the panel by setting it.

```python
tree.start_directory.set('C:/work/project')
```

## `root_directory`

The top the panel may not pass. `'/'` means the whole machine.

When confined:

- the location ladder starts at the root;
- drives and the root's own ancestors are not offered;
- `..` disappears while the panel stands on the root.

`start_directory` must be the root or somewhere under it. A violation
raises `ValueError`.

## Location ladder

With no real root, the ladder lists the machine's drives followed by the
ancestors of the folder on show, itself last:

```
['C:/', 'D:/', 'E:/', 'C:/Likianta', ..., <current folder>]
```

Every parent, and every other drive, is one pick away.

## Paths

Every row is a real file or folder, listed on demand. `value` and
`resolve()` return absolute paths.
