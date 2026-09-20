"""`v3.Selectbox(width='content')` sizes to its widest *option*.

Pseudo-code (the spec this script implements):

    1. Open the scene: three `width='content'` selectboxes (Mode, Icons,
       Dynamic) whose options differ in length, and one plain selectbox
       (Stretched) that has no `width` at all.
    2. For every option of a `width='content'` box:
         when mouse.click(item within its dropdown):
             assert box.trigger.width == the width it had for every other
                 option -- switching the value never resizes the trigger
             assert box.value is not truncated (no ellipsis)
    3. assert box.trigger.width == widest_option.text + box.chrome + arrow:
       the box is as wide as the widest option asks for, and no wider --
       `chrome` being the padding, borders and the gap the arrow sits in,
       all read off the trigger itself.
    4. When the options change at runtime (the `options` patch rebuilds the
       list, and the sizer with it):
         when mouse.click(add_button):
             assert box.trigger.width grew to fit the new longest option
    5. The box without `width` keeps filling its parent, whatever the option
       lengths are -- `'content'` is the tighter thing, not the same thing.

Run it (it starts the scene on :2212 itself):

    python test/selectbox_on_width_wrap.py

Just serve the scene, to look at it in a browser:

    python test/selectbox_on_width_wrap.py --scene
"""

import subprocess
import sys
import time
from typing import Any

import streamlit_canary as sc
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

v3 = sc.v3

PORT = 2212
URL = 'http://localhost:{}'.format(PORT)

# The scene's selectboxes, in DOM order.
MODE = 0
ICONS = 1
DYNAMIC = 2
STRETCHED = 3

# The app's content column: `#app` is 736px wide including its 16px padding.
APP_CONTENT_WIDTH = 704

# A sub-pixel difference (glyph rounding) is not a resize.
EPS = 0.6


class _State(sc.StateV2):
    modes: sc.Property[list] = ['Single', 'Multiple']


state = _State()


def scene() -> None:
    v3.Selectbox('Mode', ('Single', 'Multiple', 'Multi-cross'), width='content')
    v3.Selectbox(
        'Icons',
        (':material/abc: Alpha', ':material/account_tree: A longer label'),
        width='content',
    )
    v3.Selectbox('Dynamic', options=state.modes, width='content')
    with v3.Button('Add a longer option') as add:

        @add.on_click
        def _():
            state.modes.set(
                state.modes.get() + ['a considerably longer option']
            )

    v3.Selectbox('Stretched', ('Single', 'Multi-cross'))


# Everything about one selectbox that the assertions below need. The option
# texts are measured from the dropdown, so they only have a width while it is
# open (`hidden` is `display: none`).
_MEASURE_JS = """
(i) => {
  const round = (n) => Math.round(n * 100) / 100;
  const box = document.querySelectorAll('.st-selectbox')[i];
  const trigger = box.querySelector('.st-selectbox-trigger');
  const value = box.querySelector('.st-selectbox-value');
  const arrow = box.querySelector('.st-selectbox-arrow');
  const cs = getComputedStyle(trigger);
  const chrome = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)
    + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth)
    + parseFloat(cs.columnGap);
  const texts = [...box.querySelectorAll(
    '.st-selectbox-option-inner .st-md')];
  return {
    width: round(trigger.getBoundingClientRect().width),
    chrome: round(chrome),
    arrow: round(arrow.getBoundingClientRect().width),
    value_width: round(value.getBoundingClientRect().width),
    value_truncated: value.scrollWidth > value.clientWidth + 1,
    option_count: texts.length,
    option_texts: texts.map((el) => round(el.getBoundingClientRect().width)),
    has_sizer: !!box.querySelector('.st-selectbox-sizer'),
  };
}
"""


def measure(page: Page, index: int) -> dict[str, Any]:
    return page.evaluate(_MEASURE_JS, index)


def open_dropdown(page: Page, index: int) -> None:
    box = page.locator('.st-selectbox').nth(index)
    dropdown = box.locator('.st-selectbox-dropdown')
    if dropdown.get_attribute('hidden') is not None:
        box.locator('.st-selectbox-trigger').click()
        page.wait_for_timeout(250)


def close_dropdown(page: Page, index: int) -> None:
    """An open dropdown floats over the boxes below it, so a pass that ends
    with one open has to close it before the next box is clicked."""
    box = page.locator('.st-selectbox').nth(index)
    if box.locator('.st-selectbox-dropdown').get_attribute('hidden') is None:
        box.locator('.st-selectbox-trigger').click()
        page.wait_for_timeout(250)


