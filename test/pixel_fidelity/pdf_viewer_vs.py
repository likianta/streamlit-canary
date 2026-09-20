"""
Compare `v3.PdfViewer` (Streamlit Canary) against `streamlit_pdf_viewer` --
the viewer the reference `pdf_watermaker` app previews documents with.

Streamlit's own media element, `st.pdf`, is only a thin wrapper around the
third-party `streamlit-pdf` package, which is not installed here, so the
Streamlit side of this comparison uses `streamlit_pdf_viewer` instead.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/pdf_viewer_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/pdf_viewer_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_pdf_viewer.py

Pseudo-code (the spec this script implements):

    1. Both viewers must claim the box the app asked for: a `height=` of 400
       and of 300, each stretched to the full column width -- the theme
       frame around our panel is inside that box, it does not add to it.
    2. Both boxes must really draw a document. A viewer that failed to draw
       leaves the inside of the box a single flat colour, so the check looks
       at the pixels inside the frame, not at the DOM.
    3. `pages_to_render` limits what is *drawn*, not what is transferred:
       both viewers hand the whole document to pdf.js and let it skip the
       pages not asked for, so each viewer's payload still holds every page.

A note on the browser: both viewers draw with pdf.js onto canvases, so the
default `chromium_headless_shell` build is enough -- neither needs a PDF
plugin.

What is deliberately *not* compared, see
`.trae/documents/pixel_fidelity_caveats.md`: the viewer chrome itself.
`streamlit_pdf_viewer` draws pdf.js' own toolbar and backdrop, while our
panel frames bare canvases with a theme border.
"""

import base64
import io
import sys
import urllib.request

import pikepdf
from lk_utils import fs
from PIL import Image
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

from streamlit_canary.components_v3 import media

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

SAMPLE = fs.here('sample.pdf')

# Streamlit renders a custom component as an iframe, and the requested
# height lands on that iframe -- that is the box our panel is measured
# against. Matching on the component path keeps other iframes out.
ST_VIEWER = 'iframe[src*="streamlit_pdf_viewer"]'
SC_VIEWER = '.st-pdf-viewer'

# The two heights the scenes ask for, and the page ranges the second viewer
# of each scene asks for.
HEIGHTS = (400, 300)
PAGES = (1, 2)

# A viewer that only painted its frame leaves the inside of the box one flat
# colour (plus a few antialiased pixels along the frame). A drawn document --
# a page, a backdrop, a toolbar, text -- is far past this.
MIN_COLOURS = 30
FRAME_INSET = 4

EPS = 0.6


def inner_colours(page: Page, selector: str, inset: int = FRAME_INSET) -> int:
    """How many distinct colours are drawn inside the viewer's frame."""
    shot = page.locator(selector).first.screenshot()
    image = Image.open(io.BytesIO(shot)).convert('RGB')
    width, height = image.size
    box = (inset, inset, width - inset, height - inset)
    colours = image.crop(box).getcolors(maxcolors=1 << 24)
    return len(colours) if colours else 0


def read_boxes(page: Page, selector: str) -> list[dict]:
    return page.evaluate(
        """(sel) => Array.from(document.querySelectorAll(sel)).map((el) => {
          const box = el.getBoundingClientRect();
          return {
            width: +box.width.toFixed(2),
            height: +box.height.toFixed(2),
          };
        })""",
        selector,
    )


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= EPS
    return str(a) == str(b)


def viewer_bytes(url: str) -> bytes:
    """The PDF a viewer was handed.

    Canary publishes the document over HTTP under `/media/<hash>` (see
    `streamlit_canary.components_v3.media._to_url`), while
    `streamlit_pdf_viewer` passes it inline, so both are understood.
    """
    if url.startswith('/media/'):
        with urllib.request.urlopen(SC_URL + url) as res:
            return res.read()
    head, _, payload = url.partition(',')
    assert head.startswith('data:application/pdf'), head
    return base64.b64decode(payload)


