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

from ..components_v3.base import Component
from ..components_v3.widgets import Button
from ..components_v3.widgets import Column
from ..components_v3.widgets import Radio
from ..components_v3.widgets import Row
from ..components_v3.widgets import Selectbox
from ..components_v3.widgets import Text
from ..components_v3.widgets import Title

# ---------------------------------------------------------------------------
# Streamlit-style markup: `:color[text]` and `:material/icon`
# ---------------------------------------------------------------------------

_COLOR_RE = re.compile(r':([a-zA-Z]+)\[([^\]]*)\]')
_MATERIAL_RE = re.compile(r':material/([a-zA-Z_]+):')

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

_COLOR_CSS = {
    'red': '#ff4b4b',
    'green': '#09ab3b',
    'blue': '#1c83f0',
    'orange': '#ffa422',
    'gray': '#808080',
    'grey': '#808080',
    'violet': '#8e3ab3',
    'rainbow': None,
}


def render_markup(text: str) -> str:
    """Convert Streamlit-style markup to HTML-safe spans."""
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
    return text


# ---------------------------------------------------------------------------
# Component tree → HTML (Streamlit-style DOM)
# ---------------------------------------------------------------------------


def render_tree(roots: tp.Iterable[Component]) -> str:
    return ''.join(_render(comp) for comp in roots)


def _render(comp: Component) -> str:
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
            width_style = f' style="width:{w}px"'
        return (
            f'<div class="st-container{border_cls}" data-id="{comp.id}"'
            f'{width_style}>{children}</div>'
        )
    if isinstance(comp, Title):
        text = render_markup(str(comp.text.get()))
        return f'<h1 class="st-title" data-id="{comp.id}">{text}</h1>'
    if isinstance(comp, Text):
        text = render_markup(str(comp.text.get()))
        return f'<div class="st-text" data-id="{comp.id}">{text}</div>'
    if isinstance(comp, Button):
        return _render_button(comp)
    if isinstance(comp, Selectbox):
        return _render_selectbox(comp)
    if isinstance(comp, Radio):
        return _render_radio(comp)
    return ''.join(_render(c) for c in comp.children)


def _render_button(comp: Button) -> str:
    label = render_markup(str(comp.label.get()))
    btn_type = getattr(comp, '_type', 'secondary')
    # Streamlit: type="secondary" is default, "primary" is the accent button.
    st_type = 'primary' if btn_type == 'primary' else 'secondary'
    cls = f'st-btn st-btn-{st_type}'
    width = getattr(comp, '_width', 'content')
    width_style = ' style="width:100%"' if width == 'stretch' else ''
    help_attr = ''
    if getattr(comp, '_help', None):
        help_text = html.escape(str(comp._help))
        help_attr = f' title="{help_text}"'
    return (
        f'<button class="{cls}" data-id="{comp.id}" '
        f'onclick="scSendClick(this)"{width_style}{help_attr}>'
        f'{label}</button>'
    )


