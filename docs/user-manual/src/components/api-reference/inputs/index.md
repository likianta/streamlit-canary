# Inputs

Input widgets hold a value that the user can change. Every widget in this
section follows the same property model:

```python
with sc.Checkbox('Enabled', value=True) as box:
    @box.value.on_change
    def _():
        print(box.value.get())
```

## Shared arguments

| Argument | Meaning |
| --- | --- |
| `label` | Text drawn above the widget; bindable |
| `label_visibility` | `'auto'` (default), `'visible'`, `'hidden'`, `'collapsed'` |
| `help` | Markdown tooltip next to the label |
| `enabled` | Whether the widget accepts input; bindable |
| `width` | Size keyword, usually defaulting to `'stretch'` |

`label_visibility='auto'` behaves like `'visible'` when the label has
content and like `'collapsed'` when it is empty. This is decided when the
page is rendered; a later change to `label` does not re-evaluate it.

## Option widgets

`CheckGroup`, `RadioGroup`, `Selectbox`, `Multiselect`,
`SegmentedControl`, and `SelectSlider` share an options model:

- `options`: the choices, bindable;
- `index`: the selected position, or `None`;
- `value`: the selected value (a list for multi-select widgets);
- `format`: a callable `value -> text`, or a list of labels parallel to
  `options`.

`index` and `value` are kept in sync. Setting either one updates the
other.

```python
sc.Selectbox(
    'Level',
    options=(1, 2, 3),
    value=2,
    format=lambda n: 'Level {}'.format(n),
)
```

## Submitting text

`TextInput`, `TextArea`, and `NumberInput` expose:

- `on_value`: the committed value changed (on blur or Enter);
- `on_submit`: Enter was pressed (Ctrl+Enter for `TextArea`);
- `on_editing_finished`: editing ended, either by submit or by losing
  focus.

`TextInput` additionally exposes `on_editing`, which fires on every
keystroke while the text is still uncommitted.

## Pages

- [Checkbox and Group](./checkbox.md)
- [Radiobox and Group](./radio.md)
- [Selectbox and Multiselect](./selectbox.md)
- [NumberInput](./number-input.md)
- [TextInput and TextArea](./text-input.md)
- [Toggle](./toggle.md)
- [SegmentedControl and SelectSlider](./segmented-control.md)
- [ReducibleGroup](./reducible-group.md)
