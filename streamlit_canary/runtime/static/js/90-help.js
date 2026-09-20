  // -- Help tooltips -----------------------------------------------------
  // Widget `help` text is markdown (mirrors Streamlit). A native `title=`
  // attribute cannot render markdown, so any element carrying a `data-help`
  // attribute gets a custom tooltip built from `scRenderParagraphs`. The
  // trigger is the info glyph next to a label, or the button itself (which
  // is how Streamlit wires `st.button`'s help).
  //
  // `data-truncate-help` is the same tooltip with its own reason to exist: the
  // element holds text that is only worth showing while the box cuts it off
  // (a long path in a narrow toolbar), so it appears on hover only then.
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
  // What a trigger has to say, if anything. `scrollWidth` past the box is
  // exactly "there is more than fits", so `data-truncate-help` stays quiet
  // until the text really is cut off -- the element has to clip
  // (`overflow: hidden` + ellipsis, as `.st-selectbox-value` does) for the
  // two to differ.
  function scHelpText(target) {
    if (target.hasAttribute('data-help')) {
      return target.getAttribute('data-help');
    }
    const md = target.getAttribute('data-truncate-help');
    if (md === null) return '';
    return target.scrollWidth > target.clientWidth + 1 ? md : '';
  }
  function scShowHelp(target) {
    const md = scHelpText(target);
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
    if (!node || !node.closest) return null;
    return (
      node.closest('[data-help]') || node.closest('[data-truncate-help]')
    );
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
