# Components V3

Components V3 is the event-driven component library. It has no dependency
on Streamlit: every component is a plain Python object that owns reactive
`Property` fields and emits `Signal`s.

## Two rules to remember

1. **Build the tree once.** The app function passed to `sc.run` is called
   once. Components created inside it stay alive for the session.
2. **Change values, not the tree.** Attach handlers to signals, then update
   properties. The runtime sends the difference to the browser.

## A first component

```python
import streamlit_canary as sc

with sc.v3.Button('Say hello') as button:
    @button.on_click
    def _():
        print('clicked')
```

The `with` block is how a component is added to its parent. Outside a
`with` block it is attached to the current component on the context stack,
which is the app root by default.

## Namespaces

V3 lives under `sc.v3` so it does not collide with the legacy API:

```python
import streamlit_canary as sc

sc.v3.Button
sc.v3.Text
sc.v3.Row
```

The kernel is available at the top level:

```python
sc.Property
sc.Signal
sc.StateV2
sc.bind
sc.bbind
sc.run
```

## Component groups

The library follows Streamlit's API reference categories:

| Module | Components |
| --- | --- |
| `texts` | `Text`, `Markdown`, `Title`, `PageTitle`, `Caption`, `Code` |
| `data` | `Table` |
| `charts` | `AltairChart` |
| `buttons` | `Button`, `IconButton`, `MenuButton`, `ToggleButton` |
| `inputs` | `Checkbox`, `CheckGroup`, `Radio`, `RadioGroup`, `Selectbox`, `Multiselect`, `NumberInput`, `TextInput`, `TextArea`, `Toggle`, `SegmentedControl`, `SelectSlider`, `ReducibleGroup` |
| `layouts` | `Row`, `Column`, `Container`, `Expander`, `Grid`, `Tabs`, `Dialog`, `Popover`, `FloatingContainer`, `Space`, `BottomContainer` |
| `status` | `Info`, `Success`, `Warning`, `Error`, `Callout`, `Spinner`, `Progress`, `Toast`, `LogPanel` |
| `media` | `PdfViewer` |
| `page` | `PageConfig` |
| `trees` | `SingleTreeSelect`, `TreeView`, `FileTreeView`, `DualTreeSelect`, `ColumnView`, `PathInput`, `PathSelect`, `PathInputBrowse` |

## Shared conventions

### Sizing

Every component accepts the same size keywords:

```python
v3.Button('Go', width='stretch')
v3.Container(height=320)
v3.Text('x', min_height=40)
```

- `width` / `height`: an `int` in CSS pixels, `'stretch'`, `'content'`, or
  `'auto'` (where the component supports it).
- `max_width` / `min_width` / `max_height` / `min_height`: positive
  integers or `None`.

A capped height makes the box scroll. `'stretch'` on one axis drops that
axis's min / max bounds.

### Visibility

Most components take `visible`. Text-like components default to
`'auto'`: they show when their content is non-empty and hide when it is
blank. A boolean or a bound property is used as given.

```python
v3.Text('')                       # hidden
v3.Text('hello')                  # shown
v3.Text('hello', visible=False)   # hidden
v3.Text('', visible=True)         # shown, but empty
```

To reserve a line without text, use exactly one space: `v3.Title(' ')`.

### Reading and writing

All reactive fields use the same style:

```python
widget.value.get()
widget.value.set(42)
widget['value']          # same as .get()
widget['value'] = 42     # same as .set(42)
widget['on_value']       # same as widget.value.on_change
```

### Binding

`sc.bind(source, transform)` creates a read-only, derived property.
`sc.bbind(source)` creates a two-way binding for widgets that write back.

```python
v3.Text(sc.bind(state.count, lambda n: 'Count: {}'.format(n)))
v3.NumberInput('Channel', sc.bbind(state.channel))
```

## Pages in this section

- [The Event Driven System](./event-driven-system.md)
- [Session State](./session-state.md)
- [API Reference](./api-reference/index.md)
