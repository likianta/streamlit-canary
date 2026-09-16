"""
Compare the primary button style between Streamlit and Streamlit Canary.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_primary_button_style.py

Pseudo-code (the assertions this script implements):

    st_app = open_browser(localhost:2202)

    def is_dark_theme() -> bool: ...
    def toggle_dark_theme(): ...

    if not is_dark_theme(st_app):
        toggle_dark_theme(st_app)

    st_btn = st_app.find_element(start_eye_monitor_button)

    sc_app = open_browser(localhost:2203)
    assert is_dark_theme(sc_app)

    sc_btn = sc_app.find_element(start_eye_monitor_button)

    assert sc_btn.height == st_btn.height
    assert sc_btn.border_radius == st_btn.border_radius

    for state in (before_enter, enter, pressdown, leave):
        assert sc_btn.background == st_btn.background
        assert sc_btn.border_color == st_btn.border_color
"""

import re
import sys
import typing as tp

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit renders buttons with a `data-testid`; ours use a class.
ST_BUTTON = '[data-testid="stBaseButton-primary"]'
SC_BUTTON = '.st-btn.st-btn-primary'

# The element that actually renders the label text. Streamlit's `<button>`
# inherits its 16px base font size, but the label `<p>` it renders sets
# 14px -- so the label is what has to be compared, not the button.
ST_LABEL = '[data-testid="stBaseButton-primary"] p'
SC_LABEL = '.st-btn.st-btn-primary .st-btn-text p'

# Streamlit's right-top "⋮" menu and its theme entries.
ST_MENU_BUTTON = '[data-testid="stMainMenuButton"]'
ST_THEME_DARK = '[data-testid="stMainMenuItem-theme-Dark"]'

STATES = ('default', 'hover', 'pressdown', 'leave')

PROPS = (
    'height',
    'width',
    'border_radius',
    'background',
    'border_color',
    'color',
    'padding',
    'font_size',
    'font_family',
)

# Asserted equality (the pseudo-code's list, plus the other geometry /
# typography props that make up the same "style consistency" contract).
ASSERTED = (
    'height',
    'width',
    'border_radius',
    'background',
    'border_color',
    'color',
    'padding',
    'font_size',
    'font_family',
)

_READ_JS = """
([node, label]) => {
  const s = getComputedStyle(node);
  const r = node.getBoundingClientRect();
  const ls = getComputedStyle(label || node);
  return {
    height: r.height,
    width: r.width,
    border_radius: s.borderTopLeftRadius,
    background: s.backgroundColor,
    border_color: s.borderTopColor,
    color: s.color,
    padding: s.padding,
    font_size: ls.fontSize,
    font_family: ls.fontFamily,
  };
}
"""

_RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')


def parse_color(value: str) -> tuple[float, ...]:
    """Normalize a computed color to `(r, g, b, a)` for comparison."""
    match = _RGBA_RE.search(value)
    if match is None:
        return (float('nan'), float('nan'), float('nan'), float('nan'))
    parts = [x.strip() for x in match.group(1).split(',')]
    rgba = [float(x) for x in parts[:3]]
    rgba.append(float(parts[3]) if len(parts) > 3 else 1.0)
    return tuple(rgba)


def same_value(prop: str, a: tp.Any, b: tp.Any) -> bool:
    """Compare two captured values, tolerating sub-pixel / rounding noise."""
    if prop in ('background', 'border_color', 'color'):
        return parse_color(a) == parse_color(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if prop == 'height':
            return abs(a - b) < 0.6
        return abs(a - b) < 0.6
    return str(a) == str(b)


def is_dark_theme(page: Page) -> bool:
    bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
    r, g, b = parse_color(bg)[:3]
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance < 0.5


def toggle_dark_theme(page: Page) -> None:
    page.click(ST_MENU_BUTTON)
    page.click(ST_THEME_DARK)
    page.wait_for_timeout(800)


def read_style(page: Page, selector: str, label_selector: str) -> dict:
    node = page.locator(selector).first.element_handle()
    label = page.locator(label_selector).first.element_handle()
    assert node is not None, 'button not found: {}'.format(selector)
    return page.evaluate(_READ_JS, [node, label])


def capture_states(page: Page, selector: str, label_selector: str) -> dict:
    """Capture the button's computed style in each interaction state."""
    box = page.locator(selector).first.bounding_box()
    assert box is not None, 'button has no box: {}'.format(selector)
    cx = box['x'] + box['width'] / 2
    cy = box['y'] + box['height'] / 2

    out: dict = {}
    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    out['default'] = read_style(page, selector, label_selector)

    page.mouse.move(cx, cy)
    page.wait_for_timeout(200)
    out['hover'] = read_style(page, selector, label_selector)

    page.mouse.down()
    page.wait_for_timeout(200)
    out['pressdown'] = read_style(page, selector, label_selector)
    page.mouse.up()

    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    out['leave'] = read_style(page, selector, label_selector)

    return out


def print_table(st: dict, sc: dict) -> list[tuple[str, str, str, str, bool]]:
    rows: list[tuple[str, str, str, str, bool]] = []
    for state in STATES:
        for prop in PROPS:
            a = st[state][prop]
            b = sc[state][prop]
            ok = same_value(prop, a, b)
            rows.append((state, prop, str(a), str(b), ok))

    width = max(len(prop) for prop in PROPS)
    print('')
    print(
        '{:<10} {:<{w}} {:<34} {:<34} {}'.format(
            'state',
            'prop',
            'streamlit (:2202)',
            'canary (:2203)',
            'ok',
            w=width,
        )
    )
    print('-' * 118)
    for state, prop, a, b, ok in rows:
        if prop not in ASSERTED:
            continue
        print(
            '{:<10} {:<{w}} {:<34} {:<34} {}'.format(
                state, prop, a, b, 'YES' if ok else 'NO', w=width
            )
        )
    return rows


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_BUTTON, timeout=20000)
        if not is_dark_theme(st_page):
            toggle_dark_theme(st_page)
        assert is_dark_theme(st_page), 'failed to switch Streamlit to dark'

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_BUTTON, timeout=20000)
        assert is_dark_theme(sc_page), 'streamlit-canary is not dark themed'

        st_states = capture_states(st_page, ST_BUTTON, ST_LABEL)
        sc_states = capture_states(sc_page, SC_BUTTON, SC_LABEL)
        rows = print_table(st_states, sc_states)

        browser.close()

    failures = [
        (state, prop, a, b)
        for state, prop, a, b, ok in rows
        if prop in ASSERTED and not ok
    ]
    if failures:
        print('')
        print('FAILED ({} mismatch(es)):'.format(len(failures)))
        for state, prop, a, b in failures:
            print(
                '  [{state}] {prop}: streamlit={a!r} canary={b!r}'.format(
                    state=state, prop=prop, a=a, b=b
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
