"""
The PDF viewer scenes for the pixel fidelity test -- Streamlit side.

Streamlit's own media element, `st.pdf`, is a thin wrapper around the
third-party `streamlit-pdf` package, which this environment does not have.
The reference `pdf_watermaker` app previews documents with
`streamlit_pdf_viewer.pdf_viewer`, so that is the counterpart the canary
`v3.PdfViewer` is compared against.

Start this app, then `pdf_viewer_sc.py`, then run `compare_pdf_viewer.py`
(its docstring has the exact commands):

    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/pdf_viewer_st.py

Both scenes draw the `sample.pdf` sitting next to them: a three-page A4
document (page headings "Sample" / "page N / 3"), made with reportlab.
"""

from lk_utils import fs
from streamlit_pdf_viewer import pdf_viewer

SAMPLE = fs.here('sample.pdf')


def main():
    # A plain viewer, then one that asks for a page range -- the two things
    # `v3.PdfViewer` has to match.
    pdf_viewer(SAMPLE, height=400)
    pdf_viewer(SAMPLE, height=300, pages_to_render=[1, 2])


if __name__ == '__main__':
    # python -m streamlit run \
    #   --browser.gatherUsageStats false --runner.magicEnabled false \
    #   --server.headless true --server.port 2202 \
    #   test/pixel_fidelity/pdf_viewer_st.py
    main()
