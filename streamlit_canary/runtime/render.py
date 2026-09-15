"""
Render the v3 component tree to HTML with Streamlit-style theming.

Uses CSS custom properties (--st-*) matching Streamlit's theme variable
convention. The dark theme is the default, matching Streamlit's built-in
dark theme colors.

Delta / event protocol is unchanged from Phase 3.
"""

from __future__ import annotations

import html
import re
import typing as tp

from lk_utils import fs

from ..components_v3.base import Component
from ..components_v3.widgets import Button
from ..components_v3.widgets import Caption
from ..components_v3.widgets import Cell
from ..components_v3.widgets import Checkbox
from ..components_v3.widgets import Code
from ..components_v3.widgets import Column
from ..components_v3.widgets import Expander
from ..components_v3.widgets import Grid
from ..components_v3.widgets import NumberInput
from ..components_v3.widgets import Popover
from ..components_v3.widgets import Radio
from ..components_v3.widgets import Row
from ..components_v3.widgets import Selectbox
from ..components_v3.widgets import Spinner
from ..components_v3.widgets import Success
from ..components_v3.widgets import Table
from ..components_v3.widgets import Tabs
from ..components_v3.widgets import Text
from ..components_v3.widgets import TextInput
from ..components_v3.widgets import Title
from ..components_v3.widgets import _TabPanel

# ---------------------------------------------------------------------------
# Streamlit-style markup: `:color[text]` and `:material/icon`
# ---------------------------------------------------------------------------

_COLOR_RE = re.compile(r':([a-zA-Z]+)\[([^\]]*)\]')
_MATERIAL_RE = re.compile(r':material/([a-zA-Z_]+):')
_BOLD_RE = re.compile(r'\*\*([^*]+)\*\*')
_ITALIC_RE = re.compile(r'\*([^*]+)\*')

_MATERIAL_MAP = {
    'autorenew': '\u21bb',
    'refresh': '\u21bb',
    'delete': '\u2715',
    'add': '+',
    'check': '\u2713',
    'close': '\u2715',
    'edit': '\u270e',
    'search': '\U0001f50d',
    'settings': '\u2699',
    'download': '\u2b07',
    'upload': '\u2b06',
}

# Streamlit's "basic color palette" *text* colors for the dark theme (see
# `config.py: *_TextColor`). This is what `:orange[..]`, `:green[..]`, etc.
# resolve to inside markdown, radios, captions, ...
_COLOR_CSS = {
    'red': '#ff6c6c',
    'orange': '#ffbd45',
    'yellow': '#ffffc2',
    'blue': '#3d9df3',
    'green': '#5ce488',
    'violet': '#b27eff',
    'gray': 'rgba(250, 250, 250, 0.6)',
    'grey': 'rgba(250, 250, 250, 0.6)',
    'rainbow': None,
}


def render_markup(text: str) -> str:
    """Convert Streamlit-style markup to HTML-safe spans."""
    # Typographer (matches Streamlit's markdown): '->' renders as an arrow.
    text = text.replace('->', '\u2192')
    text = html.escape(text)

    def _mat(m: re.Match) -> str:
        name = m.group(1)
        glyph = _MATERIAL_MAP.get(name, '\u25a1')
        return f'<span class="st-icon">{glyph}</span>'

    text = _MATERIAL_RE.sub(_mat, text)

    def _col(m: re.Match) -> str:
        color = m.group(1)
        inner = m.group(2)
        css = _COLOR_CSS.get(color)
        if css is None:
            return f'<span class="st-text-{color}">{inner}</span>'
        return f'<span style="color:{css}">{inner}</span>'

    text = _COLOR_RE.sub(_col, text)
    # inline emphasis: **bold** then *italic* (matches markdown)
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _ITALIC_RE.sub(r'<em>\1</em>', text)
    return text


# ---------------------------------------------------------------------------
# Component tree → HTML (Streamlit-style DOM)
# ---------------------------------------------------------------------------


