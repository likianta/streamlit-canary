  // -- LogPanel (canary-only) -------------------------------------------
  // The server sends the whole buffer on every `lines` patch and we rewrite
  // the text. The tail then scrolls into view, the way a terminal does. The
  // panel's two extras ride the same patch: the empty-state hint and the clear
  // button are both in the markup from the first paint (a patch cannot add an
  // element), so all this does is flip their `hidden`.
  // A line may be a divider rather than text (`LogPanel.push_divider`), which
  // the panel draws as a rule across its width: see `scRenderLogLines`, whose
  // markup mirrors `render.py::_log_body_html`.
  const SC_DIVIDER_MARK = '\u200b';  // mirrors `status.DIVIDER_MARK`

  function scIsDivider(line) {
    return line.charAt(0) === SC_DIVIDER_MARK;
  }

  function scRenderLogLines(body, lines) {
    body.textContent = '';
    // the text around a divider is emitted as one node, joined by newlines --
    // the same shape the server renders, and the same as a panel without any
    // divider at all
    let run = [];
    const flush = () => {
      if (run.length) body.appendChild(document.createTextNode(run.join('\n')));
      run = [];
    };
    lines.forEach((line) => {
      if (scIsDivider(line)) {
        flush();
        const rule = document.createElement('div');
        rule.className = 'st-log-divider';
        rule.textContent = line.slice(1);  // the title, or nothing
        body.appendChild(rule);
      } else {
        run.push(line);
      }
    });
    flush();
  }

  function scPatchLog(el, lines) {
    const list = lines || [];
    const empty = !list.length;
    const body = el.querySelector('.st-log-panel-body');
    if (body) {
      // a divider is the only thing that needs elements, so the plain-text
      // path (the common case) is kept
      if (list.some(scIsDivider)) {
        scRenderLogLines(body, list);
      } else {
        body.textContent = list.join('\n');
      }
      body.scrollTop = body.scrollHeight;
    }
    const hint = el.querySelector('.st-log-placeholder');
    if (hint) hint.hidden = !empty;
    const clear = el.querySelector('.st-log-clear');
    if (clear) clear.hidden = empty;
  }
