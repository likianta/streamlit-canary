"""
Compare the popover layout of `st.popover` (Streamlit) with `v3.Popover`
(Streamlit Canary), measured with the popover expanded.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_popover_layout.py

Pseudo-code (the spec this script implements):

    1. The panel is anchored just below the trigger -- 8px below it in the
       canary, where Streamlit leaves 4px (a deliberate deviation, asserted
       explicitly against `TOP_MARGIN_SC` / `TOP_MARGIN_ST`). It is laid out
       inside the app content box: a panel wider than the room left of the
       trigger is shifted leftward so that it stays fully visible, and it
       never hugs the window's right edge.
    2. The panel wraps the expanded container: its height is the content
       height plus the panel padding and border, with no inner scrolling and
       nothing clipped.
    3. The expanded container holds a `Tabs` whose first panel is a row: the
       weighted columns `(5, 2)` come first, then a button that keeps its
       intrinsic width.
    4. Every geometry above matches Streamlit's within a sub-pixel epsilon.
       Positions *below* the panel's top edge are compared as offsets from it
       (`RELATIVE_CHECKS`), so the top-margin deviation does not skew them.

Only geometry is compared (sizes, spacing, alignment). Colours belong to the
theme and are covered by `compare_primary_button_style.py`.
"""

import sys

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit renders the popover body in a portal (`stPopoverBody`) holding the
# `width=540` container, the tab bar and the tab panel's horizontal row.
ST_SELECTORS = {
    'trigger': '[data-testid="stPopover"]',
    'panel': '[data-testid="stPopoverBody"]',
    'container': '[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"]',
    'tabs': '[data-testid="stPopoverBody"] [data-testid="stTabs"]',
    'tabList': '[data-testid="stPopoverBody"] [data-baseweb="tab-list"]',
    'row': '[data-testid="stPopoverBody"] [data-testid="stHorizontalBlock"]',
    'column': '[data-testid="stPopoverBody"] [data-testid="stColumn"]',
    'button': '[data-testid="stPopoverBody"] [data-testid="stButton"]',
    'numberInput': (
        '[data-testid="stPopoverBody"] [data-testid="stNumberInput"]'
    ),
}
SC_SELECTORS = {
    'trigger': '.st-popover-trigger',
    'panel': '.st-popover-panel',
    'container': '.st-popover-panel > .st-container',
    'tabs': '.st-popover-panel .st-tabs',
    'tabList': '.st-popover-panel .st-tabs-bar',
    'row': '.st-popover-panel .st-row',
    'column': '.st-popover-panel .st-grid-cell',
    'button': '.st-popover-panel .st-btn',
    'numberInput': '.st-popover-panel .st-number-input',
}

_READ_JS = """
(config) => {
  const one = (sel, i = 0) => document.querySelectorAll(sel)[i] || null;
  const box = (sel, i = 0) => {
    const el = one(sel, i);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      left: r.left, top: r.top, right: r.right, bottom: r.bottom,
      width: r.width, height: r.height,
    };
  };
  const px = (value) => (value ? parseFloat(value) : 0);
  const panel = one(config.panel);
  const cs = panel ? getComputedStyle(panel) : null;
  return {
    viewport: { width: window.innerWidth, height: window.innerHeight },
    panel: panel ? Object.assign(box(config.panel), {
      open: !panel.hidden,
      scrollHeight: panel.scrollHeight,
      clientHeight: panel.clientHeight,
      overflowY: cs.overflowY,
      padding: {
        top: px(cs.paddingTop), right: px(cs.paddingRight),
        bottom: px(cs.paddingBottom), left: px(cs.paddingLeft),
      },
      border: px(cs.borderTopWidth),
      radius: px(cs.borderTopLeftRadius),
    }) : null,
    trigger: box(config.trigger),
    container: box(config.container),
    tabs: box(config.tabs),
    tabList: box(config.tabList),
    row: box(config.row),
    columns: [box(config.column, 0), box(config.column, 1)],
    button: box(config.button),
    numberInputs: Array.from(document.querySelectorAll(config.numberInput))
      .map((e) => {
        const r = e.getBoundingClientRect();
        return {
          left: r.left, top: r.top, right: r.right, bottom: r.bottom,
          width: r.width, height: r.height,
        };
      }),
  };
}
"""

