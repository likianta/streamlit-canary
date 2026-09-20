  // Copy a code block's text; the button briefly switches to a check mark.
  function scCopyCode(btn) {
    const wrap = btn.closest('.st-code');
    const codeEl = wrap ? wrap.querySelector('code') : null;
    const text = codeEl ? codeEl.textContent : '';
    const done = () => {
      btn.classList.add('is-copied');
      setTimeout(() => btn.classList.remove('is-copied'), 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => {
        scCopyFallback(text);
        done();
      });
    } else {
      scCopyFallback(text);
      done();
    }
  }
  function scCopyFallback(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(area);
  }
  function scSendClick(btn) {
    ws.send(JSON.stringify({type: 'event', id: btn.dataset.id, event: 'click'}));
  }
  function scSendChange(input) {
    const id = input.dataset.compId;
    ws.send(JSON.stringify({type: 'event', id: id, event: 'change', value: input.value}));
  }
  // Serialize an option value the way the server does (`str(o)`), so a
  // non-scalar option such as the tuple `('f', 'x')` survives the round
  // trip. JSON turns a Python tuple into a JS array whose native toString()
  // is `"f,x"`, which would not match the server-rendered `"('f', 'x')"`
  // (breaking both the checked comparison and the server's `_coerce_value`).
  function scOptionKey(o) {
    if (Array.isArray(o)) {
      return '(' + o
        .map(x => (typeof x === 'string' ? "'" + x + "'" : String(x)))
        .join(', ') + ')';
    }
    return String(o);
  }
  function scOptionAttr(o) {
    return scOptionKey(o).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  }
  // The option-item shell shared by the RadioGroup and CheckGroup rebuilds
  // (mirrors the server's `_choice_group_items_html`). The two differ only in
  // the input's type, its checked test, the change handler and the box
  // (the radio's circle vs the square box of `v3.Checkbox`).
  //
  // A click anywhere on the row lands on the `<label>` that wraps it, so the
  // browser ticks the option on its own -- no script, and nothing held back
  // for a possible second click.
  //
  // `boxDisabled` lists the indices whose box is frozen (the server sends it
  // with an `options` patch): their field is inert and their row is dimmed.
  // `navigable` lists the indices that get a trailing "enter" button
  // (`scOpenRow`), which is how a tree row's folder is entered.
  // `bodyOpens` lists the indices whose own click walks in, with no button
  // (a frozen box leaves the click free; `..` is the one such row).
  //
  // `focused` is the index to draw highlighted -- the row a tree panel came
  // from when it walked back up (the server sends it with an `options` patch,
  // since rebuilding the rows is what would otherwise lose the mark).
  function scChoiceItemsHtml(config) {
    const { id, values, labels, inputType, onchange, isChecked } = config;
    const frozen = new Set(config.boxDisabled || []);
    const navigable = new Set(config.navigable || []);
    const opensOnBody = new Set(config.bodyOpens || []);
    const focused = config.focused;
    const name = inputType === 'radio' ? ` name="radio_${id}"` : '';
    const fmt = window.scRenderMarkup;
    const box =
      inputType === 'checkbox'
        ? `<div class="st-checkbox-box">` +
          `<svg viewBox="0 0 10 8" aria-hidden="true">` +
          `<polyline points="1 4 4 7 9 1"></polyline></svg></div>`
        : `<div class="st-radio-circle"><div class="st-radio-dot"></div></div>`;
    // An empty list shows upstream's disabled placeholder row (`st.radio`
    // does the same); mirrors the server's `_choice_group_empty_html`.
    if (!values.length) {
      return (
        '<div class="st-radio-empty"><div class="st-radio-item-row">' +
        box +
        '<div class="st-radio-empty-label">No options to select.</div>' +
        '</div></div>'
      );
    }
    return values.map((o, i) => {
      const off = frozen.has(i) ? ' disabled' : '';
      // `isChecked` is handed the index as well, because a flag-mode
      // CheckGroup reads its ticks by position (see `st-check-group--flags`).
      const field =
        `<span class="st-radio-input-wrap">` +
        `<input type="${inputType}"${name} value="${scOptionAttr(o)}" ` +
        `${isChecked(o, i) ? 'checked' : ''}${off} onchange="${onchange}(this)" ` +
        `data-comp-id="${id}"/></span>`;
      const text =
        `<div class="st-radio-markdown"><p>${fmt(labels[i])}</p></div>`;
      const enter = navigable.has(i) ? scRowEnterHtml() : '';
      const cls =
        'st-radio-item' +
        (frozen.has(i) ? ' is-box-disabled' : '') +
        (i === focused ? ' is-highlighted' : '');
      // the label wraps the whole row: a body click ticks the box by itself,
      // and `scHighlightChoice` adds the highlight on the way past -- unless
      // the row walks in on that click, which is `scOpenRow` (mirrors the
      // server's `_choice_group_items_html`)
      const rowClick = opensOnBody.has(i) ? 'scOpenRow' : 'scHighlightChoice';
      return (
        `<label class="${cls}">${field}` +
        `<div class="st-radio-item-body">` +
        `<div class="st-radio-item-row" ` +
        `onclick="${rowClick}(event, this)">` +
        box +
        text +
        enter +
        `</div></div></label>`
      );
    }).join('');
  }

  // The "enter" button a navigable row floats beside its text (mirrors the
  // server's `_row_enter_html`). It rides inside the row's `<label>`, which
  // is safe: a label ignores a click aimed at interactive content inside it,
  // so this opens the row without ticking its box.
  function scRowEnterHtml() {
    return (
      '<button class="st-row-open" type="button" aria-label="Open" ' +
      `onclick="scOpenRow(event, this)">` +
      `${window.scRenderMarkup(':material/arrow_forward:')}</button>`
    );
  }

  // A click on a row's body highlights that row and mirrors it on the
  // widget's `focused_index`, so the app can act on "the row just clicked".
  function scHighlightChoice(event, el) {
    const item = el.closest('.st-radio-item');
    if (!item) return;
    const items = Array.from(
      item.parentElement.querySelectorAll('.st-radio-item'));
    items.forEach((other) => {
      other.classList.toggle('is-highlighted', other === item);
    });
    const root = item.closest('.st-check-group, .st-radio');
    if (root) {
      ws.send(JSON.stringify({
        type: 'event',
        id: root.dataset.id,
        event: 'focus',
        value: items.indexOf(item),
      }));
    }
  }
  // Walk into a row: the click is reported as its own `open` event, so
  // entering never doubles as a tick of that row. Two callers share it --
  // `scRowEnterHtml`'s button (where `stopPropagation` also keeps the click
  // off the row's own handler: aiming at the arrow is not "clicking the row
  // body") and the row itself for a `bodyOpens` row such as `..`.
  function scOpenRow(event, el) {
    event.preventDefault();
    event.stopPropagation();
    const item = el.closest('.st-radio-item');
    if (!item) return;
    const root = item.closest('.st-check-group, .st-radio');
    if (!root) return;
    const items = Array.from(
      item.parentElement.querySelectorAll('.st-radio-item'));
    ws.send(JSON.stringify({
      type: 'event',
      id: root.dataset.id,
      event: 'open',
      value: items.indexOf(item),
    }));
  }
  // Line the "enter" arrows up on one x: every folder row's text is given the
  // width of the longest folder text, so the arrow that follows the row's own
  // 8px gap starts at the same offset in every row and the pointer can be
  // aimed without reading each name first. Called whenever the rows are
  // (re)built and again once the webfonts land -- both the names and the
  // arrow glyph change width when their fonts arrive.
  function scAlignRowArrows(root) {
    const texts = [];
    (root || document).querySelectorAll('.st-radio-item-row').forEach((row) => {
      // A row inside a hidden subtree measures 0 wide; skip it rather than
      // let it drag the common width down. Its own reveal re-runs this.
      if (row.offsetParent === null) return;
      if (!row.querySelector('.st-row-open')) return;
      const text = row.querySelector(':scope > .st-radio-markdown');
      if (text) texts.push(text);
    });
    // measure from scratch: the previous pass pinned a `min-width` on these
    // very elements, and that width would otherwise come back as the reading
    texts.forEach((t) => { t.style.minWidth = ''; });
    if (texts.length < 2) return;
    let widest = 0;
    texts.forEach((t) => {
      widest = Math.max(widest, t.getBoundingClientRect().width);
    });
    const px = Math.ceil(widest) + 'px';
    texts.forEach((t) => { t.style.minWidth = px; });
  }
