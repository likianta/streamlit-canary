"""Lazy access to the optional `streamlit` dependency.

`streamlit` is an optional dependency of this package: the v3 runtime
(`kernel` / `components_v3` / `runtime`) does not need it, so `import
streamlit_canary` must work without it. The v1/v2 API, the page helpers and
the legacy runner do need it -- but only once actually used. Those modules
therefore take their `st` from here instead of importing it eagerly:

    from ._streamlit import st        # top level
    from .._streamlit import st       # one level down

The first attribute access (`st.text_input`, `st.session_state`, ...) imports
the real module; if it is missing, the error says what to install. Type
checkers still see the real module, because `st` resolves to it under
`TYPE_CHECKING` (that branch never runs at runtime).
"""

import typing as tp
from types import ModuleType


class _LazyStreamlit(ModuleType):
    """Stands in for the `streamlit` module until something asks of it."""

    def __getattr__(self, name: str) -> tp.Any:
        return getattr(load(), name)


if tp.TYPE_CHECKING:
    import streamlit as st
else:
    st = _LazyStreamlit('streamlit')

_module: ModuleType | None = None


def load() -> ModuleType:
    """Import and return `streamlit`, explaining itself if it is missing."""
    global _module
    if _module is None:
        try:
            import streamlit as module
        except ImportError as error:
            raise ImportError(
                'streamlit is an optional dependency of streamlit-canary: this '
                'call needs it, but it is not installed. Install it with '
                '`uv add streamlit` (or `uv add streamlit-canary[st]`). '
                'The v3 API (`sc.v3`, `sc.Property`, the runtime) works '
                'without it.'
            ) from error
        _module = module
    return _module
