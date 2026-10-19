# Expander

A collapsible section with a clickable header.

```python
with v3.Expander('Configurations', expanded=True):
    v3.Checkbox('Enable caching')
    v3.Button('Force refresh')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Header text |
| `expanded` | `bool` | Whether the body starts open |
| `visible` | `bool \| Property` | Whether the expander is shown |

Properties: `label`, `visible`.

Expanding and collapsing is handled entirely in the browser, so it never
reaches the server and never triggers a rerun.

## Dynamic header

`label` is bindable:

```python
v3.Expander(sc.bind(state.file_count, lambda n: 'Files ({})'.format(n)))
```

## Hiding

`visible=False` removes the whole expander, header included. To keep the
header but hide the body, use a `Container` with `animated=True` and drive
its `visible` from a `ToggleButton`.
