"""Data elements: Streamlit's "Data elements" (`api-reference/data`).

`Table`.
"""

import typing as tp

from ._shared import _prop
from ._shared import _visible_when_filled
from .base import Component
from .base import Width
from ..kernel import Property


class Table(Component):
    """A static table (mirrors Streamlit's `st.table`, plus canary extras).

    Args:
        rows: an iterable of rows. The first cell of each row is the row
            header (`<th scope="row">`) and every following cell is a value
            column, so an N-cell row yields an N-column table (the common
            2-tuple form mirrors `st.table(dict)`). Cells accept the same
            `:color[..]` markup as `v3.Text`. Bindable.
        title:   optional heading drawn above the table (bindable).
        caption: optional muted line drawn under the title (bindable).
        footer:  optional muted line drawn under the table (bindable).
        header:  optional column labels, one per column; when given, a
            column-label row is drawn above the body (bindable).
        header_background: fill the header row with the secondary background.
            The canary only offers this limited knob (rather than a fully
            customisable table) for the title / caption / footer / header row.
        width: "stretch" (Streamlit's default) fills the parent column;
            "content" hugs the cell contents; an int is a pixel width.

    Properties:
        rows, title, caption, footer, header — see above.
        visible: bool — false while `rows` is empty (so a table with nothing
            to show takes no space, and comes back as soon as the bound rows
            arrive), or whenever the flag is switched off explicitly.
    """

    _default_width = 'stretch'

    def __init__(
        self,
        rows: tp.Iterable[tp.Sequence[str]] | Property | None = None,
        *,
        title: str | Property = '',
        caption: str | Property = '',
        footer: str | Property = '',
        header: tp.Sequence[str] | Property | None = None,
        header_background: bool = False,
        width: Width | None = None,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, visible=visible, **kwargs)
        self.rows = Property([])
        if isinstance(rows, Property):
            self.rows.bind(rows)
        elif rows is not None:
            self.rows.set(list(rows))
        self.title = _prop('', title)
        self.caption = _prop('', caption)
        self.footer = _prop('', footer)
        self.header: Property[list[str] | None] = Property(None)
        if isinstance(header, Property):
            self.header.bind(header)
        elif header is not None:
            self.header.set(list(header))
        self._header_background = header_background
        self.visible = _visible_when_filled(self.rows, visible)
