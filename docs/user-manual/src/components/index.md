# Components

The components are the event-driven library. It has no dependency on
Streamlit: every component is a plain Python object that owns reactive
`Property` fields and emits `Signal`s.

## Two rules to remember

1. **Build the tree once.** The app function passed to `sc.run` is called
   once. Components created inside it stay alive for the session.
2. **Change values, not the tree.** Attach handlers to signals, then update
   properties. The runtime sends the difference to the browser.

## A first component

```python
import streamlit_canary as sc

with sc.Button('Say hello') as button:
    @button.on_click
    def _():
        print('clicked')
```

The `with` block is how a component is added to its parent. Outside a
`with` block it is attached to the current component on the context stack,
which is the app root by default.

## Namespace

Since 0.5.0 the components are exported at the top level -- `sc.Button`,
`sc.Text`, `sc.Row`:

```python
import streamlit_canary as sc

sc.Button
sc.Text
sc.Row
```

`sc.v3.*` still resolves for apps written before 0.5.0, but that form is
deprecated: it emits a `DeprecationWarning`.

The kernel is available at the top level:

```python
sc.Property
sc.Signal
sc.State
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
sc.Button('Go', width='stretch')
sc.Container(height=320)
sc.Text('x', min_height=40)
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
sc.Text('')                       # hidden
sc.Text('hello')                  # shown
sc.Text('hello', visible=False)   # hidden
sc.Text('', visible=True)         # shown, but empty
```

To reserve a line without text, use exactly one space: `sc.Title(' ')`.

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
sc.Text(sc.bind(state.count, lambda n: 'Count: {}'.format(n)))
sc.NumberInput('Channel', sc.bbind(state.channel))
```

## Pages in this section

- [The Event Driven System](./event-driven-system.md)
- [Session State](./session-state.md)
- [API Reference](./api-reference/index.md)
