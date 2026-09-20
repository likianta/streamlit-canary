"""A `Selectbox` dropdown must not be cut off by its containing box.

Pseudo-code (the spec this script implements):

    1. Open the scene: a `Column(max_height=120)` holding a selectbox near
       its top, the same nested one level deeper, a selectbox in plain flow,
       a selectbox inside a row-aligned `Popover` panel, a
       `TreeSelect(max_height=200)` (the reported case: its toolbar's
       "Current location" bar), and one more capped selectbox to be scrolled
       to near the bottom of the window.
    2. For every selectbox that sits inside a box which scrolls or hides its
       overflow (`clipper`):
         when mouse.click(trigger):
             assert dropdown.position is fixed
                 -- it has to leave the clipping box behind
             assert dropdown is fully inside the window
             assert no option is cut off (dropdown height == its content)
             assert dropdown.bottom > clipper.bottom
                 -- it really did escape, not merely fit inside
             when mouse.click(option):
                 assert trigger.value == that option
                     -- and it is still a working dropdown, not just a box
    3. For the selectbox in plain flow (no clipper):
         when mouse.click(trigger):
             assert dropdown.position is absolute
                 -- the escaping is only for boxes that would clip it
    4. For the capped selectbox scrolled to the bottom of the window:
         assert dropdown.bottom <= trigger.top
             -- no room below means it opens upwards, and stays whole

Run it (it starts the scene on :2213 itself):

    python test/selectbox_popover_overflow.py

Just serve the scene, to look at it in a browser:

    python test/selectbox_popover_overflow.py --scene
"""

import subprocess
import sys
import time
from typing import Any

import streamlit_canary as sc
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

v3 = sc.v3

PORT = 2213
URL = 'http://localhost:{}'.format(PORT)

# A long ladder, so the dropdown is taller than every capped box below.
OPTIONS = (
    'C:/Users/Likianta/workspace/dev.master.likianta/streamlit-canary',
    'C:/Users/Likianta/workspace/dev.master.likianta',
    'C:/Users/Likianta/workspace',
    'C:/Users/Likianta',
    'C:/Users',
    'C:/',
    'D:/',
    'E:/',
)

# The scene's selectboxes, in DOM order. The tree's location bar is the one
# the bug report is about; the rest pin down which boxes must escape.
CAPPED = 0
NESTED = 1
PLAIN = 2
PANEL = 3
TREE = 4
BOTTOM = 5

# A sub-pixel difference is not a difference.
EPS = 1.0


def scene() -> None:
    # 1. the reported shape: a selectbox inside a height-capped box that
    # scrolls, with more content under it than the box can show
    with v3.Column(max_height=120, border=True):
        v3.Space(height=60)
        v3.Selectbox('Current location', OPTIONS, key='capped')
        v3.Space(height=400)

    # 2. the same, one box deeper
    with v3.Column(max_height=120, border=True):
        with v3.Column():
            v3.Space(height=60)
            v3.Selectbox('Nested location', OPTIONS, key='nested')
        v3.Space(height=400)

    # 3. no clipper anywhere: the ordinary case
    v3.Selectbox('Plain', OPTIONS, key='plain')

    # 4. the panel case that used to need a rule of its own: a row-aligned
    # popover panel scrolls (`overflow-y: scroll`), so a dropdown inside it
    # has to escape just like the others
    with v3.Row('center'):
        v3.TextInput('Path', key='panel-input')
        with v3.Popover('Browse', panel_align='row', panel_max_height=160):
            with v3.Column():
                v3.Space(height=40)
                v3.Selectbox('In a panel', OPTIONS, key='panel')
                v3.Space(height=200)

    # 5. the real-world case: the tree browser's toolbar, whose whole panel
    # is capped (so the location bar's dropdown was cut off at 200px)
    v3.TreeSelect(start_directory='test', max_height=200)

    # 6. to be scrolled to the bottom of the window: no room below
    v3.Space(height=700)
    with v3.Column(max_height=120, border=True):
        v3.Space(height=60)
        v3.Selectbox('Near the bottom', OPTIONS, key='bottom')


