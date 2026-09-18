  // -- SelectSlider: pick the option nearest the pointer (click or drag) --
  // The options themselves are hidden; only their values and labels matter
  // (see `.st-select-slider-options`).
  function scSelectSliderOptions(track) {
    return Array.from(track.querySelectorAll('.st-select-slider-option'));
  }
  function scSelectSliderNearest(track, clientX) {
    const rail = track.querySelector('.st-select-slider-rail');
    const n = scSelectSliderOptions(track).length;
    if (!rail || n <= 1) return 0;
    const rect = rail.getBoundingClientRect();
    if (!rect.width) return 0;
    const ratio = (clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
  }
  // Move the fill, the thumb and the value label onto `index`. The label is
  // centred on the thumb, then nudged back inside the widget so it does not
  // spill out at either end (as `st.select_slider` does). Nothing is committed
  // until `commit` is set.
  function scSelectSliderApply(track, index, commit) {
    const options = scSelectSliderOptions(track);
    const n = options.length;
    const pct = n <= 1 ? 0 : (index / (n - 1)) * 100;
    track.dataset.index = String(index);
    const fill = track.querySelector('.st-select-slider-fill');
    if (fill) fill.style.width = pct + '%';
    const thumb = track.querySelector('.st-select-slider-thumb');
    if (thumb) thumb.style.left = pct + '%';
    const root = track.closest('.st-select-slider');
    const label = root ? root.querySelector('.st-select-slider-value') : null;
    if (label && options[index]) {
      label.innerHTML = options[index].innerHTML;
      scSelectSliderPlace(track, label, pct);
    }
    if (!commit) return;
    const id = track.dataset.compId;
    const value = options[index] ? options[index].dataset.value : null;
    if (id && value !== null) {
      ws.send(JSON.stringify({
        type: 'event', id: id, event: 'change', value: value,
      }));
    }
  }
  function scSelectSliderPlace(track, label, pct) {
    const rail = track.querySelector('.st-select-slider-rail');
    if (!rail) return;
    const railRect = rail.getBoundingClientRect();
    const trackRect = track.getBoundingClientRect();
    const half = label.offsetWidth / 2;
    const x = railRect.left - trackRect.left + (pct / 100) * railRect.width;
    label.style.left =
      Math.max(half, Math.min(x, trackRect.width - half)) + 'px';
  }
  function scSelectSliderStart(ev, track) {
    ev.preventDefault();
    track._scIndex = scSelectSliderNearest(track, ev.clientX);
    scSelectSliderApply(track, track._scIndex, false);
    const move = (e) => {
      const idx = scSelectSliderNearest(track, e.clientX);
      if (idx !== track._scIndex) {
        track._scIndex = idx;
        scSelectSliderApply(track, idx, false);
      }
    };
    const up = () => {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      // A mouse press is always followed by `click`; flag it so the click
      // handler does not commit the same change a second time.
      track._scDragCommitted = true;
      scSelectSliderApply(track, track._scIndex, true);
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }
  // A plain click (no press, e.g. a synthetic `.click()`) still selects.
  function scSelectSliderClick(ev, track) {
    if (track._scDragCommitted) {
      track._scDragCommitted = false;
      return;
    }
    scSelectSliderApply(
      track, scSelectSliderNearest(track, ev.clientX), true
    );
  }

