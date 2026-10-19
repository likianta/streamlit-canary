# Text Elements

Text elements display read-only content. They share a reactive `text`
field and default to `visible='auto'`: empty content hides the element.

## `Text`

Plain text. It is rendered literally: markdown is not parsed, and
whitespace is preserved.

```python
with v3.Text('Click count: 0') as txt:
    @state.count.on_change.partial(sc._self)
    def _(count):
        txt.text.set('Click count: {}'.format(count.get()))
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | The content |
| `font_family` | `str` | Optional font override |
| `font_size` | `str` | Optional size override |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

Properties: `text`.

Use `Text` when the content must never be interpreted as markdown, for
example a path, a file name, or user input.

## `Markdown`

Renders markdown. The source is stored in a `data-md` attribute and parsed
in the browser by the bundled `markdown-it`, so formatting, icons, and
colors stay consistent with the rest of the page.

```python
v3.Markdown('**Ready** in :green[3] seconds')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Markdown source |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

Properties: `text`.

Streamlit extensions are supported:

- `:color[text]`, for example `:red[error]`;
- `:material/icon_name:`, for material icons;
- emoji shortcodes such as `:smile:`;
- effect markers `:bold[x]`, `:italic[x]`, `:strike[x]`, `:underline[x]`.

The source is dedented and stripped before rendering, so a triple-quoted
block can be indented naturally.

## `Title`

A section heading.

```python
v3.Title('Configuration')
v3.Title('Centered', horizontal_alignment='center')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Heading text |
| `horizontal_alignment` | `'left' \| 'center' \| 'right'` | Default `'left'` |
| `help` | `str` | Optional tooltip |
| `font_family` | `str` | Optional font override |
| `font_size` | `str` | Optional size override |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

`Title(' ')` (exactly one space) is the supported way to reserve an empty
heading line.

## `PageTitle`

A `Title` that also configures the page. It writes the text into the
document title and accepts the page-level options.

```python
v3.PageTitle('My App', layout='wide', default_theme='dark')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Page title |
| `layout` | `'centered' \| 'wide'` | Page width |
| `default_theme` | `'light' \| 'dark'` | Theme |
| `font_family` | `str` | Page font family |
| `dunder_literal` | `bool` | Treat `__x__` as literal text |

`PageTitle` is a canary extra. For page-level configuration without a
visible heading, use [`PageConfig`](./page-config.md).

## `Caption`

Small, muted text.

```python
v3.Caption('Last updated: 2026-10-19')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Caption text |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

## `Code`

A code block. Canary renders it as plain monospace text; there is no
syntax highlighting.

```python
v3.Code('print("hello")', language='python')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `text` | `str \| Property` | Code text |
| `language` | `str` | Language label, default `'python'` |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

## Fonts and alignment

Pass `font_family=sc.MONOSPACE` when a column of text must line up with
code. Monospace also defaults the size one step down, because the same
pixel size looks larger in a monospaced face. Pass `font_size` to override
that.
