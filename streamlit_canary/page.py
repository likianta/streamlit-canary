import typing as tp


# ---------------------------------------------------------------------------
# page-level configuration (canary-specific)
# ---------------------------------------------------------------------------
# The single place a page's own settings live. `sc.PageTitle` and
# `sc.PageConfig` write into it as they are constructed, and the runtime reads
# it back when it renders the page (see `runtime/render.py:render_page`). A
# plain dict, so the runtime (and tests) can read it directly.
global_page_config: tp.Dict[str, tp.Any] = {
    'title': 'Streamlit Canary',
    'layout': 'centered',
    'default_theme': 'dark',
    'font_family': '',
    'dunder_literal': False,
}


def update_page_config(
    *,
    title: tp.Optional[str] = None,
    layout: tp.Optional[str] = None,
    default_theme: tp.Optional[str] = None,
    font_family: tp.Optional[str] = None,
    dunder_literal: tp.Optional[bool] = None,
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
