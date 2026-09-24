"""
Render the v3 component tree to HTML with Streamlit-style theming.

Uses CSS custom properties (--st-*) matching Streamlit's theme variable
convention. The dark theme is the default, matching Streamlit's built-in
dark theme colors.

Delta / event protocol is unchanged from Phase 3.
"""

import html
import json
import typing as tp

from lk_utils import fs

from ..components_v3._shared import _Labeled
from ..components_v3.base import Component
from ..components_v3.buttons import Button

from ..components_v3.charts import AltairChart

from ..components_v3.data import Table

from ..components_v3.inputs import CheckGroup
from ..components_v3.inputs import Checkbox
from ..components_v3.inputs import Multiselect
from ..components_v3.inputs import NumberInput
from ..components_v3.inputs import RadioGroup
from ..components_v3.inputs import ReducibleGroup
from ..components_v3.inputs import SegmentedControl
from ..components_v3.inputs import SelectSlider
from ..components_v3.inputs import Selectbox
from ..components_v3.inputs import TextArea
from ..components_v3.inputs import TextInput
from ..components_v3.inputs import ToggleBox

from ..components_v3.layouts import BottomContainer
from ..components_v3.layouts import Cell
from ..components_v3.layouts import Container
from ..components_v3.layouts import Dialog
from ..components_v3.layouts import Expander
from ..components_v3.layouts import FloatingContainer
from ..components_v3.layouts import Grid
from ..components_v3.layouts import Popover
from ..components_v3.layouts import Row
from ..components_v3.layouts import Space
from ..components_v3.layouts import Tabs
from ..components_v3.layouts import _TabPanel

from ..components_v3.media import PdfViewer

from ..components_v3.status import Callout
from ..components_v3.status import LogPanel
from ..components_v3.status import Progress
from ..components_v3.status import Spinner
from ..components_v3.status import Toast

from ..components_v3.texts import Caption
from ..components_v3.texts import Code
from ..components_v3.texts import Markdown
from ..components_v3.texts import PageTitle
from ..components_v3.texts import Text
from ..components_v3.texts import Title
from ..kernel.property import Property
from ..text import MONOSPACED
from ..text import MONOSPACED_SIZE

# ---------------------------------------------------------------------------
# Markdown: parsed in the browser (see `page.js` and the bundled markdown-it)
# ---------------------------------------------------------------------------


def render_markup(text: str) -> str:
    """Emit an inline markdown placeholder for the browser to render.

    Streamlit parses markdown client-side (react-markdown); we mirror that
    with the bundled markdown-it. The server only transports the source in
    `data-md`; `page.js` fills the placeholder on load and again on every
    delta patch, so the full markdown syntax works everywhere markdown is
    accepted -- `Caption` / `Title`, widget labels, radio options, alerts,
    button labels and `help` tooltips. `Text` is the exception: it mirrors
    `st.text` and draws its value as written (see `_render_plain`).

    Inline context: no `<p>` wrapper is implied (use `_render_paragraphs`
    for multi-paragraph bodies). Streamlit's own `:color[..]` and
    `:material/..:` extensions are applied by `page.js` as well.

    The placeholder is emitted even for blank text: its class is how a
    `text` patch knows which renderer to use, and which element to land in,
    so it has to exist from the first paint. An empty one takes no space --
    the holder itself carries no margin.
    """
    escaped = html.escape(str(text), quote=True)
    return f'<span class="st-md" data-md="{escaped}"></span>'


def _render_plain(text: str) -> str:
    """Emit a plain-text holder -- what `Text` draws into.

    Escaped, not markdown: `Text` mirrors `st.text`, whose value is shown as
    written. The holder gives a `text` patch something to swap that is not the
    root, so the help glyph beside it is left alone (the same reason the
    markdown placeholders exist).
    """
    return f'<span class="st-plain">{html.escape(str(text))}</span>'


# ---------------------------------------------------------------------------
# Component tree → HTML (Streamlit-style DOM)
# ---------------------------------------------------------------------------


def render_tree(roots: tp.Iterable[Component]) -> str:
    return ''.join(_render(comp) for comp in roots)


def _render(comp: Component) -> str:
    """Render a component and its subtree, honoring its `visible` flag.

    `visible` belongs to `Component` itself, so it is applied once, here,
    instead of by each renderer: whatever root element `_render_element`
    produced gets the `hidden` mark. That is the element carrying `data-id`,
    i.e. the one a `visible` patch reaches on the client.
    """
    markup = _render_element(comp)
    if not comp.is_hidden() or not markup.startswith('<'):
        return markup
    return _mark_hidden(markup)


def _mark_hidden(markup: str) -> str:
    """Insert the ` hidden` attribute into the first tag of `markup`.

    The scan stops at the closing `>` of that tag, skipping quoted attribute
    values: a `>` inside one (`data-md="a &gt; b"` is escaped, but a bare one
    is still legal HTML) must not be mistaken for the tag's end.
    """
    quote = ''
    for i, char in enumerate(markup):
        if quote:
            if char == quote:
                quote = ''
        elif char in ('"', "'"):
            quote = char
        elif char == '>':
            return markup[:i] + ' hidden' + markup[i:]
    return markup


