"""
Compare the expanded `st.selectbox` (Streamlit) with `v3.Selectbox`
(Streamlit Canary): the popup chrome, the item geometry, and -- sampled frame
by frame with a `requestAnimationFrame` observer -- the colours the two apps
show while the popup opens and while the pointer slides over the items.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_selectbox_expanded.py

Pseudo-code (the spec this script implements):

    1. Expanding the selectbox must not repaint the control: its border is
       the theme red in the very first frame, and every item keeps one single
       colour -- no transient reddish tint fading in.
    2. Sliding the mouse over the items applies the highlight background
       immediately (a couple of frames at most, in the same colour Streamlit
       uses), and pressing an item leaves that highlight untouched.
    3. The items are 40px tall with a 28px highlight box (6px radius), so a
       three-option popup measures 122px.
    4. Two canary-only touches, both listed in
       `.trae/documents/pixel_fidelity_caveats.md`: the panel grows from 0 to
       its content height in 120ms while the chevron turns in 80ms (so the
       turn always lands before the panel is fully open), and clicking the
       control over and over keeps toggling it -- a double click never starts
       selecting the label the way Streamlit's control does.

The frame sampler is installed *before* the popup opens, so the very first
painted frame is captured; `analyse_open()` then reads the colour history out
of it. A fading colour shows up as more than one value in that history, which
is what turns the transient tint into a test failure instead of a matter of
opinion.
"""

import json
import re
import sys

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit's right-top "⋮" menu and its theme entries.
ST_MENU_BUTTON = '[data-testid="stMainMenuButton"]'
ST_THEME_DARK = '[data-testid="stMainMenuItem-theme-Dark"]'

# Streamlit renders the widget from BaseWeb/React-Aria parts; ours use classes.
# The popup of :2202 is the listbox' parent (it owns the background and the
# border), while ours is a single element.
ST_SELECTORS = {
    'control': '[data-testid="stSelectbox"] [role="group"]',
    'trigger': '[data-testid="stSelectbox"] [role="combobox"]',
    'arrow': '[data-testid="stSelectbox"] svg',
    'primary': '[data-testid="stBaseButton-primary"]',
    'listbox': '[role="listbox"]',
    'popup': '[role="listbox"]',
    'row': '[role="listbox"] [role="option"]',
    'inner': '[role="listbox"] [role="option"] > div',
}
SC_SELECTORS = {
    'control': '.st-selectbox-trigger',
    'trigger': '.st-selectbox-trigger',
    'arrow': '.st-selectbox-arrow',
    'primary': '.st-btn.st-btn-primary',
    'popup': '.st-selectbox-dropdown',
    'row': '.st-selectbox-option',
    'inner': '.st-selectbox-option-inner',
}

HOVER_ROW = 2
# The highlight has to be there "at once"; Streamlit's own 50ms fade costs
# ~3-4 frames at 60Hz, so the budget sits just above it to catch a fading
# highlight without being sensitive to jitter.
HOVER_FRAME_BUDGET = 6
EPS = 0.6

# Installed before the popup opens. Every frame records what the control and
# the items look like, so a colour that fades in shows up as a value history.
_WATCH_JS = """
(a) => {
  const popupEl = () => a.kind === 'st'
    ? (document.querySelector(a.listbox)
        ? document.querySelector(a.listbox).parentElement : null)
    : document.querySelector(a.popup);
  const rect = (e) => e.getBoundingClientRect();
  window.__frames = [];
  const t0 = performance.now();
  const tick = () => {
    const control = document.querySelector(a.control);
    const ccs = control ? getComputedStyle(control) : null;
    const popup = popupEl();
    window.__frames.push({
      t: +(performance.now() - t0).toFixed(1),
      open: !!popup && rect(popup).height > 0,
      border: ccs ? ccs.borderTopColor : null,
      shadow: ccs ? ccs.boxShadow : null,
      popup_h: popup ? +rect(popup).height.toFixed(2) : 0,
      popup_scroll_h: popup ? popup.scrollHeight : 0,
      popup_client_h: popup ? popup.clientHeight : 0,
      popup_overflow_y: popup ? getComputedStyle(popup).overflowY : null,
      rows: Array.from(document.querySelectorAll(a.row)).map((row) => {
        const inner = row.firstElementChild || row;
        const ics = getComputedStyle(inner);
        return {
          h: +rect(row).height.toFixed(2),
          ih: +rect(inner).height.toFixed(2),
          color: ics.color,
          bg: ics.backgroundColor,
        };
      }),
    });
    if (performance.now() - t0 < 1400) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return true;
}
"""

