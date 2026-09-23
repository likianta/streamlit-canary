"""`PathInput`'s value field: it is `value`, like every other input widget's.

Run:  python test/event_driven_system/path_input_value.py

`PathInput` used to carry its resolved path under `path`, so binding a plain
`sc.Property` to it the way every other widget allows --

    path_i.bind(src_inp.value)

-- raised `AttributeError: 'PathInput' object has no attribute 'value'`.
The field is `value` now, and nothing else: no `path` alias, and no second
stored field either (one `Property` under two names would be picked up twice
by `_iter_properties`, sending every change patch twice).

Sections 1-4 run in-process. Section 5 drives the pattern in a browser:
typing a real path into the box has to reach a `Property` bound to `value`.
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from lk_utils import fs
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.inputs import PathInput
from streamlit_canary.runtime import Runtime

v3 = sc.v3

PORT = 2212
URL = 'http://localhost:{}'.format(PORT)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


# == 1. the field ===========================================================

rule('1. the field')
box = PathInput('Path', 'C:/')
ok = check('`value` is a Property', isinstance(box.value, sc.Property))
ok = check('and there is no `path` alias', not hasattr(box, 'path')) and ok

names = [name for name, _ in box._iter_properties()]
ok = check('`_iter_properties` reports `value`', 'value' in names) and ok
ok = check(
    'and only once', names.count('value') == 1 and 'path' not in names
) and ok

# == 2. the six accessors ===================================================

rule('2. accessors')
box.value.set('C:/Likianta')
ok = check("box['value'] is the value", box['value'] == 'C:/Likianta') and ok
ok = check(
    "box['on_value'] is a Signal",
    type(box['on_value']).__name__ == 'Signal',
) and ok

# == 3. a Property can bind to it (the pattern that used to break) ==========

rule('3. binding')
mirror = sc.Property('')
mirror.bind(box.value)
ok = check('binding to `.value` works', mirror.get() == 'C:/Likianta') and ok

seen: list = []
box.value.on_change.connect(lambda: seen.append(box.value.get()))
box.value.set('C:/Likianta/workspace')
ok = check(
    'the mirror follows a change', mirror.get() == 'C:/Likianta/workspace'
) and ok
ok = check('one notification per change', seen == ['C:/Likianta/workspace']) and ok

# == 4. the tree wrappers ===================================================

rule('4. the trees keep working')


def _app() -> None:
    v3.TreeSelectWithInput('Tree', 'C:/', filter='.txt')


built, runtime = True, None
try:
    runtime = Runtime(_app)
    runtime.build()
except Exception as exc:
    built = False
    print('  build raised: {!r}'.format(exc))
ok = check('a tree wrapper still builds', built) and ok
if runtime is not None:
    found = [
        c for c in runtime._components.values() if isinstance(c, PathInput)
    ]
    ok = check('the wrapper built one PathInput', len(found) == 1) and ok
    if found:
        ok = check(
            'and it carries the `value` field',
            isinstance(found[0].value, sc.Property),
        ) and ok

# == 5. in a browser: typing reaches a bound Property =======================


def scene() -> None:
    sc.set_page_config('PathInput value')
    src = v3.PathInput('Source path', candidates=())
    tgt = v3.PathInput('Target path', candidates=())

    path_i = sc.Property('')
    path_o = sc.Property('')
    path_i.bind(src.value)
    path_o.bind((src.value, tgt.value), lambda x: '{}+{}'.format(x[0], x[1]))

    v3.Text(sc.bind(path_i, lambda x: 'I|' + x))
    v3.Text(sc.bind(path_o, lambda x: 'O|' + x))


_LOG_JS = """
(prefix) => {
  const el = document.querySelector('[data-md^="' + prefix + '"]');
  return el ? el.textContent.trim() : '';
}
"""


def phase_browser() -> bool:
    rule('5. a browser run of the pattern')
    server = subprocess.Popen(
        [sys.executable, __file__, '--scene'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    good = False
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
            page.wait_for_selector('input.st-text-input-box')
            page.wait_for_timeout(600)

            # A path that exists: `PathInput` resolves to `""` otherwise, and
            # then there is nothing for the bound property to follow. Both
            # processes share the working directory, so `want` is the same
            # string on either side.
            want = fs.abspath('.').replace('\\', '/')
            assert fs.exist(want), want
            box = page.locator('input.st-text-input-box').first
            box.fill(want)
            page.keyboard.press('Enter')
            page.wait_for_timeout(900)

            seen_i = page.evaluate(_LOG_JS, 'I|')
            seen_o = page.evaluate(_LOG_JS, 'O|')
            print('  typed:   {}'.format(want))
            print('  bound:   {!r}'.format(seen_i))
            print('  two-src: {!r}'.format(seen_o))
            good = seen_i == 'I|' + want and seen_o == 'O|' + want + '+'
            browser.close()
    finally:
        server.terminate()
    return check('a Property bound to `value` followed the typing', good)


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
