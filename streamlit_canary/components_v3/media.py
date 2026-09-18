"""Media elements: Streamlit's "Media elements" (`api-reference/media`).

`PdfViewer` -- Streamlit ships no PDF engine of its own: `st.pdf` is a thin
wrapper around the third-party `streamlit-pdf` component, and the reference
`pdf_watermaker` app previews documents with
`streamlit_pdf_viewer.pdf_viewer`. Both ship a whole viewer (pdf.js, ~2MB)
inside an iframe before a single page is drawn.

A browser already has a PDF engine, and `<embed type="application/pdf">`
reaches it directly. This viewer uses that: the server only hands the
document over (as a `data:` URL, cut down to the asked-for pages) and the
browser draws it. Nothing is rasterized, no engine is bundled, and the
payload is exactly the page range an app asks for.
"""

import base64
import io
import typing as tp

from ._shared import _visible_when_filled
from .base import Component
from ..kernel import Property


def _normalize_pages(pages: tp.Any) -> tp.Tuple[int, ...]:
    """`pages_to_render` as an ordered tuple of 1-based page numbers."""
    if pages is None:
        return ()
    if isinstance(pages, int):
        return (pages,)
    return tuple(int(page) for page in pages)


def _as_pdf_bytes(src: tp.Any) -> bytes:
    """The raw bytes behind a source: bytes pass through, else it is a path."""
    if isinstance(src, (bytes, bytearray, memoryview)):
        return bytes(src)
    if not src:
        return b''
    with open(str(src), 'rb') as fo:
        return fo.read()


def _subset(data: bytes, pages: tp.Tuple[int, ...]) -> bytes:
    """Keep only `pages`, in the order asked for, using `pikepdf`.

    An empty `pages` means "every page", which needs no library at all.
    Without `pikepdf` installed the document is passed through whole, so the
    viewer then shows all of it instead of the asked-for range.
    """
    wanted = [page for page in pages if page >= 1]
    if not wanted or not data:
        return data
    try:
        import pikepdf
    except ImportError:
        return data
    with pikepdf.open(io.BytesIO(data)) as pdf:
        total = len(pdf.pages)
        keep = [page for page in dict.fromkeys(wanted) if page <= total]
        if len(keep) == total:
            return data
        out = pikepdf.Pdf.new()
        for page in keep:
            out.pages.append(pdf.pages[page - 1])
        buffer = io.BytesIO()
        out.save(buffer)
        return buffer.getvalue()


def _to_url(src: tp.Any, pages: tp.Tuple[int, ...]) -> str:
    """A source (path / bytes / ready URL) as a browser-loadable `data:` URL.

    A missing file draws nothing (`''`) rather than failing: an app often
    points the viewer at a file it has not generated yet (see
    `pdf_watermaker_copy`'s watermark preview).
    """
    if isinstance(src, str) and src.startswith('data:'):
        return src
    try:
        data = _as_pdf_bytes(src)
    except OSError:
        return ''
    if not data:
        return ''
    encoded = base64.b64encode(_subset(data, pages)).decode('ascii')
    return 'data:application/pdf;base64,{}'.format(encoded)


class _UrlProperty(Property):
    """A `Property` that stores whatever is set on it as a `data:` URL.

    `PdfViewer.src` accepts a path, raw `bytes`, or a ready URL from every
    direction -- the constructor, `set()`, `bind()`, or a plain assignment --
    and normalizes it on the way in. Both consumers then read the same
    browser-loadable value: the renderer, and the `src` delta patch the
    runtime sends (which is why the property, not the renderer, owns the
    conversion -- a path or `bytes` could not travel to the client).
    """

    def __init__(self, pages: tp.Tuple[int, ...]) -> None:
        super().__init__('')
        self._pages = pages

    def set(self, value: tp.Any, notify: tp.Optional[bool] = None) -> None:
        super().set(_to_url(value, self._pages), notify)


class PdfViewer(Component):
    """A PDF viewer (mirrors `streamlit_pdf_viewer.pdf_viewer`).

    The pages are drawn by the browser's own PDF engine, through an
    `<embed type="application/pdf">`; there is no bundled viewer and nothing
    is rasterized on the server.

    Args:
        src: the PDF to show -- a file path, `bytes`, or a ready `data:`
            URL. Bindable: rebinding swaps the document in place (a `src`
            delta patch, no rerun).
        pages_to_render: 1-based page numbers to show, e.g. `(1, 2, 3)`. A
            subset is cut out of the document with `pikepdf`, so a long file
            only ships the pages asked for; empty (the default) shows every
            page. Needs `pikepdf` for a subset -- without it the whole
            document is shown.
        width: `int` px | 'stretch' (the default) | 'content' | 'auto'.
        height: `int` px | 'stretch' | None -- the box the browser scrolls
            the document inside, `500` by default. A PDF plugin needs a
            definite box, so there is no "hug the content" value.
        visible: bool (default True, bindable) -- the base-class flag, ANDed
            with the content test below (see `_visible_when_filled`).

    Properties:
        src: str -- the current document, always as a `data:` URL ('' when
            there is none). `set()` / `bind()` accept a path or `bytes` too.
        visible: bool -- false while there is no document, or whenever the
            flag is switched off explicitly.
    """

    _default_width = 'stretch'
    _default_height = 500

    def __init__(
        self,
        src: str | bytes | Property = '',
        *,
        pages_to_render: tp.Iterable[int] = (),
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(visible=visible, **kwargs)
        self.src: _UrlProperty = _UrlProperty(_normalize_pages(pages_to_render))
        if isinstance(src, Property):
            self.src.bind(src)
        else:
            self.src.set(src)
        self.visible = _visible_when_filled(self.src, visible)