# Same idea, but the pointer position is tracked, so the frame in which the
# pointer enters an item is known. The highlight latency is then the number of
# frames the item's background takes to reach its final value from there.
_HOVER_WATCH_JS = """
(a) => {
  window.__hover = [];
  window.__px = -1;
  window.__py = -1;
  document.addEventListener('mousemove', (e) => {
    window.__px = e.clientX;
    window.__py = e.clientY;
  }, true);
  const t0 = performance.now();
  const tick = () => {
    const rows = Array.from(document.querySelectorAll(a.row));
    const at = document.elementFromPoint(window.__px, window.__py);
    let hit = -1;
    rows.forEach((row, i) => { if (row.contains(at)) hit = i; });
    window.__hover.push({
      t: +(performance.now() - t0).toFixed(1),
      hit,
      bgs: rows.map((row) => getComputedStyle(
        row.firstElementChild || row).backgroundColor),
    });
    if (performance.now() - t0 < 1200) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return true;
}
"""

_READ_JS = """
(a) => {
  const popupEl = a.kind === 'st'
    ? (document.querySelector(a.listbox)
        ? document.querySelector(a.listbox).parentElement : null)
    : document.querySelector(a.popup);
  const rect = (e) => e.getBoundingClientRect();
  const pick = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    const box = rect(el);
    return {
      width: +box.width.toFixed(2),
      height: +box.height.toFixed(2),
      radius: cs.borderTopLeftRadius,
      padding: cs.padding,
      font_size: cs.fontSize,
      line_height: cs.lineHeight,
      display: cs.display,
      align_items: cs.alignItems,
      background: cs.backgroundColor,
      color: cs.color,
      border: cs.borderTopWidth + ' ' + cs.borderTopColor,
      shadow: cs.boxShadow,
      transition: cs.transition,
    };
  };
  const control = document.querySelector(a.control);
  const rows = Array.from(document.querySelectorAll(a.row));
  return {
    control: pick(control),
    popup: pick(popupEl),
    row: pick(rows[0]),
    inner: pick(rows[0] ? rows[0].firstElementChild : null),
    primary: pick(document.querySelector(a.primary)),
    row_count: rows.length,
    row_heights: rows.map((r) => +rect(r).height.toFixed(2)),
    inner_heights: rows.map((r) =>
      +rect(r.firstElementChild).height.toFixed(2)),
    box_gaps: rows.slice(1).map((row, i) => {
      const prev = rows[i].firstElementChild || rows[i];
      const cur = row.firstElementChild || row;
      return +(rect(cur).top - rect(prev).bottom).toFixed(2);
    }),
    gap_below_control: popupEl && control
      ? +(rect(popupEl).top - rect(control).bottom).toFixed(2) : null,
  };
}
"""

_RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')


def parse_color(value) -> tuple[float, ...]:
    """Normalize a computed color to `(r, g, b, a)` for comparison."""
    match = _RGBA_RE.search(value) if isinstance(value, str) else None
    if match is None:
        return (float('nan'),) * 4
    parts = [x.strip() for x in match.group(1).split(',')]
    rgba = [float(x) for x in parts[:3]]
    rgba.append(float(parts[3]) if len(parts) > 3 else 1.0)
    return tuple(rgba)


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= EPS
    return str(a) == str(b)


def same_color(a: str, b: str) -> bool:
    return parse_color(a) == parse_color(b)


def is_dark_theme(page: Page) -> bool:
    bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
    r, g, b = parse_color(bg)[:3]
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance < 0.5


def toggle_dark_theme(page: Page) -> None:
    page.click(ST_MENU_BUTTON)
    page.click(ST_THEME_DARK)
    page.wait_for_timeout(800)


