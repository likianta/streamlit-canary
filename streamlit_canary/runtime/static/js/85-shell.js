  // -- Developer toolbar: the ⋮ menu (theme + rerun) ---------------------
  // A cut-down version of Streamlit's main menu. There is no source-file
  // watcher any more (see the note above), so Rerun is how a developer picks
  // up a code change -- and the theme switch needs no round trip, since the
  // page carries both palettes (see `_THEMES_CSS` in render.py).
  const scThemeMq = matchMedia('(prefers-color-scheme: dark)');
  const scThemeChoices = [
    ['system', 'System'],
    ['light', 'Light'],
    ['dark', 'Dark']
  ];
  function scThemePref() {
    return document.documentElement.dataset.themePref || 'dark';
  }
  function scToolbar() {
    let el = document.getElementById('sc-toolbar');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-toolbar';
    el.className = 'st-toolbar';
    el.innerHTML =
      '<button class="st-toolbar-btn" type="button" title="Menu"' +
      ' aria-label="Menu" aria-haspopup="true" aria-expanded="false"' +
      ' onclick="scToggleMenu()">\u22ee</button>' +
      '<div class="st-menu" role="menu" hidden>' +
      '<div class="st-menu-title">Theme</div>' +
      scThemeChoices.map((choice) =>
        `<label class="st-menu-item">` +
        `<input type="radio" name="sc-theme" value="${choice[0]}"` +
        ` onchange="scPickTheme(this)"/>` +
        `<span>${choice[1]}</span></label>`
      ).join('') +
      '<div class="st-menu-sep"></div>' +
      '<button class="st-menu-item st-menu-action" type="button"' +
      ' role="menuitem" onclick="scMenuRerun(this)">Rerun</button>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }
  function scSyncThemeRadios() {
    const pref = scThemePref();
    scToolbar().querySelectorAll('input[name="sc-theme"]').forEach((box) => {
      box.checked = box.value === pref;
    });
  }
  function scToggleMenu() {
    const menu = scToolbar().querySelector('.st-menu');
    const open = menu.hidden;
    menu.hidden = !open;
    scToolbar().querySelector('.st-toolbar-btn')
      .setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) scSyncThemeRadios();
  }
  function scCloseMenu() {
    const bar = document.getElementById('sc-toolbar');
    if (!bar) return;
    const menu = bar.querySelector('.st-menu');
    if (menu.hidden) return;
    menu.hidden = true;
    bar.querySelector('.st-toolbar-btn').setAttribute('aria-expanded', 'false');
  }
  function scPickTheme(input) {
    scApplyTheme(input.value);
    scCloseMenu();
  }
  function scApplyTheme(pref) {
    const root = document.documentElement;
    root.dataset.themePref = pref;
    root.dataset.theme = pref === 'system'
      ? (scThemeMq.matches ? 'dark' : 'light')
      : pref;
    try { localStorage.setItem('sc-theme', pref); } catch (e) {}
    // `scColors` and the charts snapshot the theme tokens when they are
    // built, so rebuild both to make `:color[..]` spans and Altair charts
    // follow the switch.
    scColors = scBuildColors();
    scRenderMarkdown(document);
    scRestyleAltairCharts();
  }
  function scRestyleAltairCharts() {
    document.querySelectorAll('.st-altair-chart').forEach((el) => {
      const script = el.querySelector('.st-altair-spec');
      if (!script) return;
      try {
        scRenderVegaLite(el, JSON.parse(script.textContent));
      } catch (e) {}
    });
  }
  function scMenuRerun(btn) {
    btn.disabled = true;
    btn.textContent = 'Reloading\u2026';
    scRerun(() => { btn.textContent = 'Server did not come back'; });
  }
  // Following the OS while the preference is `system` is the reason the
  // resolved theme lives in an attribute rather than in the stored value.
  scThemeMq.addEventListener('change', () => {
    if (scThemePref() === 'system') scApplyTheme('system');
  });
  document.addEventListener('click', (ev) => {
    const bar = document.getElementById('sc-toolbar');
    if (bar && !bar.contains(ev.target)) scCloseMenu();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') scCloseMenu();
  });

  // -- The bottom dock -----------------------------------------------------
  // A root-level `BottomContainer` is pinned to the window's bottom edge
  // (`20-layouts.css`), so it holds no place in the page's flow any more --
  // and the page would end under it. Reserve its own height (plus one gap)
  // at the end instead, and the page's last inches stay scrollable clear of
  // the dock. The main block drops its own trailing padding for the same
  // reason (`#app:has(> .st-container--dock)` in `01-base.css`), so this is
  // the whole of the room the dock gets. The observer follows the dock as it
  // grows (a LogPanel filling with lines) or goes away (`visible=False`,
  // which reports a zero size).
  function scDockBottom() {
    const dock = document.querySelector('.st-container--dock');
    const shown = dock && !dock.hidden;
    document.body.style.paddingBottom = shown
      ? (dock.offsetHeight + 16) + 'px'
      : '';
  }
  function scObserveDockBottom() {
    const dock = document.querySelector('.st-container--dock');
    if (!dock) return;
    new ResizeObserver(() => scDockBottom()).observe(dock);
  }

  // Fill the markdown placeholders that the server rendered, then draw any
  // charts that were part of the initial page. The script tag sits at the
  // end of <body>, so the DOM is already parsed.
  scToolbar();
  scSyncThemeRadios();
  scDockBottom();
  scObserveDockBottom();
  scRenderMarkdown(document);
  scAlignRowArrows(document);
  scInitAltairCharts();
  scBootPdfViews();
  document.querySelectorAll('.st-segmented').forEach(scObserveSegmented);
  // path-like boxes show their tails (see `scTruncateStart`)
  scTruncateStart(document);
  document.fonts.ready.then(() => {
    scSyncSegmented(document);
    scAlignRowArrows(document);
    scTruncateStart(document);
  });
  document.querySelectorAll('.st-tabs').forEach(scObserveTabs);
  document.querySelectorAll('.st-toast-stack').forEach(scArmToasts);
  document.querySelectorAll('.st-select-slider').forEach((el) => {
    const track = el.querySelector('.st-select-slider-track');
    if (track) {
      scSelectSliderApply(track, Number(track.dataset.index || 0), false);
    }
  });

