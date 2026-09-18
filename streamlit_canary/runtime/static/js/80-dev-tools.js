  // -- Source-change notice (kept, no longer wired up) -------------------
  // TODO or DELETE: file watcher & reload banner needs to be refactored or
  // be deleted. Nothing calls these any more: the server stops watching its
  // source files, and a rerun is a manual action from the toolbar.
  function scRerunToast() {
    let el = document.getElementById('sc-rerun-toast');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-rerun-toast';
    el.className = 'st-rerun-toast';
    el.hidden = true;
    el.innerHTML =
      '<span class="st-rerun-icon">\u21bb</span>' +
      '<span class="st-rerun-body">' +
      '<span class="st-rerun-title">Source file changed</span>' +
      '<span class="st-rerun-detail"></span></span>' +
      '<button class="st-rerun-btn" type="button" ' +
      'onclick="scRerun()">Rerun</button>' +
      '<button class="st-rerun-close" type="button" title="Dismiss" ' +
      'onclick="scDismissRerun()">\u2715</button>';
    document.body.appendChild(el);
    return el;
  }
  // The notice is `position: fixed`, so the body reserves top padding while
  // it is visible (see `body.sc-rerun-visible` in page.css) to keep it from
  // covering the app.
  function scSetRerunVisible(visible) {
    const el = scRerunToast();
    el.hidden = !visible;
    document.body.classList.toggle('sc-rerun-visible', !!visible);
  }
  function scShowRerunToast(files) {
    const el = scRerunToast();
    if (!files.length) { scSetRerunVisible(false); return; }
    el.querySelector('.st-rerun-title').textContent = 'Source file changed';
    el.querySelector('.st-rerun-detail').textContent =
      files.length === 1 ? files[0] : files.length + ' files changed';
    el.classList.remove('is-reloading');
    el.querySelector('.st-rerun-btn').disabled = false;
    scSetRerunVisible(true);
  }
  function scDismissRerun() {
    // Client-side only: the pending change stays known to the server, so
    // reloading the page (or editing again) brings the notice back and the
    // rerun stays reachable.
    scSetRerunVisible(false);
  }
  function scRerun(onTimeout) {
    try { ws.send(JSON.stringify({ type: 'rerun' })); } catch (e) {}
    scWaitForServer(onTimeout);
  }
  // A rerun re-executes the server process (see reload.py); poll until it
  // answers again, then reload the page so the fresh render is picked up.
  // The caller owns the "waiting" feedback -- the toolbar and the exception
  // panel each label their own Rerun button -- and learns from `onTimeout`
  // that the process never came back.
  let scServerPending = false;
  function scWaitForServer(onTimeout) {
    if (scServerPending) return;
    scServerPending = true;
    let tries = 0;
    const poll = () => {
      tries += 1;
      fetch('/healthz?_=' + Date.now(), { cache: 'no-store' })
        .then(r => { if (!r.ok) throw new Error('not ready'); location.reload(); })
        .catch(() => {
          if (tries < 50) { setTimeout(poll, 400); return; }
          scServerPending = false;
          if (onTimeout) onTimeout();
        });
    };
    setTimeout(poll, 400);
  }

  // -- Uncaught exception panel ------------------------------------------
  // A handler that raises is caught by the runtime and arrives here as one
  // `traceback.format_exception` string (see `Runtime._report_error`).
  // Unlike a rerun-based app, the tree survives the error, so the panel has
  // nothing to repair -- it only has to be visible and dismissable. Its
  // Rerun button restarts the process, exactly like the source-change
  // notice, which is what "ignore this error and run again" needs.
  function scErrorPanel() {
    let el = document.getElementById('sc-error-panel');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'sc-error-panel';
    el.className = 'st-error-panel';
    el.hidden = true;
    // Streamlit titles its exception box with the error's last line and
    // keeps the whole traceback underneath, which is what we mirror.
    el.innerHTML =
      '<span class="st-error-head">' +
      '<span class="st-error-title"></span>' +
      '<button class="st-rerun-close" type="button" title="Dismiss" ' +
      'onclick="scDismissError()">\u2715</button></span>' +
      '<pre class="st-error-body"></pre>' +
      '<div class="st-error-actions">' +
      // same button as the source-change notice, hence the shared class
      '<button class="st-rerun-btn" type="button" ' +
      'onclick="scSendErrorRerun()">Rerun</button></div>';
    document.body.appendChild(el);
    return el;
  }
  function scShowError(message) {
    const el = scErrorPanel();
    const text = String(message == null ? '' : message).replace(/\s+$/, '');
    const lines = text.split('\n');
    el.querySelector('.st-error-title').textContent =
      lines[lines.length - 1] || 'Uncaught exception';
    el.querySelector('.st-error-body').textContent = text;
    const btn = el.querySelector('.st-rerun-btn');
    btn.textContent = 'Rerun';
    btn.disabled = false;
    el.hidden = false;
  }
  // The panel floats over the app, and the app stays usable after an error,
  // so it must be possible to get it out of the way without restarting the
  // process (dismissing only hides it; the next error brings it back).
  function scDismissError() {
    scErrorPanel().hidden = true;
  }
  function scSendErrorRerun() {
    const btn = scErrorPanel().querySelector('.st-rerun-btn');
    btn.disabled = true;
    btn.textContent = 'Reloading\u2026';
    scRerun(() => { btn.textContent = 'Server did not come back'; });
  }

