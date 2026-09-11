"""
Render the v3 component tree to HTML.

Each component becomes a DOM element tagged with `data-id="<component id>"`.
The frontend uses these ids to patch elements when a delta arrives.

Delta message format (server → client):
    {"type": "patch", "id": "<comp-id>", "prop": "text", "value": "..."}

Event message format (client → server):
    {"type": "event", "id": "<comp-id>", "event": "click"}
    {"type": "event", "id": "<comp-id>", "event": "change", "value": "..."}
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
# Streamlit-style markup parser: `:color[text]` and `:material/icon`
# ---------------------------------------------------------------------------

_COLOR_RE = re.compile(r':([a-zA-Z]+)\[([^\]]*)\]')
_MATERIAL_RE = re.compile(r':material/([a-zA-Z_]+):')

# Material Symbols (Segoe Fluent Icons fallback to unicode)
_MATERIAL_MAP = {
    'autorenew': '\u21bb',  # clockwise open circle arrow
    'refresh': '\u21bb',
    'delete': '\u2715',
    'add': '+',
    'check': '\u2713',
    'close': '\u2715',
    'edit': '\u270e',
    'search': '\ud83d\udd0d',
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
    # escape first
    text = html.escape(text)

    # :material/icon: → unicode glyph
    def _mat(m: re.Match) -> str:
        name = m.group(1)
        glyph = _MATERIAL_MAP.get(name, '\u25a1')
        return f'<span class="sc-icon">{glyph}</span>'

    text = _MATERIAL_RE.sub(_mat, text)

    # :color[text] → <span style="color:...">
    def _col(m: re.Match) -> str:
        color = m.group(1)
        inner = m.group(2)
        css = _COLOR_CSS.get(color)
        if css is None:
            return f'<span class="sc-text-{color}">{inner}</span>'
        return f'<span style="color:{css}">{inner}</span>'

    text = _COLOR_RE.sub(_col, text)

    return text


# ---------------------------------------------------------------------------
# Component tree → HTML
# ---------------------------------------------------------------------------


def render_tree(roots: tp.Iterable[Component]) -> str:
    return ''.join(_render(comp) for comp in roots)


def _render(comp: Component) -> str:
    if isinstance(comp, Row):
        children = ''.join(_render(c) for c in comp.children)
        return (
            f'<div class="sc-row" data-id="{comp.id}" '
            f'style="display:flex;gap:8px;align-items:center">'
            f'{children}</div>'
        )
    if isinstance(comp, Column):
        children = ''.join(_render(c) for c in comp.children)
        style = 'display:flex;flex-direction:column;gap:8px;'
        if getattr(comp, '_width', None):
            w = comp._width
            if isinstance(w, int):
                style += f'width:{w}px;'
            elif w == 'stretch':
                style += 'flex:1;'
            else:
                style += f'width:{w};'
        if getattr(comp, '_border', False):
            style += 'border:1px solid #ddd;border-radius:8px;padding:12px;'
        return (
            f'<div class="sc-column" data-id="{comp.id}" '
            f'style="{style}">{children}</div>'
        )
    if isinstance(comp, (Text, Title)):
        text = render_markup(str(comp.text.get()))
        tag = 'h1' if isinstance(comp, Title) else 'div'
        cls = 'sc-title' if isinstance(comp, Title) else 'sc-text'
        return f'<{tag} class="{cls}" data-id="{comp.id}">{text}</{tag}>'
    if isinstance(comp, Button):
        label = render_markup(str(comp.label.get()))
        btn_type = getattr(comp, '_type', 'default')
        width = getattr(comp, '_width', None)
        cls = f'sc-btn sc-btn-{btn_type}'
        style = ''
        if width == 'stretch':
            style = 'style="width:100%"'
        help_attr = ''
        if getattr(comp, '_help', None):
            help_text = html.escape(str(comp._help))
            help_attr = f' title="{help_text}"'
        return (
            f'<button class="{cls}" data-id="{comp.id}" '
            f'onclick="scSendClick(this)" {style}{help_attr}>{label}</button>'
        )
    if isinstance(comp, Selectbox):
        return _render_selectbox(comp)
    if isinstance(comp, Radio):
        return _render_radio(comp)
    # fallback: render children only
    return ''.join(_render(c) for c in comp.children)


def _render_selectbox(comp: Selectbox) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = getattr(comp, '_format_func', str)
    opt_html = ''.join(
        f'<option value="{html.escape(str(o))}" '
        f'{"selected" if o == value else ""}>'
        f'{html.escape(fmt(o))}</option>'
        for o in options
    )
    label = html.escape(getattr(comp, '_label', ''))
    return (
        f'<div class="sc-selectbox" data-id="{comp.id}">'
        f'<label class="sc-selectbox-label">{label}</label>'
        f'<select onchange="scSendChange(this)" '
        f'data-comp-id="{comp.id}">{opt_html}</select>'
        f'</div>'
    )


def _render_radio(comp: Radio) -> str:
    options = comp.options.get() or []
    value = comp.value.get()
    fmt = getattr(comp, '_format_func', str)
    label = html.escape(getattr(comp, '_label', ''))
    items = ''.join(
        f'<label class="sc-radio-item">'
        f'<input type="radio" name="radio_{comp.id}" '
        f'value="{html.escape(str(o))}" '
        f'{"checked" if o == value else ""} '
        f'onchange="scSendChange(this)" '
        f'data-comp-id="{comp.id}"/>'
        f'<span>{render_markup(fmt(o))}</span>'
        f'</label>'
        for o in options
    )
    return (
        f'<div class="sc-radio" data-id="{comp.id}">'
        f'<label class="sc-radio-label">{label}</label>'
        f'{items}</div>'
    )


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; padding: 24px; }}
  .sc-title {{ font-size: 28px; font-weight: 700; margin: 0 0 16px; }}
  .sc-text {{ font-size: 16px; margin: 4px 0; }}
  .sc-btn {{
    padding: 6px 14px; border: 1px solid #ccc; border-radius: 6px;
    cursor: pointer; font-size: 14px; background: #fff;
  }}
  .sc-btn-primary {{ background: #ff4b4b; color: #fff; border-color: #ff4b4b; }}
  .sc-btn:hover {{ opacity: 0.9; }}
  .sc-selectbox select {{
    padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px;
    font-size: 14px; min-width: 200px;
  }}
  .sc-selectbox-label, .sc-radio-label {{
    font-size: 13px; color: #666; display:block; margin-bottom: 4px;
  }}
  .sc-radio {{ display:flex; flex-direction:column; gap:4px; }}
  .sc-radio-item {{ display:flex; align-items:center; gap:6px;
    padding:4px 8px; border-radius:4px; cursor:pointer; }}
  .sc-radio-item:hover {{ background: #f5f5f5; }}
  .sc-radio-item span {{ font-size: 14px; }}
  .sc-icon {{ font-size: 16px; }}
</style>
</head>
<body>
<div id="app">{body}</div>
<script>
const ws = new WebSocket(`ws://${{location.host}}/ws`);
ws.onmessage = (e) => {{
  const msg = JSON.parse(e.data);
  if (msg.type !== 'patch') return;
  const el = document.querySelector(`[data-id="${{msg.id}}"]`);
  if (!el) return;
  // update text content for text/label/title props
  if (msg.prop === 'text' || msg.prop === 'label') {{
    el.innerHTML = window.scRenderMarkup(msg.value);
  }}
  // update selectbox/radio options + value
  if (msg.prop === 'options') {{
    if (el.tagName === 'SELECT' || el.classList.contains('sc-selectbox')) {{
      const sel = el.querySelector('select') || el;
      sel.innerHTML = msg.value.map(o =>
        `<option value="${{o}}">${{o}}</option>`).join('');
    }}
    if (el.classList.contains('sc-radio')) {{
      el.innerHTML = msg.value.map(o =>
        `<label class="sc-radio-item"><input type="radio" ` +
        `name="radio_${{msg.id}}" value="${{o}}" ` +
        `onchange="scSendChange(this)" data-comp-id="${{msg.id}}"/>` +
        `<span>${{o}}</span></label>`).join('');
    }}
  }}
  if (msg.prop === 'value') {{
    if (el.classList.contains('sc-selectbox')) {{
      const sel = el.querySelector('select');
      if (sel) sel.value = msg.value;
    }}
    if (el.classList.contains('sc-radio')) {{
      el.querySelectorAll('input').forEach(r => {{
        r.checked = (r.value === msg.value);
      }});
    }}
  }}
}};
function scSendClick(btn) {{
  ws.send(JSON.stringify({{type: 'event', id: btn.dataset.id, event: 'click'}}));
}}
function scSendChange(input) {{
  const id = input.dataset.compId;
  ws.send(JSON.stringify({{type: 'event', id: id, event: 'change', value: input.value}}));
}}
</script>
</body>
</html>
"""


def render_page(
    roots: tp.Iterable[Component], title: str = 'Streamlit Canary'
) -> str:
    return PAGE_TEMPLATE.format(
        title=html.escape(title), body=render_tree(roots)
    )