def analyse_open(frames: list[dict]) -> dict:
    """Summarise the colours the app showed while the popup was open."""
    opened = [frame for frame in frames if frame['open']]
    borders: list[str] = []
    shadows: list[str] = []
    for frame in opened:
        if frame['border'] not in borders:
            borders.append(frame['border'])
        if frame['shadow'] not in shadows:
            shadows.append(frame['shadow'])
    colours: list[list[str]] = []
    row_count = len(opened[0]['rows']) if opened else 0
    for i in range(row_count):
        seen: list[str] = []
        for frame in opened:
            row = frame['rows'][i] if i < len(frame['rows']) else None
            if row is not None and row['color'] not in seen:
                seen.append(row['color'])
        colours.append(seen)
    first = opened[0] if opened else {'rows': []}
    # The panel's entry: how many distinct heights it passed through, and
    # whether the frames in which it was still shorter than its content kept
    # that content clipped (a scrollbar would flash otherwise).
    heights: list[float] = []
    full = max((frame['popup_h'] for frame in opened), default=0)
    clipped = True
    for frame in opened:
        if frame['popup_h'] not in heights:
            heights.append(frame['popup_h'])
        if frame['popup_h'] >= full - EPS:
            continue
        if frame['popup_scroll_h'] <= frame['popup_client_h']:
            continue
        if frame['popup_overflow_y'] != 'hidden':
            clipped = False
    return {
        'frame_count': len(opened),
        'borders': borders,
        'shadows': shadows,
        'colours': colours,
        'repaints': sum(len(seen) - 1 for seen in colours),
        'first_backgrounds': [row['bg'] for row in first['rows']],
        'first_colours': [row['color'] for row in first['rows']],
        'heights': heights,
        'clipped_while_growing': clipped,
    }


def last(values: list):
    return values[-1] if values else None


def within_frames(value, budget: int = HOVER_FRAME_BUDGET) -> bool:
    return value is not None and value <= budget


def open_and_watch(page: Page, selectors: dict, kind: str) -> dict:
    """Open the dropdown while sampling every frame, then summarise it."""
    page.evaluate(_WATCH_JS, dict(selectors, kind=kind))
    control = page.locator(selectors['control']).first.bounding_box()
    assert control is not None, 'no box: {}'.format(selectors['control'])
    page.mouse.click(
        control['x'] + control['width'] / 2,
        control['y'] + control['height'] / 2,
    )
    page.wait_for_timeout(1500)
    return analyse_open(page.evaluate('window.__frames'))


def hover_latency(page: Page, selectors: dict, index: int) -> dict:
    """Slide the pointer onto item `index` and time the highlight."""
    page.mouse.move(900, 700)
    page.evaluate(_HOVER_WATCH_JS, selectors)
    page.wait_for_timeout(200)
    row = page.locator(selectors['row']).nth(index).bounding_box()
    page.mouse.move(row['x'] + row['width'] / 2, row['y'] + row['height'] / 2)
    page.wait_for_timeout(1000)
    samples = page.evaluate('window.__hover')
    entry = next((i for i, s in enumerate(samples) if s['hit'] == index), None)
    assert entry is not None, 'the pointer never entered item {}'.format(index)
    final = samples[-1]['bgs'][index]
    frames_to_final = None
    for i in range(entry, len(samples)):
        if samples[i]['bgs'][index] == final:
            frames_to_final = i - entry
            break
    return {'frames_to_final': frames_to_final, 'background': final}


def pressed_background(page: Page, selectors: dict, index: int) -> str:
    """Hold the mouse down on item `index` and read its background.

    The pointer is moved off the item before the button is released, so the
    press never turns into a selection and the app state stays untouched.
    """
    page.mouse.down()
    page.wait_for_timeout(250)
    value = page.evaluate(
        """(a) => {
          const rows = document.querySelectorAll(a.row);
          const inner = rows[a.index].firstElementChild || rows[a.index];
          return getComputedStyle(inner).backgroundColor;
        }""",
        dict(selectors, index=index),
    )
    page.mouse.move(900, 700)
    page.mouse.up()
    page.wait_for_timeout(300)
    return value


def primary_color(page: Page, selectors: dict) -> str:
    """The app's primary colour, read off its primary button."""
    return page.evaluate(
        '(sel) => getComputedStyle(document.querySelector(sel))'
        '.backgroundColor',
        selectors['primary'],
    )


