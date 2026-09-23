"""`Title(horizontal_alignment=...)` and `PageTitle`.

Run:  python test/title_test.py

`Title` gained the alignment; `PageTitle` is a `Title` that also names the
browser tab (`sc.set_page_config(title)` only reaches the first paint, since
it runs before the page is served).

Sections 1-2 are in-process (the rendered HTML and the page's `<title>`);
section 3 drives a real browser, where the alignment is a computed style and
the tab name has to follow a bound text as it changes.
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.texts import PageTitle
from streamlit_canary.components_v3.texts import Title
from streamlit_canary.runtime.render import render_page
from streamlit_canary.runtime.render import render_tree

v3 = sc.v3

PORT = 2213
URL = 'http://localhost:{}'.format(PORT)


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


# == 1. the alignment is a static field, validated like a size keyword =======

rule('1. alignment')
ok = check('left is the default', Title('T')._horizontal_alignment == 'left')
ok = (
    check('and it adds no class', 'st-title--' not in render_tree([Title('T')]))
    and ok
)
for value in ('center', 'right'):
    title = Title('T', horizontal_alignment=value)
    html = render_tree([title])
    ok = (
        check(
            '{!r} renders `st-title--{}`'.format(value, value),
            'class="st-title st-title--{}"'.format(value) in html,
        )
        and ok
    )
try:
    Title('T', horizontal_alignment='middle')
    ok = check('an unknown alignment raises', False) and ok
except ValueError as exc:
    ok = check('an unknown alignment raises: {}'.format(exc), True) and ok

# == 2. the page title ======================================================

rule('2. the page title')
ok = check('PageTitle is a Title', issubclass(PageTitle, Title))
html = render_page([PageTitle('Tab name')], title='from the config')
ok = check('it marks the element', 'st-page-title' in html) and ok
ok = check('and names the document', '<title>Tab name</title>' in html) and ok
ok = (
    check(
        'without one, the config still names it',
        '<title>from the config</title>'
        in render_page([Title('T')], title='from the config'),
    )
    and ok
)
with v3.Container() as outer:
    with v3.Container():
        PageTitle('Nested')
ok = (
    check(
        'a nested one counts too',
        '<title>Nested</title>' in render_page([outer]),
    )
    and ok
)

# == 3. in a browser ========================================================


def scene() -> None:
    sc.set_page_config('config name')
    name = sc.Property('First name')
    v3.PageTitle(name, horizontal_alignment='center')
    v3.Title('Left by default')
    v3.Title('Centered', horizontal_alignment='center')
    v3.Title('Right', horizontal_alignment='right')
    with v3.Button('Rename') as btn:

        @btn.on_click
        def _() -> None:
            name.set('Second name :smile:')


_ALIGN_JS = """
() => {
  const out = {};
  for (const el of document.querySelectorAll('h1.st-title')) {
    out[el.textContent.trim()] = getComputedStyle(el).textAlign;
  }
  return out;
}
"""


def phase_browser() -> bool:
    rule('3. in a browser')
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
            page.wait_for_selector('h1.st-title')
            page.wait_for_timeout(800)

            aligns = page.evaluate(_ALIGN_JS)
            print('  alignments: {}'.format(aligns))
            # the default is left, which chromium reports under its logical
            # spelling `start` (there is no explicit `text-align` rule for it)
            good = (
                aligns.get('Left by default') in ('left', 'start')
                and aligns.get('Centered') == 'center'
                and aligns.get('Right') == 'right'
            )
            good = check('each heading has its own text-align', good) and good

            first = page.title()
            print('  tab at first:  {!r}'.format(first))
            good = (
                check('the tab starts on the component', first == 'First name')
                and good
            )

            page.click('button.st-btn')
            page.wait_for_timeout(900)
            heading = page.inner_text('h1.st-page-title')
            second = page.title()
            print('  heading after: {!r}'.format(heading))
            print('  tab after:     {!r}'.format(second))
            good = (
                check(
                    'the heading re-rendered the markdown',
                    heading == 'Second name 😄',
                )
                and good
            )
            good = (
                check(
                    'and the tab took the text as written',
                    second == 'Second name :smile:',
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