EPS = 0.6

# The gap between the trigger's bottom edge and the panel's top edge. Ours is a
# deliberate deviation: the canary hangs every panel 8px below its trigger,
# Streamlit leaves 4px. It is measured explicitly below (and registered in
# `.trae/documents/pixel_fidelity_caveats.md`).
TOP_MARGIN_ST = 4.0
TOP_MARGIN_SC = 8.0

# Geometry that must match Streamlit exactly (addressed with a dotted path).
EQUALITY_CHECKS = (
    'panel.width',
    'panel.height',
    'panel.left',
    'panel.right',
    'panel.padding.top',
    'panel.padding.right',
    'panel.padding.bottom',
    'panel.padding.left',
    'panel.border',
    'panel.radius',
    'container.left',
    'container.width',
    'container.height',
    'tabs.width',
    'tabs.height',
    'button.left',
    'button.width',
    'button.height',
    'trigger.right',
)

# Vertical positions *below* the panel's top edge are compared as offsets from
# it, so the 4px difference in `TOP_MARGIN_*` does not skew them: everything
# inside the panel sits exactly where Streamlit puts it.
RELATIVE_CHECKS = (
    'container.bottom',
    'tabs.bottom',
    'row.bottom',
    'button.bottom',
)


def value(state: dict, path: str):
    """Read a dotted path (`'panel.padding.left'`) out of a state dict."""
    node = state
    for key in path.split('.'):
        if node is None:
            return None
        node = node[key]
    return node


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= EPS
    return str(a) == str(b)


def wait_for_fonts(page: Page) -> None:
    """Wait until the webfonts have settled.

    The text metrics decide the tab bar height, so measuring before the font
    is applied skews every vertical value by a fraction of a pixel.
    """
    page.evaluate('() => document.fonts.ready.then(() => true)')


def dismiss_rerun_notice(page: Page) -> None:
    """Dismiss the dev-time "source file changed" notice, if present.

    While it is visible the page reserves 76px of top padding for it, which
    would shift the whole app down and skew every vertical measurement.
    """
    close = page.locator('#sc-rerun-toast .st-rerun-close')
    if close.count() == 0 or not close.first.is_visible():
        return
    close.first.click()
    page.wait_for_selector('body.sc-rerun-visible', state='detached')
    page.wait_for_timeout(200)


def open_popover(page: Page, selectors: dict) -> None:
    """Click the trigger and wait until the floating panel is visible."""
    panel = page.locator(selectors['panel']).first
    already_open = panel.count() > 0 and panel.is_visible()
    if not already_open:
        page.locator(selectors['trigger']).first.click()
    panel.wait_for(state='visible', timeout=10000)
    # Let the panel settle (`scPositionPopover` runs on the same tick).
    page.wait_for_timeout(400)


def read_state(page: Page, selectors: dict) -> dict:
    state = page.evaluate(_READ_JS, selectors)
    assert state['panel'] is not None, 'popover panel not found'
    return state


