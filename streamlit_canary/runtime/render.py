"""
Render the v3 component tree to HTML with Streamlit-style theming.

Uses CSS custom properties (--st-*) matching Streamlit's theme variable
convention. The dark theme is the default, matching Streamlit's built-in
dark theme colors.

Delta / event protocol is unchanged from Phase 3.
"""

from __future__ import annotations

import html
import json
import typing as tp

from lk_utils import fs

from ..components_v3.base import Component
from ..components_v3.widgets import AltairChart
from ..components_v3.widgets import Button
from ..components_v3.widgets import Caption
from ..components_v3.widgets import Cell
from ..components_v3.widgets import Checkbox
from ..components_v3.widgets import Code
from ..components_v3.widgets import Column
from ..components_v3.widgets import Dialog
from ..components_v3.widgets import Expander
from ..components_v3.widgets import Grid
from ..components_v3.widgets import Info
from ..components_v3.widgets import Multiselect
from ..components_v3.widgets import NumberInput
from ..components_v3.widgets import Popover
from ..components_v3.widgets import Progress
from ..components_v3.widgets import Radio
from ..components_v3.widgets import Row
from ..components_v3.widgets import SelectSlider
from ..components_v3.widgets import Selectbox
from ..components_v3.widgets import Spinner
from ..components_v3.widgets import Success
from ..components_v3.widgets import Table
from ..components_v3.widgets import Tabs
from ..components_v3.widgets import Text
from ..components_v3.widgets import TextArea
from ..components_v3.widgets import TextInput
from ..components_v3.widgets import Title
from ..components_v3.widgets import Toggle
from ..components_v3.widgets import Warning
from ..components_v3.widgets import _TabPanel
from ..kernel.property import Property

# ---------------------------------------------------------------------------
# Markdown: parsed in the browser (see `page.js` and the bundled markdown-it)
# ---------------------------------------------------------------------------


def render_markup(text: str) -> str:
    """Emit an inline markdown placeholder for the browser to render.

    Streamlit parses markdown client-side (react-markdown); we mirror that
    with the bundled markdown-it. The server only transports the source in
    `data-md`; `page.js` fills the placeholder on load and again on every
    delta patch, so the full markdown syntax works everywhere markdown is
    accepted -- `Text` / `Caption` / `Title`, widget labels, radio options,
    alerts, button labels and `help` tooltips.

    Inline context: no `<p>` wrapper is implied (use `_render_paragraphs`
    for multi-paragraph bodies). Streamlit's own `:color[..]` and
    `:material/..:` extensions are applied by `page.js` as well.
    """
    raw = str(text)
    if raw == '':
        return ''
    escaped = html.escape(raw, quote=True)
    return f'<span class="st-md" data-md="{escaped}"></span>'


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
        rules: list[str] = []
        w = getattr(comp, '_width', None)
        weight = getattr(comp, '_weight', None)
        if isinstance(w, int):
            # Fixed-width column: opt out of `.st-row > * { flex: 1 }` so the
            # explicit width is honored and the sibling column fills the rest.
            rules.append(f'flex:0 0 {w}px')
            rules.append(f'width:{w}px')
            rules.append('min-width:0')
        elif weight is not None:
            # Weighted columns, e.g. `st.columns((5, 2))`.
            rules.append(f'flex:{weight} 1 0%')
            # A flex item's automatic minimum is its min-content width, which
            # lets a wide child (a chart, a nowrap row of labels) push the
            # column past its share and wrap the row onto two lines. Pinning
            # the minimum to 0 keeps the weight authoritative.
            rules.append('min-width:0')
        height = getattr(comp, '_height', None)
        if isinstance(height, int):
            # Fixed-height container: the content scrolls once it overflows.
            rules.append(f'height:{height}px')
            rules.append('overflow:auto')
        style = f' style="{";".join(rules)}"' if rules else ''
        hidden = '' if comp.visible.get() else ' hidden'
        reveal_cls = ' st-reveal' if getattr(comp, '_animated', False) else ''
        return (
            f'<div class="st-container{border_cls}{reveal_cls}"'
            f' data-id="{comp.id}"'
            f'{style}{hidden}>{children}</div>'
        )
    if isinstance(comp, Tabs):
        return _render_tabs(comp)
    if isinstance(comp, _TabPanel):
        return _render_tab_panel(comp)
    if isinstance(comp, Dialog):
        return _render_dialog(comp)
    if isinstance(comp, Expander):
        return _render_expander(comp)
    if isinstance(comp, Title):
        text = render_markup(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<h1 class="st-title" data-id="{comp.id}">{text}{help_html}</h1>'
        )
    if isinstance(comp, Caption):
        text = render_markup(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<div class="st-caption" data-id="{comp.id}">'
            f'{text}{help_html}</div>'
        )
    if isinstance(comp, Text):
        text = render_markup(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<div class="st-text" data-id="{comp.id}">{text}{help_html}</div>'
        )
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
    if isinstance(comp, (Success, Warning, Info)):
        return _render_alert(comp)
    if isinstance(comp, Popover):
        return _render_popover(comp)
    if isinstance(comp, Progress):
        return _render_progress(comp)
    if isinstance(comp, AltairChart):
        return _render_altair_chart(comp)
    if isinstance(comp, Toggle):
        return _render_toggle(comp)
    if isinstance(comp, Checkbox):
        return _render_checkbox(comp)
    if isinstance(comp, Button):
        return _render_button(comp)
    if isinstance(comp, NumberInput):
        return _render_number_input(comp)
    if isinstance(comp, TextArea):
        return _render_text_area(comp)
    if isinstance(comp, TextInput):
        return _render_text_input(comp)
    if isinstance(comp, Table):
        return _render_table(comp)
    if isinstance(comp, Code):
        return _render_code(comp)
    if isinstance(comp, Multiselect):
        return _render_multiselect(comp)
    if isinstance(comp, SelectSlider):
        return _render_select_slider(comp)
    if isinstance(comp, Selectbox):
        return _render_selectbox(comp)
    if isinstance(comp, Radio):
        return _render_radio(comp)
    return ''.join(_render(c) for c in comp.children)


