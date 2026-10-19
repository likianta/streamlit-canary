# Page Config

## `PageConfig`

Configures the page without rendering a visible element.

```python
v3.PageConfig(
    title='My App',
    layout='wide',
    default_theme='dark',
)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `title` | `str` | Document title |
| `layout` | `'centered' \| 'wide'` | Page width |
| `default_theme` | `'light' \| 'dark'` | Theme |
| `font_family` | `str` | Page font family |
| `dunder_literal` | `bool` | Treat `__x__` as literal text |

Every argument defaults to `None`, which means "leave this setting
alone". Page settings are written into a single global configuration;
later writers override earlier ones item by item.

`PageConfig` renders nothing. It is the class form of the older
`sc.set_page_config(...)`, which still works but is deprecated.

## `PageTitle`

`PageTitle` is `Title` and `PageConfig` combined. It draws a visible page
heading and also sets the document title and page options.

```python
v3.PageTitle('My App', layout='wide', default_theme='dark')
```

Use `PageTitle` when the app should show a heading. Use `PageConfig` when
the page needs configuration but no visible title.

## `dunder_literal`

Markdown normally reads `__text__` as bold. Real content often contains
dunder names such as `__init__` or `__name__`, which then turn bold by
accident.

Set `dunder_literal=True` to treat `__x__` as literal text. Bold remains
available as `**x**` or `:bold[x]`.

```python
v3.PageConfig(dunder_literal=True)
```

This is an experimental switch and is off by default.

## Document title updates

The first render sets the browser tab title from the page configuration.
After that, changing the text of a `PageTitle` patches the document title
as well. A title element is treated as plain text for this purpose, while
its visible heading still renders markdown.
