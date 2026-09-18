"""Chart elements: Streamlit's "Chart elements" (`api-reference/charts`).

`AltairChart`.
"""

import typing as tp

from .base import Component
from .base import Width
from ..kernel import Property


def _inline_datasets(node: tp.Any, datasets: dict) -> None:
    """Replace `{"name": "<key>"}` data references with inline values.

    Altair's default data transformer keeps the rows in a top-level
    `datasets` map and leaves `{"name": ...}` references behind — a
    Jupyter-only convention that plain Vega-Lite (and therefore
    `vega-embed`) does not understand. Resolving the references here keeps
    the emitted spec self-contained. The walk covers layered / concatenated
    specs too, since every nested `data` is visited.
    """
    if isinstance(node, dict):
        data = node.get('data')
        if (
            isinstance(data, dict)
            and set(data) == {'name'}
            and data['name'] in datasets
        ):
            node['data'] = {'values': datasets[data['name']]}
        for value in node.values():
            _inline_datasets(value, datasets)
    elif isinstance(node, list):
        for value in node:
            _inline_datasets(value, datasets)


def _to_vega_lite_spec(chart: tp.Any) -> dict:
    """Normalize an Altair chart (or an already-built spec) to a spec dict.

    Altair's own `to_dict()` is used when available, which keeps `altair`
    out of `streamlit_canary`'s dependencies — the chart object is the only
    thing that needs altair installed. Named datasets are inlined so the
    result renders with a plain `vega-embed` call.
    """
    to_dict = getattr(chart, 'to_dict', None)
    if callable(to_dict):
        spec = tp.cast(dict, to_dict())
        datasets = spec.pop('datasets', None)
        if datasets:
            _inline_datasets(spec, datasets)
        return spec
    if isinstance(chart, dict):
        return chart
    raise TypeError(
        'AltairChart expects an altair.Chart or a Vega-Lite spec dict, '
        f'got {type(chart).__name__}: {chart!r}'
    )


# -- widgets (alphabetical) ------------------------------------------------


class AltairChart(Component):
    """A chart drawn from an Altair (Vega-Lite) specification.

    Args:
        chart: an `altair.Chart` — more precisely, anything exposing
            `to_dict()` — or an already-built Vega-Lite spec (`dict`).
            Bindable. `None` renders nothing until a spec is set.
        width: "stretch" (default; fills the parent) | "content" | int px.

    Properties:
        chart: dict | None — the Vega-Lite spec (JSON-serializable). The
            client renders it with `vega-embed` and re-renders whenever the
            spec changes.

    `streamlit_canary` never imports altair itself; a chart object is
    converted through its own `to_dict()`, so altair stays optional:

        v3.AltairChart(chart)
        v3.AltairChart(state.spec)  # a Property holding a spec dict
    """

    _default_width = 'stretch'

    def __init__(
        self,
        chart: tp.Any = None,
        *,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)
        self.chart: Property[dict | None] = Property(None)
        if isinstance(chart, Property):
            self.chart.set_or_bind(chart)
        elif chart is not None:
            self.set_chart(chart)

    def set_chart(self, chart: tp.Any) -> None:
        """Set the chart from an Altair object or a Vega-Lite spec dict."""
        spec = _to_vega_lite_spec(chart)
        if spec is not None and self._width == 'stretch':
            # The spec usually carries its own pixel `width`; make it follow
            # the widget instead, otherwise a wide chart overflows a narrower
            # parent (Streamlit does the same for `width='stretch'`).
            spec['width'] = 'container'
            spec['autosize'] = {'type': 'fit', 'contains': 'padding'}
        self.chart.set(spec)
