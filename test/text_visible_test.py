"""Text elements: a `text` and a `visible`, and the rule that ties them.

Run:  python test/text_visible_test.py

The three invariants this guards:

1. every text element takes `text` and `visible` on its own;
2. both are `Property` (so `.get` / `.set` / `.on_change` work);
3. the element is drawn only when `visible` says so. `visible` defaults to
   `'auto'`, i.e. tied to the text: a blank one hides the element (so it
   takes no space) and it comes back as the text fills in. An explicit flag
   -- a bool or a bound `Property` -- *wins* over the content, so a blank
   element can still be shown on purpose.

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

v3 = sc

PORT = 2214
URL = 'http://localhost:{}'.format(PORT)

# the elements whose `visible` defaults to `'auto'`, i.e. tied to the text;
# Spinner / Progress are visibility toggles (they start hidden, and their
# text does not drive it), so they are checked separately below.
AUTO_BY_DEFAULT = (
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
for name in AUTO_BY_DEFAULT:
    ok = check(
        "{}: visible defaults to 'auto'".format(name),
        visible_default(name) == 'auto',
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
box = sc.Info('', key='probe')

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
    'Text': sc.Text(''),
    'Title': sc.Title(''),
    'Caption': sc.Caption(''),
    'Code': sc.Code(''),
    'Markdown': sc.Markdown(''),
    'Info': sc.Info(''),
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

off = sc.Info('something', visible=False)
ok = check('a filled box switched off is hidden', off.is_hidden())
ok = (
    check(
        'and carries the `hidden` attribute',
        has_hidden_attr(render_tree([off])),
    )
    and ok
)

# an explicit flag wins over the content: a blank element can be shown on
# purpose (the old design ANDed the two, so this was impossible)
forced = sc.Info('', visible=True)
ok = check('a blank box forced on is drawn', not forced.is_hidden()) and ok
ok = (
    check(
        'and keeps its place in the page',
        not has_hidden_attr(render_tree([forced])),
    )
    and ok
)

flag = sc.Property(True)
forced_bound = sc.Text('', visible=flag)
ok = (
    check('a bound flag shows a blank text', not forced_bound.is_hidden())
    and ok
)
flag.set(False)
ok = (
    check('and hides it when the flag goes off', forced_bound.is_hidden())
    and ok
)

# only a bool / Property / 'auto' is meaningful; a stray string is a bug
try:
    sc.Text('x', visible='visible')
except ValueError:
    ok = check('a stray string is rejected', True) and ok
else:
    ok = check('a stray string is rejected', False) and ok

# the same rule drives the non-text sources too (`Table.rows` here)
ok = check('Table: empty rows hide it', sc.Table([]).is_hidden()) and ok
ok = check('Table: rows show it', not sc.Table([('a', 'b')]).is_hidden()) and ok

# a space is content on purpose: the placeholder that keeps the line
ws = sc.Text(' ')
ok = check('a space placeholder still shows', not ws.is_hidden()) and ok

# a bound text drives `visible` without any explicit flag
source = sc.Property('')
bound = sc.Text(source)
ok = check('a bound empty text starts hidden', bound.is_hidden()) and ok
source.set('now you see me')
ok = check('and shows once it fills in', not bound.is_hidden()) and ok
source.set('')
ok = check('and hides again when it empties', bound.is_hidden()) and ok

# == 4. in a browser ========================================================

_SCENE_JS = """
() => {
  const out = {};
  const ids = ['t-empty','t-filled','i-empty','i-filled',
               'forced','bound','toggle'];
  for (const id of ids) {
    const el = document.querySelector('[data-id="' + id + '"]');
    out[id] = el ? el.getBoundingClientRect().height : -1;
  }
  return out;
}
"""


def scene() -> None:
    sc.set_page_config('text/visible')
    sc.Title('', key='t-empty')
    sc.Title('A title', key='t-filled')
    sc.Info('', key='i-empty')
    sc.Info('Some info', key='i-filled')
    sc.Info('', key='forced', visible=True)

    source = sc.Property('')
    sc.Text(source, key='bound')

    shown = sc.Property(True)
    sc.Info('Toggle me', key='toggle', visible=shown)

    with sc.Button('Fill', key='fill') as fill:

        @fill.on_click
        def _() -> None:
            source.set('hello')

    with sc.Button('Toggle', key='toggle-btn') as toggle:

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
                    'a blank alert forced on keeps its space',
                    (sizes.get('forced') or 0) > 0,
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
