"""Media elements: Streamlit's "Media elements" (`api-reference/media`).

`PdfViewer` -- Streamlit ships no PDF engine of its own: `st.pdf` is a thin
wrapper around the third-party `streamlit-pdf` component, and the reference
`pdf_watermaker` app previews documents with
`streamlit_pdf_viewer.pdf_viewer`. Both ship a whole viewer (pdf.js, ~2MB)
inside an iframe before a single page is drawn.

A browser already has a PDF engine, and `<embed type="application/pdf">`
reaches it directly. This viewer uses that by default: the server only hands
the document over (cut down to the asked-for pages, and published under
`/media/<hash>` -- see `VIEW_PARAMS` for why it cannot simply go inline) and
the browser draws it. Nothing is rasterized, no engine is bundled, and the
payload is exactly the page range an app asks for.

`enable_pdfjs=True` swaps in the other engine -- the pdf.js bundled under
`runtime/static/pdfjs`, drawn page by page onto canvases. It costs a bigger
download, and buys back the two things the built-in viewer keeps to itself
(its content is opaque to the page): a box that fits the document exactly,
and view options that are ours to set, on any browser.
"""

import base64
import io
import typing as tp

from ._shared import _visible_when_filled
from .base import Component
from .base import Height
from ..kernel import Property

VIEW_PARAMS = '#navpanes=0&zoom=page-width'
"""How the built-in viewer opens a document: the bookmarks panel stays shut,
and the page is fitted to the *width* of the box instead of to the whole
page. `zoom=page-fit` -- the viewer's own default -- letterboxes a page into
what is usually a short box, which leaves the text unreadably small.

The viewer only reads these off an http(s) URL. A `data:` URL *is* the
document, and everything after its `#` is dropped, so the bytes are published
by the runtime instead of inlined (see `Runtime.publish_media`)."""

CONTENT_HEIGHT: Height = 'content'
"""The `height` value that makes the box as tall as the document rather than
a fixed size, still capped by `max_height`.

The built-in viewer will not say how tall its content is -- `fit-content` on
a PDF `<embed>` collapses to the 150px every replaced element falls back to
-- so the box is *calculated* from the pages' shape (`_page_ratio`) plus the
viewer's own furniture, in CSS:

    height: calc((100cqw - inset) * ratio + chrome)   # see `70-media.css`

Both constants are the built-in viewer's, measured on Chromium; another
browser pads its viewer differently, so there the box may miss by a few dozen
px (it errs slightly tall, which reads as a little slack rather than as a
scrollbar).

With `enable_pdfjs=True` none of that is needed: pdf.js draws onto real
canvases, so the box simply fits them and this means plain `height: auto`.

Any other value is the usual sizing keyword (see `Component`)."""


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


def _page_ratio(data: bytes) -> float:
    """The document's shape: the pages' total height per unit of width.

    A viewer opened with `zoom=page-width` draws a page as wide as the box, so
    the height it needs is ``box_width * this``. `_to_url` sends it along as
    `?ratio=`, which is how a box can be sized to the document without having
    to ask the server again (see `CONTENT_HEIGHT`).

    `0.0` when the shape cannot be read -- not a PDF, or no `pikepdf` -- and
    the box then falls back to a definite height.
    """
    try:
        import pikepdf
    except ImportError:
        return 0.0
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            total = 0.0
            for page in pdf.pages:
                box = page.mediabox
                width = float(box[2]) - float(box[0])
                height = float(box[3]) - float(box[1])
                if width > 0:
                    total += height / width
            return total
    except pikepdf.PdfError:
        return 0.0


def _decode_data_url(url: str) -> bytes:
    """The bytes behind a base64 `data:` URL (`b''` when it is malformed)."""
    _, _, payload = url.partition(',')
    try:
        return base64.b64decode(payload, validate=False)
    except (ValueError, TypeError):
        return b''