def _render_paragraphs(text: str) -> str:
    """Emit a block markdown placeholder for the browser to render.

    Block-context counterpart of `render_markup`: markdown-it wraps each
    block in `<p>`, matching Streamlit's behavior (a blank line starts a new
    paragraph, a single newline inside one is a soft break).
    """
    raw = str(text).strip('\n')
    if raw == '':
        return ''
    escaped = html.escape(raw, quote=True)
    return f'<div class="st-md st-md-block" data-md="{escaped}"></div>'


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


def _render_dialog(comp: Dialog) -> str:
    """Render a modal dialog: a fixed backdrop plus a centred panel."""
    title = render_markup(str(comp.text.get()))
    children = ''.join(_render(c) for c in comp.children)
    hidden = '' if comp.visible.get() else ' hidden'
    width = getattr(comp, '_width', None)
    style = f' style="width:{width}px"' if isinstance(width, int) else ''
    return (
        f'<div class="st-dialog-backdrop" data-id="{comp.id}"{hidden}'
        f' onclick="scDialogBackdropClick(event, this)">'
        f'<div class="st-dialog"{style} role="dialog" aria-modal="true">'
        f'<div class="st-dialog-header">'
        f'<div class="st-dialog-title">{title}</div>'
        f'<button type="button" class="st-dialog-close" aria-label="Close"'
        f' onclick="scCloseDialog(this)">\u2715</button>'
        f'</div>'
        f'<div class="st-dialog-body">{children}</div>'
        f'</div></div>'
    )


def _render_expander(comp: Expander) -> str:
    """Render a collapsible section (mirrors Streamlit's `st.expander`)."""
    label = _render_paragraphs(str(comp.label.get()))
    body = ''.join(_render(c) for c in comp.children)
    expanded = bool(getattr(comp, '_expanded', False))
    state = 'true' if expanded else 'false'
    cls = 'st-expander is-expanded' if expanded else 'st-expander'
    hidden = '' if expanded else ' hidden'
    comp_hidden = '' if comp.visible.get() else ' hidden'
    return (
        f'<div class="{cls}" data-id="{comp.id}"{comp_hidden}>'
        f'<div class="st-expander-header" role="button" tabindex="0"'
        f' aria-expanded="{state}" onclick="scToggleExpander(this)">'
        f'<span class="st-expander-icon">{_EXPANDER_ICON}</span>'
        f'<span class="st-expander-label">{label}</span>'
        f'</div>'
        f'<div class="st-expander-body"{hidden}>'
        f'<div class="st-expander-body-inner">{body}</div>'
        f'</div>'
        f'</div>'
    )


