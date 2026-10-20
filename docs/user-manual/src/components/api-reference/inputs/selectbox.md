# Selectbox and Multiselect

## `Selectbox`

A dropdown for choosing one value.

```python
with sc.Selectbox(
    'Choose a branch',
    options=('main', 'dev', 'release'),
    value='main',
) as box:
    @box.value.on_change
    def _():
        branch.set(box.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence \| Property | Choices |
| `index` | `int` | Selected position |
| `value` | any | Selected value |
| `format` | callable or sequence | Labels |
| `placeholder` | `str \| Property` | Hint while nothing is picked |
| `accept_new_option` | `bool` | Offer an input row in the dropdown |
| `format_new_option` | callable | Convert typed text into a value |
| `take_new_option` | callable | Handle typed text yourself |
| `truncate_start` | `bool` | Show the tail of an overlong label |
| `enabled` | `bool \| Property` | Whether input is accepted |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `index`, `value`, `placeholder`.

Signals: `value.on_change`, `options.on_change`.

### Accepting a new option

```python
sc.Selectbox(
    'Channel',
    options=('A', 'B'),
    accept_new_option=True,
)
```

A submitted value that is not already an option is added at the front and
selected. `format_new_option` converts the text before it is stored:

```python
sc.Selectbox(
    'Port',
    options=(80, 443),
    accept_new_option=True,
    format_new_option=lambda x: int(x, 0),
)
```

`take_new_option` replaces that behavior entirely. Nothing is added to
`options`; the callable receives the text and decides what to do. This is
what a path bar uses.

### Width

With `width='content'`, the trigger is as wide as the widest option, not
as wide as the current value. Switching options therefore does not make
the control jump in size.

## `Multiselect`

A dropdown for choosing several values.

```python
with sc.Multiselect(
    'Select chart results',
    options=('Droop', 'PSD', 'SNDR'),
    value=('Droop', 'PSD'),
) as box:
    @box.value.on_change
    def _():
        print(box.value.get())
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `label` | `str \| Property` | Label |
| `options` | sequence \| Property | Choices |
| `value` | sequence \| Property | Selected values |
| `format` | callable or sequence | Labels |
| `placeholder` | `str \| Property` | Hint while nothing is selected |
| `height` | `'fixed'` \| size keyword | Default `'fixed'` |
| `label_visibility` | `str` | See [Inputs](./index.md) |

Properties: `label`, `options`, `value`, `placeholder`.

Signals: `value.on_change`.

### Selection order

The selection keeps the order in which rows were ticked. That order is
what the trigger shows, what `value` reports, and what the server stores.
Ticking adds to the end; unticking removes from the list.

### Height

`height='fixed'` keeps the trigger on one line and scrolls the summary
sideways. This avoids the control growing taller as more options are
picked. Pass a size keyword to override it.