def read(page: Page, selectors: dict, kind: str) -> dict:
    return page.evaluate(_READ_JS, dict(selectors, kind=kind))


# The chevron/panel animation and the control's click behaviour: a canary-only
# touch, so `animation()` + the section 5 checks below assert on each app's own
# expectation instead of comparing raw values.
_ANIM_JS = """
(a) => {
  const trig = document.querySelector(a.trigger);
  const arrow = document.querySelector(a.arrow);
  const popup = a.popup ? document.querySelector(a.popup) : null;
  const acs = arrow ? getComputedStyle(arrow) : null;
  return JSON.stringify({
    expanded: trig ? trig.getAttribute('aria-expanded') === 'true' : false,
    arrow_transform: acs ? acs.transform : null,
    arrow_duration: acs ? parseFloat(acs.transitionDuration) : null,
    popup_duration: popup
      ? parseFloat(getComputedStyle(popup).animationDuration) : null,
    selection: String(window.getSelection()),
  });
}
"""


def animation(page: Page, selectors: dict) -> dict:
    return json.loads(page.evaluate(_ANIM_JS, selectors))


def open_if_needed(page: Page, selectors: dict) -> None:
    """Section 4's press may have closed the dropdown; re-open it if so."""
    if not animation(page, selectors)['expanded']:
        page.locator(selectors['trigger']).first.click()
        page.wait_for_timeout(500)


def click_trigger(page: Page, selectors: dict, double: bool = False) -> None:
    """Click the trigger (or double-click it) the way a user toggles it."""
    locator = page.locator(selectors['trigger']).first
    if double:
        locator.dblclick()
    else:
        locator.click()
    page.wait_for_timeout(500)


def clear_selection(page: Page) -> None:
    """Drop any selection the earlier sections may have left behind.

    Section 4 releases the mouse button away from the item it pressed, so the
    drag sweeps across the page and selects whatever text is on the way. That
    selection has nothing to do with the control, hence the reset before the
    repeated-click checks.
    """
    page.evaluate('window.getSelection().removeAllRanges()')


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, bool]] = []

    def add(self, label: str, st_val, sc_val, cmp=same) -> None:
        self.rows.append(
            (label, str(st_val), str(sc_val), bool(cmp(st_val, sc_val)))
        )

    def add_predicate(self, label: str, st_ok, sc_ok) -> None:
        self.rows.append(
            (
                label,
                str(bool(st_ok)),
                str(bool(sc_ok)),
                bool(st_ok) and bool(sc_ok),
            )
        )

    def print(self) -> None:
        width = max(len(row[0]) for row in self.rows)
        print('')
        print(
            '{:<{w}} {:<34} {:<34} {}'.format(
                'check', 'streamlit (:2202)', 'canary (:2203)', 'ok', w=width
            )
        )
        print('-' * 118)
        for label, st_val, sc_val, ok in self.rows:
            print(
                '{:<{w}} {:<34} {:<34} {}'.format(
                    label, st_val, sc_val, 'YES' if ok else 'NO', w=width
                )
            )

    @property
    def failures(self) -> list[tuple[str, str, str]]:
        return [
            (label, st_val, sc_val)
            for label, st_val, sc_val, ok in self.rows
            if not ok
        ]