def inner_gap(state: dict, edge: str) -> float:
    """The panel's padding + border above / below its content."""
    panel = state['panel']
    return abs(state['container'][edge] - panel[edge])


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
            '{:<{w}} {:<30} {:<30} {}'.format(
                'check', 'streamlit (:2202)', 'canary (:2203)', 'ok', w=width
            )
        )
        print('-' * 110)
        for label, st_val, sc_val, ok in self.rows:
            print(
                '{:<{w}} {:<30} {:<30} {}'.format(
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


def compare(report: Report, st: dict, sc: dict) -> None:
    # -- 1. the panel wraps the expanded container ------------------------
    report.add_predicate(
        'panel is expanded', st['panel']['open'], sc['panel']['open']
    )
    report.add_predicate(
        'panel has no inner scrolling',
        st['panel']['scrollHeight'] <= st['panel']['clientHeight'] + 1,
        sc['panel']['scrollHeight'] <= sc['panel']['clientHeight'] + 1,
    )
    report.add_predicate(
        'panel contains the expanded container',
        st['container']['top'] >= st['panel']['top']
        and st['container']['bottom'] <= st['panel']['bottom'],
        sc['container']['top'] >= sc['panel']['top']
        and sc['container']['bottom'] <= sc['panel']['bottom'],
    )
    report.add(
        'content top - panel top', inner_gap(st, 'top'), inner_gap(sc, 'top')
    )
    report.add(
        'panel bottom - content bottom',
        inner_gap(st, 'bottom'),
        inner_gap(sc, 'bottom'),
    )

    # -- 2. the panel stays visible inside the app content box ------------
    report.add_predicate(
        'panel left of the window right edge by >= 16px',
        st['viewport']['width'] - st['panel']['right'] >= 16,
        sc['viewport']['width'] - sc['panel']['right'] >= 16,
    )
    report.add_predicate(
        'panel is fully inside the viewport',
        st['panel']['left'] >= 0
        and st['panel']['right'] <= st['viewport']['width'],
        sc['panel']['left'] >= 0
        and sc['panel']['right'] <= sc['viewport']['width'],
    )
    report.add_predicate(
        'panel starts below the trigger',
        st['panel']['top'] >= st['trigger']['bottom'],
        sc['panel']['top'] >= sc['trigger']['bottom'],
    )
    # The top margin is the one *intentional* difference: assert both apps
    # against their own expected value (4px upstream, 8px ours).
    report.add(
        'panel top margin ({}px streamlit / {}px canary)'.format(
            int(TOP_MARGIN_ST), int(TOP_MARGIN_SC)
        ),
        st['panel']['top'] - st['trigger']['bottom'],
        sc['panel']['top'] - sc['trigger']['bottom'],
        cmp=lambda a, b: (
            abs(a - TOP_MARGIN_ST) <= EPS and abs(b - TOP_MARGIN_SC) <= EPS
        ),
    )
    for path in RELATIVE_CHECKS:
        report.add(
            '{} - panel.top'.format(path),
            value(st, path) - st['panel']['top'],
            value(sc, path) - sc['panel']['top'],
        )

    # -- 3. the row inside the tab panel: columns first, then the button --
    report.add_predicate(
        'columns sit to the left of the button',
        st['columns'][1]['right'] < st['button']['left'],
        sc['columns'][1]['right'] < sc['button']['left'],
    )
    for index, name in enumerate(('line length', 'bias')):
        report.add(
            'column "{}" width'.format(name),
            st['columns'][index]['width'],
            sc['columns'][index]['width'],
        )
        report.add(
            'number input "{}" width'.format(name),
            st['numberInputs'][index]['width'],
            sc['numberInputs'][index]['width'],
        )
        report.add(
            'number input "{}" left'.format(name),
            st['numberInputs'][index]['left'],
            sc['numberInputs'][index]['left'],
        )

    # -- 4. the shared geometry ------------------------------------------
    for path in EQUALITY_CHECKS:
        report.add(path, value(st, path), value(sc, path))


def main() -> int:
    report = Report()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_SELECTORS['trigger'], timeout=20000)
        wait_for_fonts(st_page)
        dismiss_rerun_notice(st_page)
        open_popover(st_page, ST_SELECTORS)

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_SELECTORS['trigger'], timeout=20000)
        wait_for_fonts(sc_page)
        dismiss_rerun_notice(sc_page)
        open_popover(sc_page, SC_SELECTORS)

        st = read_state(st_page, ST_SELECTORS)
        sc = read_state(sc_page, SC_SELECTORS)
        compare(report, st, sc)

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
