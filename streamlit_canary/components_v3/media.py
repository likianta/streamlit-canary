"""Media elements: Streamlit's "Media elements" (`api-reference/media`).

`PdfViewer` -- Streamlit ships no PDF engine of its own: `st.pdf` is a thin
wrapper around the third-party `streamlit-pdf` component, and the reference
`pdf_watermaker` app previews documents with
`streamlit_pdf_viewer.pdf_viewer`. Both ship a whole viewer (pdf.js, ~2MB)
inside an iframe before a single page is drawn.

We bundle the same engine, but draw it inside our own page rather than an
iframe: the pdf.js under `runtime/static/pdfjs` paints the pages onto
canvases this page owns, and the server's only job is to hand the document
over. Nothing is rasterized on the server and no PDF library is needed
there -- see `_to_url` for why this engine, and what it replaced.
"""

import base64
import typing as tp

from ._shared import _visible_when_filled
from .base import Component
from .base import Height
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


def _decode_data_url(url: str) -> bytes:
    """The bytes behind a base64 `data:` URL (`b''` when it is malformed)."""
    _, _, payload = url.partition(',')
    try:
        return base64.b64decode(payload, validate=False)
    except (ValueError, TypeError):
        return b''


def _to_url(src: tp.Any, runtime: tp.Any) -> str:
    """A source (path / bytes / ready URL) as a URL the browser can load.

    Paths and raw bytes are handed to the runtime to publish, which gives a
    short, content-addressed URL the pdf.js client can fetch; with no runtime
    to publish to (a component built outside one) the bytes go inline as a
    `data:` URL, which pdf.js reads just as happily.

    A missing file draws nothing (`''`) rather than failing: an app often
    points the viewer at a file it has not generated yet (see
    `pdf_watermaker_copy`'s watermark preview).
    """
    # -- technical memo: why pdf.js, and not the browser's own viewer -------
    # why pdf.js: it is the only engine that draws a PDF *inside this page*,
    # and every requirement below follows from that.
    #   - the pages become canvases this page owns, so a box asked for
    #     `height='content'` is genuinely as tall as the document, and a
    #     `max_height` bound caps it and scrolls it like any other box.
    #   - it draws the same on every browser, including the headless builds
    #     that carry no PDF plugin.
    #   - `pages_to_render` is left to the client, so the server needs no
    #     PDF library at all.
    # the engine is fetched only by a page that really shows a viewer (see
    # `76-pdf-viewer.js`), so a page without a `PdfViewer` never pays for it.
    #
    # what it replaced: handing the document to the browser's own viewer as
    # `<embed type="application/pdf" src=...>`. That needs no engine of ours,
    # because the browser takes the box over. The version worked like this:
    # the server cut the asked-for pages out of the document with `pikepdf`,
    # published the cut bytes under `/media/<hash>`, and put that URL on the
    # `<embed>`, with open parameters (`#navpanes=0&zoom=page-width`) on the
    # end to shut the bookmarks panel and fit a page to the box's width.
    # it was dropped because a box around a viewer we do not control is
    # guesswork. The viewer never reports its content height (`height: auto`
    # on a PDF `<embed>` collapses to the 150px every replaced element falls
    # back to), so `height='content'` had to be *calculated*: one `pikepdf`
    # pass per document for the pages' shape, plus two Chromium-measured
    # constants for the viewer's own furniture, which miss by a few dozen px
    # on any other browser. It also needs a real PDF plugin, absent from the
    # headless chromium the tests use, and the page range had to be cut on
    # the server (`pikepdf` again) because an `<embed>` cannot be told which
    # pages to show. One engine, one behaviour, on every browser -- this one.
    # ----------------------------------------------------------------------
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
    if runtime is None:
        encoded = base64.b64encode(data).decode('ascii')
        return 'data:application/pdf;base64,{}'.format(encoded)
    return runtime.publish_media(data, 'application/pdf')


class _UrlProperty(Property):
    """A `Property` that stores whatever is set on it as a loadable URL.

    `PdfViewer.src` accepts a path, raw `bytes`, or a ready URL from every
    direction -- the constructor, `set()`, `bind()`, or a plain assignment --
    and normalizes it on the way in. Both consumers then read the same
    browser-loadable value: the renderer, and the `src` delta patch the
    runtime sends (which is why the property, not the renderer, owns the
    conversion -- a path or `bytes` could not travel to the client).
    """

    def __init__(self, runtime: tp.Any) -> None:
        super().__init__('')
        self._runtime = runtime

    def set(self, value: tp.Any, notify: tp.Optional[bool] = None) -> None:
        super().set(_to_url(value, self._runtime), notify)


class PdfViewer(Component):
    """A PDF viewer (mirrors `streamlit_pdf_viewer.pdf_viewer`).

    The pages are drawn by the pdf.js bundled under `runtime/static/pdfjs`,
    each onto a canvas this page owns (`76-pdf-viewer.js`). Nothing is
    rasterized on the server, and the server needs no PDF library: the
    document is only handed over (see the module docstring).

    Args:
        src: the PDF to show -- a file path, `bytes`, or a ready URL (a
            `data:` one is published again, so it gets a cacheable address).
            Bindable: rebinding swaps the document in place (a `src` delta
            patch, no rerun).
        pages_to_render: 1-based page numbers to draw, e.g. `(1, 2, 3)`.
            The client leaves the other pages out, so this limits what is
            *drawn*, not what is transferred; empty (the default) draws
            every page.
        width: `int` px | 'stretch' (the default) | 'content' | 'auto'.
        height: `int` px | 'stretch' | 'content' | None. `None` -- the usual
            default -- leaves the box at `500`px, the size `st.pdf` starts
            at too; `'content'` makes it as tall as the document. A
            `max_height` without a `height` means `'content'`: an upper
            bound on its own can only mean "as tall as it needs to be, up
            to this".
        max_height: `int` px -- an upper bound on the height; whatever does
            not fit scrolls.
        visible: bool (default True, bindable) -- the base-class flag, ANDed
            with the content test below (see `_visible_when_filled`).

    Properties:
        src: str -- the current document, always as a URL the browser can
            fetch ('' when there is none). `set()` / `bind()` accept a path
            or `bytes` too.
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
        height: Height | None = None,
        max_height: int | None = None,
        visible: bool | Property = True,
        **kwargs: tp.Any,
    ) -> None:
        if height is None and max_height is not None:
            height = 'content'
        super().__init__(
            height=height, max_height=max_height, visible=visible, **kwargs
        )
        self._pages = _normalize_pages(pages_to_render)
        # the runtime building this tree is the one to publish the document
        # with, and it has to be kept: `src` is usually set long after the
        # build, from an event handler, by which time
        # `Component._active_runtime` is None again.
        self.src: _UrlProperty = _UrlProperty(Component._active_runtime)
        if isinstance(src, Property):
            self.src.bind(src)
        else:
            self.src.set(src)
        self.visible = _visible_when_filled(self.src, visible)