def _render_element(comp: Component) -> str:
    if isinstance(comp, Grid):
        cells = sorted(comp._cells.values(), key=lambda c: (c._row, c._col))
        children = ''.join(_render(c) for c in cells)
        # Weighted columns mirror `st.columns((5, 2))`: Streamlit sizes each
        # column as `weight% - gap * (n - 1) / n`, so the tracks plus the gaps
        # exactly fill the container (with `fr` tracks the gap would instead be
        # subtracted from the whole row, narrowing every column).
        weights = comp._weights
        n = len(weights)
        gap_px = 8  # must match `--st-hgap` in `static/css/01-base.css`
        share = gap_px * (n - 1) / n
        total = sum(weights)
        tracks = ' '.join(
            '100%' if n == 1 else f'calc({w / total * 100:.6f}% - {share:g}px)'
            for w in weights
        )
        align_map = {'top': 'start', 'center': 'center', 'bottom': 'end'}
        align = align_map.get(comp._vertical_alignment, 'start')
        rules = [f'grid-template-columns:{tracks}', f'align-items:{align}']
        rules.extend(_bounds_style(comp, scroll=True))
        return (
            f'<div class="st-grid" data-id="{comp.id}"'
            f'{_style_attr(rules)}>{children}</div>'
        )
    if isinstance(comp, Cell):
        children = ''.join(_render(c) for c in comp.children)
        return (
            f'<div class="st-grid-cell" data-id="{comp.id}"'
            f'{_style_attr(_bounds_style(comp, scroll=True))}>{children}</div>'
        )
    if isinstance(comp, Row):
        children = ''.join(_render(c) for c in comp.children)
        valign = getattr(comp, '_vertical_alignment', 'top')
        align_map = {
            'top': 'flex-start',
            'center': 'center',
            'bottom': 'flex-end',
        }
        align = align_map.get(valign, 'flex-start')
        rules = [f'align-items:{align}']
        rules.extend(_bounds_style(comp, scroll=True))
        return (
            f'<div class="st-row" data-id="{comp.id}"'
            f'{_style_attr(rules)}>{children}</div>'
        )
    if isinstance(comp, Space):
        return _render_space(comp)
    # Checked before `Container`, which `FloatingContainer` subclasses.
    if isinstance(comp, FloatingContainer):
        children = ''.join(_render(c) for c in comp.children)
        return (
            f'<div class="st-floating st-floating--{comp._position}"'
            f' data-id="{comp.id}"'
            f'{_style_attr(_bounds_style(comp, scroll=True))}>{children}</div>'
        )
    if isinstance(comp, Container):
        children = ''.join(_render(c) for c in comp.children)
        # A `Container` that also carries a widget label (`TreeSelect`,
        # through `_Labeled`) draws it at the top of the panel, above the
        # toolbar.
        if isinstance(comp, _Labeled):
            children = _widget_label_html(comp) + children
        border_cls = (
            ' st-container--border' if getattr(comp, '_border', False) else ''
        )
        rules: list[str] = []
        w = getattr(comp, '_width', None)
        weight = getattr(comp, '_weight', None)
        # `flex` only means something when the column is a flex item of a
        # `Row`. Inside a vertical container `flex-basis` would constrain the
        # *height* instead (e.g. `Container(width=540)` would become 540 tall),
        # so there we only emit `width`.
        in_row = isinstance(comp._parent, Row)
        if isinstance(w, int):
            # Fixed-width column: opt out of the row's own `flex` so the
            # explicit width is honored and the sibling column fills the rest.
            if in_row:
                rules.append(f'flex:0 0 {w}px')
            rules.append(f'width:{w}px')
            rules.append('min-width:0')
        elif w == 'content':
            if in_row:
                rules.append('flex:0 1 auto')
            rules.append('width:fit-content')
        elif w == 'stretch':
            if in_row:
                # Streamlit stretches a container block from the same `8rem`
                # basis it gives the input-like widgets.
                rules.append('flex:1 1 8rem')
            rules.append('min-width:0')
        elif weight is not None and in_row:
            # Weighted columns, e.g. `st.columns((5, 2))`.
            rules.append(f'flex:{weight} 1 0%')
            # A flex item's automatic minimum is its min-content width, which
            # lets a wide child (a chart, a nowrap row of labels) push the
            # column past its share and wrap the row onto two lines. Pinning
            # the minimum to 0 keeps the weight authoritative.
            rules.append('min-width:0')
        height = getattr(comp, '_height', None)
        rules.extend(_bounds_style(comp, scroll=True))
        if isinstance(height, int):
            # Fixed-height container: the content scrolls once it overflows.
            # `_bounds_style` may have added the same `overflow` already, for a
            # `max_height` (the two are not mutually exclusive).
            rules.append(f'height:{height}px')
            if 'overflow:auto' not in rules:
                rules.append('overflow:auto')
        style = _style_attr(rules)
        reveal_cls = ' st-reveal' if getattr(comp, '_animated', False) else ''
        bottom_cls = (
            ' st-container--bottom' if isinstance(comp, BottomContainer) else ''
        )
        return (
            f'<div class="st-container{border_cls}{reveal_cls}{bottom_cls}"'
            f' data-id="{comp.id}"'
            f'{style}>{children}</div>'
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
        # `PageTitle` is a `Title` that names the tab as well: the extra class
        # is what page.js looks for when the text changes. The first paint's
        # own `<title>` is set by `render_page`, below.
        page = ' st-page-title' if isinstance(comp, PageTitle) else ''
        align = getattr(comp, '_horizontal_alignment', 'left')
        # left is the default alignment, so only the other two need a class
        align_cls = '' if align == 'left' else f' st-title--{align}'
        return (
            f'<h1 class="st-title{align_cls}{page}" data-id="{comp.id}"'
            f'{_text_style(comp)}>{text}{help_html}</h1>'
        )
    if isinstance(comp, Caption):
        text = render_markup(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<div class="st-caption" data-id="{comp.id}"{_text_style(comp)}>'
            f'{text}{help_html}</div>'
        )
    if isinstance(comp, Text):
        # plain text, not markdown: `Text` mirrors `st.text`.
        text = _render_plain(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<div class="st-text" data-id="{comp.id}"{_text_style(comp)}>'
            f'{text}{help_html}</div>'
        )
    if isinstance(comp, Markdown):
        # A block placeholder, so markdown-it wraps the source in `<p>` the
        # way Streamlit does.
        text = _render_paragraphs(str(comp.text.get()))
        help_text = _help_text(comp)
        help_html = _help_icon_html(help_text) if help_text else ''
        return (
            f'<div class="st-markdown" data-id="{comp.id}"'
            f'{_text_style(comp)}>'
            f'{text}{help_html}</div>'
        )
    if isinstance(comp, Spinner):
        children = ''.join(_render(c) for c in comp.children)
        text = render_markup(str(comp.text.get()))
        return (
            f'<div class="st-spinner" data-id="{comp.id}">'
            f'<span class="st-spinner-ring"></span>'
            f'<span class="st-spinner-text">{text}</span>'
            f'{children}</div>'
        )
    if isinstance(comp, Callout):
        return _render_alert(comp)
    if isinstance(comp, Popover):
        return _render_popover(comp)
    if isinstance(comp, Progress):
        return _render_progress(comp)
    if isinstance(comp, AltairChart):
        return _render_altair_chart(comp)
    if isinstance(comp, ToggleBox):
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
    if isinstance(comp, RadioGroup):
        return _render_radio_group(comp)
    if isinstance(comp, CheckGroup):
        return _render_check_group(comp)
    if isinstance(comp, ReducibleGroup):
        return _render_reducible_group(comp)
    if isinstance(comp, SegmentedControl):
        return _render_segmented_control(comp)
    if isinstance(comp, Toast):
        return _render_toast(comp)
    if isinstance(comp, PdfViewer):
        return _render_pdf_viewer(comp)
    if isinstance(comp, LogPanel):
        return _render_log_panel(comp)
    return ''.join(_render(c) for c in comp.children)


def _render_paragraphs(text: str) -> str:
    """Emit a block markdown placeholder for the browser to render.

    Block-context counterpart of `render_markup`: markdown-it wraps each
    block in `<p>`, matching Streamlit's behavior (a blank line starts a new
    paragraph, a single newline inside one is a soft break). `st-md-block`
    is nothing but this marker -- no stylesheet keys off it -- so a blank
    source keeps its placeholder for the reason given in `render_markup`:
    without it a patch cannot tell that this element means paragraphs.
    """
    raw = str(text).strip('\n')
    escaped = html.escape(raw, quote=True)
    return f'<div class="st-md st-md-block" data-md="{escaped}"></div>'


def _render_tabs(comp: Tabs) -> str:
    """Render a tab bar plus one panel per label (only one is visible).

    The bar carries a single underline element rather than a per-tab border,
    because only one element can *slide* between the tabs (the position comes
    from `scSyncTabIndicator` in page.js).
    """
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
        f'<div class="st-tabs" data-id="{comp.id}"'
        f'{_style_attr(_bounds_style(comp, scroll=True))}>'
        f'<div class="st-tabs-bar" role="tablist">{"".join(buttons)}'
        f'<span class="st-tabs-indicator"></span></div>'
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
    width = getattr(comp, '_width', None)
    rules: list[str] = []
    if isinstance(width, int):
        rules.append(f'width:{width}px')
    # The bounds go on the panel, not on the root element: the root is a
    # full-screen backdrop, so a cap there would mean nothing (the semantic
    # `width` above lands on the panel for the same reason).
    rules.extend(_bounds_style(comp, scroll=True))
    style = _style_attr(rules)
    return (
        f'<div class="st-dialog-backdrop" data-id="{comp.id}"'
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
    return (
        f'<div class="{cls}" data-id="{comp.id}"'
        f'{_style_attr(_bounds_style(comp, scroll=True))}>'
        f'<div class="st-expander-header" role="button" tabindex="0"'
        f' aria-expanded="{state}" onclick="scToggleExpander(this)">'
        f'<span class="st-icon st-expander-icon" translate="no">'
        f'{_EXPANDER_CHEVRON_CLOSED}</span>'
        f'<span class="st-expander-label">{label}</span>'
        f'</div>'
        f'<div class="st-expander-body"{hidden}>'
        f'<div class="st-expander-body-inner">{body}</div>'
        f'</div>'
        f'</div>'
    )


def _render_alert(comp: Component) -> str:
    """Render a coloured alert box (error / info / success / warning)."""
    kind = getattr(comp, '_kind', 'success')
    return (
        f'<div class="st-alert st-alert-{kind}" data-id="{comp.id}">'
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
    # Streamlit: type="secondary" is default, "primary" is the accent button.
    # A live `type` change rides the `type` patch (see `00-connection.js`),
    # which swaps this same class.
    st_type = 'primary' if comp.type.get() == 'primary' else 'secondary'
    cls = f'st-btn st-btn-{st_type}'
    if getattr(comp, '_icon_only', False):
        cls += ' st-btn-icon'
    width_style = _size_style(comp)
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

    Mirrors Streamlit's semantics, plus the `'auto'` default:
        auto      : decided from the label itself -- text shows the row, an
                    empty label collapses it (a blank label would otherwise
                    still hold the row's 24px line).
        visible   : shown normally, empty or not (an empty one keeps the
                    row's height, which is what `'hidden'` is for).
        hidden    : hidden, but still occupies its space.
        collapsed : hidden and removed from the layout.

    `'auto'` is decided here, once, and baked into the class: the field is
    static (like `width` / `height`), so a bound `label` that empties or
    fills in later does not re-decide it.

    A widget's `help` text is attached to a trailing info glyph.
    """
    visibility = getattr(comp, '_label_visibility', 'auto')
    label_text = str(comp.label.get() or '')
    if visibility == 'auto':
        # `auto` reads the label itself: text -> show the row, nothing to
        # draw -> collapse it, so an empty label costs no height at all.
        visibility = 'visible' if label_text.strip() else 'collapsed'
    cls = 'st-widget-label'
    if visibility == 'hidden':
        cls += ' st-widget-label--hidden'
    elif visibility == 'collapsed':
        cls += ' st-widget-label--collapsed'
    label = render_markup(label_text)
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
# The popover trigger's and the expander header's chevrons are icon-font
# glyphs, exactly like Streamlit's: they are *swapped* between two names when
# the section opens (never rotated). `page.js` swaps the name, `page.css` owns
# the box.
_POPOVER_CHEVRON_CLOSED = 'expand_more'
_POPOVER_CHEVRON_OPEN = 'expand_less'
_EXPANDER_CHEVRON_CLOSED = 'keyboard_arrow_right'
_EXPANDER_CHEVRON_OPEN = 'keyboard_arrow_down'
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


def _table_text(kind: str, text: str) -> str:
    """A `Table`'s title / caption / footer line (empty text drops the line)."""
    if not str(text):
        return ''
    return f'<div class="st-table-{kind}">{render_markup(text)}</div>'


def _table_head(comp: Table) -> str:
    """A `Table`'s optional column-label row (one `<th>` per column)."""
    header = comp.header.get()
    if not header:
        return ''
    cells = []
    for i, label in enumerate(header):
        cls = 'st-table-key' if i == 0 else 'st-table-cell'
        cells.append(f'<th class="{cls}">{render_markup(str(label))}</th>')
    return f'<thead class="st-table-head"><tr>{"".join(cells)}</tr></thead>'


def _table_row(cells: tp.Sequence[tp.Any]) -> str:
    """One body row: the first cell is the row header, every following cell
    is a value column -- so an N-cell row makes an N-column table."""
    out = []
    for i, cell in enumerate(cells):
        text = render_markup(str(cell))
        if i == 0:
            out.append(
                f'<th class="st-table-key" scope="row"><p>{text}</p></th>'
            )
        else:
            out.append(f'<td class="st-table-cell"><p>{text}</p></td>')
    return f'<tr>{"".join(out)}</tr>'


def _render_table(comp: Table) -> str:
    """Render a `Table`: a row-header column plus one value column per extra
    cell, wrapped in a bordered, scrollable box. The canary extras (title /
    caption / footer / an optional column-label row) sit around the box: title
    and caption above it, footer below it."""
    body = ''.join(_table_row(row) for row in (comp.rows.get() or []))
    cls = 'st-table'
    if getattr(comp, '_width', 'stretch') == 'content':
        cls += ' st-table--content'
    if comp._header_background:
        cls += ' st-table--head-filled'
    return (
        f'<div class="{cls}" data-id="{comp.id}"{_size_style(comp)}>'
        f'{_table_text("title", comp.title.get())}'
        f'{_table_text("caption", comp.caption.get())}'
        f'<div class="st-table-scroll">'
        f'<table class="st-table-table">'
        f'{_table_head(comp)}<tbody>{body}</tbody></table>'
        f'</div>'
        f'{_table_text("footer", comp.footer.get())}'
        f'</div>'
    )


def _size_rule(
    value: tp.Any,
    name: str,
    max_value: int | None = None,
    min_value: int | None = None,
) -> str:
    """CSS declaration(s) for one sizing value (`name` is 'width'/'height').

    `max_value` / `min_value` are the component's own bounds for that axis
    (see `Component`'s `max_height` / `min_height`), appended after the size
    itself so they win over the `max-*: 100%` a `'content'` size carries.

    Returns '' for a value the inline style does not own: `None` and the
    `'auto'` keyword are left to CSS, so a component's own rules (or the
    markdown family's vertical/horizontal switch) still apply. Bounds are
    still emitted in that case -- capping a box the CSS already sizes is
    exactly what a bound is for.

    `'stretch'` returns early, which is what makes it win over the bounds: a
    box told to fill its parent cannot also honour a cap, and the caller's
    explicit instruction is the one that survives.
    """
    if value == 'stretch':
        return f'{name}:100%'
    rules: list[str] = []
    if value == 'content':
        # Inside a flex row the row's own `flex` would stretch the element, so
        # the inline `flex: 0 1 auto` keeps the content size authoritative.
        prefix = 'flex:0 1 auto;' if name == 'width' else ''
        rules.append(f'{prefix}{name}:fit-content')
        # the cap that `content` implies -- unless the caller set their own
        if max_value is None:
            rules.append(f'max-{name}:100%')
    elif isinstance(value, int) and not isinstance(value, bool):
        # `flex: 0 1 auto` keeps the explicit size authoritative inside a flex
        # row: the row's default `flex` would otherwise let flex-basis win and
        # stretch the widget.
        rules.append(f'flex:0 1 auto;{name}:{value}px')
    if max_value is not None:
        rules.append(f'max-{name}:{max_value}px')
    if min_value is not None:
        rules.append(f'min-{name}:{min_value}px')
    return ';'.join(rules)


def _width_style(comp: Component) -> str:
    """Inline `style` attribute for a component's `width` only.

    Used by renderers that size the width on the wrapper but the height on
    an inner box (e.g. `TextArea`).
    """
    rule = _size_rule(getattr(comp, '_width', None), 'width')
    return f' style="{rule}"' if rule else ''


def _style_attr(rules: tp.Sequence[str]) -> str:
    """The ` style="..."` attribute a list of declarations produces ('' if
    the list is empty, so the element carries no `style` at all).

    The declarations are escaped for the attribute, because a value may carry
    double quotes of its own -- a `font-family` stack does -- and an unescaped
    one would end the attribute right there. The browser decodes the entities
    before it parses the CSS, so the declaration arrives intact.
    """
    if not rules:
        return ''
    declarations = html.escape(';'.join(rules), quote=True)
    return f' style="{declarations}"'


def _size_rules(comp: Component) -> list[str]:
    """The inline width / height declarations a component's own size yields.

    Split out of `_size_style` so a text element can extend the very same list
    with its `font_family` (see `_text_style`) instead of writing a second
    `style` attribute -- an element takes only one.
    """
    return [
        rule
        for name in ('width', 'height')
        if (
            rule := _size_rule(
                getattr(comp, f'_{name}', None),
                name,
                getattr(comp, f'_max_{name}', None),
                getattr(comp, f'_min_{name}', None),
            )
        )
    ]


def _size_style(comp: Component) -> str:
    """Inline `style` attribute for a component's `width` / `height`, plus the
    `max_height` / `min_height` bounds on the height axis.

    Mirrors Streamlit's sizing keywords:
        'stretch'  fill the parent (`width: 100%`).
        'content'  hug the content, capped at the parent width.
        int        a fixed pixel size.
        'auto' / None  no inline rule -- CSS decides (see `page.css`).

    The width axis passes no bounds: `max_width` / `min_width` are not part of
    the API yet. A layout that builds its own `style` (a flex weight, grid
    tracks) takes the same bounds from `_bounds_style` instead.
    """
    return _style_attr(_size_rules(comp))


def _text_style(comp: Component) -> str:
    """`_size_style`, plus the `font_family` / `font_size` a text element
    asked for.

    `font-family` is inherited, so declaring it on the root is enough: the
    markdown placeholder inside, and the `<p>` under that, both follow. The
    element that receives it is the one `_HelpText` stores it on (empty when
    the caller did not ask for a family, which leaves the page font in place).

    The canary's own monospace stack (`sc.MONOSPACED`) also brings the size
    that belongs with it -- see `MONOSPACED_SIZE`; an explicit `font_size`
    takes precedence.
    """
    rules = _size_rules(comp)
    family = getattr(comp, '_font_family', '')
    size = getattr(comp, '_font_size', '')
    if family:
        rules.append(f'font-family:{family}')
        if not size and family == MONOSPACED and not isinstance(comp, Title):
            # `MONOSPACED_SIZE` is *relative* to body text, so it belongs to
            # the elements that draw at the body size. A `Title` carries a
            # size of its own (0.875em would resolve against the parent and
            # shrink the heading); pass `font_size` to change its size.
            size = MONOSPACED_SIZE
    if size:
        rules.append(f'font-size:{size}')
    return _style_attr(rules)


def _bounds_style(comp: Component, *, scroll: bool = False) -> list[str]:
    """The `max-height` / `min-height` rules for a layout box, as a list.

    A layout emits a `style` of its own (flex weights, grid tracks), so it
    extends its rule list with these; the uniform `_size_style` path passes the
    very same bounds through `_size_rule` instead. `height='stretch'` drops
    them for the reason `_size_rule` gives.

    `scroll` adds `overflow: auto` under an upper bound: a cap on its own would
    let the content spill over the box instead of scrolling past it, which is
    the pairing a fixed `height` already has. A floor (`min_height`) never
    needs it -- it only guarantees a size.
    """
    if getattr(comp, '_height', None) == 'stretch':
        return []
    rules: list[str] = []
    max_height = getattr(comp, '_max_height', None)
    min_height = getattr(comp, '_min_height', None)
    if isinstance(max_height, int):
        rules.append(f'max-height:{max_height}px')
        if scroll:
            rules.append('overflow:auto')
    if isinstance(min_height, int):
        rules.append(f'min-height:{min_height}px')
    return rules


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
    step = getattr(comp, '_step', 0) or 0
    min_value = getattr(comp, '_min', None)
    max_value = getattr(comp, '_max', None)
    placeholder = html.escape(str(comp.placeholder.get()))
    width_style = _size_style(comp)
    # `data-value` carries the raw (unformatted) number, which is what the
    # stepper does its arithmetic on.
    data = f' data-value="{html.escape(str(value))}"'
    if step > 0:
        data += f' data-step="{step}"'
    if min_value is not None:
        data += f' data-min="{min_value}"'
    if max_value is not None:
        data += f' data-max="{max_value}"'
    # A `step` of 0 asks for no stepper at all. The gadget is a single markup
    # for every width: `page.css` stacks it vertically when the box gets
    # narrow, and hides it when even that does not fit. The buttons swallow
    # the `mousedown` that would otherwise pull focus out of the box -- which
    # would fire a stale `editing_finished` carrying the pre-step number
    # before the stepped value is even sent.
    stepper = ''
    if step > 0:
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
            'onmousedown="event.preventDefault()" '
            'onclick="scStepNumber(this, -1)">'
            f'{_ICON_MINUS}</button>'
            '<button class="st-number-step" type="button" tabindex="-1" '
            f'title="Increase"{" disabled" if at_max else ""} '
            'onmousedown="event.preventDefault()" '
            'onclick="scStepNumber(this, 1)">'
            f'{_ICON_PLUS}</button>'
            '</span>'
        )
    # A `width='content'` wrapper is sized from the box, so `page.css` keeps
    # the box out of its container queries (containment would collapse it).
    modifier = (
        ' st-number-input--content-width'
        if getattr(comp, '_width', None) == 'content'
        else ''
    )
    return (
        f'<div class="st-number-input{modifier}" data-id="{comp.id}"'
        f'{width_style}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-number-box">'
        f'<input class="st-text-input-box" type="text" '
        f'data-comp-id="{comp.id}"{data} '
        f'value="{html.escape(text)}" '
        f'placeholder="{placeholder}" '
        f'oninput="this._scSubmitted=false" '
        f'onchange="scSendChange(this)" '
        f'onkeydown="scSubmitKey(event, this)" '
        f'onblur="scSendEditingFinished(this)"/>'
        f'{stepper}</div></div>'
    )


def _render_text_area(comp: TextArea) -> str:
    placeholder = html.escape(str(comp.placeholder.get()))
    disabled = '' if comp.enabled.get() else ' disabled'
    # The width belongs to the wrapper; the height belongs to the `<textarea>`
    # (the box itself keeps `width: 100%` so it fills the wrapper).
    width_style = _width_style(comp)
    height = getattr(comp, '_height', None)
    height_style = (
        f' style="height:{height}px"' if isinstance(height, int) else ''
    )
    return (
        f'<div class="st-text-area" data-id="{comp.id}"{width_style}>'
        f'{_widget_label_html(comp)}'
        f'<textarea class="st-text-area-box" data-comp-id="{comp.id}"'
        f'{height_style} placeholder="{placeholder}"{disabled}'
        f' oninput="this._scSubmitted=false"'
        f' onchange="scSendChange(this)"'
        f' onkeydown="scSubmitAreaKey(event, this)"'
        f' onblur="scSendEditingFinished(this)">'
        f'{html.escape(str(comp.value.get()))}</textarea>'
        f'</div>'
    )


def _chevron_svg() -> str:
    """The 20px caret shared by `Selectbox` and a `TextInput`'s candidates."""
    return (
        '<svg class="st-selectbox-arrow" viewBox="0 0 24 24" '
        'width="20" height="20" fill="currentColor">'
        '<path fill="none" d="M0 0h24v24H0V0z"></path>'
        '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 '
        '1.41-1.41z"></path>'
        '</svg>'
    )


def _render_text_input(comp: TextInput) -> str:
    placeholder = html.escape(str(comp.placeholder.get()))
    disabled = '' if comp.enabled.get() else ' disabled'
    width_style = _size_style(comp)
    candidates = comp.candidates.get()
    accept_new = bool(getattr(comp, '_accept_new_option', False))
    # `accept_new_option` needs the panel too -- that is where its row lives
    # -- so it brings the caret along even with no list to show.
    framed = candidates is not None or accept_new
    extra_cls = ' st-text-input-candidates-input' if framed else ''
    # a path-like box shows its tail: the client scrolls it to the end (an
    # `<input>` clips without an ellipsis, so there is no CSS way to elide it
    # on the left -- see `scTruncateStart`)
    truncate_cls = (
        ' st-truncate-start' if getattr(comp, '_truncate_start', False) else ''
    )
    # a `TextInput` is the box its "Add: ..." row echoes, so the row has to
    # follow the text as it is typed; a `Selectbox` spells the row's own box
    # in instead (see `scNewOptionInput`)
    echo = '; scNewOptionEcho(this)' if accept_new else ''
    box = (
        f'<input class="st-text-input-box{extra_cls}{truncate_cls}" '
        f'type="text" '
        f'data-comp-id="{comp.id}" '
        f'value="{html.escape(str(comp.value.get()))}" '
        f'placeholder="{placeholder}"{disabled} '
        f'oninput="this._scSubmitted=false; scSendEditing(this){echo}" '
        f'onchange="scSendChange(this)" '
        f'onkeydown="scSubmitKey(event, this)" '
        f'onblur="scSendEditingFinished(this)"/>'
    )
    if not framed:
        return (
            f'<div class="st-text-input" data-id="{comp.id}"{width_style}>'
            f'{_widget_label_html(comp)}{box}</div>'
        )
    # `candidates`: frame the box like a `Selectbox` trigger, and let a caret
    # unfold the very same panel `Selectbox` draws.
    caret_disabled = '' if (candidates or accept_new) else ' disabled'
    # the client finds the "Add: ..." row through this: the root that takes
    # new options, and the row inside it (`scNewOptionEcho`)
    accept_attr = ' data-accept-new="1"' if accept_new else ''
    rows = _text_new_option_html(comp) if accept_new else ''
    rows += _text_candidates_html(comp, candidates or ())
    return (
        f'<div class="st-text-input st-text-input-candidates" '
        f'data-id="{comp.id}"{accept_attr}{width_style}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-selectbox-control">'
        f'<div class="st-selectbox-trigger st-text-input-candidates-box">'
        f'{box}'
        f'<button type="button" class="st-text-input-candidates-toggle" '
        f'data-comp-id="{comp.id}" aria-label="Show candidates"'
        f'{caret_disabled} onclick="scToggleCandidates(this)">'
        f'{_chevron_svg()}</button>'
        f'</div>'
        f'<div class="st-selectbox-dropdown" data-comp-id="{comp.id}" '
        f'hidden>{rows}</div>'
        f'</div></div>'
    )


def _text_new_option_html(comp: TextInput) -> str:
    """The `TextInput` half of `accept_new_option`.

    `Selectbox` spells a text box of its own into its panel's first row and
    lets that box be the new value (`_render_selectbox`). A `TextInput` is
    already a box, so this row is only an echo of it: `scNewOptionEcho` fills
    in the label while the text is typed, and taking the row submits that text
    (`scAcceptNewOption`) -- the same as pressing Enter in the box.
    """
    return (
        f'<div class="st-selectbox-newitem" role="option" '
        f'data-comp-id="{comp.id}" data-value="" '
        # the row must not take focus, or clicking it reports an
        # `editing_finished` carrying the text a moment before the click
        f'onmousedown="event.preventDefault()" '
        f'onclick="scAcceptNewOption(this)" hidden>'
        '<div class="st-selectbox-option-inner st-truncate-help"></div></div>'
    )


def _text_candidates_html(comp: TextInput, candidates: tp.Sequence) -> str:
    """The candidate rows of a `TextInput`, drawn like `Selectbox` options."""
    return ''.join(
        f'<div class="st-selectbox-option" role="option" '
        f'data-value="{html.escape(str(candidate))}" '
        f'data-comp-id="{comp.id}" onclick="scPickCandidate(this)">'
        # `st-truncate-help`: a path too long for the row is clipped, and
        # `90-help.js` then offers the whole of it on hover -- the same
        # affordance a `Selectbox` option row has.
        f'<div class="st-selectbox-option-inner st-truncate-help">'
        f'{render_markup(str(candidate))}</div></div>'
        for candidate in candidates
    )


def _render_selectbox(comp: Selectbox) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = comp.format_func
    placeholder = html.escape(str(comp.placeholder.get()))
    # Build option items for the custom dropdown panel. Two-layer structure
    # matches Streamlit: outer (padding 0 5px) + inner (padding 0 8px), so
    # the hover background on the inner div is inset from the panel edges.
    # The inner div is also what clips a label too long for the row
    # (`st-truncate-help`), so `90-help.js` can offer the whole label on hover.
    opt_items = ''.join(
        f'<div class="st-selectbox-option" role="option" '
        f'data-value="{html.escape(str(o))}" '
        f'data-comp-id="{comp.id}" '
        f'onclick="scSelectOption(this)" '
        f'{"data-selected" if o == value else ""}>'
        f'<div class="st-selectbox-option-inner st-truncate-help">'
        f'{render_markup(fmt(o))}</div></div>'
        for o in options
    )
    # The trigger shows the chosen option, or the placeholder hint while it has
    # no option to show: `options` may still be empty (a bound list that has
    # not loaded yet), or `value` may not be among them at all. Looking the
    # value up -- rather than testing it for truthiness -- keeps `0` / `False`
    # as legitimate choices.
    arrow_svg = _chevron_svg()
    # a path-like trigger shows its tail (see `.st-truncate-start`)
    truncate_cls = (
        ' st-truncate-start' if getattr(comp, '_truncate_start', False) else ''
    )
    if value in options:
        trigger_text = (
            f'<span class="st-selectbox-value{truncate_cls}">'
            f'{render_markup(fmt(value))}</span>'
        )
    else:
        # A zero-width space keeps an empty trigger from collapsing.
        hint = placeholder or '\u200b'
        trigger_text = (
            f'<span class="st-selectbox-value is-placeholder{truncate_cls}">'
            f'{hint}</span>'
        )
    # `accept_new_option`: an input row at the top of the dropdown lets the
    # user type a value that is not in the list yet.
    accept_new = bool(getattr(comp, '_accept_new_option', False))
    new_row = ''
    if accept_new:
        new_row = (
            '<div class="st-selectbox-new">'
            f'<input class="st-selectbox-new-input" type="text" '
            f'data-comp-id="{comp.id}" placeholder="Type a new value" '
            f'oninput="scNewOptionInput(this)" '
            f'onkeydown="scNewOptionKey(event, this)" '
            f'onblur="scNewOptionBlur(this)"/>'
            f'<div class="st-selectbox-newitem" role="option" '
            f'data-comp-id="{comp.id}" '
            # the item must not take focus, or clicking it blurs the input and
            # reports an `editing_finished` a moment before the submit
            f'onmousedown="event.preventDefault()" '
            f'onclick="scAddNewOption(this)" hidden>'
            '<div class="st-selectbox-option-inner st-truncate-help"></div>'
            '</div>'
            '</div>'
        )
    root_attrs = f' data-id="{comp.id}"'
    # Carried so the client can put the hint back when a patch empties the
    # trigger (`scSetSelectboxValue`).
    root_attrs += f' data-placeholder="{placeholder}"'
    if accept_new:
        root_attrs += ' data-accept-new="1"'
    disabled = '' if comp.enabled.get() else ' disabled'
    # `width='content'`: the box is as wide as its widest *option*, not as wide
    # as the value shown right now -- otherwise picking a shorter option
    # resizes the trigger. An invisible sizer stacks every option, and
    # page.css puts it and the trigger in one grid cell, so the wider of the
    # two sets the cell; the browser then picks the widest option for us, with
    # the real glyph shapes (markdown and `:material/...:` icons included).
    content_sized = comp._width == 'content'
    width_cls = ' st-selectbox--content' if content_sized else ''
    sizer = ''
    if content_sized:
        texts = ''.join(
            f'<span>{render_markup(fmt(o))}</span>' for o in options
        )
        sizer = (
            '<div class="st-selectbox-sizer" aria-hidden="true">'
            f'<span class="st-selectbox-sizer-texts">{texts}</span>'
            f'{arrow_svg}</div>'
        )
    return (
        f'<div class="st-selectbox{width_cls}"{root_attrs}{_size_style(comp)}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-selectbox-control">'
        f'<button type="button" class="st-selectbox-trigger" '
        f'data-comp-id="{comp.id}"{disabled} '
        f'onclick="scToggleSelectbox(this)">'
        f'{trigger_text}'
        f'{arrow_svg}'
        f'</button>'
        f'<div class="st-selectbox-dropdown" '
        f'data-comp-id="{comp.id}" hidden>{new_row}{opt_items}</div>'
        f'{sizer}'
        f'</div></div>'
    )


def _render_multiselect(comp: Multiselect) -> str:
    """Render a multi-select: a summary trigger plus a checkbox dropdown."""
    options = list(comp.options.get() or [])
    selected = list(comp.value.get() or [])
    fmt = comp.format_func
    placeholder = html.escape(str(comp.placeholder.get()))

    items: list[str] = []
    for i, option in enumerate(options):
        is_on = option in selected
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

    # The trigger lists the ticked options in the order they were ticked, which
    # is the order `value` keeps. The dropdown above is untouched by that: it
    # always lists the options as the app declared them. `selected` may carry
    # something that is not an option at all (the value is the caller's), so
    # the labels are looked up among the options.
    summary: list[str] = []
    for ticked in selected:
        for option in options:
            if option == ticked:
                summary.append(fmt(option))
                break

    # The client maintains that same order as it ticks and unticks, so it needs
    # the starting point: the selection as plain strings, in order (see
    # `scMultiselectSelection` in `30-overlays.js`).
    selection = html.escape(json.dumps([str(o) for o in selected]))

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

    # `height='fixed'` (the default) keeps the values on one line and lets them
    # scroll sideways; page.css turns the class into that behaviour. Any other
    # height leaves the strip clipping with an ellipsis, as before.
    fixed_cls = ' st-multiselect--fixed' if comp._height == 'fixed' else ''
    return (
        f'<div class="st-multiselect{fixed_cls}" data-id="{comp.id}"'
        f' data-placeholder="{placeholder}" data-selected="{selection}"'
        f'{_size_style(comp)}>'
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
    """Render a discrete slider: a rail with a thumb, plus the current option
    shown above the thumb (mirrors `st.select_slider`)."""
    options = list(comp.options.get() or [])
    value = comp.value.get()
    fmt = comp.format_func
    active_index = 0
    labels: list[str] = []
    n = len(options)
    for i, option in enumerate(options):
        if option == value:
            active_index = i
        labels.append(
            f'<div class="st-select-slider-option"'
            f' data-value="{html.escape(str(option))}">'
            f'{render_markup(fmt(option))}</div>'
        )
    pct = 0.0 if n <= 1 else round(active_index / (n - 1) * 100, 4)
    active_label = render_markup(fmt(options[active_index])) if options else ''
    return (
        f'<div class="st-select-slider" data-id="{comp.id}"{_size_style(comp)}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-select-slider-group">'
        f'<div class="st-select-slider-value" style="left:{pct}%">'
        f'{active_label}</div>'
        f'<div class="st-select-slider-track" data-comp-id="{comp.id}"'
        f' data-index="{active_index}"'
        f' onmousedown="scSelectSliderStart(event, this)"'
        f' onclick="scSelectSliderClick(event, this)">'
        f'<div class="st-select-slider-rail">'
        f'<div class="st-select-slider-fill" style="width:{pct}%"></div>'
        f'<div class="st-select-slider-thumb" style="left:{pct}%"></div>'
        f'</div>'
        f'<div class="st-select-slider-options">{"".join(labels)}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _choice_box_html(input_type: str) -> str:
    """The option indicator: a square tick box, or the radio's circle.

    `CheckGroup` reuses `v3.Checkbox`'s box; `RadioGroup` its own circle. The
    empty-list placeholder draws the very same indicator (see
    `_choice_group_empty_html`).
    """
    if input_type == 'checkbox':
        return (
            '<div class="st-checkbox-box">'
            '<svg viewBox="0 0 10 8" aria-hidden="true">'
            '<polyline points="1 4 4 7 9 1"></polyline></svg></div>'
        )
    return '<div class="st-radio-circle"><div class="st-radio-dot"></div></div>'


def _choice_group_empty_html(input_type: str) -> str:
    """The single placeholder row an empty option list draws.

    Mirrors `st.radio`, which swaps its options for one disabled row -- an
    (unchecked) indicator plus a faded "No options to select." line -- rather
    than leaving the widget blank.
    """
    return (
        '<div class="st-radio-empty">'
        '<div class="st-radio-item-row">'
        f'{_choice_box_html(input_type)}'
        '<div class="st-radio-empty-label">No options to select.</div>'
        '</div></div>'
    )


def _row_enter_html() -> str:
    """The "enter" button a navigable option row floats beside its text.

    It sits inside the row's `<label>`, which is safe: a label ignores clicks
    aimed at interactive content inside it, so the button opens the row
    without ticking its box on the way.  The click is reported as an `open`
    event (see `scOpenRow`), which `_NavigationGroup` in
    `components_v3/trees/` picks up -- that is where this gesture is
    defined; the generic group widgets know nothing about it.
    """
    return (
        '<button class="st-row-open" type="button" aria-label="Open" '
        'onclick="scOpenRow(event, this)">'
        f'{render_markup(":material/arrow_forward:")}</button>'
    )


def _choice_group_items_html(
    comp: RadioGroup | CheckGroup,
    values: tp.Sequence[tp.Any],
    is_checked: tp.Callable[[tp.Any], bool],
    *,
    input_type: str,
    on_change: str,
    box_disabled: tp.Callable[[tp.Any], bool] | None = None,
    navigable: tp.Callable[[tp.Any], bool] | None = None,
    body_opens: tp.Callable[[tp.Any], bool] | None = None,
) -> str:
    """The option-item shell shared by `RadioGroup` and `CheckGroup`.

    Both draw the very same row -- a box plus a markdown label, with the same
    spacing and hover highlight -- and differ only in the input's type, its
    checked test and the change handler: `RadioGroup` shows the radio circle,
    `CheckGroup` the very same square box (border + checkmark) as
    `v3.Checkbox`.

    A click anywhere on the row lands on the `<label>` that wraps it, so the
    browser ticks the option by itself: no script takes part and nothing is
    held back to leave room for a second click. `scHighlightChoice` only adds
    the row highlight on the way past.

    `box_disabled` freezes single options: their field is inert (so the
    surrounding label cannot tick them) and the row is marked
    `is-box-disabled` for the dimmed box.

    `navigable` marks the options that carry a trailing "enter" button (see
    `_row_enter_html`) -- `TreeSelect` uses it for its folders.  That button
    is the only way to walk into a row; the row's own click still just ticks
    it.

    `body_opens` marks the options whose *own* click walks in, with no button
    at all: a row with a frozen box has no tick to spend, so the click is
    free.  `TreeSelect` uses it for `..`; the handler is `scOpenRow`, the same
    one the arrow uses, so both gestures arrive as one `open` event.

    `_focus_index` draws one row highlighted -- the row a tree panel came from
    when it walked back up.  It is read off the component rather than passed
    in, because the same index has to ride along with an `options` patch as
    well (see `runtime.py`), and the patch rebuilds every row.
    """
    if not values:
        return _choice_group_empty_html(input_type)
    fmt = comp.format_func
    name = f' name="{input_type}_{comp.id}"' if input_type == 'radio' else ''
    widget_off = not comp.enabled.get()
    box = _choice_box_html(input_type)
    focused = getattr(comp, '_focus_index', -1)
    item_html = []
    for index, option in enumerate(values):
        frozen = bool(box_disabled(option)) if box_disabled else False
        off = ' disabled' if (frozen or widget_off) else ''
        field = (
            f'<span class="st-radio-input-wrap">'
            f'<input type="{input_type}"{name} '
            f'value="{html.escape(str(option))}" '
            f'{"checked" if is_checked(option) else ""}{off} '
            f'onchange="{on_change}(this)" '
            f'data-comp-id="{comp.id}"/></span>'
        )
        text = (
            f'<div class="st-radio-markdown">'
            f'<p>{render_markup(fmt(option))}</p></div>'
        )
        enter = _row_enter_html() if (navigable and navigable(option)) else ''
        item_cls = 'st-radio-item'
        if frozen:
            item_cls += ' is-box-disabled'
        if index == focused:
            item_cls += ' is-highlighted'
        # the label wraps the whole row, so a click on the body of an ordinary
        # row ticks the box by itself and `scHighlightChoice` only adds the
        # highlight; a `body_opens` row spends that click on the walk-in
        walk_in = bool(body_opens and body_opens(option))
        row_click = 'scOpenRow' if walk_in else 'scHighlightChoice'
        item_html.append(
            f'<label class="{item_cls}">{field}'
            f'<div class="st-radio-item-body">'
            f'<div class="st-radio-item-row" '
            f'onclick="{row_click}(event, this)">'
            f'{box}{text}{enter}'
            f'</div></div></label>'
        )
    return ''.join(item_html)


def _render_choice_group(
    comp: RadioGroup | CheckGroup,
    *,
    base_cls: str,
    input_type: str,
    on_change: str,
    is_checked: tp.Callable[[tp.Any], bool],
) -> str:
    """Render an option list: the shared body of the two group widgets."""
    items = _choice_group_items_html(
        comp,
        comp.options.get() or (),
        is_checked,
        input_type=input_type,
        on_change=on_change,
        box_disabled=getattr(comp, '_box_disabled', None),
        navigable=getattr(comp, '_navigable', None),
        body_opens=getattr(comp, '_body_opens', None),
    )
    root_cls = base_cls
    if getattr(comp, '_horizontal', False):
        root_cls += f' {base_cls}--horizontal'
    if not comp.enabled.get():
        root_cls += ' is-disabled'
    max_height = getattr(comp, '_max_height', None)
    group_style = (
        f' style="max-height:{max_height}px;overflow-y:auto"'
        if isinstance(max_height, int)
        else ''
    )
    return (
        f'<div class="{root_cls}" data-id="{comp.id}"{_size_style(comp)}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-radio-group"{group_style}>{items}</div>'
        f'</div>'
    )


def _render_radio_group(comp: RadioGroup) -> str:
    value = comp.value.get()
    return _render_choice_group(
        comp,
        base_cls='st-radio',
        input_type='radio',
        on_change='scSendChange',
        is_checked=lambda o: o == value,
    )


def _render_check_group(comp: CheckGroup) -> str:
    if comp._flags:
        # Flag mode (`options` arrived as a `dict`): `value` is a list of
        # booleans parallel to `options`, so the ticked options are the ones
        # the flags line up with. The extra class tells the frontend to read
        # `value` the same way when it patches.
        options = list(comp.options.get() or ())
        picked = [o for o, on in zip(options, comp.value.get() or ()) if on]
        base_cls = 'st-check-group st-check-group--flags'
    else:
        picked = list(comp.value.get() or ())
        base_cls = 'st-check-group'
    return _render_choice_group(
        comp,
        base_cls=base_cls,
        input_type='checkbox',
        on_change='scSendCheckGroup',
        is_checked=lambda o: o in picked,
    )


def _render_segmented_control(comp: SegmentedControl) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = comp.format_func
    disabled = '' if comp.enabled.get() else ' disabled'
    items = ''.join(
        f'<label class="st-segmented-item">'
        f'<input type="radio" name="seg_{comp.id}" '
        f'value="{html.escape(str(o))}" '
        f'{"checked" if o == value else ""}{disabled} '
        f'onchange="scSendChange(this)" '
        f'data-comp-id="{comp.id}"/>'
        f'<span class="st-segmented-item-label">'
        f'{render_markup(fmt(o))}</span></label>'
        for o in options
    )
    root_cls = 'st-segmented'
    if not comp.enabled.get():
        root_cls += ' is-disabled'
    return (
        f'<div class="{root_cls}" data-id="{comp.id}"{_size_style(comp)}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-segmented-group" role="radiogroup">'
        f'<div class="st-segmented-highlight"></div>'
        f'{items}</div>'
        f'</div>'
    )


def _render_checkbox(comp: Checkbox) -> str:
    checked = ' checked' if comp.value.get() else ''
    return (
        f'<div class="st-checkbox" data-id="{comp.id}"{_size_style(comp)}>'
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


def _render_toggle(comp: ToggleBox) -> str:
    checked = ' checked' if comp.value.get() else ''
    return (
        f'<div class="st-toggle" data-id="{comp.id}"{_size_style(comp)}>'
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
    width_style = _size_style(comp)
    enabled = comp.enabled.get()
    disabled = '' if enabled else ' disabled'
    panel_align = getattr(comp, '_panel_align', 'trigger')
    root_cls = 'st-popover' + ('' if enabled else ' is-disabled')
    if panel_align == 'menu':
        # `st.menu_button`'s chevron is 20px (a popover's is 16px); the extra
        # class is what `page.css` hooks to swap it (see `.st-popover--menu`).
        root_cls += ' st-popover--menu'
    help_attr = ''
    help_text = _help_text(comp)
    if help_text:
        help_attr = f' data-help="{_escape_help(help_text)}"'
    panel_cls = 'st-popover-panel'
    panel_style = ''
    if panel_align == 'row':
        panel_cls += ' st-popover-panel--row'
    elif panel_align == 'above':
        panel_cls += ' st-popover-panel--above'
    elif panel_align == 'menu':
        panel_cls += ' st-popover-panel--menu'
        # `MenuButton` carries its rows in `options`, as plain HTML, so the
        # client can rebuild them on an `options` patch (no child components).
        children = (
            f'<div class="st-menu-options">{_menu_items_html(comp)}</div>'
            + children
        )
    max_height = getattr(comp, '_panel_max_height', None)
    if isinstance(max_height, int):
        panel_style = f' style="max-height:{max_height}px"'
    return (
        f'<div class="{root_cls}" data-id="{comp.id}">'
        f'<button class="st-btn st-btn-secondary st-popover-trigger" '
        f'type="button" aria-haspopup="dialog" aria-expanded="false"'
        f'{disabled}{width_style}{help_attr} onclick="scTogglePopover(this)">'
        f'<span class="st-btn-text st-popover-trigger-label">{label}</span>'
        f'<span class="st-popover-icon">'
        f'<span class="st-icon st-popover-chevron" translate="no">'
        f'{_POPOVER_CHEVRON_CLOSED}</span></span>'
        f'</button>'
        f'<div class="{panel_cls}" role="dialog"{panel_style} hidden>'
        f'{children}'
        f'</div>'
        f'</div>'
    )


def _render_space(comp: Space) -> str:
    """A spacer carries no content; `page.css` gives it the row's slack."""
    return (
        f'<div class="st-space" data-id="{comp.id}"{_size_style(comp)}></div>'
    )


def _menu_items_html(comp: tp.Any) -> str:
    """The rows of a menu panel (`MenuButton`): one per option.

    Plain HTML, not child components: the client rebuilds them on an `options`
    patch (see `scMenuItemsHtml`), so the list is not bound to the static tree.
    """
    fmt = getattr(comp, 'format_func', str)
    return ''.join(
        f'<div class="st-menu-option" role="menuitem" '
        f'data-value="{html.escape(str(o))}" onclick="scMenuPick(this)">'
        f'<span class="st-menu-option-label">{render_markup(fmt(o))}</span>'
        f'</div>'
        for o in (comp.options.get() or ())
    )


def _render_reducible_group(comp: ReducibleGroup) -> str:
    """A list of items, each with a hover-revealed remove button.

    The rows reuse the menu rows' metrics; the trailing `x` sends a `reduce`
    event that the widget turns into an `on_reduce` signal.
    """
    fmt = comp.format_func
    items = ''.join(
        f'<div class="st-menu-option st-menu-option--reducible" '
        f'data-value="{html.escape(str(o))}">'
        f'<span class="st-menu-option-label">{render_markup(fmt(o))}</span>'
        f'<button class="st-menu-option-remove" type="button" '
        f'aria-label="Remove" onclick="scReduceItem(this)">'
        f'{render_markup(":material/close:")}</button>'
        f'</div>'
        for o in (comp.options.get() or ())
    )
    return (
        f'<div class="st-reducible-group" data-id="{comp.id}"'
        f'{_size_style(comp)}>'
        f'{_widget_label_html(comp)}'
        f'<div class="st-reducible-group-items">{items}</div>'
        f'</div>'
    )


def _render_progress(comp: Progress) -> str:
    """Render a progress bar (mirrors Streamlit's `st.progress`).

    `value` is a 0-100 percentage, or `None` for an indeterminate
    (animated) bar. The bar is hidden while `visible` is false, so a
    long-running step can toggle it like a spinner.

    The caption is the bar's label row -- it sits above the track, where a
    widget's label sits -- so `label_visibility` picks whether that row is
    drawn at all. `auto`, the default, leaves the call to `:empty`.

    The caption sits *above* the track, as it does in Streamlit, and the
    fill is a square-ended rectangle: Streamlit keeps the bar at full width
    and slides it with `transform: translateX(-(100 - percent)%)`, so the
    rounded ends you see come from the track clipping it (see the
    `.st-progress-*` rules in `page.css`).
    """
    value = comp.value.get()
    if value is None:
        bar = '<div class="st-progress-bar is-indeterminate"></div>'
    else:
        pct = max(0, min(100, int(value)))
        bar = f'<div class="st-progress-bar" style="width:{pct}%"></div>'
    # the caption stays in the tree even when empty: a `text` patch has to
    # land somewhere. Which row it is drawn as is baked in, except for
    # `auto`, which is left to `:empty` -- the caption is filled by patch, so
    # a decision taken here could not follow it.
    visibility = getattr(comp, '_label_visibility', 'auto')
    cls = 'st-progress-text st-progress-text--{}'.format(visibility)
    text = render_markup(str(comp.text.get()))
    return (
        f'<div class="st-progress" data-id="{comp.id}">'
        f'<div class="{cls}">{text}</div>'
        f'<div class="st-progress-track">{bar}</div>'
        f'</div>'
    )


def _render_altair_chart(comp: AltairChart) -> str:
    """Render a Vega-Lite chart container (drawn client-side by vega-embed).

    The spec travels as an inert JSON `<script>` block so the browser can
    parse it without any string escaping games; `page.js` reads it on load
    and re-draws whenever a `chart` patch arrives.
    """
    width_style = _size_style(comp)
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


def _load_static_parts(folder: str, names: tp.Sequence[str]) -> str:
    """Reassemble a bundled asset from its parts, in the order given.

    `page.css` / `page.js` are cut into per-component parts only so a reader
    can find a block by file name (the lists below say what is where). Both
    names are still what the rest of the code calls these bundles. The parts
    hold the very same bytes the single file used to, so this join -- the one
    place their order lives -- puts the cascade (CSS) and the declarations
    (JS) back exactly as they were.
    """
    return ''.join(
        fs.load(fs.here('static/{0}/{1}'.format(folder, name)), 'plain')
        for name in names
    ).strip()


def _theme_block(css: str, theme: str) -> str:
    """Scope one theme file's tokens to `html[data-theme="<theme>"]`.

    The theme files declare their tokens on `:root`, hence the rewrite of the
    leading selector.
    """
    return css.replace(':root', f':root[data-theme="{theme}"]', 1)


_DARK_THEME_VARS = _load_static('theme-dark.css')

_LIGHT_THEME_VARS = _load_static('theme-light.css')

# Both themes ride along in the page -- scoped by attribute -- so the toolbar
# can switch between them without a round trip. `system` is not a block of its
# own: it is resolved to one of the two before the first paint.
_THEMES_CSS = '\n'.join(
    [
        _theme_block(_DARK_THEME_VARS, 'dark'),
        _theme_block(_LIGHT_THEME_VARS, 'light'),
    ]
)

# Inlined in <head>, ahead of the stylesheet, so a page whose remembered theme
# differs from the app's default never paints in the wrong one. It has to stay
# brace-free: the page template goes through `str.format`.
_THEME_BOOT = """\
var scThemePref = localStorage.getItem('sc-theme') || '{default_theme}';
var scThemeDark = matchMedia('(prefers-color-scheme: dark)').matches;
var scThemeRoot = document.documentElement;
scThemeRoot.dataset.themePref = scThemePref;
scThemeRoot.dataset.theme = scThemePref === 'system'
  ? (scThemeDark ? 'dark' : 'light') : scThemePref;"""

# `page.css` is cut by component; the order below is the cascade order, and
# it mirrors the original single file block for block (see the loader above).
_PAGE_CSS = _load_static_parts(
    'css',
    [
        '00-fonts.css',  # the three bundled faces
        '01-base.css',  # reset, `body`, the `#app` shell
        '10-texts.css',  # Title, Text, markdown, Caption
        '11-status.css',  # Alert, Spinner
        '20-layouts.css',  # Row, Container, Floating, Grid, widget label
        '30-inputs.css',  # TextInput, TextArea, NumberInput
        '31-table.css',  # Table
        '32-code.css',  # Code block
        '33-buttons.css',  # Button, Icon
        '34-selectbox.css',  # Selectbox and its dropdown
        '35-choice.css',  # RadioGroup, CheckGroup, Segmented, Checkbox
        '40-overlays.css',  # Popover + panel variants, Menu, Toolbar
        '50-feedback.css',  # rerun notice, error panel, Tabs, Expander,
        # Dialog, Toast, Progress
        '60-misc.css',  # AltairChart, Multiselect, SelectSlider
        '70-media.css',  # PdfViewer
        '71-log.css',  # LogPanel
    ],
)

# `page.js`, same idea: `00-connection.js` carries the socket and the whole
# delta dispatcher, the rest are the per-component helpers it calls.
_PAGE_JS = _load_static_parts(
    'js',
    [
        '00-connection.js',  # the socket + the delta dispatcher
        '10-helpers.js',  # copy, send, option keys, choice rows, arrows
        '20-selectbox.js',  # dropdown, new-option row, candidates
        '30-overlays.js',  # Dialog, Multiselect, Popover, Menu
        '40-inputs.js',  # Checkbox / CheckGroup sends + dismissal
        '50-markdown.js',  # markdown-it + the `:color` / `:material` bits
        '60-toast.js',  # the toast stack
        '65-log.js',  # the LogPanel
        '70-widgets.js',  # Tabs, Expander, NumberInput stepper
        '71-slider.js',  # SelectSlider
        '75-charts.js',  # AltairChart (vega-embed)
        '76-pdf-viewer.js',  # PdfViewer with the bundled pdf.js
        '80-dev-tools.js',  # source-change notice, uncaught error panel
        '85-shell.js',  # toolbar, theme, menu + the boot calls
        '90-help.js',  # help tooltips
    ],
)

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="{theme}">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<script>
{theme_boot}
</script>
<style>
{themes}
{page_css}
</style>
</head>
<body>
<div id="app"{app_attr}>{body}</div>
<script src="/static/markdown-it.js"></script>
<script src="/static/emoji-shortcodes.js"></script>
<script>
{page_js}
</script>
</body>
</html>
"""


def _toast_item(message: tp.Mapping[str, tp.Any]) -> str:
    """One toast of the stack.

    Server-side twin of `scToastHtml` in page.js: a patched-in toast has to
    end up with exactly the same markup, so the two must be kept in step.
    """
    icon = message.get('icon') or ''
    icon_html = (
        f'<span class="st-toast-icon">{render_markup(str(icon))}</span>'
        if icon
        else ''
    )
    text = render_markup(str(message.get('text', '')))
    duration = message.get('duration')
    dur_attr = f' data-duration="{duration}"' if duration else ''
    return (
        f'<div class="st-toast" data-id="{message.get("id", "")}"{dur_attr}>'
        f'{icon_html}'
        f'<span class="st-toast-body">{text}</span>'
        f'<button type="button" class="st-toast-close" aria-label="Dismiss"'
        f' onclick="scDismissToast(this)">&#10005;</button>'
        f'</div>'
    )


def _render_toast(comp: Toast) -> str:
    """Render the toast stack.

    It is a fixed overlay, so it stays wherever the component was declared
    and CSS pins it to the page corner. An empty stack is `hidden` (a fixed
    element would otherwise keep a stray hit-area).
    """
    messages = comp.messages.get() or []
    items = ''.join(_toast_item(m) for m in messages)
    hidden = '' if messages else ' hidden'
    return (
        f'<div class="st-toast-stack" data-id="{comp.id}"{hidden}>{items}</div>'
    )


def _render_pdf_viewer(comp: PdfViewer) -> str:
    """Render a `PdfViewer`: a box for the bundled pdf.js to draw into.

    `src` already holds a loadable URL (the conversion lives on the property,
    see `media._UrlProperty`), so nothing is read or encoded here -- and the
    very same string is what a later `src` patch carries (see
    `00-connection.js`). `pages_to_render` likewise travels as `data-pages`,
    for the client to leave the other pages out.

    Sizing is the uniform `_size_style` path: pdf.js draws real canvases, so
    a `'content'` height is the document's own height, and a `max_height`
    bound simply caps and scrolls that.
    """
    src = html.escape(comp.src.get(), quote=True)
    pages = ','.join(str(page) for page in comp._pages)
    return (
        f'<div class="st-pdf-viewer st-pdf-viewer--pdfjs"'
        f' data-id="{comp.id}" data-src="{src}" data-pages="{pages}"'
        f'{_size_style(comp)}>'
        f'<div class="st-pdf-viewer-pages"></div></div>'
    )


def _render_log_panel(comp: LogPanel) -> str:
    """Render a `LogPanel`: the captured lines in a scrolling `<pre>`.

    The whole buffer is written out, and rewritten whenever `lines` changes
    (see `65-log.js`); it is capped at `LogPanel._max_lines`, so the payload
    stays small. Escaping is enough to make a log line inert -- the markup
    around it is fixed.
    """
    text = html.escape('\n'.join(comp.lines.get() or ()), quote=False)
    return (
        f'<div class="st-log-panel" data-id="{comp.id}"'
        f'{_size_style(comp)}>'
        f'<pre class="st-log-panel-body">{text}</pre></div>'
    )


def _walk_tree(roots: tp.Iterable[Component]) -> tp.Iterator[Component]:
    """Every component in the tree, each parent before its children."""
    for comp in roots:
        yield comp
        yield from _walk_tree(comp.children)


def _find_page_title(roots: tp.Iterable[Component]) -> str:
    """The text of the last `PageTitle` in the tree, `''` if there is none.

    It names the document's own `<title>`, so the first paint already carries
    the name the app asked for; a later change rides the ordinary `text` patch
    from there (page.js keeps `document.title` in step).
    """
    found = ''
    for comp in _walk_tree(roots):
        if isinstance(comp, PageTitle):
            found = str(comp.text.get())
    return found


def render_page(
    roots: tp.Iterable[Component],
    title: str = 'Streamlit Canary',
    default_theme: str = 'dark',
    layout: str = 'centered',
    dunder_literal: bool = False,
) -> str:
    # the body and the page title below both walk the roots, so materialize
    # them once -- the caller may well hand us a generator
    roots = list(roots)
    # The OS preference behind `system` lives in the browser, so the attribute
    # starts on dark and the boot script corrects it before the first paint.
    theme = default_theme if default_theme in ('light', 'dark') else 'dark'
    # A `PageTitle` has the last word on the tab's name: it is the app saying
    # so on the page, where `set_page_config` only sets a default.
    title = _find_page_title(roots) or title
    # Page config rides on the app shell: `layout` is a class and the markdown
    # flag is a data attribute, both read by page.js (see `set_page_config`).
    app_attr = ' class="st-wide"' if layout == 'wide' else ''
    if dunder_literal:
        app_attr += ' data-dunder-literal="1"'
    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        theme=theme,
        theme_boot=_THEME_BOOT.format(default_theme=default_theme).strip(),
        themes=_THEMES_CSS.strip(),
        page_css=_PAGE_CSS.strip(),
        page_js=_PAGE_JS.strip(),
        body=render_tree(roots),
        app_attr=app_attr,
    )
