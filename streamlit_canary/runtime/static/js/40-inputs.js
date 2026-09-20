  // -- Checkbox: send the boolean checked state --
  function scSendCheck(input) {
    const id = input.dataset.compId;
    ws.send(JSON.stringify({type: 'event', id: id, event: 'change', value: input.checked}));
  }
  // -- CheckGroup: tick / untick one option, then send the whole ticked set --
  function scSendCheckGroup(input) {
    const root = input.closest('.st-check-group');
    const values = Array.from(
      root.querySelectorAll('input:checked')
    ).map(box => box.value);
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: 'change',
      value: values,
    }));
  }
  // Close dropdown when clicking outside.
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.st-selectbox-control')) {
      document.querySelectorAll('.st-selectbox-dropdown:not([hidden])').forEach(d => {
        d.hidden = true;
        const t = d.closest('.st-selectbox-control').querySelector('.st-selectbox-trigger');
        if (t) t.removeAttribute('aria-expanded');
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
  // Every panel and every escaped selectbox dropdown is `position: fixed`, so
  // it has to follow its trigger -- on resize, and whenever anything scrolls
  // (the capture phase catches scrolls inside the app's own scroll containers,
  // not just the window's).
  window.addEventListener('resize', () => {
    document.querySelectorAll('.st-popover-panel:not([hidden])')
      .forEach(scPositionPanel);
    scPositionOpenDropdowns();
    scSyncSegmented(document);
  });
  document.addEventListener('scroll', () => {
    document.querySelectorAll('.st-popover-panel:not([hidden])')
      .forEach(scPositionPanel);
    scPositionOpenDropdowns();
  }, true);
