# TreeView

A classic tree over a static data model: every level lives in one listing,
and folders fold open in place.

```python
with v3.TreeView('Distribution', {
    'A': {
        'B': None,        # a leaf
        'C': {},          # an empty folder
        'D': {'E': None, 'G': {}},
    }
}) as tree:
    ...

node = tree.value.get()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `data` | `dict` | The model (bindable) |
| `filter` | `str` or tuple | Suffixes to keep |
| `start_directory`, `height`, `selection_mode`, ... | see `SingleTreeSelect` | |

Properties: `value`, `mode`, `directory`, `rows_visible`, `data`.

Signals: `value.on_change`, `on_navigate`, `on_submit`.

## The data model

`data` is one map from a name to a sub-map or `None`:

- a `dict` value is a folder; `{}` is an empty folder;
- `None` is a leaf;
- the map must have exactly one key, which is the root.

Node paths are the names joined with `/`, for example `A/D/G`. This is what
the location bar shows, and what `value` contains.

An empty model (`{}` or `None`) lists no rows. A model can be handed in
later.

## Re-rooting

`data` is bindable. Setting a new model re-roots the tree and clears the
selection, because the old paths belong to the old model:

```python
tree.data.set(new_model)
```

The new model is validated on assignment, so a malformed one raises
instead of drawing nothing.

## Folding

A folder with children carries a chevron to the left of its row. Clicking
it folds the folder open in place; clicking the row itself picks or ticks
it. The two gestures are independent.

## Multi-select

In the multi modes a folder stands for its whole subtree:

- ticking a folder drops any picks it covers, then adds it;
- once every child is picked, the picks fold into the folder itself;
- unticking a row inside a pick opens the pick one level at a time and
  leaves that row out.

A folder with only part of its subtree picked draws a half-ticked box.

## Root behavior

`..` is drawn only after leaving the root. Standing on the root, there is
no outside to walk to.
