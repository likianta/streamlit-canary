  // -- Markdown ----------------------------------------------------------
  // Streamlit parses markdown in the browser (react-markdown); we mirror
  // that with the bundled markdown-it. The server only ships the *source*
  // in `data-md` placeholders, which `scRenderMarkdown()` fills on load and
  // the delta handlers replace in place afterwards.
  const scMd = window.markdownit({ linkify: true });
  // A bare `readme.md` must stay plain text. linkify-it happily treats any
  // IANA TLD -- `.md`, `.py`, `.io`, ... -- as a domain, which turned file
  // names in prose (the tree listing, the option labels) into underlined
  // links. Keep linking what carries an explicit scheme; emails are a
  // separate switch and stay on.
  scMd.linkify.set({ fuzzyLink: false });
  // Streamlit's own inline extensions: `:material/<name>:` and `:color[..]`.
  // Streamlit renders the `:color[..]` extension with the theme's
  // `--st-<name>-text-color`, so read that instead of hardcoding -- it is
  // what makes the coloured text follow the light / dark theme.
  function scThemeColor(name, fallback) {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue('--st-' + name + '-text-color').trim();
    return value || fallback;
  }
  // Read once per theme: the toolbar rebuilds this when the theme switches,
  // so `:color[..]` spans follow the palette instead of freezing the one that
  // was live when the page loaded.
  function scBuildColors() {
    return {
      red: scThemeColor('red', '#ff6c6c'),
      orange: scThemeColor('orange', '#ffbd45'),
      yellow: scThemeColor('yellow', '#ffffc2'),
      blue: scThemeColor('blue', '#3d9df3'),
      green: scThemeColor('green', '#5ce488'),
      violet: scThemeColor('violet', '#b27eff'),
      gray: scThemeColor('gray', 'rgba(250, 250, 250, 0.4)'),
      grey: scThemeColor('gray', 'rgba(250, 250, 250, 0.4)'),
      rainbow: null
    };
  }
  let scColors = scBuildColors();
  function scColorOpen(color) {
    const css = scColors[color];
    if (css === null) {
      return '<span class="st-text-rainbow">';
    }
    return css
      ? '<span style="color:' + css + '">'
      : '<span class="st-text-' + color + '">';
  }
  // Four of the `:name[..]` marks are *effects* rather than colours: the long
  // form of the emphasis marks, so the wrapped text can be written without
  // punctuation of its own -- which matters exactly when that text is full of
  // punctuation, as names and paths are.
  //     :bold[x]       **x**     <strong>x</strong>
  //     :italic[x]     *x*       <em>x</em>
  //     :strike[x]     ~~x~~     <s>x</s>
  //     :underline[x]  --        <u>x</u>   (markdown has no underline)
  // Every one of them pushes the *same* token pair markdown-it's own rules
  // push (type `<tag>_open` / `<tag>_close`, with the tag on the token, which
  // is what the shared token renderer prints), so the result is identical to
  // the punctuation form and no renderer rule has to be added for it.
  const scEffects = {
    bold: { tag: 'strong', markup: '**' },
    italic: { tag: 'em', markup: '*' },
    strike: { tag: 's', markup: '~~' },
    underline: { tag: 'u', markup: 'u' }
  };
  // Where a `:name[..]` mark ends, given the index just past its `[`. The
  // closing bracket is the one that *balances*: the wrapped text is markdown
  // of its own, marks included, so the first `]` is not necessarily the end --
  // `:blue[:italic[a]]` has to wrap `:italic[a]`. A backslash escapes the next
  // character, which is how a literal `]` is written inside. Returns -1 when
  // nothing closes the mark, leaving it to render as the plain text it is.
  function scMarkEnd(src, from) {
    let depth = 1;
    let i = from;
    while (i < src.length) {
      const ch = src[i];
      if (ch === '\\') {
        i += 2;
        continue;
      }
      if (ch === '[') {
        depth++;
      } else if (ch === ']') {
        depth--;
        if (depth === 0) return i;
      }
      i++;
    }
    return -1;
  }
  // Inline rules (rather than a post-pass) so the extensions never fire
  // inside code spans / fenced blocks.
  scMd.inline.ruler.before('emphasis', 'st_markup', function (state, silent) {
    const rest = state.src.slice(state.pos);
    // The name is `\w+` (letters, digits, underscore), as in Streamlit --
    // e.g. `:material/settings_backup_restore:` or `:material/360:`.
    let m = /^:material\/(\w+):/.exec(rest);
    if (m !== null) {
      if (!silent) {
        const token = state.push('st_material', '', 0);
        token.meta = { name: m[1] };
      }
      state.pos += m[0].length;
      return true;
    }
    // `:smile:` -- the GitHub-style emoji shortcodes, resolved through the
    // table in `emoji-shortcodes.js` (generated from the node-emoji data
    // Streamlit itself expands with, so the two agree name for name).
    // Streamlit puts the bare character in the text -- no wrapper element,
    // no `role="img"` -- so a text token is all this is. `\+1` / `-1` are
    // spelled out because `\w` covers neither, and a name the table does not
    // know (`:notanemoji:`) is left exactly as it was typed.
    m = /^:(\+1|-1|[\w-]+):/.exec(rest);
    if (m !== null) {
      const emoji = (window.SC_EMOJI || {})[m[1]];
      if (emoji !== undefined) {
        if (!silent) {
          const token = state.push('text', '', 0);
          token.content = emoji;
        }
        state.pos += m[0].length;
        return true;
      }
    }
    m = /^:([a-zA-Z]+)\[/.exec(rest);
    if (m === null) {
      return false;
    }
    const end = scMarkEnd(rest, m[0].length);
    if (end < 0) {
      return false;
    }
    if (!silent) {
      const effect = scEffects[m[1]];
      // The wrapped text is markdown itself, e.g. `:blue[**Connect**]` or
      // `:italic[a *b* c]`, marks nested in marks included.
      const text = rest.slice(m[0].length, end);
      if (effect) {
        const open = state.push(effect.tag + '_open', effect.tag, 1);
        open.markup = effect.markup;
        state.md.inline.parse(text, state.md, state.env, state.tokens);
        const close = state.push(effect.tag + '_close', effect.tag, -1);
        close.markup = effect.markup;
      } else {
        const open = state.push('st_color_open', '', 1);
        open.meta = { color: m[1] };
        state.md.inline.parse(text, state.md, state.env, state.tokens);
        state.push('st_color_close', '', -1);
      }
    }
    state.pos += end + 1;
    return true;
  });
  scMd.renderer.rules.st_material = function (tokens, idx) {
    // Ship the icon *name* and let the Material Symbols font's ligature draw
    // it -- the same thing Streamlit does, so the glyph matches. `translate`
    // is off to keep browser translators away from the name.
    return '<span class="st-icon" translate="no">'
      + tokens[idx].meta.name + '</span>';
  };
  scMd.renderer.rules.st_color_open = function (tokens, idx) {
    return scColorOpen(tokens[idx].meta.color);
  };
  scMd.renderer.rules.st_color_close = function () {
    return '</span>';
  };
  // Streamlit's typographer (a remark plugin in StreamlitMarkdown): a few
  // ASCII combos become symbols, but only when whitespace-anchored and
  // never inside link text -- e.g. `a -> b` renders as `a → b` while
  // `a->b` is left alone.
  const scTypographer = [
    [/(^|\s)<->(\s|$)/g, '$1↔$2'],
    [/(^|\s)->(\s|$)/g, '$1→$2'],
    [/(^|\s)<-(\s|$)/g, '$1←$2'],
    [/(^|\s)--(\s|$)/g, '$1—$2'],
    [/(^|\s)>=(\s|$)/g, '$1≥$2'],
    [/(^|\s)<=(\s|$)/g, '$1≤$2'],
    [/(^|\s)~=(\s|$)/g, '$1≈$2']
  ];
  scMd.core.ruler.after('inline', 'st_typographer', function (state) {
    state.tokens.forEach(function (block) {
      if (block.type !== 'inline' || !block.children) return;
      const children = block.children;
      let linkDepth = 0;
      let i = 0;
      while (i < children.length) {
        const token = children[i];
        if (token.type === 'link_open') { linkDepth++; i++; continue; }
        if (token.type === 'link_close') { linkDepth--; i++; continue; }
        if (token.type !== 'text' || linkDepth > 0) { i++; continue; }
        // markdown-it splits text at chars like `-` and `>`, so join the
        // run of adjacent text tokens before applying the patterns.
        let j = i + 1;
        while (j < children.length && children[j].type === 'text') j++;
        const value = children
          .slice(i, j)
          .map(function (t) { return t.content; })
          .join('');
        let next = value;
        scTypographer.forEach(function (pair) {
          next = next.replace(pair[0], pair[1]);
        });
        if (next === value) {
          i = j;
          continue;
        }
        const merged = new state.Token('text', '', 0);
        merged.content = next;
        children.splice(i, j - i, merged);
        i++;
      }
    });
  });
  // `sc.set_page_config(..., dunder_literal=True)`: read `__x__` as the name it
  // is (`__init__`, `__name__`, `__file__`) instead of as emphasis. The flag
  // rides on the app shell, which is where the page config lands (`render_page`
  // in the runtime); it is off unless an app asks for it.
  //
  // Done on the token stream rather than by rewriting markdown-it's emphasis
  // rule -- that rule is a long stretch of delimiter scanning, whereas the
  // token it produced already records which delimiter it matched
  // (`token.markup`). So a `strong` opened by `__` is just put back as the two
  // literal underscores it came from: `**bold**` still bolds, `_italic_` is
  // left as it was, and anything in a code span or a fence is out of reach
  // (those never reach the inline token stream).
  if (document.getElementById('app').dataset.dunderLiteral === '1') {
    scMd.core.ruler.after('inline', 'st_dunder_literal', function (state) {
      state.tokens.forEach(function (block) {
        if (block.type !== 'inline' || !block.children) return;
        block.children = block.children.map(function (token) {
          if (
            (token.type === 'strong_open' || token.type === 'strong_close') &&
            token.markup === '__'
          ) {
            const text = new state.Token('text', '', 0);
            text.content = '__';
            return text;
          }
          return token;
        });
      });
    });
  }
  // Raw renderers (no holder): used when filling an existing `.st-md`
  // placeholder in place.
  function scMdInline(text) { return scMd.renderInline(String(text)); }
  function scMdBlock(text) { return scMd.render(String(text)).trim(); }
  // Public renderers return standalone markup *including* the `.st-md`
  // holder, because callers assign the result via `innerHTML`; the holder is
  // what the markdown styles in page.css are scoped to.
  window.scRenderMarkup = function (text) {
    return '<span class="st-md">' + scMdInline(text) + '</span>';
  };
  window.scRenderParagraphs = function (text) {
    return '<div class="st-md st-md-block">' + scMdBlock(text) + '</div>';
  };
  // Fill every server-emitted `data-md` placeholder under `root`.
  function scRenderMarkdown(root) {
    (root || document).querySelectorAll('.st-md[data-md]').forEach((el) => {
      const src = el.getAttribute('data-md') || '';
      el.innerHTML = el.classList.contains('st-md-block')
        ? scMdBlock(src)
        : scMdInline(src);
    });
  }
  // Find the markdown holder of an element: the placeholder itself, or a
  // *direct* child placeholder (keeps sibling content such as the help
  // glyph intact).
  function scMarkdownHolder(el) {
    if (el.classList.contains('st-md')) return el;
    return el.querySelector(':scope > .st-md');
  }
  // Render `value` into the markdown holder of `el` (inline or block,
  // whichever the server used), falling back to `el` itself.
  function scSetMarkdown(el, value) {
    if (!el) return;
    const holder = scMarkdownHolder(el);
    const target = holder || el;
    if (holder) holder.setAttribute('data-md', String(value));
    target.innerHTML =
      holder && holder.classList.contains('st-md-block')
        ? scMdBlock(value)
        : scMdInline(value);
  }
  // Route a `text` / `label` delta to the element that holds the markdown.
  function scPatchText(el, value) {
    if (
      el.classList.contains('st-selectbox') ||
      el.classList.contains('st-radio')
    ) {
      scSetMarkdown(el.querySelector('.st-widget-label'), value);
    } else if (el.classList.contains('st-btn')) {
      scSetMarkdown(el.querySelector('.st-btn-text') || el, value);
    } else if (el.classList.contains('st-spinner')) {
      scSetMarkdown(el.querySelector('.st-spinner-text'), value);
    } else if (el.classList.contains('st-code')) {
      const codeEl = el.querySelector('code');
      if (codeEl) codeEl.textContent = value;
    } else if (el.classList.contains('st-alert')) {
      scSetMarkdown(el.querySelector('.st-alert-text'), value);
    } else if (el.classList.contains('st-popover')) {
      scSetMarkdown(el.querySelector('.st-popover-trigger-label'), value);
    } else if (el.classList.contains('st-progress')) {
      scSetMarkdown(el.querySelector('.st-progress-text'), value);
    } else {
      scSetMarkdown(el, value);
      // `PageTitle` names the tab as well. The text as written, not the
      // rendered markdown: that is what the server put in `<title>` on the
      // first paint, and what Streamlit's own `page_title` would show.
      if (el.classList.contains('st-page-title')) document.title = value;
    }
  }
  // Route a Table extra (`title` / `caption` / `footer`) delta. An emptied
  // line is dropped, mirroring what the server would have rendered.
  function scPatchTableLine(el, kind, value) {
    let line = el.querySelector(':scope > .st-table-' + kind);
    if (!String(value)) {
      if (line) line.remove();
      return;
    }
    if (!line) {
      line = document.createElement('div');
      line.className = 'st-table-' + kind;
      const holder = document.createElement('span');
      holder.className = 'st-md';
      line.appendChild(holder);
      if (kind === 'footer') {
        el.appendChild(line);
      } else {
        el.insertBefore(line, el.querySelector('.st-table-scroll'));
      }
    }
    scSetMarkdown(line, value);
  }
  // Rebuild a Table's optional column-label row.
  function scPatchTableHead(el, value) {
    const table = el.querySelector('.st-table-table');
    if (!table) return;
    let head = table.querySelector(':scope > thead');
    if (!value) {
      if (head) head.remove();
      return;
    }
    if (!head) {
      head = document.createElement('thead');
      table.insertBefore(head, table.firstChild);
    }
    head.className = 'st-table-head';
    const fmt = window.scRenderMarkup;
    head.innerHTML =
      '<tr>' +
      value.map((label, i) => (
        '<th class="' + (i === 0 ? 'st-table-key' : 'st-table-cell') + '">' +
        fmt(String(label)) + '</th>'
      )).join('') +
      '</tr>';
  }

