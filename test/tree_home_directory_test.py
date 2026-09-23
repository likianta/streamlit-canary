"""`TreeSelect(home_directory=)`: what the toolbar's Home button goes back to.

Run:  python test/tree_home_directory_test.py

`home` used to be hard-wired to `start_directory`. It now follows its own
argument, which defaults to `start_directory` -- so the listing still opens
where the caller asked while `home` can mean somewhere else entirely.

Sections 1-4 run in-process; section 5 clicks the real button in a browser.
"""

import os
import subprocess
import sys
import time

import streamlit_canary as sc
from lk_utils import fs
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.trees import TreeSelect

v3 = sc.v3

PORT = 2219
URL = 'http://localhost:{}'.format(PORT)

HERE = fs.abspath(os.getcwd())
UP = fs.parent(HERE)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


# == 1. left out, home is where the panel opens =============================

rule('1. the default')
tree = TreeSelect('Pick', HERE)
ok = check('without it, home is the start', tree._home_dir == HERE)
ok = check('the panel opens there', tree._nav.directory == HERE) and ok
ok = check('and it is remembered', tree._nav.start_directory == HERE) and ok

# == 2. an explicit one only moves the button ===============================

rule('2. an explicit home_directory')
tree = TreeSelect('Pick', HERE, home_directory=UP)
ok = check('home follows it', tree._home_dir == UP)
ok = check('the panel still opens at the start', tree._nav.directory == HERE)
ok = (
    check(
        'and start_directory is left alone', tree._nav.start_directory == HERE
    )
    and ok
)

# == 3. the button jumps there ==============================================

rule('3. the button')
tree._jump(HERE)
ok = check('walked to the start first', tree.directory == HERE)
tree._home_btn.on_click.emit()
ok = check('home lands on the home directory', tree.directory == UP) and ok
ok = (
    check(
        'not on the start directory',
        tree.directory != tree._nav.start_directory,
    )
    and ok
)

# == 4. a relative path is resolved =========================================

rule('4. a relative home_directory')
tree = TreeSelect('Pick', HERE, home_directory='.')
ok = check('resolved against the cwd', tree._home_dir == fs.abspath('.')) and ok

# == 5. in a browser ========================================================


def scene() -> None:
    sc.set_page_config('home directory')
    v3.TreeSelect('Pick', HERE, home_directory=UP, key='tree')


_LOCATION_JS = "() => document.querySelector('.st-selectbox-value').textContent"
# the toolbar's `home` icon button: an icon-only button whose glyph is `home`
_HOME_BTN = 'button.st-btn-icon:has-text("home")'


def phase_browser() -> bool:
    rule('5. in a browser')
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
            page.wait_for_selector('.st-selectbox-value')
            page.wait_for_timeout(700)

            before = page.evaluate(_LOCATION_JS).strip()
            print('  before: {}'.format(before))
            good = (
                check('it opens at the start directory', before == HERE)
                and good
            )

            page.click(_HOME_BTN)
            page.wait_for_timeout(700)

            after = page.evaluate(_LOCATION_JS).strip()
            print('  after:  {}'.format(after))
            good = (
                check('the click lands on the home directory', after == UP)
                and good
            )

            page.click(_HOME_BTN)
            page.wait_for_timeout(500)
            again = page.evaluate(_LOCATION_JS).strip()
            good = check('and it stays there', again == UP) and good
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
