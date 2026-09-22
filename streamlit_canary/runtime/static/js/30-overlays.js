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
  // The selection as an ordered list of value strings: ticking appends to it,
  // unticking drops from it, and that order is what the trigger shows and what
  // the server stores. A `value` patch refreshes it (`00-connection.js`); until
  // one arrives, the server-rendered `data-selected` seeds it -- which is also
  // what keeps the ticks when an `options` patch rebuilds the list first.
  function scMultiselectSelection(root) {
    if (!root._scValue) {
      let seed = [];
      try {
        seed = JSON.parse(root.dataset.selected || '[]');
      } catch (error) {
        seed = [];
      }
      root._scValue = seed.map(String);
    }
    return root._scValue;
  }
  function scRenderMultiselectOptions(root, values, labels) {
    const dropdown = root.querySelector('.st-multiselect-dropdown');
    if (!dropdown) return;
    const fmt = window.scRenderMarkup;
    const esc = (s) => String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    const wanted = scMultiselectSelection(root);
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
  // The trigger summarises the ticked options, in tick order (see
  // `scMultiselectSelection`). Each label goes in as its *rendered* markup, not
  // as its text: a label may carry a `:material/...:` icon, whose plain text is
  // the icon's ligature name (same reason as `scSetSelectboxValue`).
  function scRefreshMultiselectSummary(root) {
    const valuesEl = root.querySelector('.st-multiselect-values');
    if (!valuesEl) return;
    const byValue = new Map();
    root.querySelectorAll('.st-multiselect-option').forEach(o => {
      byValue.set(String(o.dataset.value), o);
    });
    const labels = [];
    scMultiselectSelection(root).forEach((value) => {
      const option = byValue.get(String(value));
      const label = option &&
        option.querySelector('.st-multiselect-option-label');
      if (label) labels.push(label.innerHTML);
    });
    if (labels.length) {
      valuesEl.innerHTML = labels.join(', ');
      valuesEl.classList.remove('is-placeholder');
    } else {
      valuesEl.textContent = root.dataset.placeholder || 'Choose an option';
      valuesEl.classList.add('is-placeholder');
    }
    // The strip keeps to one line under `height='fixed'`, so the newest value
    // has to be brought into view (see `.st-multiselect--fixed` in page.css).
    if (root.classList.contains('st-multiselect--fixed')) {
      valuesEl.scrollLeft = valuesEl.scrollWidth;
    }
  }
  function scToggleMultiselectOption(option) {
    const root = option.closest('.st-multiselect');
    const value = String(option.dataset.value);
    const selection = scMultiselectSelection(root);
    const at = selection.indexOf(value);
    const ticked = at < 0;
    // ticking appends, so the newest value is also the last one shown
    if (ticked) selection.push(value);
    else selection.splice(at, 1);
    option.classList.toggle('is-checked', ticked);
    scRefreshMultiselectSummary(root);
    // The whole selection is sent on every toggle, in tick order.
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: 'change',
      value: selection,
    }));
  }
  // -- Custom popover interaction (toggle is client-only; no rerun) --
  // A panel is folded away from several places -- its own trigger, another
  // panel opening, a click outside, Escape, `Popover.close()` -- so telling
  // the server about it happens here, once, rather than at each of them. The
  // open half is in `scTogglePopover`, the only place a panel goes up.
  function scNotifyPopover(root, open) {
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: open ? 'open' : 'close',
    }));
  }
  function scClosePopovers(except) {
    document.querySelectorAll('.st-popover-panel:not([hidden])').forEach(p => {
      // Skip the panel being opened and any panel that *contains* it: a
      // nested popover (e.g. the bucket sitting in the tree-select panel's
      // toolbar) must not take its own ancestor down with it.
      if (except && p.contains(except)) return;
      p.hidden = true;
      const root = p.closest('.st-popover');
      const t = root ? root.querySelector('.st-popover-trigger') : null;
      if (t) t.setAttribute('aria-expanded', 'false');
      if (root) scNotifyPopover(root, false);
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
  // Place a panel. Every panel is `position: fixed` and therefore lives in
  // viewport coordinates, so it may spill past a scrollable ancestor's
  // `overflow` -- which is how Streamlit's portalled overlays behave. The
  // variant decides the anchoring:
  //   --row    spans the surrounding row, from that row's text input's left
  //            edge to the row's right edge
  //   --above  hangs above the trigger (anchored by its bottom edge, so its
  //            entry animation unfolds upwards)
  //   --menu   hangs under the trigger, flipping above when there is no room
  //   default  hangs under the trigger, left-aligned, kept inside the app box
  // The gap between a trigger and its panel is a design choice: a menu's rows
  // are tightly bound to the trigger, so they sit close (4px, like
  // `st.menu_button`); a general popover can host arbitrary content and gets a
  // roomier 8px (see `pixel_fidelity_caveats.md`).
  const SC_PANEL_GAP = 8;
  const SC_MENU_PANEL_GAP = 4;
  function scPositionPanel(panel) {
    const pop = panel.closest('.st-popover');
    const trigger = pop.querySelector('.st-popover-trigger');
    const t = trigger.getBoundingClientRect();
    const bounds = scPopoverBounds();
    const gap = panel.classList.contains('st-popover-panel--menu')
      ? SC_MENU_PANEL_GAP
      : SC_PANEL_GAP;
    panel.style.left = '';
    panel.style.top = '';
    panel.style.bottom = '';
    panel.style.width = '';
    if (panel.classList.contains('st-popover-panel--row')) {
      const row = pop.closest('.st-row');
      if (row) {
        const input = row.querySelector('.st-text-input');
        const rowRect = row.getBoundingClientRect();
        const start = input ? input.getBoundingClientRect().left : rowRect.left;
        panel.style.left = Math.round(start) + 'px';
        panel.style.width = Math.round(rowRect.right - start) + 'px';
      }
      panel.style.top = Math.round(t.bottom + SC_PANEL_GAP) + 'px';
      return;
    }
    if (panel.classList.contains('st-popover-panel--above')) {
      panel.style.left = Math.round(t.left) + 'px';
      panel.style.bottom =
        Math.round(window.innerHeight - t.top + SC_PANEL_GAP) + 'px';
      return;
    }
    // The panel's height has to come from `scrollHeight`: its entry animation
    // starts the box at height 0.
    const height = panel.scrollHeight;
    let top = t.bottom + gap;
    if (
      top + height > window.innerHeight - gap &&
      t.top - gap - height > 0
    ) {
      top = t.top - gap - height;
    }
    // Anchor to the trigger's left edge, shifting left when that would overflow
    // the app's content box (and back right when it would overflow the left).
    let left = t.left;
    if (left + panel.offsetWidth > bounds.right) {
      left = bounds.right - panel.offsetWidth;
    }
    if (left < bounds.left) left = bounds.left;
    panel.style.left = Math.round(left) + 'px';
    panel.style.top = Math.round(top) + 'px';
  }
  // The trigger's chevron is an icon-font glyph that Streamlit *swaps* when
  // the panel opens (`expand_more` <-> `expand_less`), rather than rotating.
  function scSwapChevron(host, selector, closed, open, isOpen) {
    const glyph = host.querySelector(selector);
    if (glyph) glyph.textContent = isOpen ? open : closed;
  }
  // Park the segmented control's sliding highlight under the checked pill.
  // The pills size themselves from their text, so this has to be measured --
  // and only once the control is actually laid out (a hidden panel reports
  // zero widths), hence the call sites: page load, fonts ready, panel open,
  // options / value patches and window resize.
  function scSyncSegmented(root) {
    const scope = root || document;
    // `root` may be the control itself (a `value` / `options` patch) or any
    // ancestor of it (a panel opening), so check both ways.
    if (scope.classList && scope.classList.contains('st-segmented')) {
      scPlaceSegmentedHighlight(scope);
    }
    scope.querySelectorAll('.st-segmented').forEach(scPlaceSegmentedHighlight);
  }
  function scPlaceSegmentedHighlight(seg) {
    const highlight = seg.querySelector('.st-segmented-highlight');
    if (!highlight) return;
    const checked = seg.querySelector('.st-segmented-item input:checked');
    if (!checked || seg.offsetParent === null) {
      highlight.style.opacity = '0';
      // The layout is unknown while hidden (the pills measure 0 wide), so the
      // next placement has to be instant rather than a slide from nowhere.
      delete highlight.dataset.placed;
      return;
    }
    const item = checked.closest('.st-segmented-item');
    // Only the very first placement is instant: afterwards the pending
    // `transition` (see `.st-segmented-highlight`) animates the slide.
    const instant = !highlight.dataset.placed;
    if (instant) highlight.classList.add('is-instant');
    highlight.style.width = item.offsetWidth + 'px';
    highlight.style.transform = 'translateX(' + item.offsetLeft + 'px)';
    if (instant) {
      // Read back a layout value so the browser commits the jump before the
      // transition is re-armed for the next change.
      void highlight.offsetWidth;
      highlight.classList.remove('is-instant');
      highlight.dataset.placed = '1';
    }
    highlight.style.opacity = '1';
  }
  // -- MenuButton / ReducibleGroup rows ---------------------------------
  // The rows are plain HTML (the server writes them, an `options` patch
  // rebuilds them), so they hook up through these globals rather than through
  // component events.
  function scMenuItemsHtml(values, formatted) {
    const fmt = window.scRenderMarkup;
    const labels = formatted || values.map(x => x);
    return values.map((o, i) =>
      `<div class="st-menu-option" role="menuitem" ` +
      `data-value="${scOptionAttr(o)}" onclick="scMenuPick(this)">` +
      `<span class="st-menu-option-label">${fmt(labels[i])}</span></div>`
    ).join('');
  }
  function scReducibleItemsHtml(values, formatted) {
    const fmt = window.scRenderMarkup;
    const labels = formatted || values.map(x => x);
    return values.map((o, i) =>
      `<div class="st-menu-option st-menu-option--reducible" ` +
      `data-value="${scOptionAttr(o)}">` +
      `<span class="st-menu-option-label">${fmt(labels[i])}</span>` +
      `<button class="st-menu-option-remove" type="button" aria-label="Remove" ` +
      `onclick="scReduceItem(this)">${fmt(':material/close:')}</button></div>`
    ).join('');
  }
  // Picking a menu option sets the widget's `value` and closes the menu.
  function scMenuPick(item) {
    const root = item.closest('.st-popover');
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: 'change',
      value: item.dataset.value,
    }));
    const panel = root.querySelector('.st-popover-panel');
    panel.hidden = true;
    const trigger = root.querySelector('.st-popover-trigger');
    trigger.setAttribute('aria-expanded', 'false');
    scSwapChevron(
      trigger, '.st-popover-chevron', 'expand_more', 'expand_less', false
    );
    scNotifyPopover(root, false);
  }
  // Dropping an item sends a `reduce` event; the widget removes it from
  // `options` and patches the list back.
  function scReduceItem(button) {
    const item = button.closest('.st-menu-option');
    const group = item.closest('.st-reducible-group');
    ws.send(JSON.stringify({
      type: 'event',
      id: group.dataset.id,
      event: 'reduce',
      value: item.dataset.value,
    }));
  }
  function scTogglePopover(trigger) {
    // A disabled trigger is inert: the `disabled` attribute already swallows
    // the click, this is the belt-and-braces guard.
    if (trigger.disabled) return;
    const root = trigger.closest('.st-popover');
    const panel = root.querySelector('.st-popover-panel');
    const isOpen = !panel.hidden;
    scClosePopovers(panel);
    if (isOpen) {
      panel.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      scNotifyPopover(root, false);
    } else {
      panel.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      scNotifyPopover(root, true);
      scPositionPanel(panel);
      // Measured after the placement pass, so a row-aligned panel is sized
      // from its final width. The chevron is swapped, not animated.
      scMeasureOpenHeight(panel, '--st-popover-open-height');
      // Two things inside the panel only become measurable now: a segmented
      // control, and the tree rows' text -- their widths are what pins the
      // `->` arrows to one x, and inside a hidden panel every reading is 0.
      scSyncSegmented(panel);
      scAlignRowArrows(panel);
    }
    scSwapChevron(
      trigger, '.st-popover-chevron', 'expand_more', 'expand_less', !isOpen
    );
  }