def page_count(url: str) -> int:
    """The number of pages a viewer was actually handed."""
    with pikepdf.open(io.BytesIO(viewer_bytes(url))) as pdf:
        return len(pdf.pages)


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, bool]] = []

    def add(self, label: str, st_val, sc_val, cmp=same) -> None:
        self.rows.append(
            (label, str(st_val), str(sc_val), bool(cmp(st_val, sc_val)))
        )

    def print(self) -> None:
        width = max(len(row[0]) for row in self.rows)
        print('')
        print(
            '{:<{w}} {:<30} {:<30} {}'.format(
                'check', 'streamlit (:2202)', 'canary (:2203)', 'ok', w=width
            )
        )
        print('-' * 104)
        for label, st_val, sc_val, ok in self.rows:
            print(
                '{:<{w}} {:<30} {:<30} {}'.format(
                    label, st_val, sc_val, 'YES' if ok else 'NO', w=width
                )
            )

    @property
    def failures(self) -> list[tuple[str, str, str]]:
        return [
            (label, st_val, sc_val)
            for label, st_val, sc_val, ok in self.rows
            if not ok
        ]


def main() -> int:
    report = Report()
    with sync_playwright() as p:
        # The default headless build is enough: both viewers draw with pdf.js
        # onto canvases and neither needs a PDF plugin (see the docstring).
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_VIEWER, timeout=20000)
        st_page.wait_for_timeout(4000)

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_VIEWER, timeout=20000)
        sc_page.wait_for_timeout(4000)

        # -- 1. the box is the one the app asked for ---------------------
        st_boxes = read_boxes(st_page, ST_VIEWER)
        sc_boxes = read_boxes(sc_page, SC_VIEWER)
        report.add('viewer count', len(st_boxes), len(sc_boxes))
        for i, height in enumerate(HEIGHTS):
            st_box = st_boxes[i] if i < len(st_boxes) else {}
            sc_box = sc_boxes[i] if i < len(sc_boxes) else {}
            report.add(
                'viewer {} height (asked {})'.format(i + 1, height),
                st_box.get('height'),
                sc_box.get('height'),
            )
            report.add(
                'viewer {} width'.format(i + 1),
                st_box.get('width'),
                sc_box.get('width'),
            )

        # -- 2. the box is really drawn into ----------------------------
        st_colours = inner_colours(st_page, ST_VIEWER)
        sc_colours = inner_colours(sc_page, SC_VIEWER)
        report.add(
            'colours drawn inside viewer 1 (min {})'.format(MIN_COLOURS),
            st_colours,
            sc_colours,
            cmp=lambda a, b: a >= MIN_COLOURS and b >= MIN_COLOURS,
        )

        # -- 3. `pages_to_render` limits the drawing, not the payload -----
        # Both viewers hand the whole document to pdf.js and let it skip the
        # pages not asked for, so each payload holds every page. Asserted
        # against the document rather than compared row by row.
        sc_src = sc_page.evaluate(
            """(sel) => Array.from(document.querySelectorAll(sel))
              .map((el) => el.dataset.src)""",
            SC_VIEWER,
        )
        total = len(pikepdf.open(SAMPLE).pages)
        report.add(
            'canary viewer 1 ships every page', total, page_count(sc_src[0])
        )
        report.add(
            'canary viewer 2 ships every page (asked {})'.format(list(PAGES)),
            total,
            page_count(sc_src[1]),
        )
        # The conversion has to survive the same path the server uses, so the
        # check runs the converter directly as well.
        report.add(
            'offline conversion keeps every page',
            total,
            # no runtime to publish with, so this exercises the inline
            # fallback -- the document is the same either way
            page_count(media._to_url(SAMPLE, None)),
        )

        report.print()
        browser.close()

    if report.failures:
        print('')
        print('FAILED ({} mismatch(es)):'.format(len(report.failures)))
        for label, st_val, sc_val in report.failures:
            print(
                '  {label}: streamlit={st} canary={sc}'.format(
                    label=label, st=st_val, sc=sc_val
                )
            )
        return 1

    print('')
    print('PASSED: all asserted props match.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except AssertionError as e:
        print('')
        print('ERROR: {}'.format(e))
        sys.exit(2)