def _render_selectbox(comp: Selectbox) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = getattr(comp, '_format_func', str)
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
        f'{html.escape(fmt(o))}</div></div>'
        for o in options
    )
    # Display text for the trigger button.
    display_text = html.escape(fmt(value)) if value else '\u200b'
    label = html.escape(getattr(comp, '_label', ''))
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
        f'<label class="st-widget-label">{label}</label>'
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
    fmt = getattr(comp, '_format_func', str)
    label = html.escape(getattr(comp, '_label', ''))
    items = ''.join(
        f'<label class="st-radio-item">'
        f'<input type="radio" name="radio_{comp.id}" '
        f'value="{html.escape(str(o))}" '
        f'{"checked" if o == value else ""} '
        f'onchange="scSendChange(this)" '
        f'data-comp-id="{comp.id}"/>'
        f'<span class="st-radio-label-text">'
        f'{render_markup(fmt(o))}</span>'
        f'</label>'
        for o in options
    )
    return (
        f'<div class="st-radio" data-id="{comp.id}">'
        f'<label class="st-widget-label">{label}</label>'
        f'<div class="st-radio-group">{items}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Page template with Streamlit dark theme
# ---------------------------------------------------------------------------

_DARK_THEME_VARS = """
  :root {
    --st-background-color: #0d1117;
    --st-secondary-background-color: #161b22;
    --st-text-color: #e6edf3;
    --st-heading-color: #e6edf3;
    --st-primary-color: #ff4b4b;
    --st-border-color: #30363d;
    --st-border-color-light: #21262d;
    --st-widget-border-color: #30363d;
    --st-base-radius: 8px;
    --st-button-radius: 6px;
    --st-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Source Sans 3", sans-serif;
    --st-heading-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Source Sans 3", sans-serif;
    --st-code-font: "Source Code Pro", "SF Mono", monospace;
    --st-base-font-size: 14px;
    --st-base-font-weight: 400;
    --st-green-color: #3fb950;
    --st-orange-color: #d29922;
    --st-red-color: #f85149;
    --st-blue-color: #58a6ff;
    --st-gray-color: #8b949e;
  }
"""

_LIGHT_THEME_VARS = """
  :root {
    --st-background-color: #ffffff;
    --st-secondary-background-color: #f6f8fa;
    --st-text-color: #1f2328;
    --st-heading-color: #1f2328;
    --st-primary-color: #ff4b4b;
    --st-border-color: #d0d7de;
    --st-border-color-light: #eaeef2;
    --st-widget-border-color: #d0d7de;
    --st-base-radius: 8px;
    --st-button-radius: 6px;
    --st-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Source Sans 3", sans-serif;
    --st-heading-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Source Sans 3", sans-serif;
    --st-code-font: "Source Code Pro", "SF Mono", monospace;
    --st-base-font-size: 14px;
    --st-base-font-weight: 400;
    --st-green-color: #1a7f37;
    --st-orange-color: #bf8700;
    --st-red-color: #cf222e;
    --st-blue-color: #0969da;
    --st-gray-color: #57606a;
  }
"""

_PAGE_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--st-font);
    font-size: var(--st-base-font-size);
    font-weight: var(--st-base-font-weight);
    background-color: var(--st-background-color);
    color: var(--st-text-color);
    line-height: 1.6;
    padding: 24px 0;
  }
  #app {
    max-width: 768px;
    margin: 0 auto;
    padding: 0 16px;
  }

  /* Title */
  .st-title {
    font-family: var(--st-heading-font);
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--st-heading-color);
    margin-bottom: 16px;
    line-height: 1.25;
  }

  /* Text */
  .st-text {
    font-size: 14px;
    color: var(--st-text-color);
    margin-bottom: 8px;
  }

  /* Layout: Row */
  .st-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    margin-bottom: 8px;
  }
  .st-row > * { flex: 1; }
  .st-row > .st-btn-secondary { flex: 0 0 auto; }
  /* Neutralize widget bottom margins so `align-items` aligns the actual
  box edges, not the margin box. Use higher specificity than single-class
  widget rules (e.g. `.st-selectbox { margin-bottom: 8px }`). */
  .st-row > .st-selectbox,
  .st-row > .st-radio,
  .st-row > .st-btn,
  .st-row > .st-text,
  .st-row > .st-title { margin-bottom: 0; }

  /* Layout: Container (Column) */
  .st-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 8px;
  }
  .st-container--border {
    border: 1px solid var(--st-border-color);
    border-radius: var(--st-base-radius);
    padding: 16px;
  }

  /* Widget label */
  .st-widget-label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--st-text-color);
    margin-bottom: 4px;
    visibility: visible;
  }

  /* Button */
  .st-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 16px;
    min-height: 38px;
    border: 1px solid var(--st-widget-border-color);
    border-radius: var(--st-button-radius);
    font-family: var(--st-font);
    font-size: 14px;
    font-weight: 400;
    line-height: 1.4;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s;
    user-select: none;
  }
  .st-btn-secondary {
    background-color: var(--st-secondary-background-color);
    color: var(--st-text-color);
    border-color: rgba(250, 250, 250, 0.2);
  }
  .st-btn-secondary:hover {
    background-color: rgba(172, 177, 195, 0.15);
  }
  .st-btn-secondary:active {
    background-color: rgba(172, 177, 195, 0.25);
  }
  .st-btn-primary {
    background-color: var(--st-primary-color);
    color: #ffffff;
    border-color: var(--st-primary-color);
  }
  .st-btn-primary:hover {
    filter: brightness(1.1);
  }
  .st-icon { font-size: 16px; line-height: 1; }

  /* Selectbox (custom dropdown — no native <select>) */
  .st-selectbox { margin-bottom: 8px; }
  .st-selectbox-control {
    position: relative;
    display: flex;
    align-items: center;
  }
  .st-selectbox-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    min-height: 38px;
    padding: 8px 12px;
    border: 1px solid var(--st-widget-border-color);
    border-radius: var(--st-button-radius);
    background-color: var(--st-secondary-background-color);
    color: var(--st-text-color);
    font-family: var(--st-font);
    font-size: 14px;
    line-height: 1.4;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  /* No border-color change on hover — matches Streamlit's behavior. */
  .st-selectbox-trigger:focus {
    outline: none;
    border-color: var(--st-primary-color);
    box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.2);
  }
  .st-selectbox-value {
    flex: 1;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .st-selectbox-arrow {
    color: var(--st-text-color);
    flex-shrink: 0;
    transition: transform 0.2s;
  }
  .st-selectbox-trigger[aria-expanded="true"] .st-selectbox-arrow {
    transform: rotate(180deg);
  }
  .st-selectbox-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    z-index: 1000;
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--st-widget-border-color);
    border-radius: var(--st-button-radius);
    background-color: var(--st-secondary-background-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    padding: 4px 0;
  }
  .st-selectbox-option {
    padding: 0 5px;
    color: var(--st-text-color);
    cursor: pointer;
  }
  .st-selectbox-option-inner {
    padding: 8px 8px;
    font-size: 14px;
    line-height: 1.4;
    border-radius: 4px;
    transition: background-color 0.1s;
  }
  .st-selectbox-option:hover > .st-selectbox-option-inner {
    background-color: var(--st-border-color);
  }
  .st-selectbox-option[data-selected] .st-selectbox-option-inner {
    color: var(--st-primary-color);
  }
  .st-selectbox-dropdown::-webkit-scrollbar {
    width: 6px;
  }
  .st-selectbox-dropdown::-webkit-scrollbar-track {
    background: transparent;
  }
  .st-selectbox-dropdown::-webkit-scrollbar-thumb {
    background: var(--st-border-color);
    border-radius: 3px;
  }

  /* Radio */
  .st-radio { margin-bottom: 8px; }
  .st-radio-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 400px;
    overflow-y: auto;
  }
  .st-radio-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.1s;
  }
  .st-radio-item:hover {
    background-color: var(--st-border-color-light);
  }
  .st-radio-item input[type="radio"] {
    appearance: none;
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    border: 2px solid var(--st-widget-border-color);
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.15s;
    position: relative;
    flex-shrink: 0;
  }
  .st-radio-item input[type="radio"]:checked {
    border-color: var(--st-primary-color);
    background-color: var(--st-primary-color);
  }
  .st-radio-item input[type="radio"]:checked::after {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ffffff;
  }
  .st-radio-item input[type="radio"]:focus {
    outline: none;
    box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.2);
  }
  .st-radio-label-text {
    font-size: 14px;
    color: var(--st-text-color);
  }

  /* Scrollbar (dark theme) */
  .st-radio-group::-webkit-scrollbar {
    width: 6px;
  }
  .st-radio-group::-webkit-scrollbar-track {
    background: transparent;
  }
  .st-radio-group::-webkit-scrollbar-thumb {
    background: var(--st-border-color);
    border-radius: 3px;
  }
  .st-radio-group::-webkit-scrollbar-thumb:hover {
    background: var(--st-gray-color);
  }
