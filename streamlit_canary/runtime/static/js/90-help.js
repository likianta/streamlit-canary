  // -- Help tooltips -----------------------------------------------------
  // Widget `help` text is markdown (mirrors Streamlit). A native `title=`
  // attribute cannot render markdown, so any element carrying a `data-help`
  // attribute gets a custom tooltip built from `scRenderParagraphs`. The
  // trigger is the info glyph next to a label, or the button itself (which
  // is how Streamlit wires `st.button`'s help).
  //
  // `st-truncate-help` marks an element worth a tooltip only while its box
  // cuts it off -- a dropdown item too long for its row. It shows the
  // element's *own* content, which is already rendered markup, so a label
  // carrying a `:material/...:` icon or emphasis reads exactly as the row
  // does and nothing extra has to travel down for it.
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
  // Is this element cut off? `scrollWidth` past the box is exactly "there is
  // more than fits", which needs the element to clip (`overflow: hidden`, as
  // `.st-selectbox-option-inner` does) for the two to differ.
  function scHelpIsTruncated(target) {
    return (
      target.classList.contains('st-truncate-help') &&
      target.scrollWidth > target.clientWidth + 1
    );
  }
  // What a trigger has to say, if anything. `html` says whether `text` is
  // already markup (a clipped row's own content) or markdown to render.
  function scHelpContent(target) {
    if (target.hasAttribute('data-help')) {
      return { html: false, text: target.getAttribute('data-help') };
    }
    if (scHelpIsTruncated(target)) {
      return { html: true, text: target.innerHTML };
    }
    return null;
  }
  function scShowHelp(target) {
    const content = scHelpContent(target);
    if (!content) {
      // A marked element with room to spare: nothing of its own to show, and
      // whatever a neighbouring row put up is stale by now.
      scHideHelp();
      return;
    }
    const tip = scHelpTooltipEl();
    tip.innerHTML = content.html
      ? content.text
      : window.scRenderParagraphs(content.text);
    // A clipped label is read-only, so its pane must not swallow the pointer:
    // the rows under it are what the pointer is there for. Help text keeps its
    // pointer events (it can carry links).
    tip.classList.toggle('st-help-tooltip--plain', content.html);
    tip.hidden = false;
    const rect = target.getBoundingClientRect();
    const box = tip.getBoundingClientRect();
    let left = rect.left;
    let top = rect.bottom + 8;
    if (content.html) {
      // Beside the list rather than over it, so the rows the pointer may move
      // on to stay readable (the pane is wider than a row, and a list is many
      // rows tall).
      const list = target.closest('.st-selectbox-dropdown') || target;
      const beside = list.getBoundingClientRect().right + 8;
      if (beside + box.width <= window.innerWidth - 4) left = beside;
    }
    // Prefer below the trigger; flip above when it would overflow.
    if (top + box.height > window.innerHeight - 4) {
      top = rect.top - box.height - 8;
    }
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
  // be entered. A clipped label's pane is not interactive (`--plain`), so
  // there is nothing to travel onto and it goes the moment the pointer leaves
  // the row -- which is also what keeps it out of the way of the row below.
  function scScheduleHelpHide() {
    if (scHelpTip && scHelpTip.classList.contains('st-help-tooltip--plain')) {
      scHideHelp();
      return;
    }
    if (scHelpTimer) clearTimeout(scHelpTimer);
    scHelpTimer = setTimeout(() => {
      scHelpTimer = 0;
      if (scHelpTip) scHelpTip.hidden = true;
    }, 200);
  }
  function scHelpTrigger(node) {
    if (!node || !node.closest) return null;
    return node.closest('[data-help]') || node.closest('.st-truncate-help');
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
    const t = scHelpTrigger(e.target);
    if (!t) return;
    // Moving onto a child of the same trigger is not leaving it -- the row's
    // label span is inside the box that carries the marker, and re-showing on
    // the way in would make the pane blink.
    if (e.relatedTarget && t.contains(e.relatedTarget)) return;
    scScheduleHelpHide();
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