def main() -> int:
    report = Report()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_SELECTORS['control'], timeout=20000)
        st_page.wait_for_timeout(1200)
        if not is_dark_theme(st_page):
            toggle_dark_theme(st_page)
        assert is_dark_theme(st_page), 'failed to switch Streamlit to dark'

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_SELECTORS['control'], timeout=20000)
        sc_page.wait_for_timeout(1200)
        assert is_dark_theme(sc_page), 'streamlit-canary is not dark themed'

        st_primary = primary_color(st_page, ST_SELECTORS)
        sc_primary = primary_color(sc_page, SC_SELECTORS)
        report.add('primary colour', st_primary, sc_primary, same_color)

        # -- 1. expanding must not repaint the control ------------------
        st_open = open_and_watch(st_page, ST_SELECTORS, 'st')
        sc_open = open_and_watch(sc_page, SC_SELECTORS, 'sc')
        report.add_predicate(
            'the popup really opened',
            st_open['frame_count'] > 0,
            sc_open['frame_count'] > 0,
        )
        report.add_predicate(
            'opening keeps one border colour',
            len(st_open['borders']) == 1 and len(st_open['shadows']) == 1,
            len(sc_open['borders']) == 1 and len(sc_open['shadows']) == 1,
        )
        report.add(
            'control border while opening',
            ' -> '.join(st_open['borders']),
            ' -> '.join(sc_open['borders']),
        )
        report.add_predicate(
            'the border is the theme red at once',
            same_color(last(st_open['borders']), st_primary),
            same_color(last(sc_open['borders']), sc_primary),
        )
        report.add_predicate(
            'the focus border comes without a ring',
            st_open['shadows'] == ['none'],
            sc_open['shadows'] == ['none'],
        )
        report.add_predicate(
            'items never repaint while opening',
            st_open['repaints'] == 0,
            sc_open['repaints'] == 0,
        )
        # The panel's entry is a canary-only height animation: it grows from 0
        # to its content height over several frames, while Streamlit's popup
        # appears at full height in a single frame. Clipping is what keeps the
        # items from spilling out of the still-short panel and keeps a
        # scrollbar from flashing -- for Streamlit there is no mid-growth frame
        # at all, so the check holds trivially.
        report.add_predicate(
            'the panel grows over several frames (canary only)',
            len(st_open['heights']) == 1,
            len(sc_open['heights']) > 1,
        )
        report.add_predicate(
            'the growing panel clips instead of scrolling',
            st_open['clipped_while_growing'],
            sc_open['clipped_while_growing'],
        )
        # Shown for reference only -- the two apps are expected to differ here,
        # so the row is never compared.
        report.add(
            'panel heights while opening (not compared)',
            ', '.join(str(h) for h in st_open['heights']),
            ', '.join(str(h) for h in sc_open['heights']),
            cmp=lambda _a, _b: True,
        )
        # Streamlit marks the current selection with the highlight background,
        # we mark it with the theme colour of the item's text. Which item is
        # the current one is up to the app, so any item may carry the mark.
        report.add_predicate(
            'the current selection is marked in the list',
            any(
                bg != 'rgba(0, 0, 0, 0)' for bg in st_open['first_backgrounds']
            ),
            any(
                same_color(color, sc_primary)
                for color in sc_open['first_colours']
            ),
        )

        # -- 2. the highlight appears immediately ----------------------
        st_hover = hover_latency(st_page, ST_SELECTORS, HOVER_ROW)
        sc_hover = hover_latency(sc_page, SC_SELECTORS, HOVER_ROW)
        report.add(
            'hover highlight delay (frames, budget {})'.format(
                HOVER_FRAME_BUDGET
            ),
            st_hover['frames_to_final'],
            sc_hover['frames_to_final'],
            cmp=lambda a, b: within_frames(a) and within_frames(b),
        )
        report.add(
            'hover highlight colour',
            st_hover['background'],
            sc_hover['background'],
            same_color,
        )

        # -- 3. geometry ----------------------------------------------
        st = read(st_page, ST_SELECTORS, 'st')
        sc = read(sc_page, SC_SELECTORS, 'sc')
        report.add('item count', st['row_count'], sc['row_count'])
        report.add(
            'item height', max(st['row_heights']), max(sc['row_heights'])
        )
        report.add(
            'highlight box height',
            max(st['inner_heights']),
            max(sc['inner_heights']),
        )
        report.add(
            'highlight box radius', st['inner']['radius'], sc['inner']['radius']
        )
        report.add(
            'highlight box width', st['inner']['width'], sc['inner']['width']
        )
        report.add_predicate(
            'the highlight box fills the item row',
            st['inner']['width'] - (st['row']['width'] - 10) <= EPS,
            sc['inner']['width'] - (sc['row']['width'] - 10) <= EPS,
        )
        report.add(
            'gap between the highlight boxes',
            ', '.join(str(gap) for gap in st['box_gaps']),
            ', '.join(str(gap) for gap in sc['box_gaps']),
        )
        report.add(
            'item font size', st['inner']['font_size'], sc['inner']['font_size']
        )
        report.add('popup height', st['popup']['height'], sc['popup']['height'])
        report.add(
            'popup padding', st['popup']['padding'], sc['popup']['padding']
        )
        report.add(
            'popup background',
            st['popup']['background'],
            sc['popup']['background'],
            same_color,
        )
        report.add('popup border', st['popup']['border'], sc['popup']['border'])
        report.add('popup radius', st['popup']['radius'], sc['popup']['radius'])
        report.add(
            'gap below the control',
            st['gap_below_control'],
            sc['gap_below_control'],
        )
        report.add(
            'control height', st['control']['height'], sc['control']['height']
        )
        report.add(
            'control background',
            st['control']['background'],
            sc['control']['background'],
            same_color,
        )

        # -- 4. pressing an item (this closes the popup) ----------------
        st_pressed = pressed_background(st_page, ST_SELECTORS, HOVER_ROW)
        sc_pressed = pressed_background(sc_page, SC_SELECTORS, HOVER_ROW)
        report.add(
            'pressed highlight',
            st_pressed,
            sc_pressed,
            cmp=lambda a, b: (
                same_color(a, st_hover['background'])
                and same_color(b, sc_hover['background'])
            ),
        )

        # -- 5. canary-only chevron turn + repeated-click toggling ------
        # Both are deliberate differences, listed as such in
        # .trae/documents/pixel_fidelity_caveats.md: the chevron turns (80ms)
        # while the panel grows (120ms) -- the turn lands first, so the panel
        # is never fully open with the chevron still halfway -- and the
        # control can be clicked over and over to collapse/expand it instead
        # of turning into a text selection.
        open_if_needed(st_page, ST_SELECTORS)
        open_if_needed(sc_page, SC_SELECTORS)
        st_anim = animation(st_page, ST_SELECTORS)
        sc_anim = animation(sc_page, SC_SELECTORS)
        report.add_predicate(
            'the chevron turns on expand (canary only)',
            st_anim['arrow_transform'] == 'none',
            sc_anim['arrow_transform'] == 'matrix(-1, 0, 0, -1, 0, 0)',
        )
        report.add_predicate(
            'the chevron turn is no slower than the panel growth',
            st_anim['arrow_duration'] <= st_anim['popup_duration'],
            sc_anim['arrow_duration'] <= sc_anim['popup_duration'],
        )
        # Shown for reference only: the canary's two clocks (80ms for the turn,
        # 120ms for the growth) against Streamlit's single frame.
        report.add(
            'turn / growth duration (not compared)',
            '{} / {}'.format(
                st_anim['arrow_duration'], st_anim['popup_duration']
            ),
            '{} / {}'.format(
                sc_anim['arrow_duration'], sc_anim['popup_duration']
            ),
            cmp=lambda _a, _b: True,
        )
        clear_selection(st_page)
        clear_selection(sc_page)
        click_trigger(st_page, ST_SELECTORS)
        click_trigger(sc_page, SC_SELECTORS)
        st_again = animation(st_page, ST_SELECTORS)
        sc_again = animation(sc_page, SC_SELECTORS)
        report.add_predicate(
            'a repeat click collapses the dropdown (canary only)',
            st_again['expanded'],
            not sc_again['expanded'],
        )
        # A double click is where the two apps really part ways: Streamlit's
        # control has no `user-select: none` guard, so the second press starts
        # selecting its label, while ours keeps toggling.
        clear_selection(st_page)
        clear_selection(sc_page)
        click_trigger(st_page, ST_SELECTORS, double=True)
        click_trigger(sc_page, SC_SELECTORS, double=True)
        st_sel = animation(st_page, ST_SELECTORS)['selection']
        sc_sel = animation(sc_page, SC_SELECTORS)['selection']
        report.add_predicate(
            'a double click selects no text (canary only)',
            st_sel != '',
            sc_sel == '',
        )

        report.print()
        browser.close()

    if report.failures:
        print('')
        print('FAILED ({} mismatch(es)):'.format(len(report.failures)))
        for label, st_val, sc_val in report.failures:
            print(
                '  {label}: streamlit={st} canary={sc}'.format(
                    label=label, st=st_val, sc=sc_val
                )
            )
        return 1

    print('')
    print('PASSED: all asserted props match.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except AssertionError as e:
        print('')
        print('ERROR: {}'.format(e))
        sys.exit(2)
