"""
Render the v3 component tree to HTML.

Each component becomes a DOM element tagged with `data-id="<component id>"`.
The frontend uses these ids to patch elements when a delta arrives.

Delta message format (server → client):
    {"type": "patch", "id": "<comp-id>", "prop": "text", "value": "..."}

Event message format (client → server):
    {"type": "event", "id": "<comp-id>", "event": "click"}
"""

from __future__ import annotations

import html
import typing as tp

from ..components_v3.base import Component
from ..components_v3.widgets import Button
from ..components_v3.widgets import Row
from ..components_v3.widgets import Text


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
    if isinstance(comp, Text):
        text = html.escape(str(comp.text.get()))
        return f'<div class="sc-text" data-id="{comp.id}">{text}</div>'
    if isinstance(comp, Button):
        label = html.escape(str(comp.label.get()))
        btn_type = getattr(comp, '_type', 'default')
        cls = f'sc-btn sc-btn-{btn_type}'
        return (
            f'<button class="{cls}" data-id="{comp.id}" '
            f'onclick="scSendClick(this)">{label}</button>'
        )
    # fallback: render children only
    return ''.join(_render(c) for c in comp.children)


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Streamlit Canary (event-driven)</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; padding: 24px; }}
  .sc-text {{ font-size: 16px; margin: 4px 0; }}
  .sc-btn {{
    padding: 6px 14px; border: 1px solid #ccc; border-radius: 6px;
    cursor: pointer; font-size: 14px; background: #fff;
  }}
  .sc-btn-primary {{ background: #ff4b4b; color: #fff; border-color: #ff4b4b; }}
  .sc-btn:hover {{ opacity: 0.9; }}
</style>
</head>
<body>
<div id="app">{body}</div>
<script>
const ws = new WebSocket(`ws://${{location.host}}/ws`);
ws.onmessage = (e) => {{
  const msg = JSON.parse(e.data);
  if (msg.type === 'patch') {{
    const el = document.querySelector(`[data-id="${{msg.id}}"]`);
    if (!el) return;
    if (msg.prop === 'text' || msg.prop === 'label') {{
      el.textContent = msg.value;
    }}
  }}
}};
function scSendClick(btn) {{
  ws.send(JSON.stringify({{type: 'event', id: btn.dataset.id, event: 'click'}}));
}}
</script>
</body>
</html>
"""


def render_page(roots: tp.Iterable[Component]) -> str:
    return PAGE_TEMPLATE.format(body=render_tree(roots))