def render_tree(roots: tp.Iterable[Component]) -> str:
    return ''.join(_render(comp) for comp in roots)


def _render(comp: Component) -> str:
    if isinstance(comp, Grid):
        cells = sorted(comp._cells.values(), key=lambda c: (c._row, c._col))
        children = ''.join(_render(c) for c in cells)
        return (
            f'<div class="st-grid" data-id="{comp.id}" '
            f'style="grid-template-columns:repeat({comp._columns},1fr)">'
            f'{children}</div>'
        )
    if isinstance(comp, Cell):
        children = ''.join(_render(c) for c in comp.children)
        return f'<div class="st-grid-cell" data-id="{comp.id}">{children}</div>'
    if isinstance(comp, Row):
        children = ''.join(_render(c) for c in comp.children)
        valign = getattr(comp, '_vertical_alignment', 'top')
        align_map = {
            'top': 'flex-start',
            'center': 'center',
            'bottom': 'flex-end',
        }
        align = align_map.get(valign, 'flex-start')
        return (
            f'<div class="st-row" data-id="{comp.id}" '
            f'style="align-items:{align}">{children}</div>'
        )
    if isinstance(comp, Column):
        children = ''.join(_render(c) for c in comp.children)
        border_cls = (
            ' st-container--border' if getattr(comp, '_border', False) else ''
        )
        width_style = ''
        w = getattr(comp, '_width', None)
        if isinstance(w, int):
            # Fixed-width column: opt out of `.st-row > * { flex: 1 }` so the
            # explicit width is honored and the sibling column fills the rest.
            width_style = f' style="flex:0 0 {w}px;width:{w}px"'
        return (
            f'<div class="st-container{border_cls}" data-id="{comp.id}"'
            f'{width_style}>{children}</div>'
        )
    if isinstance(comp, Tabs):
        return _render_tabs(comp)
    if isinstance(comp, _TabPanel):
        return _render_tab_panel(comp)
    if isinstance(comp, Expander):
        return _render_expander(comp)
    if isinstance(comp, Title):
        text = render_markup(str(comp.text.get()))
        return f'<h1 class="st-title" data-id="{comp.id}">{text}</h1>'
    if isinstance(comp, Caption):
        text = render_markup(str(comp.text.get()))
        return f'<div class="st-caption" data-id="{comp.id}">{text}</div>'
    if isinstance(comp, Text):
        text = render_markup(str(comp.text.get()))
        return f'<div class="st-text" data-id="{comp.id}">{text}</div>'
    if isinstance(comp, Spinner):
        children = ''.join(_render(c) for c in comp.children)
        hidden = '' if comp.visible.get() else ' hidden'
        text = render_markup(str(comp.text.get()))
        return (
            f'<div class="st-spinner" data-id="{comp.id}"{hidden}>'
            f'<span class="st-spinner-ring"></span>'
            f'<span class="st-spinner-text">{text}</span>'
            f'{children}</div>'
        )
    if isinstance(comp, Success):
        return _render_success(comp)
    if isinstance(comp, Popover):
        return _render_popover(comp)
    if isinstance(comp, Checkbox):
        return _render_checkbox(comp)
    if isinstance(comp, Button):
        return _render_button(comp)
    if isinstance(comp, NumberInput):
        return _render_number_input(comp)
    if isinstance(comp, TextInput):
        return _render_text_input(comp)
    if isinstance(comp, Table):
        return _render_table(comp)
    if isinstance(comp, Code):
        return _render_code(comp)
    if isinstance(comp, Selectbox):
        return _render_selectbox(comp)
    if isinstance(comp, Radio):
        return _render_radio(comp)
    return ''.join(_render(c) for c in comp.children)


