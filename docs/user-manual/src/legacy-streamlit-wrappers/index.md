# Legacy Streamlit Wrappers (V1)

> [!CAUTION]
> The V1 wrappers are no longer exported as `sc.*` (they left the top-level
> namespace in 0.5.0). Import them from
> `streamlit_canary.legacy_streamlit_wrappers`. For new work, read
> [Components](../components/index.md).

Components V1 is the original layer of Streamlit Canary. It is built
directly on top of Streamlit and follows the same rerun model: every
interaction re-executes the script, and widgets return their current value
from that run.

They are still there, under their own module:

```python
from streamlit_canary import legacy_streamlit_wrappers as legacy

value = legacy.toggle_button('Show details')
```

It remains useful for:

- small scripts that do not need persistent state;
- porting an existing Streamlit app with minimal changes;
- comparing behavior against upstream Streamlit.

It is **not** the recommended way to build a new app. The rerun model is
exactly what V3 removes, and V1 widgets cannot participate in the V3
component tree or its delta patches.

## Related pages

- [Migrating to the default components](./migration.md)
- [Components](../components/index.md)
