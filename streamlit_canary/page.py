"""Streamlit pages, and the canary's page-level configuration."""

import typing as t

from ._streamlit import st

if t.TYPE_CHECKING:
    from streamlit.navigation.page import StreamlitPage


# ---------------------------------------------------------------------------
# page-level configuration (canary-specific)
# ---------------------------------------------------------------------------
# The single place a page's own settings live. `v3.PageTitle` and
# `v3.PageConfig` write into it as they are constructed, and the runtime reads
# it back when it renders the page (see `runtime/render.py:render_page`). A
# plain dict, so the runtime (and tests) can read it directly.
global_page_config: t.Dict[str, t.Any] = {
    'title': 'Streamlit Canary',
    'layout': 'centered',
    'default_theme': 'dark',
    'font_family': '',
    'dunder_literal': False,
}


def update_page_config(
    *,
    title: t.Optional[str] = None,
    layout: t.Optional[str] = None,
    default_theme: t.Optional[str] = None,
    font_family: t.Optional[str] = None,
    dunder_literal: t.Optional[bool] = None,
) -> None:
    """Merge the given page settings into `global_page_config`.

    A `None` leaves its knob as it was, so a later `PageConfig` / `PageTitle`
    can adjust one setting without resetting the rest; for each knob, the last
    writer wins.
    """
    for key, value in (
        ('title', title),
        ('layout', layout),
        ('default_theme', default_theme),
        ('font_family', font_family),
        ('dunder_literal', dunder_literal),
    ):
        if value is not None:
            global_page_config[key] = value


def pages(
    elements: t.Dict[str, t.Callable[[], t.Any]]
) -> 'StreamlitPage':
    normalized_elements = []
    for k, v in elements.items():
        normalized_elements.append(st.Page(
            v,
            title=k,
            url_path=k.lower().replace(' ', '-'),
        ))
    return st.navigation(normalized_elements)
