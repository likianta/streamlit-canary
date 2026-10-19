# Trees

The tree components browse a folder hierarchy. They are canary extras:
Streamlit has no equivalent.

There are four panels, all built on the same row and selection engine:

| Component | Shape |
| --- | --- |
| `SingleTreeSelect` | One folder at a time; `..` walks up |
| `TreeView` | Every level in one listing over a static data model |
| `FileTreeView` | The same classic tree, rooted on a real folder |
| `DualTreeSelect` | Two columns: subfolders left, files right |
| `ColumnView` | Finder-style stack of columns, one level per column |

On top of the panels there are path inputs:

| Component | Shape |
| --- | --- |
| `PathInput` | A text box that resolves its text into a path |
| `PathSelect` | `PathInput` plus a navigation ladder |
| `PathInputBrowse` | A path box paired with one of the panels |

## Shared selection modes

The single-list, classic, and file trees share three modes:

- `'single'`: one node;
- `'multiple'`: several nodes within the folder being browsed; leaving the
  folder drops them;
- `'multicross'`: nodes gathered across folders into a bucket.

A tuple of modes, such as `('single', 'multicross')`, shows a mode switch.
`selection_mode` decides which modes are offered; `initial_mode` decides
which one opens.

`DualTreeSelect` and `ColumnView` are single-select only.

## Shared row gestures

- Clicking a row picks or ticks it.
- Hovering a folder reveals an `->` arrow; clicking it walks into the
  folder.
- The `..` row walks up. Its checkbox is frozen because it is a
  navigation target, not a node.

## Filtering

`filter` keeps files by suffix:

```python
v3.FileTreeView(filter='.py')
v3.FileTreeView(filter=('.py', '.pyi'))
```

Folders are always listed.

## Pages

- [SingleTreeSelect](./single-list.md)
- [TreeView](./tree-view.md)
- [FileTreeView](./file-tree-view.md)
- [DualTreeSelect](./dual-pane.md)
- [ColumnView](./column-view.md)
- [PathInput and PathSelect](./path-input.md)
- [PathInputBrowse](./path-input-browse.md)
