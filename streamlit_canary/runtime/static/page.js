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
        if (labelEl) labelEl.innerHTML = window.scRenderMarkup(msg.value);
      } else if (el.classList.contains('st-btn')) {
        el.innerHTML = window.scRenderButtonText(msg.value);
      } else if (el.classList.contains('st-spinner')) {
        const textEl = el.querySelector('.st-spinner-text');
        if (textEl) textEl.innerHTML = window.scRenderMarkup(msg.value);
      } else if (el.classList.contains('st-code')) {
        const codeEl = el.querySelector('code');
        if (codeEl) codeEl.textContent = msg.value;
      } else if (el.classList.contains('st-alert')) {
        const textEl = el.querySelector('.st-alert-text');
        if (textEl) textEl.innerHTML = window.scRenderParagraphs(msg.value);
      } else if (el.classList.contains('st-popover')) {
        const labelEl = el.querySelector('.st-popover-trigger-label');
        if (labelEl) labelEl.innerHTML = window.scRenderParagraphs(msg.value);
      } else {
        el.innerHTML = window.scRenderMarkup(msg.value);
      }
    }
    if (msg.prop === 'enabled') {
      if (el.classList.contains('st-btn')) el.disabled = !msg.value;
    }
    if (msg.prop === 'visible') {
      el.hidden = !msg.value;
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
          `<span class="st-radio-input-wrap">` +
          `<input type="radio" name="radio_${id}" value="${o}" ` +
          `${o === currentVal ? 'checked' : ''} ` +
          `onchange="scSendChange(this)" data-comp-id="${id}"/></span>` +
          `<div class="st-radio-item-body">` +
          `<div class="st-radio-item-row">` +
          `<div class="st-radio-circle"><div class="st-radio-dot"></div></div>` +
          `<div class="st-radio-markdown"><p>${fmt(labels[i])}</p></div>` +
          `</div></div></label>`
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
      if (el.classList.contains('st-text-input')) {
        const box = el.querySelector('.st-text-input-box');
        // Don't clobber what the user is currently typing.
        if (box && box.value !== msg.value) box.value = msg.value;
      }
      if (el.classList.contains('st-number-input')) {
        const box = el.querySelector('.st-text-input-box');
        const next = (msg.formatted !== undefined) ? msg.formatted : msg.value;
        // Don't clobber what the user is currently typing.
        if (box && box.value !== String(next)) box.value = String(next);
      }
      if (el.classList.contains('st-checkbox')) {
        const box = el.querySelector('input[type="checkbox"]');
        if (box) box.checked = !!msg.value;
      }
    }
    if (msg.prop === 'rows') {
      if (el.classList.contains('st-table')) {
        const tbody = el.querySelector('tbody');
        const fmt = window.scRenderMarkup;
        tbody.innerHTML = (msg.value || []).map(r =>
          '<tr>' +
          '<td class="st-table-cell"><p>' + fmt(String(r[0])) + '</p></td>' +
          '<td class="st-table-cell"><p>' + fmt(String(r[1])) + '</p></td>' +
          '</tr>'
        ).join('');
      }
    }
  };
  // Copy a code block's text; the button briefly switches to a check mark.
  function scCopyCode(btn) {
    const wrap = btn.closest('.st-code');
    const codeEl = wrap ? wrap.querySelector('code') : null;
    const text = codeEl ? codeEl.textContent : '';
    const done = () => {
      btn.classList.add('is-copied');
      setTimeout(() => btn.classList.remove('is-copied'), 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => {
        scCopyFallback(text);
        done();
      });
    } else {
      scCopyFallback(text);
      done();
    }
  }
  function scCopyFallback(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(area);
  }
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
  // -- Custom popover interaction (toggle is client-only; no rerun) --
  function scClosePopovers(except) {
    document.querySelectorAll('.st-popover-panel:not([hidden])').forEach(p => {
      if (p === except) return;
      p.hidden = true;
      const root = p.closest('.st-popover');
      const t = root ? root.querySelector('.st-popover-trigger') : null;
      if (t) t.setAttribute('aria-expanded', 'false');
    });
  }
  function scTogglePopover(trigger) {
    const root = trigger.closest('.st-popover');
    const panel = root.querySelector('.st-popover-panel');
    const isOpen = !panel.hidden;
    scClosePopovers(panel);
    if (isOpen) {
      panel.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    } else {
      panel.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
    }
  }
  // -- Checkbox: send the boolean checked state --
  function scSendCheck(input) {
    const id = input.dataset.compId;
    ws.send(JSON.stringify({type: 'event', id: id, event: 'change', value: input.checked}));
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
    if (!e.target.closest('.st-popover')) {
      scClosePopovers(null);
    }
  });
  // Close popovers on Escape.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') scClosePopovers(null);
  });
  // expose markup renderer for WS patches
  window.scRenderMarkup = function(text) {
    // typographer: '->' renders as an arrow (matches Streamlit markdown)
    let s = String(text).replace(/->/g, '→');
    // escape
    s = s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // :material/icon:
    const matMap = {autorenew:'↻',refresh:'↻',delete:'✕',add:'+',check:'✓',close:'✕',edit:'✎',search:'🔍',settings:'⚙',download:'⬇',upload:'⬆'};
    s = s.replace(/:material\/([a-zA-Z_]+):/g, (m,n) => `<span class="st-icon">${matMap[n]||'□'}</span>`);
    // :color[text]
    const colMap = {red:'#ff6c6c',orange:'#ffbd45',yellow:'#ffffc2',blue:'#3d9df3',green:'#5ce488',violet:'#b27eff',gray:'rgba(250, 250, 250, 0.6)',grey:'rgba(250, 250, 250, 0.6)'};
    s = s.replace(/:([a-zA-Z]+)\[([^\]]*)\]/g, (m,c,t) => {
      const css = colMap[c];
      return css ? `<span style="color:${css}">${t}</span>` : `<span class="st-text-${c}">${t}</span>`;
    });
    // inline emphasis: **bold** then *italic* (matches the Python side)
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    return s;
  };
  // expose paragraph renderer: one <p> per blank-line-separated block,
  // mirroring the Python-side `_render_paragraphs`.
  window.scRenderParagraphs = function(text) {
    const NL = String.fromCharCode(10);
    const parts = String(text).trim().split(NL + NL).map(p => p.trim()).filter(p => p.length > 0);
    return parts.map(p => '<p>' + window.scRenderMarkup(p) + '</p>').join('');
  };

  // expose button-text renderer: one <p> per blank-line-separated block,
  // mirroring the Python-side `_render_paragraphs`.
  window.scRenderButtonText = function(text) {
    const NL = String.fromCharCode(10);
    const parts = String(text).split(NL + NL).map(p => p.trim()).filter(p => p.length > 0);
    return '<span class="st-btn-text">' + parts.map(p => '<p>' + window.scRenderMarkup(p) + '</p>').join('') + '</span>';
  };
