# Media Elements

## `PdfViewer`

Displays a PDF in the page using the bundled `pdf.js`.

```python
sc.PdfViewer('manual.pdf')
sc.PdfViewer('https://example.com/report.pdf')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `src` | `str \| bytes` | A local path, a URL, or PDF bytes |
| `pages_to_render` | sequence of ints | Pages to draw; empty means all |
| `height` | size keyword | Default `500` |
| `max_height` | `int` | Cap the viewer height |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

Properties: `src`, `visible`.

`src` may be:

- a filesystem path;
- an HTTP(S) URL;
- raw PDF bytes.

`pages_to_render` limits which pages are drawn. This is useful for a large
document where only a few pages matter.

If only `max_height` is given, the height becomes `'content'` and the
viewer grows up to that cap. An empty `src` hides the viewer when
`visible='auto'`.
