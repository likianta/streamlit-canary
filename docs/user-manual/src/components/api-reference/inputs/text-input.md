# TextInput and TextArea

## `TextInput`

A single-line text box.

```python
with sc.TextInput('Project name', value='') as box:
    @box.on_submit
    def _(text):
        create_project(text)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `value` | `str \| Property` | Current text |
| `placeholder` | `str \| Property` | Hint while empty |
| `enabled` | `bool \| Property` | Whether input is accepted |
| `help` | `str` | Tooltip |
| `input_history` | sequence, Property, or `None` | Suggestions panel |
| `accept_new_option` | `bool` | Add an "Add: ..." row to the panel |
| `truncate_start` | `bool` | Show the tail of an overlong value |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `value`, `placeholder`, `enabled`, `input_history`.

Signals: `value.on_change`, `on_editing`, `on_submit`,
`on_editing_finished`.

`value` is committed on blur or Enter. `on_editing` reports every
keystroke, which is how a caller can follow text before it is committed.

### Input history

`input_history` adds a caret that opens a list of suggestions:

```python
sc.TextInput('File', input_history=('/tmp/a.txt', '/tmp/b.txt'))
```

- `None`: no caret.
- An empty sequence: a caret that is disabled.
- A non-empty sequence: a working panel.

Picking a row fills the box. The text remains freely editable, so this is
also a way to get "selectbox with free text".

`accept_new_option=True` adds an "Add: ..." row for the current text.

### Truncating from the start

`truncate_start=True` keeps the end of an overlong value in view. Use it
for paths, where the last segment is the part that distinguishes one value
from another.

## `TextArea`

A multi-line text box. It has the same fields and signals as
`TextInput`, except `on_editing`, `input_history`, `accept_new_option`,
and `truncate_start`.

```python
with sc.TextArea('Notes', height=160) as box:
    @box.on_submit
    def _(text):
        save_notes(text)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `value` | `str \| Property` | Current text |
| `placeholder` | `str \| Property` | Hint while empty |
| `height` | size keyword | Default `200` |
| `enabled` | `bool \| Property` | Whether input is accepted |
| `help` | `str` | Tooltip |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Press Ctrl+Enter to submit. Plain Enter inserts a newline. The box
scrolls when the text overflows its height.
