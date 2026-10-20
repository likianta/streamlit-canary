# Chart Elements

## `AltairChart`

Renders an Altair / Vega-Lite chart.

```python
import altair as alt

chart = alt.Chart(data).mark_bar().encode(
    x='category',
    y='value',
)

sc.AltairChart(chart)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `chart` | Altair chart or dict | The chart specification |
| `width` | size keyword | Chart width |
| `visible` | `bool \| Property` | Default `True` |

Properties: `chart`.

`AltairChart` accepts either an Altair chart object (anything with a
`to_dict()` method) or a plain Vega-Lite dictionary. Altair itself is an
optional dependency: the component does not import it.

To update a chart, call `set_chart()` or set the `chart` property with a
new specification:

```python
with sc.AltairChart(chart) as view:
    @state.data.on_change
    def _():
        view.set_chart(alt.Chart(state.data.get()).mark_line())
```
