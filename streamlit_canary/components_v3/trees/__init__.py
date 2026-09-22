"""Tree-style file selectors (v3).

Two symmetric pairs.  Each one splits a browser *panel* from the "input +
panel" wrapper that drives it:

    TreeSelect / TreeSelectWithInput
        the single-pane browser -- a folder listing that navigates itself
        (its toolbar only carries refresh / bucket / mode) -- plus a path
        input whose "Browse" trigger opens the panel in a `Popover`.

    TreeSelectDualPane / TreeSelectDualPaneWithInput
        the two-column browser, plus a path input whose "Browse" trigger
        opens the panel in a modal `Dialog`.

The two wrappers share the same pieces: `PathInput` (a text input that
resolves what was typed into an existing path) and `Recent` (the "Recent"
dropdown).  Only `TreeSelect` and `TreeSelectWithInput` are exported from
`components_v3`; the rest are building blocks, importable from this module.

Everything is driven through `Property` fields instead of a rerun, so a
caller reads the picked path from `.value` at any time and can react to
`value.on_change`.

Ported from the v1 `streamlit_canary/components/tree_select/` package, which
was written against Streamlit's rerun model.  Where v1 needed Streamlit-only
primitives, the v3 build uses:

    st.dialog         -> `Dialog` (✕ / backdrop / Esc also dismiss it)
    st.menu_button    -> a `Popover` holding a single-choice list
    st.radio + st.container(height) -> `RadioGroup(max_height=...)`
    st.button(':material/...')      -> `IconButton`

    st.segmented_control (`node_type='both'`) is not implemented; only
    `node_type='file'` and `'folder'` are supported.
"""

from ._shared import T
from .recent import Recent
from .tree_select import TreeSelect
from .tree_select import TreeSelectWithInput
from .tree_select_dual_pane import TreeSelectDualPane
from .tree_select_dual_pane import TreeSelectDualPaneWithInput
from ..inputs import PathInput