def _render_alert(comp: Component) -> str:
    """Render a coloured alert box (success / warning / info)."""
    hidden = '' if comp.visible.get() else ' hidden'
    kind = getattr(comp, '_kind', 'success')
    return (
        f'<div class="st-alert st-alert-{kind}" data-id="{comp.id}"{hidden}>'
        f'<div class="st-alert-container" role="status">'
        f'<div class="st-alert-content">'
        f'<div class="st-alert-text">'
        f'{_render_paragraphs(str(comp.text.get()))}'
        f'</div></div></div></div>'
    )


def _help_text(comp: Component) -> str:
    """Return a component's current `help` markdown, or '' when unset."""
    prop = getattr(comp, 'help', None)
    if isinstance(prop, Property):
        value = prop.get()
        return '' if value is None else str(value)
    return ''


def _escape_help(help_text: tp.Any) -> str:
    """Escape a `help` string for use in a `data-help` attribute.

    The markdown source is kept verbatim (only HTML-escaped); `page.js`
    renders it into the tooltip, so markdown syntax must survive.
    """
    return html.escape(str(help_text), quote=True)


def _help_icon_html(help_text: tp.Any) -> str:
    """Render the trailing info glyph that triggers a `help` tooltip.

    Mirrors Streamlit's `stTooltipIcon`: the glyph is the hover / focus
    target, and the markdown source rides along in `data-help`.
    """
    return (
        '<span class="st-widget-help" role="img" aria-label="Help" '
        f'data-help="{_escape_help(help_text)}">'
        '<svg viewBox="0 0 24 24" width="16" height="16" '
        'fill="currentColor" aria-hidden="true" focusable="false">'
        '<path d="M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 '
        '10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59'
        '-8 8-8 8 3.59 8 8-3.59 8-8 8z"></path></svg></span>'
    )


