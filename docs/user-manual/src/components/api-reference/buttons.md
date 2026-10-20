# Button

Button-style widgets trigger actions. They have no value of their own,
except for `ToggleButton`.

## `Button`

```python
with sc.Button('Save', type='primary') as button:
    @button.on_click
    def _():
        save()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Button text |
| `type` | `'secondary' \| 'primary'` | Visual style, default `'secondary'` |
| `help` | `str \| Property` | Markdown tooltip |
| `width` | size keyword | Default `'content'` |
| `enabled` | `bool \| Property` | Default `True` |
| `on_click` | callable | Optional handler, attached at construction |

Properties: `text`, `type`, `enabled`, `help`.

Signals: `on_click`.

`type`, `enabled`, and `help` are reactive, so a button can change
appearance or availability as state changes:

```python
sc.Button(
    'Deploy',
    enabled=sc.bind(state.ready, lambda x: x),
)
```

## `IconButton`

A button that contains only an icon. A bare material icon name is wrapped
as `:material/<name>:` automatically.

```python
sc.IconButton('refresh', help='Reload the list')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `icon` | `str \| Property` | Icon name or short label |
| `help` | `str` | Tooltip; recommended |

Other arguments are inherited from `Button`.

## `MenuButton`

A button that opens a menu of options. Choosing a row sets `value` and
closes the menu, without a server round trip.

```python
menu = sc.MenuButton('Export', options=('CSV', 'JSON'))

@menu.value.on_change
def _():
    export_as(menu.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Trigger label |
| `options` | sequence \| Property | Menu rows |
| `value` | any | Current choice |
| `format` | callable or sequence | Row labels |
| `panel_max_height` | `int` | Scroll the menu past this height |

Properties: `text`, `options`, `value`.

## `ToggleButton`

A canary extra: a button that stays lit while its `value` is true.

```python
with sc.ToggleButton('Bold') as bold:
    @bold.value.on_change
    def _():
        apply_style(bold.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Button text |
| `value` | `bool \| Property` | Initial on / off state |
| `help`, `width`, `enabled` | as `Button` | |
| `on_click` | callable | Runs after `value` flips |

Properties: `value`, and a read-only `type` derived from `value`
(`'primary'` while on, `'secondary'` while off).

`ToggleButton` does not accept a `type` argument. Writing `type` raises an
error, so the look cannot disagree with the state.
