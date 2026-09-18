  // -- LogPanel (canary-only) -------------------------------------------
  // The server sends the whole buffer on every `lines` patch and we rewrite
  // the text. The tail then scrolls into view, the way a terminal does.
  function scPatchLog(el, lines) {
    const body = el.querySelector('.st-log-panel-body');
    if (!body) return;
    body.textContent = (lines || []).join('\n');
    body.scrollTop = body.scrollHeight;
  }
