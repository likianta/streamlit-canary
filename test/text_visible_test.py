"""Text elements: a `text` and a `visible`, and the rule that ties them.

Run:  python test/text_visible_test.py

The three invariants this guards:

1. every text element takes `text` and `visible` on its own;
2. both are `Property` (so `.get` / `.set` / `.on_change` work);
3. the element is drawn only when the text is non-blank *and* `visible` is
   true -- otherwise it is hidden, taking no space.

Sections 1-3 run in-process (the defaults, the fields, the rendered HTML);
section 4 drives a real browser, where "hidden" means the element measures
zero height and flips live as the text or the flag changes.
"""

import inspect
import subprocess
import sys
import time

import streamlit_canary as sc
from playwright.sync_api import sync_playwright
from streamlit_canary.runtime.render import render_tree

v3 = sc.v3

PORT = 2214
URL = 'http://localhost:{}'.format(PORT)

# the elements whose default is "shown"; Spinner / Progress are visibility
# toggles (they start hidden, and their text does not drive it), so they are
# checked separately below.
SHOWN_BY_DEFAULT = (
    'Text',
    'Title',
    'Caption',
    'Code',
    'Markdown',
    'Info',
    'Success',
    'Error',
    'Warning',
)
TOGGLED_BY_DEFAULT = ('Spinner', 'Progress')


def check(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def rule(text: str) -> None:
    print('== {} {}'.format(text, '=' * max(0, 66 - len(text))))


def visible_default(name: str) -> object:
    sig = inspect.signature(getattr(v3, name).__init__)
    return sig.parameters['visible'].default


def has_hidden_attr(html: str) -> bool:
    """Whether `render_tree` marked the root element `hidden`."""
    return ' hidden>' in html


# == 1. the default the user flagged ========================================

rule('1. defaults')
for name in SHOWN_BY_DEFAULT:
    ok = check(
        '{}: visible defaults to True'.format(name),
        visible_default(name) is True,
    )
    if not ok:
        break
for name in TOGGLED_BY_DEFAULT:
    ok = check(
        '{}: visible defaults to False (a toggle)'.format(name),
        visible_default(name) is False,
    )
    if not ok:
        break

# == 2. text and visible are separate Properties ============================

rule('2. both are Properties')
box = v3.Info('', key='probe')

ok = check('`text` is a Property', isinstance(box.text, sc.Property))
ok = (
    check('`visible` is a Property', isinstance(box.visible, sc.Property))
    and ok
)

box['text'] = 'hello'
box['visible'] = True
ok = check("`['text']` reads the value", box['text'] == 'hello') and ok
ok = check("`['visible']` reads the value", box['visible'] is True) and ok

box.text.set('world')
ok = check('`text.set` reaches `[text]`', box['text'] == 'world') and ok

box.visible.set(False)
ok = check('`visible.set` reaches `[visible]`', box['visible'] is False) and ok

# == 3. render only when both are true ======================================

rule('3. shown only when filled and switched on')

blank = {
    'Text': v3.Text(''),
    'Title': v3.Title(''),
    'Caption': v3.Caption(''),
    'Code': v3.Code(''),
    'Markdown': v3.Markdown(''),
    'Info': v3.Info(''),
}
for name, comp in blank.items():
    html = render_tree([comp])
    ok = check('{}: blank text is hidden'.format(name), has_hidden_attr(html))
    if not ok:
        break

for name in blank:
    comp = getattr(v3, name)('something')
    ok = check('{}: filled text is drawn'.format(name), not comp.is_hidden())
    if not ok:
        break

off = v3.Info('something', visible=False)
ok = check('a filled box switched off is hidden', off.is_hidden())
ok = (
    check(
        'and carries the `hidden` attribute',
        has_hidden_attr(render_tree([off])),
    )
    and ok
)

# a space is content on purpose: the placeholder that keeps the line
ws = v3.Text(' ')
ok = check('a space placeholder still shows', not ws.is_hidden()) and ok

# a bound text drives `visible` without any explicit flag
source = sc.Property('')
bound = v3.Text(source)
ok = check('a bound empty text starts hidden', bound.is_hidden()) and ok
source.set('now you see me')
ok = check('and shows once it fills in', not bound.is_hidden()) and ok
source.set('')
ok = check('and hides again when it empties', bound.is_hidden()) and ok

# == 4. in a browser ========================================================

_SCENE_JS = """
() => {
  const out = {};
  for (const id of ['t-empty','t-filled','i-empty','i-filled','bound','toggle']) {
    const el = document.querySelector('[data-id="' + id + '"]');
    out[id] = el ? el.getBoundingClientRect().height : -1;
  }
  return out;
}
"""


def scene() -> None:
    sc.set_page_config('text/visible')
    v3.Title('', key='t-empty')
    v3.Title('A title', key='t-filled')
    v3.Info('', key='i-empty')
    v3.Info('Some info', key='i-filled')

    source = sc.Property('')
    v3.Text(source, key='bound')

    shown = sc.Property(True)
    v3.Info('Toggle me', key='toggle', visible=shown)

    with v3.Button('Fill', key='fill') as fill:

        @fill.on_click
        def _() -> None:
            source.set('hello')

    with v3.Button('Toggle', key='toggle-btn') as toggle:

        @toggle.on_click
        def _() -> None:
            shown.set(not shown.get())


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
            page.wait_for_selector('[data-id="t-filled"]')
            page.wait_for_timeout(700)

            sizes = page.evaluate(_SCENE_JS)
            print('  heights: {}'.format(sizes))
            good = (
                check('a blank title takes no space', sizes.get('t-empty') == 0)
                and good
            )
            good = (
                check(
                    'a filled title takes space',
                    (sizes.get('t-filled') or 0) > 0,
                )
                and good
            )
            good = (
                check('a blank alert takes no space', sizes.get('i-empty') == 0)
                and good
            )
            good = (
                check(
                    'a filled alert takes space',
                    (sizes.get('i-filled') or 0) > 0,
                )
                and good
            )
            good = (
                check(
                    'a bound empty text takes no space', sizes.get('bound') == 0
                )
                and good
            )

            page.click('button[data-id="fill"]')
            page.wait_for_timeout(700)
            sizes = page.evaluate(_SCENE_JS)
            print('  after fill: {}'.format(sizes))
            good = (
                check(
                    'a bound text appears once it fills in',
                    (sizes.get('bound') or 0) > 0,
                )
                and good
            )

            page.click('button[data-id="toggle-btn"]')
            page.wait_for_timeout(700)
            sizes = page.evaluate(_SCENE_JS)
            print('  after toggle: {}'.format(sizes))
            good = (
                check(
                    'a box switched off disappears live',
                    sizes.get('toggle') == 0,
                )
                and good
            )

            page.click('button[data-id="toggle-btn"]')
            page.wait_for_timeout(700)
            sizes = page.evaluate(_SCENE_JS)
            print('  after toggle back: {}'.format(sizes))
            good = (
                check(
                    'and comes back when switched on',
                    (sizes.get('toggle') or 0) > 0,
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
