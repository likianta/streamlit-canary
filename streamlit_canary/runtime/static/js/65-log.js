  // -- LogPanel (canary-only) -------------------------------------------
  // The server sends the whole buffer on every `lines` patch and we rewrite
  // the text. The tail then scrolls into view, the way a terminal does. The
  // panel's two extras ride the same patch: the empty-state hint and the clear
  // button are both in the markup from the first paint (a patch cannot add an
  // element), so all this does is flip their `hidden`.
  function scPatchLog(el, lines) {
    const empty = !(lines && lines.length);
    const body = el.querySelector('.st-log-panel-body');
    if (body) {
      body.textContent = (lines || []).join('\n');
      body.scrollTop = body.scrollHeight;
    }
    const hint = el.querySelector('.st-log-placeholder');
    if (hint) hint.hidden = !empty;
    const clear = el.querySelector('.st-log-clear');
    if (clear) clear.hidden = empty;
  }