# Everything about one selectbox that the assertions below need. The clipper
# is found exactly the way the page does it: the nearest ancestor that does
# not leave its overflow `visible`.
_MEASURE_JS = """
(i) => {
  const round = (n) => Math.round(n * 100) / 100;
  const box = document.querySelectorAll('.st-selectbox')[i];
  const trigger = box.querySelector('.st-selectbox-trigger');
  const dropdown = box.querySelector('.st-selectbox-dropdown');
  const r = dropdown.getBoundingClientRect();
  const t = trigger.getBoundingClientRect();
  let clipper = null;
  for (
    let el = dropdown.parentElement;
    el && el !== document.body && el !== document.documentElement;
    el = el.parentElement
  ) {
    const cs = getComputedStyle(el);
    if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
      clipper = el;
      break;
    }
  }
  const cr = clipper && clipper.getBoundingClientRect();
  // `box-sizing: border-box` (see `01-base.css`), so the CSS cap counts the
  // borders: the content box it leaves is the cap minus them.
  const dcs = getComputedStyle(dropdown);
  const cap = parseFloat(dcs.maxHeight);
  const borders = parseFloat(dcs.borderTopWidth)
    + parseFloat(dcs.borderBottomWidth);
  const options = [...dropdown.querySelectorAll('.st-selectbox-option')];
  // Is this point actually painted by the dropdown? An `absolute` dropdown
  // that is cut off at a clipping ancestor's edge fails here, even though its
  // layout rect (what `getBoundingClientRect` reports) says otherwise.
  const hit = (x, y) => {
    const el = document.elementFromPoint(x, y);
    return !!(el && dropdown.contains(el));
  };
  return {
    position: getComputedStyle(dropdown).position,
    open: !dropdown.hidden,
    value: box.querySelector('.st-selectbox-value').textContent,
    rect: {
      top: round(r.top), bottom: round(r.bottom), left: round(r.left),
      right: round(r.right), width: round(r.width), height: round(r.height),
    },
    client_height: dropdown.clientHeight,
    content_height: round(dropdown.scrollHeight),
    cap_content_height: Number.isFinite(cap) ? round(cap - borders) : 0,
    trigger: {top: round(t.top), bottom: round(t.bottom)},
    clipper: cr && {top: round(cr.top), bottom: round(cr.bottom)},
    option_count: options.length,
    last_option_bottom: options.length
      ? round(options[options.length - 1].getBoundingClientRect().bottom)
      : 0,
    edges_painted: [
      hit(r.left + r.width / 2, r.top + 3),
      hit(r.left + r.width / 2, r.bottom - 3),
    ],
    viewport_height: window.innerHeight,
  };
}
"""


def measure(page: Page, index: int) -> dict[str, Any]:
    return page.evaluate(_MEASURE_JS, index)


def open_dropdown(page: Page, index: int) -> None:
    box = page.locator('.st-selectbox').nth(index)
    if box.locator('.st-selectbox-dropdown').get_attribute('hidden') is None:
        return
    box.locator('.st-selectbox-trigger').click()
    page.wait_for_timeout(300)


def close_dropdown(page: Page, index: int) -> None:
    """An open dropdown floats over the boxes below it, so a pass that ends
    with one open has to close it before the next box is clicked."""
    box = page.locator('.st-selectbox').nth(index)
    if box.locator('.st-selectbox-dropdown').get_attribute('hidden') is None:
        box.locator('.st-selectbox-trigger').click()
        page.wait_for_timeout(300)


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


def report(label: str, good: bool, detail: str = '') -> bool:
    print('  [{}] {}{}'.format('ok  ' if good else 'FAIL', label, detail))
    return good


