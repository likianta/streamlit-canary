  // -- Toast stack (canary-only) ----------------------------------------
  // Server-side twin of `_toast_item` in render.py: keep the markup identical
  // so a patched-in toast is indistinguishable from a server-rendered one.
  function scToastHtml(m) {
    const fmt = window.scRenderMarkup;
    const icon = m.icon
      ? '<span class="st-toast-icon">' + fmt(m.icon) + '</span>'
      : '';
    return (
      icon +
      '<span class="st-toast-body">' + fmt(String(m.text)) + '</span>' +
      '<button type="button" class="st-toast-close" aria-label="Dismiss"' +
      ' onclick="scDismissToast(this)">\u2715</button>'
    );
  }
  // Arm a toast's auto-dismiss countdown from its `data-duration` (seconds).
  // The attribute is absent for an "infinite" toast, which stays put until the
  // user dismisses it. Hovering the stack pauses every countdown so a message
  // can be read (mirrors `st.toast`).
  function scToastArm(node) {
    scToastDisarm(node);
    const raw = node.dataset.duration;
    if (!raw) return;
    const ms = Number(raw) * 1000;
    node._scRemaining = ms;
    node._scStartedAt = Date.now();
    node._scTimer = setTimeout(() => scToastExpire(node), ms);
  }
  function scToastDisarm(node) {
    if (node._scTimer) clearTimeout(node._scTimer);
    node._scTimer = null;
  }
  function scToastPause(node) {
    if (!node._scTimer) return;
    const elapsed = Date.now() - node._scStartedAt;
    scToastDisarm(node);
    node._scRemaining = Math.max(0, node._scRemaining - elapsed);
  }
  function scToastResume(node) {
    if (node._scTimer || node._scRemaining === undefined) return;
    node._scStartedAt = Date.now();
    node._scTimer = setTimeout(() => scToastExpire(node), node._scRemaining);
  }
  function scToastExpire(node) {
    scToastDisarm(node);
    scToastDismissNode(node);
  }
  // Drop one toast: tell the server, which removes it from `messages` and
  // patches the stack back.
  function scToastDismissNode(node) {
    const stack = node.closest('.st-toast-stack');
    if (!stack) return;
    ws.send(JSON.stringify({
      type: 'event', id: stack.dataset.id, event: 'dismiss',
      value: node.dataset.id,
    }));
  }
  function scToastListen(el) {
    if (el.dataset.armed) return;
    el.dataset.armed = '1';
    el.addEventListener('mouseenter', () => {
      el.querySelectorAll('.st-toast').forEach(scToastPause);
    });
    el.addEventListener('mouseleave', () => {
      el.querySelectorAll('.st-toast').forEach(scToastResume);
    });
  }
  // Arm the toasts the server rendered on the initial page; the ones that
  // arrive later are armed by `scPatchToasts` as they are appended.
  function scArmToasts(el) {
    scToastListen(el);
    el.querySelectorAll('.st-toast').forEach(scToastArm);
  }
  // Reconcile the stack with the server's `messages` list, keyed by each
  // toast's stable id: append the new ones (a freshly created node plays the
  // CSS entrance animation), drop the ones the server no longer lists, and
  // rewrite a node only when its message really changed -- so an append never
  // resets the spread transition already in flight.
  function scPatchToasts(el, messages) {
    const list = messages || [];
    const seen = new Set();
    const byId = new Map();
    scToastListen(el);
    Array.from(el.children).forEach((c) => {
      if (c.classList.contains('st-toast')) byId.set(c.dataset.id, c);
    });
    list.forEach((m) => {
      const id = String(m.id);
      seen.add(id);
      let node = byId.get(id);
      if (!node) {
        node = document.createElement('div');
        node.className = 'st-toast';
        node.dataset.id = id;
        el.appendChild(node);
      }
      const sig = JSON.stringify(m);
      if (node.dataset.sig !== sig) {
        node.dataset.sig = sig;
        if (m.duration) node.dataset.duration = String(m.duration);
        else delete node.dataset.duration;
        node.innerHTML = scToastHtml(m);
        scToastArm(node);
      }
    });
    byId.forEach((node, id) => {
      if (!seen.has(id) && node.parentNode) {
        scToastDisarm(node);
        node.parentNode.removeChild(node);
      }
    });
  }
  function scDismissToast(btn) {
    const node = btn.closest('.st-toast');
    if (node) scToastDismissNode(node);
  }