def _render_paragraphs(text: str) -> str:
    """Render markdown-style paragraphs: blank lines split into `<p>`.

    Matches Streamlit's markdown behavior, where a blank line starts a new
    paragraph (a single newline inside a paragraph becomes a soft break).
    """
    text = text.strip('\n')
    if text == '':
        return ''
    parts = re.split(r'\n[ \t]*\n', text)
    return ''.join(f'<p>{render_markup(p)}</p>' for p in parts)


def _render_tabs(comp: Tabs) -> str:
    """Render a tab bar plus one panel per label (only one is visible)."""
    active = str(comp.active.get())
    buttons: list[str] = []
    panels: list[str] = []
    for label in comp._labels:
        escaped = html.escape(label)
        is_active = label == active
        selected = 'true' if is_active else 'false'
        buttons.append(
            f'<button class="st-tab{" is-active" if is_active else ""}"'
            f' type="button" role="tab" aria-selected="{selected}"'
            f' data-tab="{escaped}" onclick="scSelectTab(this)">'
            f'{escaped}</button>'
        )
        panel = comp._panels.get(label)
        body = ''.join(_render(c) for c in panel.children) if panel else ''
        hidden = '' if is_active else ' hidden'
        panels.append(
            f'<div class="st-tab-panel" role="tabpanel" data-tab="{escaped}"'
            f'{hidden}>{body}</div>'
        )
    return (
        f'<div class="st-tabs" data-id="{comp.id}">'
        f'<div class="st-tabs-bar" role="tablist">{"".join(buttons)}</div>'
        f'<div class="st-tabs-panels">{"".join(panels)}</div>'
        f'</div>'
    )


def _render_tab_panel(comp: _TabPanel) -> str:
    # Panels are normally rendered by `_render_tabs`; this branch only runs
    # if a panel ends up being rendered on its own.
    children = ''.join(_render(c) for c in comp.children)
    return (
        f'<div class="st-tab-panel" role="tabpanel"'
        f' data-tab="{html.escape(comp._label)}">{children}</div>'
    )


def _render_expander(comp: Expander) -> str:
    """Render a collapsible section (mirrors Streamlit's `st.expander`)."""
    label = _render_paragraphs(str(comp.label.get()))
    body = ''.join(_render(c) for c in comp.children)
    expanded = bool(getattr(comp, '_expanded', False))
    state = 'true' if expanded else 'false'
    cls = 'st-expander is-expanded' if expanded else 'st-expander'
    hidden = '' if expanded else ' hidden'
    return (
        f'<div class="{cls}" data-id="{comp.id}">'
        f'<div class="st-expander-header" role="button" tabindex="0"'
        f' aria-expanded="{state}" onclick="scToggleExpander(this)">'
        f'<span class="st-expander-icon">{_EXPANDER_ICON}</span>'
        f'<span class="st-expander-label">{label}</span>'
        f'</div>'
        f'<div class="st-expander-body"{hidden}>{body}</div>'
        f'</div>'
    )


def _render_success(comp: Success) -> str:
    """Render a green alert box (mirrors Streamlit's `st.success`)."""
    hidden = '' if comp.visible.get() else ' hidden'
    return (
        f'<div class="st-alert" data-id="{comp.id}"{hidden}>'
        f'<div class="st-alert-container" role="status">'
        f'<div class="st-alert-content">'
        f'<div class="st-alert-text">'
        f'{_render_paragraphs(str(comp.text.get()))}'
        f'</div></div></div></div>'
    )


def _render_button(comp: Button) -> str:
    label = _render_paragraphs(str(comp.text.get()))
    btn_type = getattr(comp, '_type', 'secondary')
    # Streamlit: type="secondary" is default, "primary" is the accent button.
    st_type = 'primary' if btn_type == 'primary' else 'secondary'
    cls = f'st-btn st-btn-{st_type}'
    width_style = _style_width(getattr(comp, '_width', None))
    disabled = '' if comp.enabled.get() else ' disabled'
    help_attr = ''
    if getattr(comp, '_help', None):
        help_text = html.escape(str(comp._help))
        help_attr = f' title="{help_text}"'
    return (
        f'<button class="{cls}" data-id="{comp.id}" type="button"{disabled} '
        f'onclick="scSendClick(this)"{width_style}{help_attr}>'
        f'<span class="st-btn-text">{label}</span></button>'
    )