def _render_button(comp: Button) -> str:
    label = _render_paragraphs(str(comp.text.get()))
    btn_type = getattr(comp, '_type', 'secondary')
    # Streamlit: type="secondary" is default, "primary" is the accent button.
    st_type = 'primary' if btn_type == 'primary' else 'secondary'
    cls = f'st-btn st-btn-{st_type}'
    if getattr(comp, '_icon_only', False):
        cls += ' st-btn-icon'
    width_style = _style_width(getattr(comp, '_width', None))
    disabled = '' if comp.enabled.get() else ' disabled'
    help_attr = ''
    help_text = _help_text(comp)
    if help_text:
        help_attr = f' data-help="{_escape_help(help_text)}"'
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

    A widget's `help` text is attached to a trailing info glyph.
    """
    visibility = getattr(comp, '_label_visibility', 'visible')
    cls = 'st-widget-label'
    if visibility == 'hidden':
        cls += ' st-widget-label--hidden'
    elif visibility == 'collapsed':
        cls += ' st-widget-label--collapsed'
    label = render_markup(str(comp.label.get()))
    help_text = _help_text(comp)
    help_html = _help_icon_html(help_text) if help_text else ''
    return f'<label class="{cls}">{label}{help_html}</label>'


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
# Stepper glyphs for NumberInput. Drawn on an 8x8 grid so that they render
# at the same weight as Streamlit's own 8x8 stepper icons.
_ICON_MINUS = (
    '<svg viewBox="0 0 8 8" width="8" height="8" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
    '<path d="M0 3h8v2H0z"></path></svg>'
)
_ICON_PLUS = (
    '<svg viewBox="0 0 8 8" width="8" height="8" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
    '<path d="M3 0h2v3h3v2H5v3H3V5H0V3h3z"></path></svg>'
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
    """Render `st.table`'s shape: an `<th scope="row">` key column plus a
    value column, wrapped in a bordered, scrollable box."""
    body = ''.join(
        '<tr>'
        f'<th class="st-table-key" scope="row">'
        f'<p>{render_markup(str(key))}</p></th>'
        f'<td class="st-table-cell"><p>{render_markup(str(value))}</p></td>'
        '</tr>'
        for key, value in (comp.rows.get() or [])
    )
    cls = 'st-table'
    if getattr(comp, '_width', 'stretch') == 'content':
        cls += ' st-table--content'
    return (
        f'<div class="{cls}" data-id="{comp.id}"'
        f'{_style_width(getattr(comp, "_width", "stretch"))}>'
        f'<div class="st-table-scroll">'
        f'<table class="st-table-table"><tbody>{body}</tbody></table>'
        f'</div>'
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
        # `flex: 0 1 auto` keeps `width` authoritative inside a flex row:
        # the default `.st-row > * { flex: 1 }` would otherwise let
        # flex-basis win and stretch the widget.
        return f' style="flex:0 1 auto;width:{width}px"'
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
        # Sitting on a bound disables the arrow that would leave the range,
        # exactly like Streamlit does.
        numeric = isinstance(value, (int, float))
        at_min = (
            numeric
            and isinstance(min_value, (int, float))
            and value <= min_value
        )
        at_max = (
            numeric
            and isinstance(max_value, (int, float))
            and value >= max_value
        )
        stepper = (
            '<span class="st-number-stepper">'
            '<button class="st-number-step" type="button" tabindex="-1" '
            f'title="Decrease"{" disabled" if at_min else ""} '
            'onclick="scStepNumber(this, -1)">'
            f'{_ICON_MINUS}</button>'
            '<button class="st-number-step" type="button" tabindex="-1" '
            f'title="Increase"{" disabled" if at_max else ""} '
            'onclick="scStepNumber(this, 1)">'
            f'{_ICON_PLUS}</button>'
            '</span>'
        )
    return (
        f'<div class="st-number-input" data-id="{comp.id}"{width_style}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-number-box">'
        f'<input class="st-text-input-box" type="text" '
        f'data-comp-id="{comp.id}"{data} '
        f'value="{html.escape(text)}" '
        f'placeholder="{placeholder}" '
        f'onchange="scSendChange(this)"/>'
        f'{stepper}</div></div>'
    )


def _render_text_area(comp: TextArea) -> str:
    placeholder = html.escape(str(getattr(comp, '_placeholder', '')))
    disabled = '' if comp.enabled.get() else ' disabled'
    height = getattr(comp, '_height', 200)
    style = _style_width(getattr(comp, '_width', None))
    if style:
        style = f'{style[:-1]};height:{height}px"'
    else:
        style = f' style="height:{height}px"'
    return (
        f'<div class="st-text-area" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<textarea class="st-text-area-box" data-comp-id="{comp.id}"'
        f'{style} placeholder="{placeholder}"{disabled}'
        f' onchange="scSendChange(this)">'
        f'{html.escape(str(comp.value.get()))}</textarea>'
        f'</div>'
    )


def _render_text_input(comp: TextInput) -> str:
    placeholder = html.escape(str(getattr(comp, '_placeholder', '')))
    disabled = '' if comp.enabled.get() else ' disabled'
    width_style = _style_width(getattr(comp, '_width', None))
    return (
        f'<div class="st-text-input" data-id="{comp.id}"{width_style}>'
        f'{_widget_label_html(comp)}'
        f'<input class="st-text-input-box" type="text" '
        f'data-comp-id="{comp.id}" '
        f'value="{html.escape(str(comp.value.get()))}" '
        f'placeholder="{placeholder}"{disabled} '
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
    # `accept_new_options`: an input row at the top of the dropdown lets the
    # user type a value that is not in the list yet.
    accept_new = bool(getattr(comp, '_accept_new_options', False))
    new_row = ''
    if accept_new:
        new_row = (
            '<div class="st-selectbox-new">'
            f'<input class="st-selectbox-new-input" type="text" '
            f'data-comp-id="{comp.id}" placeholder="Type a new value" '
            f'oninput="scNewOptionInput(this)" '
            f'onkeydown="scNewOptionKey(event, this)"/>'
            f'<div class="st-selectbox-newitem" role="option" '
            f'data-comp-id="{comp.id}" onclick="scAddNewOption(this)" hidden>'
            '<div class="st-selectbox-option-inner"></div></div>'
            '</div>'
        )
    root_attrs = f' data-id="{comp.id}"'
    if accept_new:
        root_attrs += ' data-accept-new="1"'
    disabled = '' if comp.enabled.get() else ' disabled'
    return (
        f'<div class="st-selectbox"{root_attrs}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-selectbox-control">'
        f'<button type="button" class="st-selectbox-trigger" '
        f'data-comp-id="{comp.id}"{disabled} '
        f'onclick="scToggleSelectbox(this)">'
        f'<span class="st-selectbox-value">{display_text}</span>'
        f'{arrow_svg}'
        f'</button>'
        f'<div class="st-selectbox-dropdown" '
        f'data-comp-id="{comp.id}" hidden>{new_row}{opt_items}</div>'
        f'</div></div>'
    )


def _render_multiselect(comp: Multiselect) -> str:
    """Render a multi-select: a summary trigger plus a checkbox dropdown."""
    options = list(comp.options.get() or [])
    selected = list(comp.value.get() or [])
    fmt = comp.format_func
    placeholder = html.escape(str(getattr(comp, '_placeholder', '')))

    summary: list[str] = []
    items: list[str] = []
    for i, option in enumerate(options):
        is_on = option in selected
        if is_on:
            summary.append(fmt(option))
        items.append(
            f'<div class="st-multiselect-option'
            f'{" is-checked" if is_on else ""}"'
            f' role="option"'
            f' data-value="{html.escape(str(option))}" data-index="{i}"'
            f' onclick="scToggleMultiselectOption(this)">'
            f'<span class="st-multiselect-check">✓</span>'
            f'<div class="st-multiselect-option-label">'
            f'{render_markup(fmt(option))}</div>'
            f'</div>'
        )

    if summary:
        body = (
            f'<div class="st-multiselect-values">'
            f'{render_markup(", ".join(summary))}</div>'
        )
    else:
        body = (
            f'<div class="st-multiselect-values is-placeholder">'
            f'{placeholder}</div>'
        )

    return (
        f'<div class="st-multiselect" data-id="{comp.id}"'
        f' data-placeholder="{placeholder}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-multiselect-trigger"'
        f' onclick="scToggleMultiselect(this)">'
        f'{body}'
        f'<span class="st-multiselect-arrow">▾</span>'
        f'</div>'
        f'<div class="st-multiselect-dropdown" hidden>'
        f'{"".join(items)}'
        f'</div>'
        f'</div>'
    )


def _render_select_slider(comp: SelectSlider) -> str:
    """Render a discrete slider: a rail plus one tick per option."""
    options = list(comp.options.get() or [])
    value = comp.value.get()
    fmt = comp.format_func
    active_index = 0
    ticks: list[str] = []
    n = len(options)
    for i, option in enumerate(options):
        is_active = option == value
        if is_active:
            active_index = i
        left = 0.0 if n <= 1 else round(i / (n - 1) * 100, 4)
        ticks.append(
            f'<div class="st-select-slider-tick'
            f'{" is-active" if is_active else ""}"'
            f' style="left:{left}%"'
            f' data-value="{html.escape(str(option))}" data-index="{i}">'
            f'<div class="st-select-slider-dot"></div>'
            f'<div class="st-select-slider-tick-label">'
            f'{render_markup(fmt(option))}</div>'
            f'</div>'
        )
    fill = 0.0 if n <= 1 else round(active_index / (n - 1) * 100, 4)
    return (
        f'<div class="st-select-slider" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-select-slider-track" data-comp-id="{comp.id}"'
        f' onmousedown="scSelectSliderStart(event, this)"'
        f' onclick="scSelectSliderClick(event, this)">'
        f'<div class="st-select-slider-rail">'
        f'<div class="st-select-slider-fill" style="width:{fill}%"></div>'
        f'</div>'
        f'<div class="st-select-slider-ticks">{"".join(ticks)}</div>'
        f'</div>'
        f'</div>'
    )


def _render_radio(comp: Radio) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = comp.format_func
    disabled = '' if comp.enabled.get() else ' disabled'
    items = ''.join(
        f'<label class="st-radio-item">'
        f'<span class="st-radio-input-wrap">'
        f'<input type="radio" name="radio_{comp.id}" '
        f'value="{html.escape(str(o))}" '
        f'{"checked" if o == value else ""}{disabled} '
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
    if not comp.enabled.get():
        root_cls += ' is-disabled'
    max_height = getattr(comp, '_max_height', None)
    group_style = (
        f' style="max-height:{max_height}px;overflow-y:auto"'
        if isinstance(max_height, int)
        else ''
    )
    return (
        f'<div class="{root_cls}" data-id="{comp.id}">'
        f'{_widget_label_html(comp)}'
        f'<div class="st-radio-group"{group_style}>{items}</div>'
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


def _render_toggle(comp: Toggle) -> str:
    checked = ' checked' if comp.value.get() else ''
    return (
        f'<div class="st-toggle" data-id="{comp.id}">'
        f'<label class="st-toggle-label">'
        f'<span class="st-toggle-input-wrap">'
        f'<input type="checkbox" data-comp-id="{comp.id}" '
        f'{checked} onchange="scSendCheck(this)"/></span>'
        f'<div class="st-toggle-track"><div class="st-toggle-thumb"></div></div>'
        f'<div class="st-toggle-text">'
        f'{render_markup(str(comp.label.get()))}</div>'
        f'</label></div>'
    )


def _render_popover(comp: Popover) -> str:
    label = _render_paragraphs(str(comp.text.get()))
    children = ''.join(_render(c) for c in comp.children)
    width_style = _style_width(getattr(comp, '_width', None))
    hidden = '' if comp.visible.get() else ' hidden'
    help_attr = ''
    help_text = _help_text(comp)
    if help_text:
        help_attr = f' data-help="{_escape_help(help_text)}"'
    panel_cls = 'st-popover-panel'
    panel_style = ''
    if getattr(comp, '_panel_align', 'trigger') == 'row':
        panel_cls += ' st-popover-panel--row'
    max_height = getattr(comp, '_panel_max_height', None)
    if isinstance(max_height, int):
        panel_style = f' style="max-height:{max_height}px"'
    return (
        f'<div class="st-popover" data-id="{comp.id}"{hidden}>'
        f'<button class="st-btn st-btn-secondary st-popover-trigger" '
        f'type="button" aria-haspopup="dialog" aria-expanded="false"'
        f'{width_style}{help_attr} onclick="scTogglePopover(this)">'
        f'<span class="st-btn-text st-popover-trigger-label">{label}</span>'
        f'<span class="st-popover-icon">{_CHEVRON_DOWN}</span>'
        f'</button>'
        f'<div class="{panel_cls}" role="dialog"{panel_style} hidden>'
        f'{children}'
        f'</div>'
        f'</div>'
    )


def _render_progress(comp: Progress) -> str:
    """Render a progress bar (mirrors Streamlit's `st.progress`).

    `value` is a 0-100 percentage, or `None` for an indeterminate
    (animated) bar. The bar is hidden while `visible` is false, so a
    long-running step can toggle it like a spinner.
    """
    hidden = '' if comp.visible.get() else ' hidden'
    value = comp.value.get()
    if value is None:
        bar = '<div class="st-progress-bar is-indeterminate"></div>'
    else:
        pct = max(0, min(100, int(value)))
        bar = f'<div class="st-progress-bar" style="width:{pct}%"></div>'
    text = render_markup(str(comp.text.get()))
    return (
        f'<div class="st-progress" data-id="{comp.id}"{hidden}>'
        f'<div class="st-progress-track">{bar}</div>'
        f'<div class="st-progress-text">{text}</div>'
        f'</div>'
    )


def _render_altair_chart(comp: AltairChart) -> str:
    """Render a Vega-Lite chart container (drawn client-side by vega-embed).

    The spec travels as an inert JSON `<script>` block so the browser can
    parse it without any string escaping games; `page.js` reads it on load
    and re-draws whenever a `chart` patch arrives.
    """
    width_style = _style_width(getattr(comp, '_width', 'stretch'))
    spec = comp.chart.get()
    spec_html = ''
    if spec is not None:
        # Escape `</` so a `</script>` inside the payload cannot terminate
        # the block early.
        raw = json.dumps(spec, separators=(',', ':')).replace('</', '<\\/')
        spec_html = (
            '<script type="application/json" class="st-altair-spec">'
            f'{raw}</script>'
        )
    return (
        f'<div class="st-altair-chart" data-id="{comp.id}"{width_style}>'
        f'<div class="st-altair-canvas"></div>'
        f'{spec_html}'
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
<div id="app"{app_attr}>{body}</div>
<script src="/static/markdown-it.js"></script>
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
    layout: str = 'centered',
) -> str:
    theme_vars = (
        _DARK_THEME_VARS if default_theme == 'dark' else _LIGHT_THEME_VARS
    )
    app_attr = ' class="st-wide"' if layout == 'wide' else ''
    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        app_attr=app_attr,
        theme_vars=theme_vars.strip(),
        page_css=_PAGE_CSS.strip(),
        page_js=_PAGE_JS.strip(),
        body=render_tree(roots),
    )
