  // -- AltairChart: draw Vega-Lite specs with vega-embed (lazy CDN load) --
  // `vega`, `vega-lite` and `vega-embed` are pulled in on first use and
  // cached for the lifetime of the page. vega-embed expects both globals to
  // be present, so the scripts are loaded in order.
  const SC_VEGA_URLS = [
    'https://cdn.jsdelivr.net/npm/vega@6',
    'https://cdn.jsdelivr.net/npm/vega-lite@6',
    'https://cdn.jsdelivr.net/npm/vega-embed@7',
  ];
  let scVegaEmbedPromise = null;
  function scLoadVega() {
    if (scVegaEmbedPromise) return scVegaEmbedPromise;
    const loadScript = (src) => new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.async = false;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('failed to load ' + src));
      document.head.appendChild(s);
    });
    scVegaEmbedPromise = SC_VEGA_URLS
      .reduce((p, src) => p.then(() => loadScript(src)), Promise.resolve())
      .then(() => (typeof window.vegaEmbed === 'function' ? window.vegaEmbed : null))
      .catch(() => null);
    return scVegaEmbedPromise;
  }
  // Vega-Lite's built-in config is light. Feed it the app's theme tokens so
  // the chart follows the page (dark chart on a dark page), the way
  // Streamlit's `st.altair_chart` does.
  function scVegaThemeConfig() {
    const css = getComputedStyle(document.documentElement);
    const token = (name, fallback) => {
      const value = css.getPropertyValue(name).trim();
      return value || fallback;
    };
    const background = token('--st-background-color', '#ffffff');
    const axisColor = token('--st-heading-color', '#1f2328');
    const gridColor = token('--st-border-color', '#d0d7de');
    const titleColor = token('--st-text-color', '#1f2328');
    return {
      background,
      axis: {
        labelColor: axisColor,
        titleColor: axisColor,
        domainColor: gridColor,
        tickColor: gridColor,
        gridColor,
        labelFontSize: 12,
        titleFontSize: 14,
      },
      legend: { labelColor: axisColor, titleColor: axisColor },
      title: { color: titleColor, fontSize: 14, fontWeight: 'bold' },
    };
  }
  function scRenderVegaLite(el, spec) {
    const canvas = el.querySelector('.st-altair-canvas');
    if (!canvas) return;
    if (!spec) {
      canvas.innerHTML = '';
      el.removeAttribute('data-sc-rendered');
      return;
    }
    scLoadVega().then((embed) => {
      if (!embed) return;
      // vega-embed replaces the container's content; a stale render is
      // discarded so rapid `chart` patches don't interleave.
      embed(canvas, spec, {
        actions: false,
        config: scVegaThemeConfig(),
        renderer: 'svg',
      })
        .then(() => { el.setAttribute('data-sc-rendered', '1'); })
        .catch(() => {});
    });
  }
  function scInitAltairCharts() {
    document.querySelectorAll('.st-altair-chart').forEach((el) => {
      if (el.dataset.scInitialized) return;
      el.dataset.scInitialized = '1';
      const script = el.querySelector('.st-altair-spec');
      if (!script) return;
      try {
        scRenderVegaLite(el, JSON.parse(script.textContent));
      } catch (e) {}
    });
  }

