# NumberInput

A box for entering a number.

```python
with v3.NumberInput('Workers', value=4, min_value=1, step=1) as box:
    @box.value.on_change
    def _():
        workers.set(box.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `value` | `int \| float \| Property` | Current number |
| `min_value` | `int \| float` | Inclusive lower bound |
| `max_value` | `int \| float` | Inclusive upper bound |
| `step` | `int \| float` | Stepper increment, default `0` |
| `format` | callable | Display formatter (for example `hex`) |
| `placeholder` | `str \| Property` | Hint while empty |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `value`, `placeholder`.

Signals: `value.on_change`, `on_submit`, `on_editing_finished`.

## Integer versus float

The initial `value` decides the widget's numeric type:

```python
v3.NumberInput('Count', value=0)     # int widget
v3.NumberInput('Ratio', value=0.0)   # float widget
```

An int widget requires int bounds and an int step. A float widget also
accepts ints and converts them to float.

The client sends the text; the server parses it with the widget's type. An
int widget therefore accepts both `'41'` and `'0x29'`.

## Stepper

`step=0` (the default) shows no stepper. A positive value adds `+` / `-`
controls. If the stepper does not fit the available width, it degrades to
a vertical form and is eventually dropped.

## Signals

- `on_value`: the committed value changed.
- `on_submit`: Enter was pressed; carries the raw text.
- `on_editing_finished`: editing ended (submit or blur); carries the raw
  text.

A submit emits both `on_submit` and `on_editing_finished`, in that order.

## Validation

Constructing a widget with an out-of-range value raises `ValueError`.
Passing a bound property that later falls out of range leaves the
validation to your handler.
