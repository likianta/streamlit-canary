# Components V1 (Legacy)

> [!CAUTION]
> This part is going to be removed in future versions, for latest reference, please read [Components V3 docs](../components-v3/index.md).

Components V1 is the original layer of Streamlit Canary. It is built
directly on top of Streamlit and follows the same rerun model: every
interaction re-executes the script, and widgets return their current value
from that run.

V1 is still available under the top-level namespace:

```python
import streamlit_canary as sc

value = sc.selectbox('Choose one', ('a', 'b', 'c'))
```

It remains useful for:

- small scripts that do not need persistent state;
- porting an existing Streamlit app with minimal changes;
- comparing behavior against upstream Streamlit.

It is **not** the recommended way to build a new app. The rerun model is
exactly what V3 removes, and V1 widgets cannot participate in the V3
component tree or its delta patches.

## Related pages

- [Migrating to V3](./migration-to-v3.md)
- [Components V3](../components-v3/index.md)