def check_clipped(page: Page, index: int, name: str) -> bool:
    """A dropdown inside a clipping box must escape it, whole."""
    open_dropdown(page, index)
    data = measure(page, index)
    rect = data['rect']
    ok = True
    ok = (
        report(
            '{}: dropdown is promoted to `fixed`'.format(name),
            data['position'] == 'fixed',
            ' position={}'.format(data['position']),
        )
        and ok
    )
    ok = (
        report(
            '{}: dropdown is fully inside the window'.format(name),
            rect['top'] >= -EPS
            and rect['bottom'] <= data['viewport_height'] + EPS,
            ' top={} bottom={} window={}'.format(
                rect['top'], rect['bottom'], data['viewport_height']
            ),
        )
        and ok
    )
    expected = min(data['content_height'], data['cap_content_height'])
    ok = (
        report(
            '{}: the box is as tall as it needs (up to its cap)'.format(name),
            abs(data['client_height'] - expected) <= EPS,
            ' client_height={} content={} cap={}'.format(
                data['client_height'],
                data['content_height'],
                data['cap_content_height'],
            ),
        )
        and ok
    )
    ok = (
        report(
            '{}: its top and bottom rows are painted, not cut off'.format(name),
            all(data['edges_painted']),
            ' edges_painted={}'.format(data['edges_painted']),
        )
        and ok
    )
    if data['content_height'] <= data['cap_content_height']:
        ok = (
            report(
                '{}: every option is inside the box'.format(name),
                data['last_option_bottom'] <= rect['bottom'] + EPS,
                ' last_option_bottom={} box_bottom={}'.format(
                    data['last_option_bottom'], rect['bottom']
                ),
            )
            and ok
        )
    return ok


def verify() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        errors: list = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        wait_for_scene(page)
        ok = True

        counted = page.locator('.st-selectbox').count() == BOTTOM + 1
        ok = (
            report(
                'the scene has {} selectboxes'.format(BOTTOM + 1),
                counted,
                ' found {}'.format(page.locator('.st-selectbox').count()),
            )
            and ok
        )

        print('-- a capped box must not cut its dropdown off --')
        ok = check_clipped(page, CAPPED, 'capped') and ok
        ok = check_clipped(page, NESTED, 'nested') and ok
        ok = check_clipped(page, TREE, 'tree location') and ok

        print('-- the dropdown still works: picking updates the value --')
        before = measure(page, TREE)['value']
        box = page.locator('.st-selectbox').nth(TREE)
        box.locator('.st-selectbox-option').nth(1).click()
        page.wait_for_timeout(400)
        after = measure(page, TREE)['value']
        ok = (
            report(
                'tree location: picking an option changes the value',
                after != before and after != '',
                ' {!r} -> {!r}'.format(before[:28], after[:28]),
            )
            and ok
        )

        print('-- a popover panel must not cut its dropdown off either --')
        page.locator('.st-popover-trigger').first.click()
        page.wait_for_timeout(400)
        ok = check_clipped(page, PANEL, 'popover panel') and ok
        page.locator('.st-popover-trigger').first.click()
        page.wait_for_timeout(300)

        print('-- a box with no clipper keeps its plain placement --')
        open_dropdown(page, PLAIN)
        plain = measure(page, PLAIN)
        ok = (
            report(
                'plain: dropdown stays `absolute`',
                plain['position'] == 'absolute',
                ' position={} clipper={}'.format(
                    plain['position'], plain['clipper']
                ),
            )
            and ok
        )
        close_dropdown(page, PLAIN)

        print('-- no room below means it opens upwards --')
        page.evaluate(
            """(i) => {
              const trigger = document.querySelectorAll('.st-selectbox')[i]
                .querySelector('.st-selectbox-trigger');
              const bottom = trigger.getBoundingClientRect().bottom;
              window.scrollBy(0, bottom - (window.innerHeight - 30));
            }""",
            BOTTOM,
        )
        page.wait_for_timeout(200)
        open_dropdown(page, BOTTOM)
        bottom = measure(page, BOTTOM)
        flipped = bottom['rect']['bottom'] <= bottom['trigger']['top'] + EPS
        inside = (
            bottom['rect']['top'] >= -EPS
            and bottom['rect']['bottom'] <= bottom['viewport_height'] + EPS
        )
        ok = (
            report(
                'bottom: dropdown flipped above the trigger',
                flipped and inside,
                ' dropdown.bottom={} trigger.top={} window={}'.format(
                    bottom['rect']['bottom'],
                    bottom['trigger']['top'],
                    bottom['viewport_height'],
                ),
            )
            and ok
        )
        close_dropdown(page, BOTTOM)

        print()
        print('errors:', errors if errors else 'none')
        print('RESULT:', 'ok' if ok and not errors else 'FAILED')
        browser.close()
        return 0 if (ok and not errors) else 1


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
