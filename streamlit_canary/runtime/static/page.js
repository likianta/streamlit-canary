const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'error') { scShowError(msg.message); return; }
    if (msg.type === 'reloading') { scWaitForServer(); return; }
    if (msg.type !== 'patch') return;
    const el = document.querySelector(`[data-id="${msg.id}"]`);
    if (!el) return;
    if (msg.prop === 'text' || msg.prop === 'label') {
      scPatchText(el, msg.value);
    }
    if (msg.prop === 'help') {
      // `help` is reactive: a widget's tooltip may depend on state (e.g. an
      // ON/OFF suffix). Update the markdown carried by whichever element
      // triggers the tooltip (the root itself for buttons, else a glyph).
      const holder = el.hasAttribute('data-help')
        ? el
        : el.querySelector('[data-help]');
      if (holder) {
        if (msg.value) {
          holder.setAttribute('data-help', msg.value);
        } else {
          holder.removeAttribute('data-help');
        }
      }
      window.scHideHelp();
    }
    if (msg.prop === 'enabled') {
      if (el.classList.contains('st-btn')) {
        el.disabled = !msg.value;
      } else if (
        el.classList.contains('st-selectbox') ||
        el.classList.contains('st-radio') ||
        el.classList.contains('st-select-slider') ||
        el.classList.contains('st-multiselect')
      ) {
        // Option widgets: grey out the visual and stop clicks. The selectbox
        // and multiselect triggers are real controls, the rest are div-drawn,
        // so set both the class and the `disabled` attribute.
        el.classList.toggle('is-disabled', !msg.value);
        const trigger = el.querySelector(
          '.st-selectbox-trigger, .st-multiselect-trigger'
        );
        if (trigger) trigger.disabled = !msg.value;
        el.querySelectorAll('input, textarea').forEach(box => {
          box.disabled = !msg.value;
        });
      } else {
        const box = el.querySelector('input, textarea');
        if (box) box.disabled = !msg.value;
      }
    }
    if (msg.prop === 'visible') {
      if (el.classList.contains('st-reveal')) {
        // Server-driven reveal: reuse the expander's height animation.
        scAnimateExpanderBody(el, !!msg.value);
      } else {
        el.hidden = !msg.value;
      }
    }
    if (msg.prop === 'options') {
      if (el.classList.contains('st-selectbox')) {
        // Custom dropdown: rebuild option items + update trigger label.
        const fmt = window.scRenderMarkup;
        const labels = msg.formatted || msg.value.map(x => x);
        scRenderSelectboxOptions(el, msg.value, labels, msg.id);
        const currentVal = el._scValue || msg.value[0];
        const selIdx = msg.value.indexOf(currentVal);
        const valEl = el.querySelector('.st-selectbox-value');
        if (valEl) valEl.innerHTML = selIdx >= 0 ? fmt(labels[selIdx]) : '';
      }
      if (el.classList.contains('st-multiselect')) {
        // Options grew (e.g. new chart results are available): rebuild the
        // list, then re-apply the current selection.
        const labels = msg.formatted || msg.value.map(x => x);
        scRenderMultiselectOptions(el, msg.value, labels);
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
          `<input type="radio" name="radio_${id}" value="${scOptionAttr(o)}" ` +
          `${scOptionKey(o) === scOptionKey(currentVal) ? 'checked' : ''} ` +
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
        // `dataset.value` is always a string while `msg.value` keeps the
        // option's real type (e.g. the int 48), so compare as strings.
        const wanted = String(msg.value);
        optEls.forEach(o => {
          if (o.dataset.value === wanted) {
            o.setAttribute('data-selected', '');
          } else {
            o.removeAttribute('data-selected');
          }
        });
        // Update trigger text from the matching option's inner div.
        const matched = Array.from(optEls).find(o => o.dataset.value === wanted);
        const inner = matched ? matched.querySelector('.st-selectbox-option-inner') : null;
        const valEl = el.querySelector('.st-selectbox-value');
        if (valEl && inner) valEl.textContent = inner.textContent;
      }
      if (el.classList.contains('st-radio')) {
        el._scValue = msg.value;
        // `input.value` is always a string while `msg.value` keeps the
        // option's real type (e.g. the int 48, or the tuple ('f', 'x')), so
        // compare via `scOptionKey` (mirrors the server's `str(o)`).
        const wanted = scOptionKey(msg.value);
        el.querySelectorAll('input').forEach(r => {
          r.checked = (r.value === wanted);
        });
      }
      if (
        el.classList.contains('st-text-input') ||
        el.classList.contains('st-text-area')
      ) {
        const box = el.querySelector('.st-text-input-box, .st-text-area-box');
        // Don't clobber what the user is currently typing.
        if (box && box.value !== msg.value) box.value = msg.value;
      }
      if (el.classList.contains('st-number-input')) {
        const box = el.querySelector('.st-text-input-box');
        const next = (msg.formatted !== undefined) ? msg.formatted : msg.value;
        // Don't clobber what the user is currently typing.
        if (box && box.value !== String(next)) box.value = String(next);
        // The stepper does arithmetic on the raw value, not on the display
        // text (which may be formatted, e.g. hex).
        if (box) box.dataset.value = String(msg.value);
        // Keep the arrows' enabled state in sync with the clamped value.
        if (box) scSyncNumberStepper(box);
      }
      if (
        el.classList.contains('st-checkbox') ||
        el.classList.contains('st-toggle')
      ) {
        const box = el.querySelector('input[type="checkbox"]');
        if (box) box.checked = !!msg.value;
      }
      if (el.classList.contains('st-multiselect')) {
        // `input.value` style comparison does not apply here: the selection
        // is a list, so compare the option values as strings.
        el._scValue = msg.value || [];
        const wanted = el._scValue.map(String);
        el.querySelectorAll('.st-multiselect-option').forEach(o => {
          o.classList.toggle('is-checked', wanted.indexOf(o.dataset.value) >= 0);
        });
        scRefreshMultiselectSummary(el);
      }
      if (el.classList.contains('st-select-slider')) {
        const track = el.querySelector('.st-select-slider-track');
        if (track) {
          const wanted = String(msg.value);
          let idx = 0;
          scSelectSliderOptions(track).forEach((o, i) => {
            if (o.dataset.value === wanted) idx = i;
          });
          scSelectSliderApply(track, idx, false);
        }
      }
      if (el.classList.contains('st-progress')) {
        const bar = el.querySelector('.st-progress-bar');
        if (bar) {
          if (msg.value === null || msg.value === undefined) {
            bar.classList.add('is-indeterminate');
            bar.style.width = '';
          } else {
            bar.classList.remove('is-indeterminate');
            const pct = Math.max(0, Math.min(100, msg.value));
            bar.style.width = pct + '%';
          }
        }
      }
    }
    if (msg.prop === 'chart') {
      if (el.classList.contains('st-altair-chart')) {
        scRenderVegaLite(el, msg.value);
      }
    }
    if (msg.prop === 'rows') {
      if (el.classList.contains('st-table')) {
        const tbody = el.querySelector('tbody');
        const fmt = window.scRenderMarkup;
        tbody.innerHTML = (msg.value || []).map(r =>
          '<tr>' +
          '<th class="st-table-key" scope="row"><p>' + fmt(String(r[0])) +
          '</p></th>' +
          '<td class="st-table-cell"><p>' + fmt(String(r[1])) + '</p></td>' +
          '</tr>'
        ).join('');
      }
    }
    if (
      msg.prop === 'title' ||
      msg.prop === 'caption' ||
      msg.prop === 'footer'
    ) {
      if (el.classList.contains('st-table')) {
        scPatchTableLine(el, msg.prop, msg.value);
      }
    }
    if (msg.prop === 'header') {
      if (el.classList.contains('st-table')) {
        scPatchTableHead(el, msg.value);
      }
    }
    if (msg.prop === 'messages') {
      if (el.classList.contains('st-toast-stack')) {
        scPatchToasts(el, msg.value);
        el.hidden = !(msg.value && msg.value.length);
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
  // Serialize an option value the way the server does (`str(o)`), so a
  // non-scalar option such as the tuple `('f', 'x')` survives the round
  // trip. JSON turns a Python tuple into a JS array whose native toString()
  // is `"f,x"`, which would not match the server-rendered `"('f', 'x')"`
  // (breaking both the checked comparison and the server's `_coerce_value`).
  function scOptionKey(o) {
    if (Array.isArray(o)) {
      return '(' + o
        .map(x => (typeof x === 'string' ? "'" + x + "'" : String(x)))
        .join(', ') + ')';
    }
    return String(o);
  }
  function scOptionAttr(o) {
    return scOptionKey(o).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  }
  // -- Selectbox options rendering -----------------------------------------
  // Shared by the initial render's patch path: rebuilding the dropdown must
  // re-create the "accept_new_options" input row, since `innerHTML` replaces
  // the whole subtree.
  function scNewOptionRow(el) {
    const id = el.dataset.id;
    return (
      '<div class="st-selectbox-new">' +
      `<input class="st-selectbox-new-input" type="text" ` +
      `data-comp-id="${id}" placeholder="Type a new value" ` +
      `oninput="scNewOptionInput(this)" ` +
      `onkeydown="scNewOptionKey(event, this)"/>` +
      `<div class="st-selectbox-newitem" role="option" ` +
      `data-comp-id="${id}" onclick="scAddNewOption(this)" hidden>` +
      '<div class="st-selectbox-option-inner"></div></div></div>'
    );
  }
  function scRenderSelectboxOptions(el, values, labels, id) {
    const dropdown = el.querySelector('.st-selectbox-dropdown');
    if (!dropdown) return;
    const current = el._scValue;
    const fmt = window.scRenderMarkup;
    const items = values.map((o, i) =>
      `<div class="st-selectbox-option" role="option" ` +
      `data-value="${o}" data-comp-id="${id}" ` +
      `onclick="scSelectOption(this)" ` +
      `${o === current ? 'data-selected' : ''}>` +
      `<div class="st-selectbox-option-inner">${fmt(labels[i])}</div></div>`
    ).join('');
    dropdown.innerHTML =
      (el.dataset.acceptNew ? scNewOptionRow(el) : '') + items;
  }
  // -- Selectbox "accept_new_options" input row --
  function scNewOptionInput(input) {
    const row = input.closest('.st-selectbox-new');
    const item = row ? row.querySelector('.st-selectbox-newitem') : null;
    if (!item) return;
    const text = input.value.trim();
    item.hidden = text === '';
    if (text !== '') {
      const inner = item.querySelector('.st-selectbox-option-inner');
      if (inner) inner.textContent = 'Add: "' + text + '"';
    }
  }
  function scNewOptionKey(event, input) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    scAddNewOption(input);
  }
  function scAddNewOption(el) {
    // `el` is the input or the "Add: ..." item; both sit inside the root.
    const root = el.closest('.st-selectbox');
    const input = root ? root.querySelector('.st-selectbox-new-input') : null;
    if (!root || !input) return;
    const text = input.value.trim();
    if (text === '') return;
    ws.send(JSON.stringify({
      type: 'event', id: root.dataset.id, event: 'new_option', value: text,
    }));
    input.value = '';
    // Reset the "Add: ..." row; if the backend rejects the value (e.g. the
    // format function raises), no `options` patch arrives to rebuild it.
    scNewOptionInput(input);
    // Close the dropdown; the incoming `options` / `value` patches refresh it.
    const dropdown = root.querySelector('.st-selectbox-dropdown');
    const trigger = root.querySelector('.st-selectbox-trigger');
    if (dropdown) dropdown.hidden = true;
    if (trigger) trigger.removeAttribute('aria-expanded');
  }
  // -- Expanded-area entry animation --
  // The panels that unfold on click (the selectbox dropdown, the popover panel)
  // are grown by the `...-in` keyframes in page.css, which need a target
  // height: `auto` is not animatable, so it has to be measured. Call this in
  // the same task as the `hidden` flip so the first painted frame already grows
  // towards the right height, and after any placement pass so a panel sized
  // from its surroundings is measured at its final width. `scrollHeight`
  // reports the whole content even while the box is 0 tall, and `max-height`
  // caps tall content (a long option list, a scrolling panel) -- hence the
  // clamp against the computed cap.
  function scMeasureOpenHeight(el, varName) {
    const cap = parseFloat(getComputedStyle(el).maxHeight);
    const height = el.scrollHeight;
    el.style.setProperty(
      varName,
      (Number.isFinite(cap) ? Math.min(height, cap) : height) + 'px',
    );
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
      // The chevron turn (80ms) is quicker than the panel growth (120ms), so
      // the rotation is over before the panel is fully open.
      scMeasureOpenHeight(dropdown, '--st-selectbox-open-height');
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
  // -- Dialog (modal) --
  // Dismissing on the client (✕ / backdrop / Esc) also tells the server, so
  // the `visible` property stays in sync with what the user sees.
  function scCloseDialogEl(backdrop) {
    if (!backdrop || backdrop.hidden) return;
    backdrop.hidden = true;
    ws.send(JSON.stringify({
      type: 'event',
      id: backdrop.dataset.id,
      event: 'close',
    }));
  }
  function scCloseDialog(btn) {
    scCloseDialogEl(btn.closest('.st-dialog-backdrop'));
  }
  function scDialogBackdropClick(event, backdrop) {
    if (event.target === backdrop) scCloseDialogEl(backdrop);
  }
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = Array.from(
      document.querySelectorAll('.st-dialog-backdrop:not([hidden])')
    );
    if (open.length) scCloseDialogEl(open[open.length - 1]);
  });

  // -- Custom multiselect dropdown interaction --
  function scRenderMultiselectOptions(root, values, labels) {
    const dropdown = root.querySelector('.st-multiselect-dropdown');
    if (!dropdown) return;
    const fmt = window.scRenderMarkup;
    const esc = (s) => String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    const wanted = (root._scValue || []).map(String);
    dropdown.innerHTML = values.map((v, i) => {
      const checked = wanted.indexOf(String(v)) >= 0 ? ' is-checked' : '';
      return `<div class="st-multiselect-option${checked}" role="option" ` +
        `data-value="${esc(v)}" data-index="${i}" ` +
        `onclick="scToggleMultiselectOption(this)">` +
        `<span class="st-multiselect-check">✓</span>` +
        `<div class="st-multiselect-option-label">${fmt(labels[i])}</div>` +
        `</div>`;
    }).join('');
    scRefreshMultiselectSummary(root);
  }
  function scCloseMultiselects(except) {
    document.querySelectorAll('.st-multiselect-dropdown:not([hidden])').forEach(d => {
      const root = d.closest('.st-multiselect');
      if (root === except) return;
      d.hidden = true;
      const t = root.querySelector('.st-multiselect-trigger');
      if (t) t.removeAttribute('aria-expanded');
    });
  }
  function scToggleMultiselect(trigger) {
    const root = trigger.closest('.st-multiselect');
    const dropdown = root.querySelector('.st-multiselect-dropdown');
    const isOpen = !dropdown.hidden;
    scCloseMultiselects(root);
    dropdown.hidden = isOpen;
    if (isOpen) trigger.removeAttribute('aria-expanded');
    else trigger.setAttribute('aria-expanded', 'true');
  }
  // The trigger summarises the ticked options, so it is rebuilt from the
  // option labels rather than from any server-provided text.
  function scRefreshMultiselectSummary(root) {
    const valuesEl = root.querySelector('.st-multiselect-values');
    if (!valuesEl) return;
    const labels = Array.prototype.map.call(
      root.querySelectorAll('.st-multiselect-option.is-checked'),
      o => o.querySelector('.st-multiselect-option-label').textContent.trim()
    );
    if (labels.length) {
      valuesEl.textContent = labels.join(', ');
      valuesEl.classList.remove('is-placeholder');
    } else {
      valuesEl.textContent = root.dataset.placeholder || 'Choose an option';
      valuesEl.classList.add('is-placeholder');
    }
  }
  function scToggleMultiselectOption(option) {
    option.classList.toggle('is-checked');
    const root = option.closest('.st-multiselect');
    scRefreshMultiselectSummary(root);
    // The whole selection is sent on every toggle.
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: 'change',
      value: Array.prototype.map.call(
        root.querySelectorAll('.st-multiselect-option.is-checked'),
        o => o.dataset.value
      ),
    }));
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
  // The app content box (page padding excluded). The floating panel is kept
  // inside it, the way Streamlit's floating-ui respects its clipping ancestor,
  // so a wide panel neither sticks out past the page padding nor hugs the
  // window edge.
  function scPopoverBounds() {
    const app = document.querySelector('#app');
    if (!app) {
      const vw = document.documentElement.clientWidth;
      return { left: 16, right: vw - 16 };
    }
    const rect = app.getBoundingClientRect();
    const cs = getComputedStyle(app);
    return {
      left: rect.left + (parseFloat(cs.paddingLeft) || 0),
      right: rect.right - (parseFloat(cs.paddingRight) || 0),
    };
  }
  // Keep the floating panel inside `scPopoverBounds()`: anchor it to the
  // trigger's left edge, but shift it leftward when that would overflow the
  // right edge (and back rightward when it would overflow the left edge).
  function scPositionPopover(panel) {
    panel.style.left = '0px';
    const rect = panel.getBoundingClientRect();
    const bounds = scPopoverBounds();
    let left = 0;
    if (rect.right > bounds.right) {
      left -= rect.right - bounds.right;
    }
    if (rect.left + left < bounds.left) {
      left += bounds.left - (rect.left + left);
    }
    panel.style.left = left + 'px';
  }
  // Row-aligned panel: span from the surrounding row's text input's left
  // edge to the row's right edge (offsets are relative to the popover,
  // which is the panel's positioned ancestor).
  function scAlignPopoverToRow(panel) {
    const pop = panel.closest('.st-popover');
    const row = pop ? pop.closest('.st-row') : null;
    if (!row) return;
    const input = row.querySelector('.st-text-input');
    const popRect = pop.getBoundingClientRect();
    const rowRect = row.getBoundingClientRect();
    const start = input
      ? input.getBoundingClientRect().left
      : rowRect.left;
    panel.style.left = (start - popRect.left) + 'px';
    panel.style.width = (rowRect.right - start) + 'px';
  }
  // The trigger's chevron is an icon-font glyph that Streamlit *swaps* when
  // the panel opens (`expand_more` <-> `expand_less`), rather than rotating.
  function scSwapChevron(host, selector, closed, open, isOpen) {
    const glyph = host.querySelector(selector);
    if (glyph) glyph.textContent = isOpen ? open : closed;
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
      if (panel.classList.contains('st-popover-panel--row')) {
        scAlignPopoverToRow(panel);
      } else {
        scPositionPopover(panel);
      }
      // Measured after the placement pass, so a row-aligned panel is sized
      // from its final width. The chevron is swapped, not animated.
      scMeasureOpenHeight(panel, '--st-popover-open-height');
    }
    scSwapChevron(
      trigger, '.st-popover-chevron', 'expand_more', 'expand_less', !isOpen
    );
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
    if (!e.target.closest('.st-multiselect')) {
      scCloseMultiselects(null);
    }
  });
  // Close popovers on Escape.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') scClosePopovers(null);
  });
  // Keep an open row-aligned panel in sync with its row on resize.
  window.addEventListener('resize', () => {
    document.querySelectorAll('.st-popover-panel--row:not([hidden])')
      .forEach(scAlignPopoverToRow);
  });
  // -- Markdown ----------------------------------------------------------
  // Streamlit parses markdown in the browser (react-markdown); we mirror
  // that with the bundled markdown-it. The server only ships the *source*
  // in `data-md` placeholders, which `scRenderMarkdown()` fills on load and
  // the delta handlers replace in place afterwards.
  const scMd = window.markdownit({ linkify: true });
  // Streamlit's own inline extensions: `:material/<name>:` and `:color[..]`.
  // Streamlit renders the `:color[..]` extension with the theme's
  // `--st-<name>-text-color`, so read that instead of hardcoding -- it is
  // what makes the coloured text follow the light / dark theme.
  function scThemeColor(name, fallback) {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue('--st-' + name + '-text-color').trim();
    return value || fallback;
  }
  // Read once per theme: the toolbar rebuilds this when the theme switches,
  // so `:color[..]` spans follow the palette instead of freezing the one that
  // was live when the page loaded.
  function scBuildColors() {
    return {
      red: scThemeColor('red', '#ff6c6c'),
      orange: scThemeColor('orange', '#ffbd45'),
      yellow: scThemeColor('yellow', '#ffffc2'),
      blue: scThemeColor('blue', '#3d9df3'),
      green: scThemeColor('green', '#5ce488'),
      violet: scThemeColor('violet', '#b27eff'),
      gray: scThemeColor('gray', 'rgba(250, 250, 250, 0.4)'),
      grey: scThemeColor('gray', 'rgba(250, 250, 250, 0.4)'),
      rainbow: null
    };
  }
  let scColors = scBuildColors();
  function scColorOpen(color) {
    const css = scColors[color];
    if (css === null) {
      return '<span class="st-text-rainbow">';
    }
    return css
      ? '<span style="color:' + css + '">'
      : '<span class="st-text-' + color + '">';
  }
  // Inline rules (rather than a post-pass) so the extensions never fire
  // inside code spans / fenced blocks.
  scMd.inline.ruler.before('emphasis', 'st_markup', function (state, silent) {
    const rest = state.src.slice(state.pos);
    // The name is `\w+` (letters, digits, underscore), as in Streamlit --
    // e.g. `:material/settings_backup_restore:` or `:material/360:`.
    let m = /^:material\/(\w+):/.exec(rest);
    if (m !== null) {
      if (!silent) {
        const token = state.push('st_material', '', 0);
        token.meta = { name: m[1] };
      }
      state.pos += m[0].length;
      return true;
    }
    m = /^:([a-zA-Z]+)\[([^\]]*)\]/.exec(rest);
    if (m === null) {
      return false;
    }
    if (!silent) {
      const open = state.push('st_color_open', '', 1);
      open.meta = { color: m[1] };
      // The wrapped text is markdown itself, e.g. `:blue[**Connect**]`.
      state.md.inline.parse(m[2], state.md, state.env, state.tokens);
      state.push('st_color_close', '', -1);
    }
    state.pos += m[0].length;
    return true;
  });
  scMd.renderer.rules.st_material = function (tokens, idx) {
    // Ship the icon *name* and let the Material Symbols font's ligature draw
    // it -- the same thing Streamlit does, so the glyph matches. `translate`
    // is off to keep browser translators away from the name.
    return '<span class="st-icon" translate="no">'
      + tokens[idx].meta.name + '</span>';
  };
  scMd.renderer.rules.st_color_open = function (tokens, idx) {
    return scColorOpen(tokens[idx].meta.color);
  };
  scMd.renderer.rules.st_color_close = function () {
    return '</span>';
  };
  // Streamlit's typographer (a remark plugin in StreamlitMarkdown): a few
  // ASCII combos become symbols, but only when whitespace-anchored and
  // never inside link text -- e.g. `a -> b` renders as `a → b` while
  // `a->b` is left alone.
  const scTypographer = [
    [/(^|\s)<->(\s|$)/g, '$1↔$2'],
    [/(^|\s)->(\s|$)/g, '$1→$2'],
    [/(^|\s)<-(\s|$)/g, '$1←$2'],
    [/(^|\s)--(\s|$)/g, '$1—$2'],
    [/(^|\s)>=(\s|$)/g, '$1≥$2'],
    [/(^|\s)<=(\s|$)/g, '$1≤$2'],
    [/(^|\s)~=(\s|$)/g, '$1≈$2']
  ];
  scMd.core.ruler.after('inline', 'st_typographer', function (state) {
    state.tokens.forEach(function (block) {
      if (block.type !== 'inline' || !block.children) return;
      const children = block.children;
      let linkDepth = 0;
      let i = 0;
      while (i < children.length) {
        const token = children[i];
        if (token.type === 'link_open') { linkDepth++; i++; continue; }
        if (token.type === 'link_close') { linkDepth--; i++; continue; }
        if (token.type !== 'text' || linkDepth > 0) { i++; continue; }
        // markdown-it splits text at chars like `-` and `>`, so join the
        // run of adjacent text tokens before applying the patterns.
        let j = i + 1;
        while (j < children.length && children[j].type === 'text') j++;
        const value = children
          .slice(i, j)
          .map(function (t) { return t.content; })
          .join('');
        let next = value;
        scTypographer.forEach(function (pair) {
          next = next.replace(pair[0], pair[1]);
        });
        if (next === value) {
          i = j;
          continue;
        }
        const merged = new state.Token('text', '', 0);
        merged.content = next;
        children.splice(i, j - i, merged);
        i++;
      }
    });
  });
  // Raw renderers (no holder): used when filling an existing `.st-md`
  // placeholder in place.
  function scMdInline(text) { return scMd.renderInline(String(text)); }
  function scMdBlock(text) { return scMd.render(String(text)).trim(); }
  // Public renderers return standalone markup *including* the `.st-md`
  // holder, because callers assign the result via `innerHTML`; the holder is
  // what the markdown styles in page.css are scoped to.
  window.scRenderMarkup = function (text) {
    return '<span class="st-md">' + scMdInline(text) + '</span>';
  };
  window.scRenderParagraphs = function (text) {
    return '<div class="st-md st-md-block">' + scMdBlock(text) + '</div>';
  };
  // Fill every server-emitted `data-md` placeholder under `root`.
  function scRenderMarkdown(root) {
    (root || document).querySelectorAll('.st-md[data-md]').forEach((el) => {
      const src = el.getAttribute('data-md') || '';
      el.innerHTML = el.classList.contains('st-md-block')
        ? scMdBlock(src)
        : scMdInline(src);
    });
  }
  // Find the markdown holder of an element: the placeholder itself, or a
  // *direct* child placeholder (keeps sibling content such as the help
  // glyph intact).
  function scMarkdownHolder(el) {
    if (el.classList.contains('st-md')) return el;
    return el.querySelector(':scope > .st-md');
  }
  // Render `value` into the markdown holder of `el` (inline or block,
  // whichever the server used), falling back to `el` itself.
  function scSetMarkdown(el, value) {
    if (!el) return;
    const holder = scMarkdownHolder(el);
    const target = holder || el;
    if (holder) holder.setAttribute('data-md', String(value));
    target.innerHTML =
      holder && holder.classList.contains('st-md-block')
        ? scMdBlock(value)
        : scMdInline(value);
  }
  // Route a `text` / `label` delta to the element that holds the markdown.
  function scPatchText(el, value) {
    if (
      el.classList.contains('st-selectbox') ||
      el.classList.contains('st-radio')
    ) {
      scSetMarkdown(el.querySelector('.st-widget-label'), value);
    } else if (el.classList.contains('st-btn')) {
      scSetMarkdown(el.querySelector('.st-btn-text') || el, value);
    } else if (el.classList.contains('st-spinner')) {
      scSetMarkdown(el.querySelector('.st-spinner-text'), value);
    } else if (el.classList.contains('st-code')) {
      const codeEl = el.querySelector('code');
      if (codeEl) codeEl.textContent = value;
    } else if (el.classList.contains('st-alert')) {
      scSetMarkdown(el.querySelector('.st-alert-text'), value);
    } else if (el.classList.contains('st-popover')) {
      scSetMarkdown(el.querySelector('.st-popover-trigger-label'), value);
    } else if (el.classList.contains('st-progress')) {
      scSetMarkdown(el.querySelector('.st-progress-text'), value);
    } else {
      scSetMarkdown(el, value);
    }
  }
  // Route a Table extra (`title` / `caption` / `footer`) delta. An emptied
  // line is dropped, mirroring what the server would have rendered.
  function scPatchTableLine(el, kind, value) {
    let line = el.querySelector(':scope > .st-table-' + kind);
    if (!String(value)) {
      if (line) line.remove();
      return;
    }
    if (!line) {
      line = document.createElement('div');
      line.className = 'st-table-' + kind;
      const holder = document.createElement('span');
      holder.className = 'st-md';
      line.appendChild(holder);
      if (kind === 'footer') {
        el.appendChild(line);
      } else {
        el.insertBefore(line, el.querySelector('.st-table-scroll'));
      }
    }
    scSetMarkdown(line, value);
  }
  // Rebuild a Table's optional column-label row.
  function scPatchTableHead(el, value) {
    const table = el.querySelector('.st-table-table');
    if (!table) return;
    let head = table.querySelector(':scope > thead');
    if (!value) {
      if (head) head.remove();
      return;
    }
    if (!head) {
      head = document.createElement('thead');
      table.insertBefore(head, table.firstChild);
    }
    head.className = 'st-table-head';
    const fmt = window.scRenderMarkup;
    head.innerHTML =
      '<tr>' +
      value.map((label, i) => (
        '<th class="' + (i === 0 ? 'st-table-key' : 'st-table-cell') + '">' +
        fmt(String(label)) + '</th>'
      )).join('') +
      '</tr>';
  }

  // -- Toast stack (canary-only) ----------------------------------------
  // Server-side twin of `_toast_item` in render.py: keep the markup identical
  // so a patched-in toast is indistinguishable from a server-rendered one.
  function scToastHtml(m) {
    const fmt = window.scRenderMarkup;
    const icon = m.icon
      ? '<span class="st-toast-icon">' + fmt(m.icon) + '</span>'
      : '';
    return (
      icon +
      '<span class="st-toast-body">' + fmt(String(m.text)) + '</span>' +
      '<button type="button" class="st-toast-close" aria-label="Dismiss"' +
      ' onclick="scDismissToast(this)">\u2715</button>'
    );
  }
  // Arm a toast's auto-dismiss countdown from its `data-duration` (seconds).
  // The attribute is absent for an "infinite" toast, which stays put until the
  // user dismisses it. Hovering the stack pauses every countdown so a message
  // can be read (mirrors `st.toast`).
  function scToastArm(node) {
    scToastDisarm(node);
    const raw = node.dataset.duration;
    if (!raw) return;
    const ms = Number(raw) * 1000;
    node._scRemaining = ms;
    node._scStartedAt = Date.now();
    node._scTimer = setTimeout(() => scToastExpire(node), ms);
  }
  function scToastDisarm(node) {
    if (node._scTimer) clearTimeout(node._scTimer);
    node._scTimer = null;
  }
  function scToastPause(node) {
    if (!node._scTimer) return;
    const elapsed = Date.now() - node._scStartedAt;
    scToastDisarm(node);
    node._scRemaining = Math.max(0, node._scRemaining - elapsed);
  }
  function scToastResume(node) {
    if (node._scTimer || node._scRemaining === undefined) return;
    node._scStartedAt = Date.now();
    node._scTimer = setTimeout(() => scToastExpire(node), node._scRemaining);
  }
  function scToastExpire(node) {
    scToastDisarm(node);
    scToastDismissNode(node);
  }
  // Drop one toast: tell the server, which removes it from `messages` and
  // patches the stack back.
  function scToastDismissNode(node) {
    const stack = node.closest('.st-toast-stack');
    if (!stack) return;
    ws.send(JSON.stringify({
      type: 'event', id: stack.dataset.id, event: 'dismiss',
      value: node.dataset.id,
    }));
  }
  function scToastListen(el) {
    if (el.dataset.armed) return;
    el.dataset.armed = '1';
    el.addEventListener('mouseenter', () => {
      el.querySelectorAll('.st-toast').forEach(scToastPause);
    });
    el.addEventListener('mouseleave', () => {
      el.querySelectorAll('.st-toast').forEach(scToastResume);
    });
  }
  // Arm the toasts the server rendered on the initial page; the ones that
  // arrive later are armed by `scPatchToasts` as they are appended.
  function scArmToasts(el) {
    scToastListen(el);
    el.querySelectorAll('.st-toast').forEach(scToastArm);
  }
  // Reconcile the stack with the server's `messages` list, keyed by each
  // toast's stable id: append the new ones (a freshly created node plays the
  // CSS entrance animation), drop the ones the server no longer lists, and
  // rewrite a node only when its message really changed -- so an append never
  // resets the spread transition already in flight.
  function scPatchToasts(el, messages) {
    const list = messages || [];
    const seen = new Set();
    const byId = new Map();
    scToastListen(el);
    Array.from(el.children).forEach((c) => {
      if (c.classList.contains('st-toast')) byId.set(c.dataset.id, c);
    });
    list.forEach((m) => {
      const id = String(m.id);
      seen.add(id);
      let node = byId.get(id);
      if (!node) {
        node = document.createElement('div');
        node.className = 'st-toast';
        node.dataset.id = id;
        el.appendChild(node);
      }
      const sig = JSON.stringify(m);
      if (node.dataset.sig !== sig) {
        node.dataset.sig = sig;
        if (m.duration) node.dataset.duration = String(m.duration);
        else delete node.dataset.duration;
        node.innerHTML = scToastHtml(m);
        scToastArm(node);
      }
    });
    byId.forEach((node, id) => {
      if (!seen.has(id) && node.parentNode) {
        scToastDisarm(node);
        node.parentNode.removeChild(node);
      }
    });
  }
  function scDismissToast(btn) {
    const node = btn.closest('.st-toast');
    if (node) scToastDismissNode(node);
  }

  // -- Tabs / Expander / NumberInput stepper (client-side UI state) --
  function scSelectTab(btn) {
    const root = btn.closest('.st-tabs');
    if (!root) return;
    const label = btn.dataset.tab;
    const bar = root.querySelector('.st-tabs-bar');
    const previous = bar ? bar.querySelector('.st-tab.is-active') : null;
    // Scope to *this* tab group. The selectors below are descendant
    // selectors, so without the guard they would also match a nested
    // `Tabs` (e.g. one inside a popover in a panel), clearing its active
    // tab and hiding all of its panels.
    root.querySelectorAll('.st-tabs-bar > .st-tab').forEach(b => {
      if (b.closest('.st-tabs') !== root) return;
      const on = b === btn;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    root.querySelectorAll('.st-tabs-panels > .st-tab-panel').forEach(p => {
      if (p.closest('.st-tabs') !== root) return;
      p.hidden = p.dataset.tab !== label;
    });
    if (previous && previous !== btn) {
      scSlideTabIndicator(root, previous, btn);
    } else {
      scSyncTabIndicator(root);
    }
    // Keep the server-side `active` property in sync.
    const id = root.dataset.id;
    if (id) {
      ws.send(JSON.stringify({
        type: 'event', id: id, event: 'change', value: label,
      }));
    }
  }
  // Move the underline from one tab to another the way a sticky one moves: it
  // stretches until it spans both tabs, then contracts onto the new one, so
  // the trailing edge looks like it is being dragged along. Measured from the
  // tabs themselves rather than from the underline, so a switch mid-animation
  // still starts from a real tab. `scSyncTabIndicator` runs at the end both to
  // park the underline and to hand the geometry back to the inline style.
  function scSlideTabIndicator(root, from, to) {
    const bar = root.querySelector('.st-tabs-bar');
    const indicator = bar ? bar.querySelector('.st-tabs-indicator') : null;
    if (!indicator) return;
    const fromLeft = from.offsetLeft;
    const toLeft = to.offsetLeft;
    const fromWidth = from.offsetWidth;
    const toWidth = to.offsetWidth;
    // Spanning the union of both tabs is what makes the *leading* edge move
    // first and leaves the trailing edge behind, whichever way the switch
    // goes; hopping over a middle tab stretches across it, as Streamlit's
    // underline does.
    const stretchLeft = Math.min(fromLeft, toLeft);
    const stretchWidth =
      Math.max(fromLeft + fromWidth, toLeft + toWidth) - stretchLeft;
    const at = x => 'translateX(' + x + 'px)';
    if (indicator._scSlideAnim) indicator._scSlideAnim.cancel();
    // Both halves ease out (a quadratic curve: fastest right after the click,
    // settling at the end), which is what gives the line its dragged feel. The
    // duration matches Streamlit's plain slide.
    indicator._scSlideAnim = indicator.animate([
      { transform: at(fromLeft), width: fromWidth + 'px' },
      {
        transform: at(stretchLeft),
        width: stretchWidth + 'px',
        offset: 0.5,
      },
      { transform: at(toLeft), width: toWidth + 'px' },
    ], { duration: 200, easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)' });
    indicator._scSlideAnim.addEventListener('finish', () => {
      indicator._scSlideAnim = null;
      scSyncTabIndicator(root);
    });
  }
  // Park the bar's single underline under the active tab. `offsetLeft` is
  // measured against the offset parent, which is the bar (it is positioned),
  // so the width and the offset share one origin. This places the underline
  // without animating it, which is what a resize or a first paint wants.
  function scSyncTabIndicator(root) {
    const bar = root.querySelector('.st-tabs-bar');
    const indicator = bar ? bar.querySelector('.st-tabs-indicator') : null;
    const active = bar ? bar.querySelector('.st-tab.is-active') : null;
    if (!indicator || !active) return;
    indicator.style.width = active.offsetWidth + 'px';
    indicator.style.transform = 'translateX(' + active.offsetLeft + 'px)';
  }
  function scObserveTabs(root) {
    const bar = root.querySelector('.st-tabs-bar');
    if (!bar) return;
    // The bar measures 0 while its tabs sit inside something hidden -- a
    // popover, a dialog, an inactive tab panel -- so the underline has to be
    // re-placed whenever the bar's box changes. Observing the box covers that
    // as well as a window resize and the webfont landing.
    new ResizeObserver(() => scSyncTabIndicator(root)).observe(bar);
    scSyncTabIndicator(root);
  }
  function scToggleExpander(header) {
    const root = header.closest('.st-expander');
    if (!root) return;
    const expanded = !root.classList.contains('is-expanded');
    root.classList.toggle('is-expanded', expanded);
    header.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const body = root.querySelector('.st-expander-body');
    if (body) scAnimateExpanderBody(body, expanded);
    scSwapChevron(
      header, '.st-expander-icon',
      'keyboard_arrow_right', 'keyboard_arrow_down', expanded
    );
  }
  // Expand/collapse the body with a height animation. `hidden` still drives
  // the server-rendered state; while animating the height is set explicitly
  // and the overflow is clipped (so a dropdown inside is not cut off once
  // the transition is over).
  function scAnimateExpanderBody(body, expanded) {
    if (body._scExpandAnim) body._scExpandAnim.cancel();
    const from = body.hidden ? 0 : body.getBoundingClientRect().height;
    body.hidden = false;
    const to = expanded ? body.scrollHeight : 0;
    if (from === to) {
      body.hidden = !expanded;
      body.style.height = '';
      return;
    }
    body.style.height = from + 'px';
    body.style.overflow = 'hidden';
    body._scExpandAnim = body.animate(
      { height: [from + 'px', to + 'px'] },
      { duration: 200, easing: 'ease' }
    );
    body._scExpandAnim.addEventListener('finish', () => {
      body._scExpandAnim = null;
      body.style.height = '';
      body.style.overflow = '';
      body.hidden = !expanded;
    });
  }
  // Enable/disable the stepper arrows from the current value, mirroring
  // Streamlit: sitting on a bound disables the arrow pointing out of it.
  function scSyncNumberStepper(input) {
    const box = input.closest('.st-number-box');
    if (!box) return;
    // Markup order is [decrease, increase].
    const steps = box.querySelectorAll('.st-number-step');
    if (steps.length < 2) return;
    const value = parseFloat(input.dataset.value);
    if (!isFinite(value)) return;
    const min = input.dataset.min;
    const max = input.dataset.max;
    steps[0].disabled =
      min !== undefined && min !== '' && value <= parseFloat(min);
    steps[1].disabled =
      max !== undefined && max !== '' && value >= parseFloat(max);
  }

  function scStepNumber(btn, direction) {
    const box = btn.closest('.st-number-box');
    const input = box ? box.querySelector('input') : null;
    if (!input) return;
    const step = parseFloat(input.dataset.step);
    const current = parseFloat(input.dataset.value);
    if (!isFinite(step) || !isFinite(current)) return;
    let value = current + direction * step;
    const min = input.dataset.min;
    const max = input.dataset.max;
    if (min !== undefined && min !== '' && value < parseFloat(min)) {
      value = parseFloat(min);
    }
    if (max !== undefined && max !== '' && value > parseFloat(max)) {
      value = parseFloat(max);
    }
    // Trim the float noise a step like 0.1 introduces.
    const decimals = (String(step).split('.')[1] || '').length;
    const text = decimals ? value.toFixed(decimals) : String(value);
    input.dataset.value = text;
    input.value = text;
    scSyncNumberStepper(input);
    scSendChange(input);
  }

  // -- SelectSlider: pick the option nearest the pointer (click or drag) --
  // The options themselves are hidden; only their values and labels matter
  // (see `.st-select-slider-options`).
  function scSelectSliderOptions(track) {
    return Array.from(track.querySelectorAll('.st-select-slider-option'));
  }
  function scSelectSliderNearest(track, clientX) {
    const rail = track.querySelector('.st-select-slider-rail');
    const n = scSelectSliderOptions(track).length;
    if (!rail || n <= 1) return 0;
    const rect = rail.getBoundingClientRect();
    if (!rect.width) return 0;
    const ratio = (clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
  }
  // Move the fill, the thumb and the value label onto `index`. The label is
  // centred on the thumb, then nudged back inside the widget so it does not
  // spill out at either end (as `st.select_slider` does). Nothing is committed
  // until `commit` is set.
  function scSelectSliderApply(track, index, commit) {
    const options = scSelectSliderOptions(track);
    const n = options.length;
    const pct = n <= 1 ? 0 : (index / (n - 1)) * 100;
    track.dataset.index = String(index);
    const fill = track.querySelector('.st-select-slider-fill');
    if (fill) fill.style.width = pct + '%';
    const thumb = track.querySelector('.st-select-slider-thumb');
    if (thumb) thumb.style.left = pct + '%';
    const root = track.closest('.st-select-slider');
    const label = root ? root.querySelector('.st-select-slider-value') : null;
    if (label && options[index]) {
      label.innerHTML = options[index].innerHTML;
      scSelectSliderPlace(track, label, pct);
    }
    if (!commit) return;
    const id = track.dataset.compId;
    const value = options[index] ? options[index].dataset.value : null;
    if (id && value !== null) {
      ws.send(JSON.stringify({
        type: 'event', id: id, event: 'change', value: value,
      }));
    }
  }
  function scSelectSliderPlace(track, label, pct) {
    const rail = track.querySelector('.st-select-slider-rail');
    if (!rail) return;
    const railRect = rail.getBoundingClientRect();
    const trackRect = track.getBoundingClientRect();
    const half = label.offsetWidth / 2;
    const x = railRect.left - trackRect.left + (pct / 100) * railRect.width;
    label.style.left =
      Math.max(half, Math.min(x, trackRect.width - half)) + 'px';
  }
  function scSelectSliderStart(ev, track) {
    ev.preventDefault();
    track._scIndex = scSelectSliderNearest(track, ev.clientX);
    scSelectSliderApply(track, track._scIndex, false);
    const move = (e) => {
      const idx = scSelectSliderNearest(track, e.clientX);
      if (idx !== track._scIndex) {
        track._scIndex = idx;
        scSelectSliderApply(track, idx, false);
      }
    };
    const up = () => {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      // A mouse press is always followed by `click`; flag it so the click
      // handler does not commit the same change a second time.
      track._scDragCommitted = true;
      scSelectSliderApply(track, track._scIndex, true);
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }
  // A plain click (no press, e.g. a synthetic `.click()`) still selects.
  function scSelectSliderClick(ev, track) {
    if (track._scDragCommitted) {
      track._scDragCommitted = false;
      return;
    }
    scSelectSliderApply(
      track, scSelectSliderNearest(track, ev.clientX), true
    );
  }

  // -- AltairChart: draw Vega-Lite specs with vega-embed (lazy CDN load) --
  // `vega`, `vega-lite` and `vega-embed` are pulled in on first use and
  // cached for the lifetime of the page. vega-embed expects both globals to
  // be present, so the scripts are loaded in order.
  const SC_VEGA_URLS = [
    'https://cdn.jsdelivr.net/npm/vega@6',
    'https://cdn.jsdelivr.net/npm/vega-lite@6',
    'https://cdn.jsdelivr.net/npm/vega-embed@7',
  ];
  let scVegaEmbedPromise = null;
  function scLoadVega() {
    if (scVegaEmbedPromise) return scVegaEmbedPromise;
    const loadScript = (src) => new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.async = false;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('failed to load ' + src));
      document.head.appendChild(s);
    });
    scVegaEmbedPromise = SC_VEGA_URLS
      .reduce((p, src) => p.then(() => loadScript(src)), Promise.resolve())
      .then(() => (typeof window.vegaEmbed === 'function' ? window.vegaEmbed : null))
      .catch(() => null);
    return scVegaEmbedPromise;
  }
  // Vega-Lite's built-in config is light. Feed it the app's theme tokens so
  // the chart follows the page (dark chart on a dark page), the way
  // Streamlit's `st.altair_chart` does.
  function scVegaThemeConfig() {
    const css = getComputedStyle(document.documentElement);
    const token = (name, fallback) => {
      const value = css.getPropertyValue(name).trim();
      return value || fallback;
    };
    const background = token('--st-background-color', '#ffffff');
    const axisColor = token('--st-heading-color', '#1f2328');
    const gridColor = token('--st-border-color', '#d0d7de');
    const titleColor = token('--st-text-color', '#1f2328');
    return {
      background,
      axis: {
        labelColor: axisColor,
        titleColor: axisColor,
        domainColor: gridColor,
        tickColor: gridColor,
        gridColor,
        labelFontSize: 12,
        titleFontSize: 14,
      },
      legend: { labelColor: axisColor, titleColor: axisColor },
      title: { color: titleColor, fontSize: 14, fontWeight: 'bold' },
    };
  }
  function scRenderVegaLite(el, spec) {
    const canvas = el.querySelector('.st-altair-canvas');
    if (!canvas) return;
    if (!spec) {
      canvas.innerHTML = '';
      el.removeAttribute('data-sc-rendered');
      return;
    }
    scLoadVega().then((embed) => {
      if (!embed) return;
      // vega-embed replaces the container's content; a stale render is
      // discarded so rapid `chart` patches don't interleave.
      embed(canvas, spec, {
        actions: false,
        config: scVegaThemeConfig(),
        renderer: 'svg',
      })
        .then(() => { el.setAttribute('data-sc-rendered', '1'); })
        .catch(() => {});
    });
  }
  function scInitAltairCharts() {
    document.querySelectorAll('.st-altair-chart').forEach((el) => {
      if (el.dataset.scInitialized) return;
      el.dataset.scInitialized = '1';
      const script = el.querySelector('.st-altair-spec');
      if (!script) return;
      try {
        scRenderVegaLite(el, JSON.parse(script.textContent));
      } catch (e) {}
    });
  }

  // -- Source-change notice (kept, no longer wired up) -------------------
  // TODO or DELETE: file watcher & reload banner needs to be refactored or
  // be deleted. Nothing calls these any more: the server stops watching its
  // source files, and a rerun is a manual action from the toolbar.
  function scRerunToast() {
    let el = document.getElementById('sc-rerun-toast');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-rerun-toast';
    el.className = 'st-rerun-toast';
    el.hidden = true;
    el.innerHTML =
      '<span class="st-rerun-icon">\u21bb</span>' +
      '<span class="st-rerun-body">' +
      '<span class="st-rerun-title">Source file changed</span>' +
      '<span class="st-rerun-detail"></span></span>' +
      '<button class="st-rerun-btn" type="button" ' +
      'onclick="scRerun()">Rerun</button>' +
      '<button class="st-rerun-close" type="button" title="Dismiss" ' +
      'onclick="scDismissRerun()">\u2715</button>';
    document.body.appendChild(el);
    return el;
  }
  // The notice is `position: fixed`, so the body reserves top padding while
  // it is visible (see `body.sc-rerun-visible` in page.css) to keep it from
  // covering the app.
  function scSetRerunVisible(visible) {
    const el = scRerunToast();
    el.hidden = !visible;
    document.body.classList.toggle('sc-rerun-visible', !!visible);
  }
  function scShowRerunToast(files) {
    const el = scRerunToast();
    if (!files.length) { scSetRerunVisible(false); return; }
    el.querySelector('.st-rerun-title').textContent = 'Source file changed';
    el.querySelector('.st-rerun-detail').textContent =
      files.length === 1 ? files[0] : files.length + ' files changed';
    el.classList.remove('is-reloading');
    el.querySelector('.st-rerun-btn').disabled = false;
    scSetRerunVisible(true);
  }
  function scDismissRerun() {
    // Client-side only: the pending change stays known to the server, so
    // reloading the page (or editing again) brings the notice back and the
    // rerun stays reachable.
    scSetRerunVisible(false);
  }
  function scRerun(onTimeout) {
    try { ws.send(JSON.stringify({ type: 'rerun' })); } catch (e) {}
    scWaitForServer(onTimeout);
  }
  // A rerun re-executes the server process (see reload.py); poll until it
  // answers again, then reload the page so the fresh render is picked up.
  // The caller owns the "waiting" feedback -- the toolbar and the exception
  // panel each label their own Rerun button -- and learns from `onTimeout`
  // that the process never came back.
  let scServerPending = false;
  function scWaitForServer(onTimeout) {
    if (scServerPending) return;
    scServerPending = true;
    let tries = 0;
    const poll = () => {
      tries += 1;
      fetch('/healthz?_=' + Date.now(), { cache: 'no-store' })
        .then(r => { if (!r.ok) throw new Error('not ready'); location.reload(); })
        .catch(() => {
          if (tries < 50) { setTimeout(poll, 400); return; }
          scServerPending = false;
          if (onTimeout) onTimeout();
        });
    };
    setTimeout(poll, 400);
  }

  // -- Uncaught exception panel ------------------------------------------
  // A handler that raises is caught by the runtime and arrives here as one
  // `traceback.format_exception` string (see `Runtime._report_error`).
  // Unlike a rerun-based app, the tree survives the error, so the panel has
  // nothing to repair -- it only has to be visible and dismissable. Its
  // Rerun button restarts the process, exactly like the source-change
  // notice, which is what "ignore this error and run again" needs.
  function scErrorPanel() {
    let el = document.getElementById('sc-error-panel');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-error-panel';
    el.className = 'st-error-panel';
    el.hidden = true;
    // Streamlit titles its exception box with the error's last line and
    // keeps the whole traceback underneath, which is what we mirror.
    el.innerHTML =
      '<span class="st-error-head">' +
      '<span class="st-error-title"></span>' +
      '<button class="st-rerun-close" type="button" title="Dismiss" ' +
      'onclick="scDismissError()">\u2715</button></span>' +
      '<pre class="st-error-body"></pre>' +
      '<div class="st-error-actions">' +
      // same button as the source-change notice, hence the shared class
      '<button class="st-rerun-btn" type="button" ' +
      'onclick="scSendErrorRerun()">Rerun</button></div>';
    document.body.appendChild(el);
    return el;
  }
  function scShowError(message) {
    const el = scErrorPanel();
    const text = String(message == null ? '' : message).replace(/\s+$/, '');
    const lines = text.split('\n');
    el.querySelector('.st-error-title').textContent =
      lines[lines.length - 1] || 'Uncaught exception';
    el.querySelector('.st-error-body').textContent = text;
    const btn = el.querySelector('.st-rerun-btn');
    btn.textContent = 'Rerun';
    btn.disabled = false;
    el.hidden = false;
  }
  // The panel floats over the app, and the app stays usable after an error,
  // so it must be possible to get it out of the way without restarting the
  // process (dismissing only hides it; the next error brings it back).
  function scDismissError() {
    scErrorPanel().hidden = true;
  }
  function scSendErrorRerun() {
    const btn = scErrorPanel().querySelector('.st-rerun-btn');
    btn.disabled = true;
    btn.textContent = 'Reloading\u2026';
    scRerun(() => { btn.textContent = 'Server did not come back'; });
  }

  // -- Developer toolbar: the ⋮ menu (theme + rerun) ---------------------
  // A cut-down version of Streamlit's main menu. There is no source-file
  // watcher any more (see the note above), so Rerun is how a developer picks
  // up a code change -- and the theme switch needs no round trip, since the
  // page carries both palettes (see `_THEMES_CSS` in render.py).
  const scThemeMq = matchMedia('(prefers-color-scheme: dark)');
  const scThemeChoices = [
    ['system', 'System'],
    ['light', 'Light'],
    ['dark', 'Dark']
  ];
  function scThemePref() {
    return document.documentElement.dataset.themePref || 'dark';
  }
  function scToolbar() {
    let el = document.getElementById('sc-toolbar');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-toolbar';
    el.className = 'st-toolbar';
    el.innerHTML =
      '<button class="st-toolbar-btn" type="button" title="Menu"' +
      ' aria-label="Menu" aria-haspopup="true" aria-expanded="false"' +
      ' onclick="scToggleMenu()">\u22ee</button>' +
      '<div class="st-menu" role="menu" hidden>' +
      '<div class="st-menu-title">Theme</div>' +
      scThemeChoices.map((choice) =>
        `<label class="st-menu-item">` +
        `<input type="radio" name="sc-theme" value="${choice[0]}"` +
        ` onchange="scPickTheme(this)"/>` +
        `<span>${choice[1]}</span></label>`
      ).join('') +
      '<div class="st-menu-sep"></div>' +
      '<button class="st-menu-item st-menu-action" type="button"' +
      ' role="menuitem" onclick="scMenuRerun(this)">Rerun</button>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }
  function scSyncThemeRadios() {
    const pref = scThemePref();
    scToolbar().querySelectorAll('input[name="sc-theme"]').forEach((box) => {
      box.checked = box.value === pref;
    });
  }
  function scToggleMenu() {
    const menu = scToolbar().querySelector('.st-menu');
    const open = menu.hidden;
    menu.hidden = !open;
    scToolbar().querySelector('.st-toolbar-btn')
      .setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) scSyncThemeRadios();
  }
  function scCloseMenu() {
    const bar = document.getElementById('sc-toolbar');
    if (!bar) return;
    const menu = bar.querySelector('.st-menu');
    if (menu.hidden) return;
    menu.hidden = true;
    bar.querySelector('.st-toolbar-btn').setAttribute('aria-expanded', 'false');
  }
  function scPickTheme(input) {
    scApplyTheme(input.value);
    scCloseMenu();
  }
  function scApplyTheme(pref) {
    const root = document.documentElement;
    root.dataset.themePref = pref;
    root.dataset.theme = pref === 'system'
      ? (scThemeMq.matches ? 'dark' : 'light')
      : pref;
    try { localStorage.setItem('sc-theme', pref); } catch (e) {}
    // `scColors` and the charts snapshot the theme tokens when they are
    // built, so rebuild both to make `:color[..]` spans and Altair charts
    // follow the switch.
    scColors = scBuildColors();
    scRenderMarkdown(document);
    scRestyleAltairCharts();
  }
  function scRestyleAltairCharts() {
    document.querySelectorAll('.st-altair-chart').forEach((el) => {
      const script = el.querySelector('.st-altair-spec');
      if (!script) return;
      try {
        scRenderVegaLite(el, JSON.parse(script.textContent));
      } catch (e) {}
    });
  }
  function scMenuRerun(btn) {
    btn.disabled = true;
    btn.textContent = 'Reloading\u2026';
    scRerun(() => { btn.textContent = 'Server did not come back'; });
  }
  // Following the OS while the preference is `system` is the reason the
  // resolved theme lives in an attribute rather than in the stored value.
  scThemeMq.addEventListener('change', () => {
    if (scThemePref() === 'system') scApplyTheme('system');
  });
  document.addEventListener('click', (ev) => {
    const bar = document.getElementById('sc-toolbar');
    if (bar && !bar.contains(ev.target)) scCloseMenu();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') scCloseMenu();
  });

  // Fill the markdown placeholders that the server rendered, then draw any
  // charts that were part of the initial page. The script tag sits at the
  // end of <body>, so the DOM is already parsed.
  scToolbar();
  scSyncThemeRadios();
  scRenderMarkdown(document);
  scInitAltairCharts();
  document.querySelectorAll('.st-tabs').forEach(scObserveTabs);
  document.querySelectorAll('.st-toast-stack').forEach(scArmToasts);
  document.querySelectorAll('.st-select-slider').forEach((el) => {
    const track = el.querySelector('.st-select-slider-track');
    if (track) {
      scSelectSliderApply(track, Number(track.dataset.index || 0), false);
    }
  });

  // -- Help tooltips -----------------------------------------------------
  // Widget `help` text is markdown (mirrors Streamlit). A native `title=`
  // attribute cannot render markdown, so any element carrying a `data-help`
  // attribute gets a custom tooltip built from `scRenderParagraphs`. The
  // trigger is the info glyph next to a label, or the button itself (which
  // is how Streamlit wires `st.button`'s help).
  let scHelpTip = null;
  let scHelpTimer = 0;
  function scHelpTooltipEl() {
    if (scHelpTip) return scHelpTip;
    scHelpTip = document.createElement('div');
    // `st-md` brings the markdown styling (tables, code, lists, spacing) with
    // it, exactly as it does for a `.st-md-block` placeholder.
    scHelpTip.className = 'st-help-tooltip st-md';
    scHelpTip.setAttribute('role', 'tooltip');
    scHelpTip.hidden = true;
    document.body.appendChild(scHelpTip);
    return scHelpTip;
  }
  function scShowHelp(target) {
    const md = target.getAttribute('data-help');
    if (!md) return;
    const tip = scHelpTooltipEl();
    tip.innerHTML = window.scRenderParagraphs(md);
    tip.hidden = false;
    const rect = target.getBoundingClientRect();
    const box = tip.getBoundingClientRect();
    // Prefer below the trigger; flip above when it would overflow.
    let top = rect.bottom + 8;
    if (top + box.height > window.innerHeight - 4) {
      top = rect.top - box.height - 8;
    }
    let left = rect.left;
    if (left + box.width > window.innerWidth - 4) {
      left = window.innerWidth - box.width - 4;
    }
    tip.style.top = Math.max(4, top) + 'px';
    tip.style.left = Math.max(4, left) + 'px';
  }
  function scHideHelp() {
    if (scHelpTimer) {
      clearTimeout(scHelpTimer);
      scHelpTimer = 0;
    }
    if (scHelpTip) scHelpTip.hidden = true;
  }
  // Leaving the glyph does not hide the tooltip right away: the pointer needs
  // a moment to cross the gap onto the pane, and arriving there cancels the
  // pending hide. Without the delay the pane closes on the way and can never
  // be entered.
  function scScheduleHelpHide() {
    if (scHelpTimer) clearTimeout(scHelpTimer);
    scHelpTimer = setTimeout(() => {
      scHelpTimer = 0;
      if (scHelpTip) scHelpTip.hidden = true;
    }, 200);
  }
  function scHelpTrigger(node) {
    return node && node.closest ? node.closest('[data-help]') : null;
  }
  // The pane is interactive (links, tables, selectable text), so hovering it
  // has to count as "still on the help".
  function scInstallHelpTooltipHandlers() {
    const tip = scHelpTooltipEl();
    tip.addEventListener('mouseenter', () => {
      if (scHelpTimer) {
        clearTimeout(scHelpTimer);
        scHelpTimer = 0;
      }
    });
    tip.addEventListener('mouseleave', scScheduleHelpHide);
  }
  scInstallHelpTooltipHandlers();
  document.addEventListener('mouseover', (e) => {
    const t = scHelpTrigger(e.target);
    if (!t) return;
    if (scHelpTimer) {
      clearTimeout(scHelpTimer);
      scHelpTimer = 0;
    }
    scShowHelp(t);
  });
  document.addEventListener('mouseout', (e) => {
    if (scHelpTrigger(e.target)) scScheduleHelpHide();
  });
  document.addEventListener('focusin', (e) => {
    const t = scHelpTrigger(e.target);
    if (t) scShowHelp(t);
  });
  document.addEventListener('focusout', scHideHelp);
  // A tooltip pinned to the viewport goes stale as soon as the page moves.
  document.addEventListener('scroll', scHideHelp, true);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') scHideHelp();
  });
