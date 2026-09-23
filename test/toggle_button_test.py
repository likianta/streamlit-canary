"""`ToggleButton`: a `Button` whose look follows its own `value`.

Run:  python test/toggle_button_test.py

Clicking flips `value` (a `Property[bool]`); the button then draws primary
while it is on and secondary while off. `type` is *derived* from `value` and
read-only -- there is no `type` argument, and writing the field raises, so
the two can never fall out of step.

Sections 1-3 run in-process (the fields, a click, the rendered class);
section 4 drives a real browser, where a click must swap the palette class
live through the `type` patch.
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.buttons import ToggleButton
from streamlit_canary.runtime.render import render_tree

v3 = sc.v3

PORT = 2216
URL = 'http://localhost:{}'.format(PORT)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


def rejects_type_kwarg() -> bool:
    try:
        ToggleButton('X', type='primary')
    except TypeError:
        return True
    return False


def refuses(fn, *args) -> bool:
    try:
        fn(*args)
    except AttributeError:
        return True
    return False


# == 1. the fields ==========================================================

rule('1. the fields')
tb = ToggleButton('Bold')
ok = check('`value` is a Property', isinstance(tb.value, sc.Property))
ok = check('and starts False', tb['value'] is False) and ok
ok = check('`type` is a Property', isinstance(tb.type, sc.Property)) and ok
ok = check('and starts "secondary"', tb['type'] == 'secondary') and ok
ok = (
    check(
        '`_iter_properties` reports both',
        {'value', 'type'} <= {name for name, _ in tb._iter_properties()},
    )
    and ok
)

# == 2. type is derived and read-only =======================================

rule('2. type is derived and read-only')
ok = check('no `type` argument', rejects_type_kwarg())
ok = check('`type.set` is refused', refuses(tb.type.set, 'primary')) and ok
ok = (
    check("`tb['type'] =` is refused", refuses(tb.__setitem__, 'type', 'x'))
    and ok
)

# == 3. a click flips value, and type follows ===============================

rule('3. a click flips value, and type follows')
tb = ToggleButton('Bold')
ok = check('off: renders secondary', 'st-btn-secondary' in render_tree([tb]))
ok = (
    check('off: no primary class', 'st-btn-primary' not in render_tree([tb]))
    and ok
)

tb.on_click.emit()
ok = check('after a click: value is True', tb['value'] is True) and ok
ok = check('after a click: type is "primary"', tb['type'] == 'primary') and ok
ok = (
    check(
        'after a click: renders primary', 'st-btn-primary' in render_tree([tb])
    )
    and ok
)

tb.on_click.emit()
ok = check('a second click flips it back', tb['value'] is False) and ok
ok = check('and type returns to secondary', tb['type'] == 'secondary') and ok

# a handler observes the state the click just produced
seen = []
tb2 = ToggleButton('Bold', on_click=lambda: seen.append(tb2['value']))


@tb2.on_click
def _() -> None:
    seen.append(tb2['value'])


tb2.on_click.emit()
ok = check('on_click handlers see the new value', seen == [True, True]) and ok

# a bound `value` drives it from the outside
src = sc.Property(False)
bound = ToggleButton('Bold', value=src)
ok = (
    check('a bound value starts secondary', bound['type'] == 'secondary') and ok
)
src.set(True)
ok = check('and follows its source', bound['type'] == 'primary') and ok
ok = check('without writing the field', bound['value'] is True) and ok

# == 4. in a browser ========================================================


def scene() -> None:
    sc.set_page_config('toggle button')
    v3.ToggleButton('Bold', key='bold')


_STATE_JS = """
() => {
  const el = document.querySelector('[data-id="bold"]');
  return {
    cls: el.className,
    bg: getComputedStyle(el).backgroundColor,
  };
}
"""


def phase_browser() -> bool:
    rule('4. in a browser')
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
            page.wait_for_selector('[data-id="bold"]')
            page.wait_for_timeout(700)

            before = page.evaluate(_STATE_JS)
            print('  before: {}'.format(before))
            good = (
                check(
                    'it starts secondary', 'st-btn-secondary' in before['cls']
                )
                and good
            )

            page.click('button[data-id="bold"]')
            page.wait_for_timeout(700)
            after = page.evaluate(_STATE_JS)
            print('  after:  {}'.format(after))
            good = (
                check(
                    'a click lights it up (primary)',
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

            page.click('button[data-id="bold"]')
            # step off the button first: hovering repaints it, and we want to
            # compare the resting background with the one we started from.
            page.mouse.move(0, 0)
            page.wait_for_timeout(700)
            back = page.evaluate(_STATE_JS)
            print('  back:   {}'.format(back))
            good = (
                check(
                    'a second click turns it off again',
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