def pick(page: Page, index: int, option: int) -> None:
    """Open the box and click one of its options."""
    open_dropdown(page, index)
    page.locator('.st-selectbox').nth(index).locator(
        '.st-selectbox-option'
    ).nth(option).click()
    page.wait_for_timeout(250)


def wait_for_scene(page: Page) -> None:
    """Poll the port until the scene answers (the server is a child process)."""
    deadline = time.time() + 30
    while True:
        try:
            page.goto(URL, wait_until='domcontentloaded', timeout=2000)
            break
        except Exception:
            if time.time() > deadline:
                raise SystemExit('the scene never came up on {}'.format(URL))
            time.sleep(0.5)
    page.wait_for_selector('.st-selectbox', timeout=10000)
    # the labels and option texts are markdown, filled by page.js on load
    page.wait_for_timeout(800)


def check_content_box(page: Page, index: int, name: str) -> bool:
    """One `width='content'` box: one width for every option, sized to the
    widest of them."""
    count = (
        page.locator('.st-selectbox')
        .nth(index)
        .locator('.st-selectbox-option')
        .count()
    )
    widths: list[float] = []
    ok = True
    for option in range(count):
        pick(page, index, option)
        data = measure(page, index)
        # the option texts only have a width while the dropdown is open
        open_dropdown(page, index)
        texts = measure(page, index)['option_texts']
        expected = round(max(texts) + data['chrome'] + data['arrow'], 2)
        fits = abs(data['width'] - expected) <= 1
        good = fits and not data['value_truncated']
        ok = ok and good
        widths.append(data['width'])
        print(
            '  {:<8} option {:<3} width={:<7} expected={:<7} value={:<7} '
            'truncated={:<6} {}'.format(
                name,
                option,
                data['width'],
                expected,
                data['value_width'],
                str(data['value_truncated']),
                'ok' if good else 'BAD',
            )
        )
    spread = round(max(widths) - min(widths), 2)
    ok = ok and spread <= EPS
    print(
        '  {:<8} {} options, width spread={} {}'.format(
            name, count, spread, 'ok' if spread <= EPS else 'BAD'
        )
    )
    close_dropdown(page, index)
    return ok


def verify() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        errors: list = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        wait_for_scene(page)
        ok = True

        print('-- width="content": one width for every option --')
        ok = check_content_box(page, MODE, 'Mode') and ok
        ok = check_content_box(page, ICONS, 'Icons') and ok
        structural = measure(page, MODE)['has_sizer']
        ok = ok and structural
        print(
            '  {:<8} sizer present: {} {}'.format(
                'Mode', structural, 'ok' if structural else 'BAD'
            )
        )

        print('-- options added at runtime: the width follows --')
        before = measure(page, DYNAMIC)
        page.get_by_role('button', name='Add a longer option').click()
        page.wait_for_timeout(800)
        open_dropdown(page, DYNAMIC)
        after = measure(page, DYNAMIC)
        expected = round(
            max(after['option_texts']) + after['chrome'] + after['arrow'], 2
        )
        grew = after['width'] > before['width']
        right = abs(after['width'] - expected) <= 1
        counted = after['option_count'] == before['option_count'] + 1
        good = grew and right and counted
        ok = ok and good
        print(
            '  {:<8} options {} -> {}, width {} -> {}, expected={} {}'.format(
                'Dynamic',
                before['option_count'],
                after['option_count'],
                before['width'],
                after['width'],
                expected,
                'ok' if good else 'BAD',
            )
        )
        close_dropdown(page, DYNAMIC)

        print('-- the box without `width` fills its parent --')
        stretched = measure(page, STRETCHED)
        mode_width = measure(page, MODE)['width']
        fills = abs(stretched['width'] - APP_CONTENT_WIDTH) <= 1
        tighter = mode_width < stretched['width']
        ok = ok and fills and tighter
        print(
            '  {:<8} width={} (parent={}), Mode width={} {}'.format(
                'Stretched',
                stretched['width'],
                APP_CONTENT_WIDTH,
                mode_width,
                'ok' if (fills and tighter) else 'BAD',
            )
        )

        print()
        print('errors:', errors if errors else 'none')
        print('RESULT:', 'ok' if ok else 'FAILED')
        browser.close()
        return 0 if ok else 1


def main() -> int:
    if '--scene' in sys.argv:
        sc.run(scene, port=PORT)
        return 0
    server = subprocess.Popen([sys.executable, __file__, '--scene'])
    try:
        return verify()
    finally:
        server.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
