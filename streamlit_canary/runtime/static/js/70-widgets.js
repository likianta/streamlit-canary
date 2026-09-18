  // -- Tabs / Expander / NumberInput stepper (client-side UI state) --
  function scSelectTab(btn) {
    const root = btn.closest('.st-tabs');
    if (!root) return;
    const label = btn.dataset.tab;
    const bar = root.querySelector('.st-tabs-bar');
    const previous = bar ? bar.querySelector('.st-tab.is-active') : null;
    // Scope to *this* tab group. The selectors below are descendant
    // selectors, so without the guard they would also match a nested
    // `Tabs` (e.g. one inside a popover in a panel), clearing its active
    // tab and hiding all of its panels.
    root.querySelectorAll('.st-tabs-bar > .st-tab').forEach(b => {
      if (b.closest('.st-tabs') !== root) return;
      const on = b === btn;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    root.querySelectorAll('.st-tabs-panels > .st-tab-panel').forEach(p => {
      if (p.closest('.st-tabs') !== root) return;
      p.hidden = p.dataset.tab !== label;
    });
    if (previous && previous !== btn) {
      scSlideTabIndicator(root, previous, btn);
    } else {
      scSyncTabIndicator(root);
    }
    // Keep the server-side `active` property in sync.
    const id = root.dataset.id;
    if (id) {
      ws.send(JSON.stringify({
        type: 'event', id: id, event: 'change', value: label,
      }));
    }
  }
  // Move the underline from one tab to another the way a sticky one moves: it
  // stretches until it spans both tabs, then contracts onto the new one, so
  // the trailing edge looks like it is being dragged along. Measured from the
  // tabs themselves rather than from the underline, so a switch mid-animation
  // still starts from a real tab. `scSyncTabIndicator` runs at the end both to
  // park the underline and to hand the geometry back to the inline style.
  function scSlideTabIndicator(root, from, to) {
    const bar = root.querySelector('.st-tabs-bar');
    const indicator = bar ? bar.querySelector('.st-tabs-indicator') : null;
    if (!indicator) return;
    const fromLeft = from.offsetLeft;
    const toLeft = to.offsetLeft;
    const fromWidth = from.offsetWidth;
    const toWidth = to.offsetWidth;
    // Spanning the union of both tabs is what makes the *leading* edge move
    // first and leaves the trailing edge behind, whichever way the switch
    // goes; hopping over a middle tab stretches across it, as Streamlit's
    // underline does.
    const stretchLeft = Math.min(fromLeft, toLeft);
    const stretchWidth =
      Math.max(fromLeft + fromWidth, toLeft + toWidth) - stretchLeft;
    const at = x => 'translateX(' + x + 'px)';
    if (indicator._scSlideAnim) indicator._scSlideAnim.cancel();
    // Both halves ease out (a quadratic curve: fastest right after the click,
    // settling at the end), which is what gives the line its dragged feel. The
    // duration matches Streamlit's plain slide.
    indicator._scSlideAnim = indicator.animate([
      { transform: at(fromLeft), width: fromWidth + 'px' },
      {
        transform: at(stretchLeft),
        width: stretchWidth + 'px',
        offset: 0.5,
      },
      { transform: at(toLeft), width: toWidth + 'px' },
    ], { duration: 200, easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)' });
    indicator._scSlideAnim.addEventListener('finish', () => {
      indicator._scSlideAnim = null;
      scSyncTabIndicator(root);
    });
  }
  // Park the bar's single underline under the active tab. `offsetLeft` is
  // measured against the offset parent, which is the bar (it is positioned),
  // so the width and the offset share one origin. This places the underline
  // without animating it, which is what a resize or a first paint wants.
  function scSyncTabIndicator(root) {
    const bar = root.querySelector('.st-tabs-bar');
    const indicator = bar ? bar.querySelector('.st-tabs-indicator') : null;
    const active = bar ? bar.querySelector('.st-tab.is-active') : null;
    if (!indicator || !active) return;
    indicator.style.width = active.offsetWidth + 'px';
    indicator.style.transform = 'translateX(' + active.offsetLeft + 'px)';
  }
  function scObserveTabs(root) {
    const bar = root.querySelector('.st-tabs-bar');
    if (!bar) return;
    // The bar measures 0 while its tabs sit inside something hidden -- a
    // popover, a dialog, an inactive tab panel -- so the underline has to be
    // re-placed whenever the bar's box changes. Observing the box covers that
    // as well as a window resize and the webfont landing.
    new ResizeObserver(() => scSyncTabIndicator(root)).observe(bar);
    scSyncTabIndicator(root);
  }
  function scToggleExpander(header) {
    const root = header.closest('.st-expander');
    if (!root) return;
    const expanded = !root.classList.contains('is-expanded');
    root.classList.toggle('is-expanded', expanded);
    header.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const body = root.querySelector('.st-expander-body');
    if (body) scAnimateExpanderBody(body, expanded);
    scSwapChevron(
      header, '.st-expander-icon',
      'keyboard_arrow_right', 'keyboard_arrow_down', expanded
    );
  }
  // Expand/collapse the body with a height animation. `hidden` still drives
  // the server-rendered state; while animating the height is set explicitly
  // and the overflow is clipped (so a dropdown inside is not cut off once
  // the transition is over).
  function scAnimateExpanderBody(body, expanded) {
    if (body._scExpandAnim) body._scExpandAnim.cancel();
    const from = body.hidden ? 0 : body.getBoundingClientRect().height;
    body.hidden = false;
    const to = expanded ? body.scrollHeight : 0;
    if (from === to) {
      body.hidden = !expanded;
      body.style.height = '';
      return;
    }
    body.style.height = from + 'px';
    body.style.overflow = 'hidden';
    body._scExpandAnim = body.animate(
      { height: [from + 'px', to + 'px'] },
      { duration: 200, easing: 'ease' }
    );
    body._scExpandAnim.addEventListener('finish', () => {
      body._scExpandAnim = null;
      body.style.height = '';
      body.style.overflow = '';
      body.hidden = !expanded;
    });
  }
  // Enable/disable the stepper arrows from the current value, mirroring
  // Streamlit: sitting on a bound disables the arrow pointing out of it.
  function scSyncNumberStepper(input) {
    const box = input.closest('.st-number-box');
    if (!box) return;
    // Markup order is [decrease, increase].
    const steps = box.querySelectorAll('.st-number-step');
    if (steps.length < 2) return;
    const value = parseFloat(input.dataset.value);
    if (!isFinite(value)) return;
    const min = input.dataset.min;
    const max = input.dataset.max;
    steps[0].disabled =
      min !== undefined && min !== '' && value <= parseFloat(min);
    steps[1].disabled =
      max !== undefined && max !== '' && value >= parseFloat(max);
  }

  function scStepNumber(btn, direction) {
    const box = btn.closest('.st-number-box');
    const input = box ? box.querySelector('input') : null;
    if (!input) return;
    const step = parseFloat(input.dataset.step);
    const current = parseFloat(input.dataset.value);
    if (!isFinite(step) || !isFinite(current)) return;
    let value = current + direction * step;
    const min = input.dataset.min;
    const max = input.dataset.max;
    if (min !== undefined && min !== '' && value < parseFloat(min)) {
      value = parseFloat(min);
    }
    if (max !== undefined && max !== '' && value > parseFloat(max)) {
      value = parseFloat(max);
    }
    // Trim the float noise a step like 0.1 introduces.
    const decimals = (String(step).split('.')[1] || '').length;
    const text = decimals ? value.toFixed(decimals) : String(value);
    input.dataset.value = text;
    input.value = text;
    scSyncNumberStepper(input);
    scSendChange(input);
  }

