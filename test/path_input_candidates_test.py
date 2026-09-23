"""`PathInput.candidates`: a literal seed becomes a memory of paths.

Run:  python test/path_input_candidates_test.py

Handing `PathInput` a plain sequence used to just forward it to the inner
`TextInput`. It now seeds a *memory*: every path the box resolves to joins it
(newest first, no duplicates), capped at a capacity of at least 20 -- a
larger seed rounds up to the next ten (23 -> 30) -- and the panel lists what
it holds alphabetically. A `Property` is still relayed untouched (the caller
owns the list), and `None` still means no panel.

`TextInput` keeps the plain, order-preserving field, and so does
`TreeSelectWithInput`'s private box (which passes no candidates at all).

Sections 1-6 run in-process; section 7 drives a browser, where resolving a
path must refresh the open panel through a `candidates` patch.
"""

import os
import subprocess
import sys
import time

import streamlit_canary as sc
from lk_utils import fs
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.inputs import PathInput
from streamlit_canary.components_v3.inputs import TextInput
from streamlit_canary.components_v3.inputs import _candidate_capacity
from streamlit_canary.runtime.render import render_tree

v3 = sc.v3

PORT = 2217
URL = 'http://localhost:{}'.format(PORT)

HERE = fs.abspath(os.getcwd())
UP = fs.parent(HERE)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


# == 1. the capacity ========================================================

rule('1. the capacity')
ok = check('a small seed gets the 20 floor', _candidate_capacity(5) == 20)
ok = check('exactly 20 stays 20', _candidate_capacity(20) == 20) and ok
ok = check('21 rounds up to 30', _candidate_capacity(21) == 30) and ok
ok = check('23 rounds up to 30', _candidate_capacity(23) == 30) and ok
ok = check('an empty seed still gets 20', _candidate_capacity(0) == 20) and ok

# == 2. a literal seed becomes a memory, listed alphabetically ==============

rule('2. a literal seed')
box = PathInput('Path', candidates=['z:/b', 'z:/a'])
ok = check('the memory exists', box._memory is not None)
ok = check('and is capped at 20', box._memory.maxlen == 20) and ok
ok = (
    check('the panel starts sorted', box['candidates'] == ['z:/a', 'z:/b'])
    and ok
)

big = PathInput('Path', candidates=['p{}'.format(i) for i in range(23)])
ok = check('a 23-path seed is capped at 30', big._memory.maxlen == 30) and ok

# == 3. a resolved path joins the memory ====================================

rule('3. a resolved path')
box = PathInput('Path', candidates=['z:/a'])
box.show(HERE)
ok = check('it joins the panel', HERE in box['candidates'])
ok = check('the memory holds it newest-first', list(box._memory)[0] == HERE)
ok = (
    check(
        'and the panel stays sorted',
        box['candidates'] == sorted(box['candidates']),
    )
    and ok
)

box.show(UP)
ok = check('the next one lands in front', list(box._memory)[0] == UP) and ok
ok = (
    check(
        'and is listed in place',
        box['candidates'] == sorted([HERE, UP, 'z:/a']),
    )
    and ok
)

# == 4. no duplicates =======================================================

rule('4. no duplicates')
before = list(box['candidates'])
order = list(box._memory)
box.show(HERE)
ok = check('showing it again adds nothing', box['candidates'] == before)
ok = (
    check('and leaves the memory order alone', list(box._memory) == order)
    and ok
)
ok = (
    check(
        'the memory holds no repeat', len(box._memory) == len(set(box._memory))
    )
    and ok
)

# == 5. the window slides ===================================================

rule('5. the window slides')
cap = box._memory.maxlen
for i in range(cap + 5):
    box.show('{}/filled{}'.format(HERE, i))
ok = check('the memory stops at the capacity', len(box._memory) == cap) and ok
ok = (
    check(
        'the newest is kept',
        list(box._memory)[0] == '{}/filled{}'.format(HERE, cap + 4),
    )
    and ok
)
ok = (
    check('the oldest seed dropped off', 'z:/a' not in box['candidates']) and ok
)

# == 6. a Property, None, and the neighbours ================================

rule('6. a Property, None, and the neighbours')
src = sc.Property(None)
pbox = PathInput('Path', candidates=src)
src.set(['z:/b', 'z:/a'])
ok = check(
    'a bound Property is relayed as-is', pbox['candidates'] == ['z:/b', 'z:/a']
)
pbox.show(HERE)
ok = (
    check(
        'nothing is remembered for it', pbox['candidates'] == ['z:/b', 'z:/a']
    )
    and ok
)
ok = check('and there is no memory', pbox._memory is None) and ok

nbox = PathInput('Path')
ok = check('None still means no panel', nbox['candidates'] is None)
ok = check('and no memory', nbox._memory is None) and ok

tin = TextInput('Text', candidates=['z:/b', 'z:/a'])
ok = (
    check(
        'TextInput keeps the given order', tin['candidates'] == ['z:/b', 'z:/a']
    )
    and ok
)

sel = v3.TreeSelectWithInput('Pick', os.getcwd())
ok = (
    check(
        "TreeSelectWithInput's own box takes no candidates",
        sel._path_input['candidates'] is None,
    )
    and ok
)
ok = check('so it has no memory either', sel._path_input._memory is None) and ok

# the sorted order reaches the markup
html = render_tree([PathInput('Path', candidates=['zzz', 'aaa'])])
ok = (
    check('the panel renders sorted', html.index('aaa') < html.index('zzz'))
    and ok
)

# == 7. in a browser ========================================================


def scene() -> None:
    sc.set_page_config('path input candidates')
    v3.PathInput('Path', candidates=['zzz-seed'], key='pi')


_ROWS_JS = """
() => Array.from(
  document.querySelectorAll(
    '.st-text-input-candidates .st-selectbox-option'
  )
).map((el) => el.dataset.value)
"""


def phase_browser() -> bool:
    rule('7. in a browser')
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
            page.wait_for_selector('.st-text-input-candidates')
            page.wait_for_timeout(700)

            rows = page.evaluate(_ROWS_JS)
            print('  before: {}'.format(rows))
            good = (
                check('it starts from the seed', rows == ['zzz-seed']) and good
            )

            page.fill('.st-text-input-box', HERE)
            page.press('.st-text-input-box', 'Enter')
            page.wait_for_timeout(700)

            rows = page.evaluate(_ROWS_JS)
            print('  after:  {}'.format(rows))
            good = (
                check('the resolved path joined the panel', HERE in rows)
                and good
            )
            good = (
                check('and the panel is sorted', rows == sorted(rows)) and good
            )
            good = (
                check('with the seed still there', 'zzz-seed' in rows) and good
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
