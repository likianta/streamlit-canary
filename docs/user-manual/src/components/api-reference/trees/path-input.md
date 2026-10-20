# PathInput and PathSelect

## `PathInput`

A text input whose text is resolved into a path.

```python
with sc.PathInput('Output folder', 'C:/work') as box:
    @box.on_submit
    def _(text):
        use_path(box.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str` | Label |
| `value` | `str` | Initial text |
| `width` | size keyword | Width |
| `input_history` | sequence, Property, or `None` | Suggestions |
| `accept_new_option` | `bool` | Add an "Add: ..." row |

Properties: `value`, `input_history`.

Signals: `on_submit`, `on_editing_finished` (both carry the text as typed).

Method: `show(path)`, which makes `path` the value and rewrites the box
even when it already shows that path in another spelling (backslashes, a
trailing separator, a `..`).

### Path resolution

- Blank text resolves to `''`.
- Text that names something on disk resolves to an absolute path with
  forward slashes.
- Text that names nothing yet is kept, with only its separators
  straightened. A path that does not exist is still a path, and the caller
  decides what it means.

### History

`input_history` is both a suggestion list and a memory:

- `None`: no caret, no panel.
- A literal sequence: seeds a memory. Every non-empty path the box holds
  joins it (newest first, no duplicates). Capacity is at least 20; a
  larger seed rounds up to the next ten. The panel lists the memory in
  alphabetical order.
- A `Property`: the caller owns the list; nothing is remembered.

## `PathSelect`

A `PathInput` with a navigation ladder.

```python
with sc.PathSelect(
    'Go to',
    '.',
    ladder=['C:/', 'C:/work', 'C:/work/app'],
) as box:
    ...

path = box.value.get()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `ladder` | sequence or Property | Rungs; the current folder is last |

Properties: `value`, `input_history`, `ladder`.

The box looks the same as `PathInput`, but has two dropdowns:

- clicking the input area opens the **ladder**: drives, then the ancestors
  of the folder on show. The last rung is drawn as selected.
- clicking the caret opens `input_history`. The caret is greyed out while
  the history is empty.

Both close on a click outside or Escape. `PathSelect` takes no
`accept_new_option`, because clicking the box already opens the ladder,
and typing plus Enter already resolves the path.

The ladder is fed by the host, since the box does not know which folder it
is "in".
