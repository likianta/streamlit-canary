"""
The PDF viewer scenes for the pixel fidelity test -- Streamlit Canary side.

The same two documents as `pdf_viewer_st.py`, drawn by `v3.PdfViewer`, which
paints with the bundled pdf.js. Note the `pages_to_render` split: both
viewers ship the whole document and let pdf.js leave the other pages out, so
`pages_to_render` limits what is *drawn* rather than what is transferred.

    python test/pixel_fidelity/pdf_viewer_sc.py
"""

import streamlit_canary as sc
from lk_utils import fs
from streamlit_canary import components_v3 as v3

SAMPLE = fs.here('sample.pdf')


def main():
    v3.PdfViewer(SAMPLE, height=400)
    v3.PdfViewer(SAMPLE, height=300, pages_to_render=(1, 2))


if __name__ == '__main__':
    # python test/pixel_fidelity/pdf_viewer_sc.py
    sc.run(main, port=2203)