def _widget_label_html(comp: Component) -> str:
    """Render a widget label, honouring `label_visibility`.

    Mirrors Streamlit's semantics:
        visible   : shown normally.
        hidden    : hidden, but still occupies its space.
        collapsed : hidden and removed from the layout.
    """
    visibility = getattr(comp, '_label_visibility', 'visible')
    cls = 'st-widget-label'
    if visibility == 'hidden':
        cls += ' st-widget-label--hidden'
    elif visibility == 'collapsed':
        cls += ' st-widget-label--collapsed'
    return (
        f'<label class="{cls}">{render_markup(str(comp.label.get()))}</label>'
    )


# Material icons: "content_copy" and "check" (same paths Streamlit uses).
_COPY_ICON = (
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14'
    'c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z">'
    '</path>'
)
_CHECK_ICON = (
    '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"></path>'
)
# Chevron-down used by the popover trigger (Streamlit's `expand_more`).
_CHEVRON_DOWN = (
    '<svg class="st-popover-chevron" viewBox="0 0 24 24" width="20" '
    'height="20" fill="currentColor" aria-hidden="true" focusable="false">'
    '<path fill="none" d="M0 0h24v24H0V0z"></path>'
    '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z">'
    '</path></svg>'
)
# Expander header chevron (material `keyboard_arrow_right`); CSS rotates it
# to point down while the section is expanded.
_EXPANDER_ICON = (
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
    '<path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"></path></svg>'
)
# Stepper glyphs for NumberInput (material `remove` / `add`).
_ICON_MINUS = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
    '<path d="M19 13H5v-2h14v2z"></path></svg>'
)
_ICON_PLUS = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
    '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"></path></svg>'
)


def _render_code(comp: Code) -> str:
    return (
        f'<div class="st-code" data-id="{comp.id}">'
        f'<pre><code>{html.escape(str(comp.text.get()))}</code></pre>'
        f'<div class="st-code-toolbar">'
        f'<span class="st-code-copy-chip">'
        f'<button class="st-code-copy" type="button" '
        f'aria-label="Copy to clipboard" title="Copy to clipboard" '
        f'onclick="scCopyCode(this)">'
        f'<svg class="icon-copy" viewBox="0 0 24 24" aria-hidden="true" '
        f'focusable="false" fill="currentColor">{_COPY_ICON}</svg>'
        f'<svg class="icon-done" viewBox="0 0 24 24" aria-hidden="true" '
        f'focusable="false" fill="currentColor">{_CHECK_ICON}</svg>'
        f'</button>'
        f'</span>'
        f'</div>'
        f'</div>'
    )


def _render_table(comp: Table) -> str:
    body = ''.join(
        '<tr>'
        f'<td class="st-table-cell"><p>{render_markup(str(key))}</p></td>'
        f'<td class="st-table-cell"><p>{render_markup(str(value))}</p></td>'
        '</tr>'
        for key, value in (comp.rows.get() or [])
    )
    return (
        f'<div class="st-table" data-id="{comp.id}">'
        f'<table class="st-table-table"><tbody>{body}</tbody></table>'
        f'</div>'
    )


def _style_width(width: tp.Any) -> str:
    """CSS `style` attribute for a widget's `width` argument.

    `'stretch'` fills the parent, an `int` is a pixel width, and
    `'content'` / `None` keeps the default (content-based) sizing.
    """
    if width is None or width == 'content':
        return ''
    if width == 'stretch':
        return ' style="width:100%"'
    if isinstance(width, int):
        return f' style="width:{width}px"'
    return f' style="width:{html.escape(str(width))}"'


