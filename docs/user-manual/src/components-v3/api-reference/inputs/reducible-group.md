# ReducibleGroup

A list of items, each of which can be removed from its own trailing `x`.

```python
with v3.ReducibleGroup('Files', options=('a.txt', 'b.txt')) as group:
    @group.on_reduce
    def _(item):
        print('removed', item)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Optional label |
| `options` | sequence \| Property | The items |
| `format` | callable or sequence | Labels |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`.

Signals: `on_reduce` (the dropped item), `options.on_change`.

The rows are laid out like a `MenuButton`'s menu. Hovering a row reveals
the `x`; clicking it removes the item from `options` and emits
`on_reduce`.

The component updates its own `options` list. Your handler receives the
dropped item so it can keep an external list in sync.

```python
@group.on_reduce
def _(item):
    state.files.set([x for x in state.files.get() if x != item])
```
