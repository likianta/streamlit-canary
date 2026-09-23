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
      } else if (el.classList.contains('st-popover')) {
        // The patch targets the popover root, but the clickable element is the
        // trigger button inside it (`Popover` / `MenuButton`).
        el.classList.toggle('is-disabled', !msg.value);
        const trigger = el.querySelector('.st-popover-trigger');
        if (trigger) trigger.disabled = !msg.value;
      } else if (
        el.classList.contains('st-selectbox') ||
        el.classList.contains('st-radio') ||
        el.classList.contains('st-check-group') ||
        el.classList.contains('st-segmented') ||
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
    if (msg.prop === 'type' && el.classList.contains('st-btn')) {
      // A button's accent is reactive: swap the palette class in place (the
      // server maps anything but "primary" to "secondary", as it does on the
      // first paint).
      el.classList.toggle('st-btn-primary', msg.value === 'primary');
      el.classList.toggle('st-btn-secondary', msg.value !== 'primary');
    }
    if (msg.prop === 'visible') {
      if (el.classList.contains('st-reveal')) {
        // Server-driven reveal: reuse the expander's height animation.
        scAnimateExpanderBody(el, !!msg.value);
      } else {
        el.hidden = !msg.value;
      }
      // An element that was hidden only becomes measurable now, and the tree
      // rows' text widths are what line the `->` arrows up.
      if (msg.value) scAlignRowArrows(el);
    }
    // `Popover.close()`: a counter bump asking us to fold the panel away.
    // The trigger stays put, so this is the close half of `scTogglePopover`.
    if (msg.prop === '_close') {
      const panel = el.querySelector('.st-popover-panel');
      const trigger = el.querySelector('.st-popover-trigger');
      // only a panel that was actually up has a close to report
      if (panel && !panel.hidden) {
        panel.hidden = true;
        scNotifyPopover(el, false);
      }
      if (trigger) {
        trigger.setAttribute('aria-expanded', 'false');
        scSwapChevron(
          trigger, '.st-popover-chevron', 'expand_more', 'expand_less', false
        );
      }
    }
    if (msg.prop === 'src') {
      // `PdfViewer`: hand the new document to pdf.js, which re-draws the box
      // (see `76-pdf-viewer.js`).
      const box = el.classList.contains('st-pdf-viewer')
        ? el
        : el.querySelector('.st-pdf-viewer');
      if (box) {
        box.dataset.src = msg.value || '';
        window.scDrawPdfView(box);
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
        const currentVal = el._scValue || msg.value[0];
        el.querySelector('.st-radio-group').innerHTML = scChoiceItemsHtml({
          id: msg.id,
          values: msg.value,
          labels: msg.formatted || msg.value.map(x => x),
          inputType: 'radio',
          onchange: 'scSendChange',
          isChecked: (o) => scOptionKey(o) === scOptionKey(currentVal),
          boxDisabled: msg.box_disabled,
          navigable: msg.navigable,
          bodyOpens: msg.body_opens,
          focused: msg.focused,
        });
        scAlignRowArrows(el);
      }
      if (el.classList.contains('st-check-group')) {
        // Flag mode reads its ticks by position (see `st-check-group--flags`),
        // and `msg.flags` carries the current value for a rebuilt row set.
        const flags = el.classList.contains('st-check-group--flags');
        const flagValues = flags ? (msg.flags || el._scValue || []) : null;
        const wanted = new Set((el._scValue || []).map(scOptionKey));
        el.querySelector('.st-radio-group').innerHTML = scChoiceItemsHtml({
          id: msg.id,
          values: msg.value,
          labels: msg.formatted || msg.value.map(x => x),
          inputType: 'checkbox',
          onchange: 'scSendCheckGroup',
          isChecked: flags
            ? (o, i) => !!flagValues[i]
            : (o) => wanted.has(scOptionKey(o)),
          boxDisabled: msg.box_disabled,
          navigable: msg.navigable,
          bodyOpens: msg.body_opens,
          focused: msg.focused,
        });
        scAlignRowArrows(el);
      }
      if (el.classList.contains('st-segmented')) {
        const group = el.querySelector('.st-segmented-group');
        const id = msg.id;
        const currentVal = el._scValue || msg.value[0];
        const fmt = window.scRenderMarkup;
        const labels = msg.formatted || msg.value.map(x => x);
        group.innerHTML = msg.value.map((o, i) =>
          `<label class="st-segmented-item">` +
          `<input type="radio" name="seg_${id}" value="${scOptionAttr(o)}" ` +
          `${scOptionKey(o) === scOptionKey(currentVal) ? 'checked' : ''} ` +
          `onchange="scSendChange(this)" data-comp-id="${id}"/>` +
          `<span class="st-segmented-item-label">${fmt(labels[i])}</span>` +
          `</label>`
        ).join('');
        scSyncSegmented(el);
      }
      if (el.classList.contains('st-reducible-group')) {
        el.querySelector('.st-reducible-group-items').innerHTML =
          scReducibleItemsHtml(msg.value, msg.formatted);
      }
      // A `MenuButton`'s rows live inside its panel, but the patch targets the
      // `.st-popover` root (that is where its `data-id` is).
      const menuItems = el.querySelector('.st-menu-options');
      if (menuItems) {
        menuItems.innerHTML = scMenuItemsHtml(msg.value, msg.formatted);
      }
    }
    if (msg.prop === 'candidates') {
      if (el.classList.contains('st-text-input-candidates')) {
        // An empty list keeps the caret but greys it out (a `null` sent at
        // runtime reads as empty -- the caret's presence is fixed at build).
        const list = msg.value || [];
        const dropdown = el.querySelector('.st-selectbox-dropdown');
        const toggle = el.querySelector('.st-text-input-candidates-toggle');
        if (dropdown) dropdown.innerHTML = scCandidatesHtml(list, msg.id);
        if (toggle) toggle.disabled = list.length === 0;
      }
    }
    if (msg.prop === 'placeholder') {
      // All five placeholder-carrying widgets share the field (see
      // `_HasPlaceholder`), so a hint can follow something else -- the scene in
      // `test/pixel_fidelity/ui_scene_sc.py` makes it the last committed name.
      // The text-like widgets show it as the box's own attribute; the two
      // triggers show it *in place of* a missing selection, so only the one
      // currently showing the hint is redrawn (a picked trigger keeps its
      // label).
      const text = msg.value == null ? '' : String(msg.value);
      const box = el.querySelector('.st-text-input-box, .st-text-area-box');
      if (box) {
        box.placeholder = text;
      } else {
        el.dataset.placeholder = text;
        const shown = el.querySelector(
          '.st-selectbox-value.is-placeholder, ' +
          '.st-multiselect-values.is-placeholder'
        );
        if (shown) shown.textContent = text;
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
        // Update trigger label from the matching option's inner div.
        const matched = Array.from(optEls).find(o => o.dataset.value === wanted);
        scSetSelectboxValue(
          el,
          matched ? matched.querySelector('.st-selectbox-option-inner') : null,
        );
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
      if (el.classList.contains('st-segmented')) {
        // Same string-vs-real-type caveat as the radio above.
        el._scValue = msg.value;
        const wanted = scOptionKey(msg.value);
        el.querySelectorAll('input').forEach(r => {
          r.checked = (r.value === wanted);
        });
        scSyncSegmented(el);
      }
      if (el.classList.contains('st-check-group')) {
        // A list value: tick every box whose option is in the selection --
        // or, in flag mode, the boxes the parallel booleans line up with.
        el._scValue = msg.value || [];
        const flags = el.classList.contains('st-check-group--flags');
        const wanted = new Set(el._scValue.map(scOptionKey));
        el.querySelectorAll('input').forEach((box, i) => {
          box.checked = flags ? !!el._scValue[i] : wanted.has(box.value);
        });
      }
      if (
        el.classList.contains('st-text-input') ||
        el.classList.contains('st-text-area')
      ) {
        const box = el.querySelector('.st-text-input-box, .st-text-area-box');
        // Don't clobber what the user is currently typing.
        if (box && box.value !== msg.value) box.value = msg.value;
        // a path-like box reads from its tail, and the new value is a new
        // string to bring that tail of (see `scTruncateStartEl`)
        if (box) scTruncateStartEl(box);
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
        // is a list, so compare the option values as strings. Its order is the
        // tick order, which is what the trigger shows (see
        // `scMultiselectSelection`).
        el._scValue = (msg.value || []).map(String);
        el.querySelectorAll('.st-multiselect-option').forEach(o => {
          o.classList.toggle(
            'is-checked', el._scValue.indexOf(o.dataset.value) >= 0
          );
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
    if (msg.prop === 'lines') {
      if (el.classList.contains('st-log-panel')) {
        scPatchLog(el, msg.value);
      }
    }
  };
