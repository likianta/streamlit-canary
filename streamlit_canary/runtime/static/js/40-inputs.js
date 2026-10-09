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
      scCloseSelectboxDropdowns();
    }
    if (!e.target.closest('.st-popover')) {
      scClosePopovers(null);
    }
    if (!e.target.closest('.st-multiselect')) {
      scCloseMultiselects(null);
    }
  });
  // Close popovers and dropdowns on Escape.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      scClosePopovers(null);
      scCloseSelectboxDropdowns();
    }
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