"""

_PAGE_JS = """
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type !== 'patch') return;
    const el = document.querySelector(`[data-id="${msg.id}"]`);
    if (!el) return;
    if (msg.prop === 'text' || msg.prop === 'label') {
      // For selectbox/radio, label is in .st-widget-label, not the root
      if (el.classList.contains('st-selectbox') || el.classList.contains('st-radio')) {
        const labelEl = el.querySelector('.st-widget-label');
        if (labelEl) labelEl.textContent = msg.value;
      } else {
        el.innerHTML = window.scRenderMarkup(msg.value);
      }
    }
    if (msg.prop === 'options') {
      if (el.classList.contains('st-selectbox')) {
        // Custom dropdown: rebuild option items + update trigger label.
        const trigger = el.querySelector('.st-selectbox-trigger');
        const dropdown = el.querySelector('.st-selectbox-dropdown');
        const id = msg.id;
        const currentVal = el._scValue || msg.value[0];
        const labels = msg.formatted || msg.value.map(x => x);
        const fmt = window.scRenderMarkup;
        dropdown.innerHTML = msg.value.map((o, i) =>
          `<div class="st-selectbox-option" role="option" ` +
          `data-value="${o}" data-comp-id="${id}" ` +
          `onclick="scSelectOption(this)" ` +
          `${o === currentVal ? 'data-selected' : ''}>` +
          `<div class="st-selectbox-option-inner">${fmt(labels[i])}</div></div>`
        ).join('');
        const selIdx = msg.value.indexOf(currentVal);
        const valEl = el.querySelector('.st-selectbox-value');
        if (valEl) valEl.innerHTML = selIdx >= 0 ? fmt(labels[selIdx]) : '';
      }
      if (el.classList.contains('st-radio')) {
        const group = el.querySelector('.st-radio-group');
        const id = msg.id;
        const currentVal = el._scValue || msg.value[0];
        const fmt = window.scRenderMarkup;
        const labels = msg.formatted || msg.value.map(x => x);
        group.innerHTML = msg.value.map((o, i) =>
          `<label class="st-radio-item">` +
          `<input type="radio" name="radio_${id}" value="${o}" ` +
          `${o === currentVal ? 'checked' : ''} ` +
          `onchange="scSendChange(this)" data-comp-id="${id}"/>` +
          `<span class="st-radio-label-text">${fmt(labels[i])}</span>` +
          `</label>`
        ).join('');
      }
    }
    if (msg.prop === 'value') {
      if (el.classList.contains('st-selectbox')) {
        // Custom dropdown: update trigger display + selected marker.
        el._scValue = msg.value;
        const dropdown = el.querySelector('.st-selectbox-dropdown');
        const fmt = window.scRenderMarkup;
        // Rebuild labels from existing options if formatted map is cached.
        const optEls = dropdown ? dropdown.querySelectorAll('.st-selectbox-option') : [];
        optEls.forEach(o => {
          if (o.dataset.value === msg.value) {
            o.setAttribute('data-selected', '');
          } else {
            o.removeAttribute('data-selected');
          }
        });
        // Update trigger text from the matching option's inner div.
        const matched = Array.from(optEls).find(o => o.dataset.value === msg.value);
        const inner = matched ? matched.querySelector('.st-selectbox-option-inner') : null;
        const valEl = el.querySelector('.st-selectbox-value');
        if (valEl && inner) valEl.textContent = inner.textContent;
      }
      if (el.classList.contains('st-radio')) {
        el._scValue = msg.value;
        el.querySelectorAll('input').forEach(r => {
          r.checked = (r.value === msg.value);
        });
      }
    }
  };
  function scSendClick(btn) {
    ws.send(JSON.stringify({type: 'event', id: btn.dataset.id, event: 'click'}));
  }
  function scSendChange(input) {
    const id = input.dataset.compId;
    ws.send(JSON.stringify({type: 'event', id: id, event: 'change', value: input.value}));
  }
  // -- Custom selectbox dropdown interaction --
  function scToggleSelectbox(trigger) {
    const control = trigger.closest('.st-selectbox-control');
    const dropdown = control.querySelector('.st-selectbox-dropdown');
    const isOpen = !dropdown.hidden;
    // Close any other open dropdown first.
    document.querySelectorAll('.st-selectbox-dropdown:not([hidden])').forEach(d => {
      if (d !== dropdown) {
        d.hidden = true;
        const t = d.closest('.st-selectbox-control').querySelector('.st-selectbox-trigger');
        t.removeAttribute('aria-expanded');
      }
    });
    if (isOpen) {
      dropdown.hidden = true;
      trigger.removeAttribute('aria-expanded');
    } else {
      dropdown.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
    }
  }
  function scSelectOption(opt) {
    const id = opt.dataset.compId;
    const value = opt.dataset.value;
    // Update UI immediately.
    const root = document.querySelector(`[data-id="${id}"]`);
    if (root) {
      root._scValue = value;
      // Update selected marker.
      root.querySelectorAll('.st-selectbox-option').forEach(o => {
        if (o.dataset.value === value) o.setAttribute('data-selected', '');
        else o.removeAttribute('data-selected');
      });
      // Update trigger label from the inner div's text.
      const inner = opt.querySelector('.st-selectbox-option-inner');
      const valEl = root.querySelector('.st-selectbox-value');
      if (valEl && inner) valEl.textContent = inner.textContent;
      // Close dropdown.
      const dropdown = root.querySelector('.st-selectbox-dropdown');
      const trigger = root.querySelector('.st-selectbox-trigger');
      if (dropdown) dropdown.hidden = true;
      if (trigger) trigger.removeAttribute('aria-expanded');
    }
    // Send change event to backend.
    ws.send(JSON.stringify({type: 'event', id: id, event: 'change', value: value}));
  }
  // Close dropdown when clicking outside.
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.st-selectbox-control')) {
      document.querySelectorAll('.st-selectbox-dropdown:not([hidden])').forEach(d => {
        d.hidden = true;
        const t = d.closest('.st-selectbox-control').querySelector('.st-selectbox-trigger');
        t.removeAttribute('aria-expanded');
      });
    }
  });
  // expose markup renderer for WS patches
  window.scRenderMarkup = function(text) {
    // escape
    let s = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // :material/icon:
    const matMap = {autorenew:'\u21bb',refresh:'\u21bb',delete:'\u2715',add:'+',check:'\u2713',close:'\u2715',edit:'\u270e',search:'\U0001f50d',settings:'\u2699',download:'\u2b07',upload:'\u2b06'};
    s = s.replace(/:material\/([a-zA-Z_]+):/g, (m,n) => `<span class="st-icon">${matMap[n]||'\u25a1'}</span>`);
    // :color[text]
    const colMap = {red:'#ff4b4b',green:'#09ab3b',blue:'#1c83f0',orange:'#ffa422',gray:'#808080',grey:'#808080',violet:'#8e3ab3'};
    s = s.replace(/:([a-zA-Z]+)\[([^\]]*)\]/g, (m,c,t) => {
      const css = colMap[c];
      return css ? `<span style="color:${css}">${t}</span>` : `<span class="st-text-${c}">${t}</span>`;
    });
    return s;
  };
"""

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
