"""
The PDF viewer scenes for the pixel fidelity test -- Streamlit Canary side.

The same two documents as `pdf_viewer_st.py`, drawn by `v3.PdfViewer`. Mind
the `pages_to_render` split: `streamlit_pdf_viewer` ships the whole document
and lets pdf.js leave the other pages out, while `v3.PdfViewer` cuts the
range out of the document server-side (with `pikepdf`), so only the pages
asked for travel to the browser at all.

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
