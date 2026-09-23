"""Text elements: Streamlit's "Text elements" (`api-reference/text`).

`Caption`, `Code`, `Markdown`, `PageTitle`, `Text`, `Title`.
"""

import typing as tp

from ._shared import _HasText
from ._shared import _HelpText
from ._shared import _visible_when_filled
from ..kernel import Property

# Where a heading can sit in its box. Only `Title` offers a choice: Streamlit
# hangs `text_alignment` on the markdown elements (and also allows `justify`),
# while a caption or a body of text reads left-aligned.
_ALIGNMENTS: tp.Final[tuple[str, ...]] = ('left', 'center', 'right')


def _validate_alignment(value: tp.Any, name: str) -> str:
    """Reject an alignment outside the three (the way `base.py` checks its
    sizing keywords)."""
    if isinstance(value, str) and value in _ALIGNMENTS:
        return value
    raise ValueError(f'{name} must be one of {_ALIGNMENTS}, got {value!r}')


class Caption(_HelpText):
    """A small caption / helper text (mirrors Streamlit's `st.caption`).

    A caption with no text is hidden, so a bound text that is still empty
    leaves no gap behind.

    Args:
        text: the caption content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
        visible: the base-class flag, ANDed with the content test above --
            see `_visible_when_filled`.
    """


class Code(_HasText):
    """A code block with a hover-revealed "copy to clipboard" button.

    A block with no code is hidden, so a bound source that is still empty
    leaves no empty frame behind.

    Args:
        text: the code content (bindable).
        language: kept for parity with Streamlit's `st.code`; this
            implementation does not syntax-highlight.
        visible: the base-class flag, ANDed with the content test above --
            see `_visible_when_filled`.

    Properties:
        text: str — the code content.
        visible: bool — false while `text` is blank, or whenever the flag is
            switched off explicitly.
    """

    _default_width = 'stretch'

    def __init__(
        self,
        text: str | Property = '',
        *,
        language: str = 'python',
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, visible=visible, **kwargs)
        self._language = language
        self.visible = _visible_when_filled(self.text, visible)


class Markdown(_HelpText):
    """A markdown block (mirrors Streamlit's `st.markdown`).

        v3.Markdown('Press :material/play_arrow: to **start**.')

    The source is parsed in the browser, just like Streamlit's, so the
    Streamlit-only extensions (`:material/..:` icons, `:color[..]` spans) work
    here as well. A blank line starts a new paragraph.

    A block with no source is hidden, so a bound source that is still empty
    leaves no gap behind.

    Args:
        text: the markdown source (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
        visible: the base-class flag, ANDed with the content test above --
            see `_visible_when_filled`.

    Properties:
        text: str — the markdown source.
        visible: bool — false while `text` is blank, or whenever the flag is
            switched off explicitly.
    """

    def __init__(
        self,
        text: str | Property = '',
        *,
        help: str | Property = '',
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, help=help, visible=visible, **kwargs)


class Text(_HelpText):
    """A text display component (mirrors Streamlit's `st.text`).

    A text with no content is hidden, so a bound text that is still empty
    leaves no gap behind.

    Args:
        text: the text content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
        visible: the base-class flag, ANDed with the content test above --
            see `_visible_when_filled`.
    """


class Title(_HelpText):
    """A title (heading) component (mirrors Streamlit's `st.title`).

    A title with no text is hidden, so a bound text that is still empty
    leaves no gap behind.

    Args:
        text: the title content (bindable).
        help: optional markdown tooltip shown next to the text.
        horizontal_alignment: "left" (default) | "center" | "right" -- where
            the heading sits in its box.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
        visible: the base-class flag, ANDed with the content test above --
            see `_visible_when_filled`.
    """

    def __init__(
        self,
        text: str | Property = '',
        horizontal_alignment: tp.Literal['left', 'center', 'right'] = 'left',
        *,
        help: str | Property = '',
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(text, help=help, visible=visible, **kwargs)
        self._horizontal_alignment = _validate_alignment(
            horizontal_alignment, 'horizontal_alignment'
        )


# Last rather than in alphabetical order: it subclasses `Title`, which has to
# be defined first (the same reason `_shared.py`'s private bases sit up front).
class PageTitle(Title):
    """A title that names the page as well as drawing one (a canary extra).

    Streamlit's `st.title` is a heading and nothing else: the tab is named
    once, up front, through `set_page_config(page_title=...)`. This element
    does both, so an app can write

        v3.PageTitle('mklink GUI')

    and have the heading and the tab agree. The heading parses the text as
    markdown like any other `Title`, while the tab keeps it as written --
    Streamlit's `page_title` is plain text, and `:material/..:` reads better
    as an icon on the page than as a shortcode in a tab. A bound text keeps
    the tab in step; an app that draws more than one leaves the last one
    naming the page.

    Args:
        text: the title content (bindable).
        help: optional markdown tooltip shown next to the text.
        horizontal_alignment: "left" (default) | "center" | "right" -- where
            the heading sits in its box.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """
