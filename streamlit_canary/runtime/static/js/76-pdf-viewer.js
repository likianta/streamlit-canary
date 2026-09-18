/* Experimental: the pdf.js engine (see `PdfViewer(enable_pdfjs=True)`).

   The browser's built-in viewer keeps its content to itself: the page cannot
   measure it or restyle it, so a box around one has to be sized by arithmetic
   (see `70-media.css`). pdf.js draws each page onto a canvas this page owns,
   so a viewer simply fits its document, and the pages follow the app's own
   styling.

   pdf.js is fetched only when a page actually asks for it. */
(function () {
  const LIB = '/static/pdfjs/pdf.min.mjs';
  const WORKER = '/static/pdfjs/pdf.worker.min.mjs';
  const MAX_DOCS = 4;

  let libPromise = null;
  const docs = new Map();

  function scPdfJs() {
    if (!libPromise) {
      libPromise = import(LIB).then((lib) => {
        lib.GlobalWorkerOptions.workerSrc = WORKER;
        return lib;
      });
    }
    return libPromise;
  }

  // one loaded document per source, so re-fitting after a resize does not
  // download it again (the sources are content-addressed and immutable)
  function scLoadDocument(src) {
    if (!docs.has(src)) {
      const loading = scPdfJs().then((lib) => lib.getDocument(src).promise);
      docs.set(src, loading);
      if (docs.size > MAX_DOCS) {
        const oldest = docs.keys().next().value;
        const dropped = docs.get(oldest);
        docs.delete(oldest);
        dropped.then((doc) => doc.destroy()).catch(() => {});
      }
    }
    return docs.get(src);
  }

  function scAskedPages(box, count) {
    const asked = (box.dataset.pages || '')
      .split(',')
      .map((x) => parseInt(x, 10))
      .filter((x) => x > 0);
    if (asked.length) {
      return asked;
    }
    return Array.from({ length: count }, (_, i) => i + 1);
  }

  async function scDrawPdfView(box) {
    const host = box.querySelector('.st-pdf-viewer-pages');
    if (!host) {
      return;
    }
    const src = box.dataset.src || '';
    // the width is part of the key: a resize asks for a fresh pass, while a
    // height change (which drawing itself causes) asks for nothing
    const token = src + '|' + Math.round(host.clientWidth);
    if (box._scPdfToken === token) {
      return;
    }
    box._scPdfToken = token;
    if (!src) {
      host.replaceChildren();
      return;
    }
    let doc;
    try {
      doc = await scLoadDocument(src);
    } catch (err) {
      host.textContent = 'pdf.js could not read this document: ' + err;
      return;
    }
    const width = host.clientWidth || box.clientWidth;
    if (!width) {
      return;
    }
    host.replaceChildren();
    for (const number of scAskedPages(box, doc.numPages)) {
      if (number > doc.numPages) {
        continue;
      }
      const page = await doc.getPage(number);
      const base = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: width / base.width });
      const canvas = document.createElement('canvas');
      canvas.className = 'st-pdf-viewer-page';
      canvas.width = Math.round(viewport.width);
      canvas.height = Math.round(viewport.height);
      await page.render({
        canvasContext: canvas.getContext('2d'),
        viewport: viewport,
      }).promise;
      if (box._scPdfToken !== token) {
        return; // a newer pass took over this box
      }
      host.appendChild(canvas);
    }
  }

  // a column that changes width needs its pages re-fitted; the delay keeps a
  // drag down to one pass
  let resizeTimer = 0;
  const resizeObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      document
        .querySelectorAll('.st-pdf-viewer--pdfjs')
        .forEach(scDrawPdfView);
    }, 150);
  });

  function scBootPdfViews(root) {
    (root || document)
      .querySelectorAll('.st-pdf-viewer--pdfjs')
      .forEach((box) => {
        resizeObserver.observe(box);
        scDrawPdfView(box);
      });
  }

  window.scBootPdfViews = scBootPdfViews;
  window.scDrawPdfView = scDrawPdfView;
})();
