"""Page-level configuration element: `PageConfig` (canary-specific).

The class-form replacement for `sc.set_page_config`, so a page's settings are
declared like the rest of the component tree:

    def main():
        v3.PageConfig('My App', layout='wide', default_theme='light')

It draws nothing -- it is the app saying "the page looks like this" -- and
writes its settings into the shared `global_page_config` the runtime reads
back when it renders the page (see `streamlit_canary/page.py`).
"""

import typing as tp

from ..page import update_page_config
from .base import Component


class PageConfig(Component):
    """Declare the page's own settings (title / layout / theme / font).

    A `PageConfig` writes straight into the shared `global_page_config` as it
    is constructed, so it has no visible element of its own; declaring it in
    the tree is how the app states the page's configuration. Every knob but
    the title is optional, and `None` means "leave that knob alone", so a
    second `PageConfig` can adjust one setting without resetting the others.
    When more than one is declared -- or a `PageTitle` is in the mix -- the
    last one wins for each knob it set.

    Args:
        title: the browser tab / document title.
        layout: "centered" (default) | "wide".
        default_theme: "dark" (default) | "light".
        font_family: a CSS `font-family` value applied to the whole page
            (body text and headings alike); empty keeps the theme's own font.
            Code keeps its monospace face whatever this is.
        dunder_literal: experimental, off by default. Keep `__x__` as plain
            text instead of letting markdown read it as bold, so a `__init__`
            or `__name__` in prose survives; `**x**` and `:bold[x]` are then
            the only ways to bold. Handy for an app whose text is full of
            Python names.
    """

    def __init__(
        self,
        title: tp.Optional[str] = None,
        *,
        layout: tp.Optional[str] = None,
        default_theme: tp.Optional[str] = None,
        font_family: tp.Optional[str] = None,
        dunder_literal: tp.Optional[bool] = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        update_page_config(
            title=title,
            layout=layout,
            default_theme=default_theme,
            font_family=font_family,
            dunder_literal=dunder_literal,
        )
