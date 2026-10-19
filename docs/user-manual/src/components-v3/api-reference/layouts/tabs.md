# Tabs

A tab bar with one panel per label.

```python
with v3.Tabs(('Overview', 'Details')) as tabs:
    with tabs['Overview']:
        v3.Text('Summary')
    with tabs['Details']:
        v3.Text('Full details')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `labels` | sequence of strings | Tab labels |
| `active` | `str \| Property` | Visible tab, default the first |

Properties: `active`.

Signals: `active.on_change` (`tabs['on_active']`).

## Addressing panels

```python
with tabs['Overview']:
    ...

# or in label order
with v3.Tabs(('a', 'b')) as tabs:
    with next(tabs):
        ...
    with next(tabs):
        ...
```

`tabs[label]` returns that label's panel, creating it on first access and
reusing it afterwards. Panels are built up front; switching tabs is
entirely client-side.

## Label collisions

A label wins over property access. A tab named `active` is not reachable
as `tabs['active']`; read the property through `tabs.active` instead.

## Programmatic switching

```python
tabs.active.set('Details')
```

The client switches to that panel on the next patch.