def _format_number(comp: NumberInput, value: tp.Any) -> str:
    """Apply a widget's `format` callable, tolerating a type mismatch.

    `hex` on a float widget raises `TypeError`; the display then simply
    falls back to `str(value)`.
    """
    fmt = getattr(comp, 'format', None)
    if callable(fmt):
        try:
            return str(fmt(value))
        except (TypeError, ValueError):
            pass
    return str(value)


def _render_number_input(comp: NumberInput) -> str:
    value = comp.value.get()
    text = _format_number(comp, value)
    step = getattr(comp, '_step', None)
    min_value = getattr(comp, '_min', None)
    max_value = getattr(comp, '_max', None)
    placeholder = html.escape(str(getattr(comp, '_placeholder', '')))
    width_style = _style_width(getattr(comp, '_width', None))
    # `data-value` carries the raw (unformatted) number, which is what the
    # stepper does its arithmetic on.
    data = f' data-value="{html.escape(str(value))}"'
    if step is not None:
        data += f' data-step="{step}"'
    if min_value is not None:
        data += f' data-min="{min_value}"'
    if max_value is not None:
        data += f' data-max="{max_value}"'
    # A float widget without an explicit `step` shows no stepper.
    stepper = ''
    if step is not None:
        stepper = (
            '<span class="st-number-stepper">'
            f'<button class="st-number-step" type="button" tabindex="-1" '
            f'title="Decrease" onclick="scStepNumber(this, -1)">'
            f'{_ICON_MINUS}</button>'
            f'<button class="st-number-step" type="button" tabindex="-1" '
            f'title="Increase" onclick="scStepNumber(this, 1)">'
            f'{_ICON_PLUS}</button>'
            '</span>'
        )
    return (
        f'<div class="st-number-input" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-number-box"{width_style}>'
        f'<input class="st-text-input-box" type="text" '
        f'data-comp-id="{comp.id}"{data} '
        f'value="{html.escape(text)}" '
        f'placeholder="{placeholder}" '
        f'onchange="scSendChange(this)"/>'
        f'{stepper}</div></div>'
    )


def _render_text_input(comp: TextInput) -> str:
    placeholder = html.escape(str(getattr(comp, '_placeholder', '')))
    return (
        f'<div class="st-text-input" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<input class="st-text-input-box" type="text" '
        f'data-comp-id="{comp.id}" '
        f'value="{html.escape(str(comp.value.get()))}" '
        f'placeholder="{placeholder}" '
        f'onchange="scSendChange(this)"/>'
        f'</div>'
    )


def _render_selectbox(comp: Selectbox) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = comp.format_func
    # Build option items for the custom dropdown panel. Two-layer structure
    # matches Streamlit: outer (padding 0 5px) + inner (padding 0 8px), so
    # the hover background on the inner div is inset from the panel edges.
    opt_items = ''.join(
        f'<div class="st-selectbox-option" role="option" '
        f'data-value="{html.escape(str(o))}" '
        f'data-comp-id="{comp.id}" '
        f'onclick="scSelectOption(this)" '
        f'{"data-selected" if o == value else ""}>'
        f'<div class="st-selectbox-option-inner">'
        f'{render_markup(fmt(o))}</div></div>'
        for o in options
    )
    # Display text for the trigger button.
    display_text = render_markup(fmt(value)) if value else '\u200b'
    arrow_svg = (
        '<svg class="st-selectbox-arrow" viewBox="0 0 24 24" '
        'width="20" height="20" fill="currentColor">'
        '<path fill="none" d="M0 0h24v24H0V0z"></path>'
        '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 '
        '1.41-1.41z"></path>'
        '</svg>'
    )
    return (
        f'<div class="st-selectbox" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-selectbox-control">'
        f'<button type="button" class="st-selectbox-trigger" '
        f'data-comp-id="{comp.id}" onclick="scToggleSelectbox(this)">'
        f'<span class="st-selectbox-value">{display_text}</span>'
        f'{arrow_svg}'
        f'</button>'
        f'<div class="st-selectbox-dropdown" '
        f'data-comp-id="{comp.id}" hidden>{opt_items}</div>'
        f'</div></div>'
    )


