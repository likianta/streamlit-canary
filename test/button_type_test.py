"""`Button.type` is a reactive Property, not static config.

Run:  python test/button_type_test.py

`type` used to be a plain attribute (`_type`), fixed at construction. It is a
`Property` now, so a button can turn primary / secondary as state changes.

Sections 1-2 run in-process (the field, the rendered class); section 3 drives
a real browser, where a bound `type` has to swap the palette class -- and with
it the painted background -- live.
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.buttons import Button
from streamlit_canary.runtime.render import render_tree

v3 = sc.v3

PORT = 2215
URL = 'http://localhost:{}'.format(PORT)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


# == 1. the field ===========================================================

rule('1. the field')
btn = Button('Go')
ok = check('`type` is a Property', isinstance(btn.type, sc.Property))
ok = check('and defaults to "secondary"', btn['type'] == 'secondary') and ok
ok = check('there is no static `_type` left', not hasattr(btn, '_type')) and ok
ok = (
    check(
        '`_iter_properties` reports `type`',
        'type' in [name for name, _ in btn._iter_properties()],
    )
    and ok
)

ok = (
    check('a value is taken', Button('Go', type='primary')['type'] == 'primary')
    and ok
)

# == 2. the rendered class ==================================================

rule('2. the rendered class')
html = render_tree([Button('Go')])
ok = check('secondary is the default class', 'st-btn-secondary' in html)
ok = (
    check(
        "'primary' switches the class",
        'st-btn-primary' in render_tree([Button('Go', type='primary')]),
    )
    and ok
)
ok = (
    check(
        'anything else falls back to secondary',
        'st-btn-secondary' in render_tree([Button('Go', type='ghost-button')]),
    )
    and ok
)

# a bound `type` follows its source
src = sc.Property('secondary')
bound = Button('Go', type=src)
ok = (
    check(
        'a bound type starts as secondary',
        'st-btn-secondary' in render_tree([bound]),
    )
    and ok
)
src.set('primary')
ok = (
    check('and follows the source', 'st-btn-primary' in render_tree([bound]))
    and ok
)

# == 3. in a browser ========================================================


def scene() -> None:
    sc.set_page_config('button type')
    src = sc.Property('secondary')
    v3.Button('Action', type=src, key='target')

    with v3.Button('Toggle', key='toggle') as btn:

        @btn.on_click
        def _() -> None:
            src.set('primary' if src.get() != 'primary' else 'secondary')


_STATE_JS = """
() => {
  const el = document.querySelector('[data-id="target"]');
  return {
    cls: el.className,
    bg: getComputedStyle(el).backgroundColor,
  };
}
"""


def phase_browser() -> bool:
    rule('3. in a browser')
    server = subprocess.Popen(
        [sys.executable, __file__, '--scene'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    good = True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1000, 'height': 800})
            deadline = time.time() + 40
            while True:
                try:
                    page.goto(URL, wait_until='domcontentloaded', timeout=2000)
                    break
                except Exception:
                    if time.time() > deadline:
                        raise SystemExit('the scene never came up')
                    time.sleep(0.5)
            page.wait_for_selector('[data-id="target"]')
            page.wait_for_timeout(700)

            before = page.evaluate(_STATE_JS)
            print('  before: {}'.format(before))
            good = (
                check(
                    'it starts secondary',
                    'st-btn-secondary' in before['cls']
                    and 'st-btn-primary' not in before['cls'],
                )
                and good
            )

            page.click('button[data-id="toggle"]')
            page.wait_for_timeout(700)
            after = page.evaluate(_STATE_JS)
            print('  after:  {}'.format(after))
            good = (
                check(
                    'the class swaps to primary',
                    'st-btn-primary' in after['cls']
                    and 'st-btn-secondary' not in after['cls'],
                )
                and good
            )
            good = (
                check(
                    'and the painted background follows',
                    after['bg'] != before['bg'],
                )
                and good
            )

            page.click('button[data-id="toggle"]')
            page.wait_for_timeout(700)
            back = page.evaluate(_STATE_JS)
            print('  back:   {}'.format(back))
            good = (
                check(
                    'and it swaps back',
                    'st-btn-secondary' in back['cls']
                    and back['bg'] == before['bg'],
                )
                and good
            )
            browser.close()
    finally:
        server.terminate()
    return good


def main() -> int:
    if '--scene' in sys.argv:
        sc.run(scene, port=PORT)
        return 0
    good = phase_browser() and ok
    print('')
    print('RESULT:', 'ok' if good else 'FAILED')
    return 0 if good else 1


if __name__ == '__main__':
    raise SystemExit(main())
