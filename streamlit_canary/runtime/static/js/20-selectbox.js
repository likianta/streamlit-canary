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
  // A dropdown that opens inside a popover panel (the tree-select toolbar's
  // location bar) has to clear that panel's `overflow` clip -- the panel is
  // scrollable, so an `absolute` dropdown would be cut off at its edge. Like
  // the panel itself, such a dropdown is `position: fixed` (see page.css) and
  // placed here in viewport coordinates, aligned to the control it belongs to;
  // a dropdown outside any panel keeps its plain `absolute` placement.
  function scPositionSelectboxDropdown(dropdown) {
    if (!dropdown.closest('.st-popover-panel')) return;
    const control = dropdown.closest('.st-selectbox-control');
    if (!control) return;
    const rect = control.getBoundingClientRect();
    dropdown.style.left = Math.round(rect.left) + 'px';
    dropdown.style.width = Math.round(rect.width) + 'px';
    dropdown.style.top = Math.round(rect.bottom + 4) + 'px';
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
      scPositionSelectboxDropdown(dropdown);
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
  // -- TextInput `candidates`: a Selectbox-styled suggestion panel --
  function scCandidatesHtml(values, id) {
    const fmt = window.scRenderMarkup;
    return values.map((v) =>
      `<div class="st-selectbox-option" role="option" ` +
      `data-value="${v}" data-comp-id="${id}" ` +
      `onclick="scPickCandidate(this)">` +
      `<div class="st-selectbox-option-inner">${fmt(v)}</div></div>`
    ).join('');
  }
  function scToggleCandidates(toggle) {
    const control = toggle.closest('.st-selectbox-control');
    if (!control) return;
    const dropdown = control.querySelector('.st-selectbox-dropdown');
    const box = control.querySelector('.st-text-input-candidates-box');
    const isOpen = !dropdown.hidden;
    // Close any other open dropdown first (mirrors `scToggleSelectbox`).
    document.querySelectorAll('.st-selectbox-dropdown:not([hidden])')
      .forEach(d => {
        if (d !== dropdown) {
          d.hidden = true;
          const t = d.closest('.st-selectbox-control')
            .querySelector('.st-selectbox-trigger');
          if (t) t.removeAttribute('aria-expanded');
        }
      });
    if (isOpen) {
      dropdown.hidden = true;
      box.removeAttribute('aria-expanded');
    } else {
      dropdown.hidden = false;
      // Same growth animation as the selectbox panel.
      scPositionSelectboxDropdown(dropdown);
      scMeasureOpenHeight(dropdown, '--st-selectbox-open-height');
      box.setAttribute('aria-expanded', 'true');
    }
  }
  function scPickCandidate(opt) {
    const root = opt.closest('.st-text-input');
    if (!root) return;
    const input = root.querySelector('.st-text-input-box');
    if (input) {
      input.value = opt.dataset.value;
      scSendChange(input);
    }
    const dropdown = root.querySelector('.st-selectbox-dropdown');
    const box = root.querySelector('.st-text-input-candidates-box');
    if (dropdown) dropdown.hidden = true;
    if (box) box.removeAttribute('aria-expanded');
  }
  // Enter commits a TextInput right away; `change` alone would wait for the
  // box to lose focus (`st.text_input` commits on Enter too).
  function scSubmitKey(event, input) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    scSendChange(input);
  }
