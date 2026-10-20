# Status Elements

Status elements report what the app is doing. Most of them are reactive:
update the text or value and the browser follows.

## Callouts

`Info`, `Success`, `Warning`, and `Error` are one alert box in four
palettes. `Callout` is the shared base.

```python
sc.Info('Loading the project...')
sc.Success('Saved.')
sc.Warning('This overwrites the existing file.')
sc.Error('Could not connect to the server.')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Message; `:color[..]` markup allowed |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

Properties: `text`, `visible`.

With `visible='auto'`, a blank message draws nothing, and a non-blank one
shows. Pass a bound value to drive visibility yourself:

```python
sc.Error(state.error, visible=sc.bind(state.error, bool))
```

## `Spinner`

A spinner indicator. It is hidden by default and is usually driven with a
`with` block or a bound flag.

```python
spinner = sc.Spinner()

with spinner('Syncing...'):
    do_work()
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Label next to the ring |
| `visible` | `bool \| Property` | Default `False` |

Properties: `text`, `visible`; method `reset(text='')`.

Calling the spinner sets its text and returns the spinner, so
`with spinner('Syncing...')` reads naturally. Entering shows it; exiting
restores the visibility it had before.

A state-driven form:

```python
sc.Spinner(state.busy_text, visible=sc.bind(state.busy_text, bool))
```

## `Progress`

A progress bar.

```python
with sc.Progress(total=len(sheets)) as progress:
    for sheet in sheets:
        progress.update(sheet.title)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `value` | `int \| None \| Property` | Percentage, or `None` for indeterminate |
| `text` | `str \| Property` | Caption under the bar |
| `label_visibility` | `str` | How the caption row is drawn |
| `visible` | `bool \| Property` | Default `False` |
| `total` | `int` | Steps used by `update()` |
| `auto_close` | `bool` | Hide the bar when the `with` block ends |

Properties: `value`, `text`, `visible`; attributes `total`, `index`.

Methods:

- `update(item=None)`: advance one step and set the caption;
- `close()`: hide the bar, keeping its value;
- `reset(text='', value=0)`: put it back to idle.

Use the `with` form **inside a handler**, where the block spans the work.
At build time the block would be the build itself and would close the bar
immediately.

## `Toast`

A stack of transient notifications at the page's top-right.

```python
toast.show('Saved!', icon=':material/check:')
```

Properties: `messages` (a list of dictionaries).

Methods:

- `show(text, icon='', duration='short')`;
- `clear()`.

Durations follow Streamlit: `'short'` (4s), `'long'` (10s), `'infinite'`,
or a positive number of seconds. Up to five messages are visible. Hovering
the stack fans it out and pauses the countdowns; each message also has a
close button.

Most apps do not declare a `Toast`. `sc.toast(...)` reaches the page's
single stack, which the runtime creates if needed.

## `LogPanel`

A live view of what the app prints to the terminal.

```python
with sc.BottomContainer():
    sc.LogPanel(source='stdout')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `source` | `'stdout' \| 'stderr'` | Stream to follow |
| `border_title` | `str \| Property` | Border title, default `'LOG'` |
| `placeholder` | `str \| Property` | Hint while there are no lines |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |
| `height` | size keyword | Default `200` |

Properties: `lines`, `border_title`, `placeholder`, `visible`.

Every line written to `source` lands in the panel, newest at the bottom.
The buffer keeps the last 500 lines; the oldest are dropped. ANSI color
codes are stripped.

`push_divider(title='')` inserts a rule, which is useful for marking the
boundary between two runs:

```python
panel.push_divider('12:00:00')
```

A clear button floats in the top-right corner while there is something to
clear.

With `visible='auto'`, an empty panel is hidden. A `placeholder` counts as
content, so a panel with only a hint keeps its frame.
