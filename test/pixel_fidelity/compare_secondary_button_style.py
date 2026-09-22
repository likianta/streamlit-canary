"""
Compare the secondary button's three background states between Streamlit and
Streamlit Canary, in both themes.

The background is the interesting one here: the resting fill is the page
colour lifted a hair (Streamlit's `lightenedBg05`), and hover / press are
translucent overlays on top of it. If the resting fill is instead the
secondary background, those overlays composite back to the colour they
started from -- so hovering looks like nothing happens at all. This script
pins all three states against Streamlit, per theme.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_secondary_button_style.py

Pseudo-code (the assertions this script implements):

    for theme in (light, dark):
        st_app = open_browser(localhost:2202, color_scheme=theme)
        sc_app = open_browser(localhost:2203, stored_theme=theme)

        st_btn = st_app.find_element(secondary_button)
        sc_btn = sc_app.find_element(secondary_button)

        for state in (default, hover, pressdown):
            assert sc_btn.background == st_btn.background

        # and the three of them are distinct, i.e. the states are visible
        assert len({background of each state}) == 3
"""

import re
import sys

from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit renders buttons with a `data-testid`; ours use a class.
ST_BUTTON = '[data-testid="stBaseButton-secondary"]'
SC_BUTTON = '.st-btn.st-btn-secondary'

# Both scenes show the same "⋮" popover trigger as the first secondary
# button, so `.first` picks the same control on either side.
STATES = ('default', 'hover', 'pressdown')
THEMES = ('light', 'dark')

_RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')


def parse_color(value: str) -> tuple[float, ...]:
    """Normalize a computed colour to `(r, g, b, a)` for comparison."""
    match = _RGBA_RE.search(value)
    if match is None:
        return (float('nan'),) * 4
    parts = [x.strip() for x in match.group(1).split(',')]
    rgba = [float(x) for x in parts[:3]]
    rgba.append(float(parts[3]) if len(parts) > 3 else 1.0)
    return tuple(rgba)


def capture(page, selector: str) -> dict:
    """The button's `background-color` in each interaction state."""
    loc = page.locator(selector).first
    box = loc.bounding_box()
    assert box is not None, 'no box for {}'.format(selector)
    cx = box['x'] + box['width'] / 2
    cy = box['y'] + box['height'] / 2

    out: dict = {}
    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    out['default'] = loc.evaluate('el => getComputedStyle(el).backgroundColor')
    page.mouse.move(cx, cy)
    page.wait_for_timeout(250)
    out['hover'] = loc.evaluate('el => getComputedStyle(el).backgroundColor')
    page.mouse.down()
    page.wait_for_timeout(250)
    out['pressdown'] = loc.evaluate(
        'el => getComputedStyle(el).backgroundColor'
    )
    page.mouse.up()
    return out


def open_app(page, url: str, selector: str) -> None:
    page.goto(url)
    page.wait_for_selector(selector, timeout=30000)
    page.wait_for_timeout(1500)


def main() -> int:
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for theme in THEMES:
            st_page = browser.new_page(
                viewport={'width': 1280, 'height': 900}, color_scheme=theme
            )
            open_app(st_page, ST_URL, ST_BUTTON)

            sc_page = browser.new_page(viewport={'width': 1280, 'height': 900})
            # `--theme-boot` reads this on load (see `render.py`).
            sc_page.add_init_script(
                'localStorage.setItem("sc-theme", "{}")'.format(theme)
            )
            open_app(sc_page, SC_URL, SC_BUTTON)

            st_states = capture(st_page, ST_BUTTON)
            sc_states = capture(sc_page, SC_BUTTON)

            print('== {} theme =='.format(theme))
            for state in STATES:
                a = st_states[state]
                b = sc_states[state]
                ok = parse_color(a) == parse_color(b)
                if not ok:
                    failures.append(
                        '[{}] {}: streamlit={!r} canary={!r}'.format(
                            theme, state, a, b
                        )
                    )
                print(
                    '  {:<10} streamlit={:<26} canary={:<26} {}'.format(
                        state, a, b, 'ok' if ok else 'MISMATCH'
                    )
                )
            distinct = len({sc_states[s] for s in STATES})
            if distinct != len(STATES):
                failures.append(
                    '[{}] the three states are not distinct ({}) -- hover / '
                    'press would be invisible'.format(theme, distinct)
                )
            print(
                '  distinct backgrounds: {} of {}'.format(distinct, len(STATES))
            )

            st_page.close()
            sc_page.close()
        browser.close()

    if failures:
        print('')
        print('FAILED ({} issue(s)):'.format(len(failures)))
        for one in failures:
            print('  ' + one)
        return 1
    print('')
    print('PASSED: both themes match Streamlit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