def _render_radio(comp: Radio) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = comp.format_func
    items = ''.join(
        f'<label class="st-radio-item">'
        f'<span class="st-radio-input-wrap">'
        f'<input type="radio" name="radio_{comp.id}" '
        f'value="{html.escape(str(o))}" '
        f'{"checked" if o == value else ""} '
        f'onchange="scSendChange(this)" '
        f'data-comp-id="{comp.id}"/></span>'
        f'<div class="st-radio-item-body">'
        f'<div class="st-radio-item-row">'
        f'<div class="st-radio-circle">'
        f'<div class="st-radio-dot"></div></div>'
        f'<div class="st-radio-markdown">'
        f'<p>{render_markup(fmt(o))}</p>'
        f'</div></div></div></label>'
        for o in options
    )
    root_cls = 'st-radio'
    if getattr(comp, '_horizontal', False):
        root_cls += ' st-radio--horizontal'
    return (
        f'<div class="{root_cls}" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-radio-group">{items}</div>'
        f'</div>'
    )


def _render_checkbox(comp: Checkbox) -> str:
    checked = ' checked' if comp.value.get() else ''
    return (
        f'<div class="st-checkbox" data-id="{comp.id}">'
        f'<label class="st-checkbox-label">'
        f'<span class="st-checkbox-input-wrap">'
        f'<input type="checkbox" data-comp-id="{comp.id}" '
        f'{checked} onchange="scSendCheck(this)"/></span>'
        f'<div class="st-checkbox-box">'
        f'<svg viewBox="0 0 10 8" aria-hidden="true">'
        f'<polyline points="1 4 4 7 9 1"></polyline></svg></div>'
        f'<div class="st-checkbox-text">'
        f'{render_markup(str(comp.label.get()))}</div>'
        f'</label></div>'
    )


def _render_popover(comp: Popover) -> str:
    label = _render_paragraphs(str(comp.text.get()))
    children = ''.join(_render(c) for c in comp.children)
    return (
        f'<div class="st-popover" data-id="{comp.id}">'
        f'<button class="st-btn st-btn-secondary st-popover-trigger" '
        f'type="button" aria-haspopup="dialog" aria-expanded="false" '
        f'onclick="scTogglePopover(this)">'
        f'<span class="st-btn-text st-popover-trigger-label">{label}</span>'
        f'<span class="st-popover-icon">{_CHEVRON_DOWN}</span>'
        f'</button>'
        f'<div class="st-popover-panel" role="dialog" hidden>'
        f'{children}'
        f'</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Page template with Streamlit dark theme
# ---------------------------------------------------------------------------


def _load_static(filename: str) -> str:
    """Load a bundled static asset (CSS/JS) next to this module."""
    return fs.load(fs.here('static/' + filename), 'plain').strip()


_DARK_THEME_VARS = _load_static('theme-dark.css')

_LIGHT_THEME_VARS = _load_static('theme-light.css')

_PAGE_CSS = _load_static('page.css')

_PAGE_JS = _load_static('page.js')

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
{theme_vars}
{page_css}
</style>
</head>
<body>
<div id="app">{body}</div>
<script>
{page_js}
</script>
</body>
</html>
"""


def render_page(
    roots: tp.Iterable[Component],
    title: str = 'Streamlit Canary',
    default_theme: str = 'dark',
) -> str:
    theme_vars = (
        _DARK_THEME_VARS if default_theme == 'dark' else _LIGHT_THEME_VARS
    )
    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        theme_vars=theme_vars.strip(),
        page_css=_PAGE_CSS.strip(),
        page_js=_PAGE_JS.strip(),
        body=render_tree(roots),
    )