def _to_url(src: tp.Any, pages: tp.Tuple[int, ...], runtime: tp.Any) -> str:
    """A source (path / bytes / ready URL) as a URL the browser can load.

    Paths and raw bytes are handed to the runtime to publish, which is what
    buys the http URL that `VIEW_PARAMS` needs; with no runtime to publish to
    (a component built outside one) the bytes go inline as a `data:` URL,
    which shows the same document minus the view options.

    A missing file draws nothing (`''`) rather than failing: an app often
    points the viewer at a file it has not generated yet (see
    `pdf_watermaker_copy`'s watermark preview).
    """
    if isinstance(src, str) and src.startswith('/media/'):
        return src  # already published, e.g. the same value set twice
    if isinstance(src, str) and src.startswith('data:'):
        data = _decode_data_url(src)
    else:
        try:
            data = _as_pdf_bytes(src)
        except OSError:
            return ''
    if not data:
        return ''
    data = _subset(data, pages)
    if runtime is None:
        encoded = base64.b64encode(data).decode('ascii')
        return 'data:application/pdf;base64,{}'.format(encoded)
    url = runtime.publish_media(data, 'application/pdf')
    # the shape goes along with the document, so a `src` patch lets the client
    # re-size the box on its own (see `CONTENT_HEIGHT`)
    ratio = _page_ratio(data)
    if ratio > 0:
        url += '?ratio={:.4f}'.format(ratio)
    return url + VIEW_PARAMS


class _UrlProperty(Property):
    """A `Property` that stores whatever is set on it as a loadable URL.

    `PdfViewer.src` accepts a path, raw `bytes`, or a ready URL from every
    direction -- the constructor, `set()`, `bind()`, or a plain assignment --
    and normalizes it on the way in. Both consumers then read the same
    browser-loadable value: the renderer, and the `src` delta patch the
    runtime sends (which is why the property, not the renderer, owns the
    conversion -- a path or `bytes` could not travel to the client).
    """

    def __init__(self, pages: tp.Tuple[int, ...], runtime: tp.Any) -> None:
        super().__init__('')
        self._pages = pages
        self._runtime = runtime

    def set(self, value: tp.Any, notify: tp.Optional[bool] = None) -> None:
        super().set(_to_url(value, self._pages, self._runtime), notify)


class PdfViewer(Component):
    """A PDF viewer (mirrors `streamlit_pdf_viewer.pdf_viewer`).

    The pages are drawn by the browser's own PDF engine, through an
    `<embed type="application/pdf">`; there is no bundled viewer and nothing
    is rasterized on the server. `enable_pdfjs=True` asks for the bundled
    pdf.js instead (see the module docstring).

    Args:
        src: the PDF to show -- a file path, `bytes`, or a ready URL (a
            `data:` one is published again, so the view options still
            apply). Bindable: rebinding swaps the document in place (a
            `src` delta patch, no rerun).
        pages_to_render: 1-based page numbers to show, e.g. `(1, 2, 3)`. A
            subset is cut out of the document with `pikepdf`, so a long file
            only ships the pages asked for; empty (the default) shows every
            page. Needs `pikepdf` for a subset -- without it the whole
            document is shown.
        enable_pdfjs: draw with the bundled pdf.js rather than the browser's
            own viewer. Experimental: the download is bigger, and nothing
            appears until that JavaScript has loaded.
        width: `int` px | 'stretch' (the default) | 'content' | 'auto'.
        height: `int` px | 'stretch' | 'content' | None. `None` -- the usual
            default -- leaves the box at `500`px, the size `st.pdf` starts
            at too; `'content'` makes it as tall as the document (see
            `CONTENT_HEIGHT`). A `max_height` without a `height` means
            `'content'`: an upper bound on its own can only mean "as tall as
            it needs to be, up to this".
        max_height: `int` px -- an upper bound on the height; whatever does
            not fit scrolls.
        visible: bool (default True, bindable) -- the base-class flag, ANDed
            with the content test below (see `_visible_when_filled`).

    Properties:
        src: str -- the current document, always as a URL the browser can
            fetch and that carries the view options ('' when there is none).
            `set()` / `bind()` accept a path or `bytes` too.
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
        enable_pdfjs: bool = False,
        height: Height | None = None,
        max_height: int | None = None,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        if height is None and max_height is not None:
            height = CONTENT_HEIGHT
        super().__init__(
            height=height, max_height=max_height, visible=visible, **kwargs
        )
        self._enable_pdfjs = enable_pdfjs
        self._pages = _normalize_pages(pages_to_render)
        # the runtime building this tree is the one to publish the document
        # with, and it has to be kept: `src` is usually set long after the
        # build, from an event handler, by which time
        # `Component._active_runtime` is None again.
        self.src: _UrlProperty = _UrlProperty(
            self._pages, Component._active_runtime
        )
        if isinstance(src, Property):
            self.src.bind(src)
        else:
            self.src.set(src)
        self.visible = _visible_when_filled(self.src, visible)
