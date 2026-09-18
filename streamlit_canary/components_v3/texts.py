"""Text elements: Streamlit's "Text elements" (`api-reference/text`).

`Caption`, `Code`, `Markdown`, `Text`, `Title`.
"""

import typing as tp

from ._shared import _HasText
from ._shared import _HelpText
from ._shared import _visible_when_filled
from ..kernel import Property


class Caption(_HelpText):
    """A small caption / helper text (mirrors Streamlit's `st.caption`).

    Args:
        text: the caption content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
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
        self.visible = _visible_when_filled(self.text, visible)


class Text(_HelpText):
    """A text display component (mirrors Streamlit's `st.text`).

    Args:
        text: the text content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """


class Title(_HelpText):
    """A title (heading) component (mirrors Streamlit's `st.title`).

    Args:
        text: the title content (bindable).
        help: optional markdown tooltip shown next to the text.
        width: `int` px | 'stretch' | 'content' | 'auto' (default; see
            `_HelpText`).
    """
