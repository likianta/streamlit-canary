"""`on_submit` / `on_editing_finished` on the input widgets, in a browser.

Pseudo-code (the spec this script implements):

    1. Open a scene with a `TextInput`, a `TextArea`, a `NumberInput`, and a
       `Selectbox(accept_new_option=True)`. Every signal emission is appended
       to a server-side log drawn into a `Text('LOG|...')` element; the browser
       reads it back through the element's raw `data-md` source.
    2. TextInput, Enter:
       when keyboard.type('aaa') in the text box and keyboard.press('Enter'):
           assert one  `ti.submit=aaa`
           assert one  `ti.editing_finished=aaa`  -- a submit ends the session
       when mouse.click(text area)  -- the Enter had left the focus in the box:
           assert still one `ti.editing_finished=aaa`
               -- the submit already ended the session, so the blur is not a
                  second end
    3. TextInput, blur alone:
       when keyboard.type('bbb') in the text box and mouse.click(text area):
           assert zero  `ti.submit=bbb`
           assert one   `ti.editing_finished=bbb`
    4. TextArea (plain Enter inserts a newline, Ctrl+Enter submits):
       when keyboard.press('Enter'):
           assert zero  `ta.submit=`
       when keyboard.press('Control+Enter'):
           assert one   `ta.submit=ccc`
    5. NumberInput (Enter submits; the stepper must not blur the box):
       when keyboard.type('42') and keyboard.press('Enter'):
           assert one   `ni.submit=42`
       when mouse.click(increase stepper):
           assert document.activeElement is still the number box
               -- `onmousedown preventDefault` kept the focus, so no stale
                  pre-step `editing_finished` went out
           assert no new `ni.editing_finished`
       when mouse.click(text area):
           assert one   `ni.editing_finished=<the stepped value>`
    6. Selectbox new-option row:
       when keyboard.type('eee') and keyboard.press('Enter'):
           assert one   `sb.new_option_submit=eee`
           assert one   `sb.new_option_editing_finished=eee`
       when keyboard.type('fff') and mouse.click(text area):
           assert zero  `sb.new_option_submit=fff`
           assert one   `sb.new_option_editing_finished=fff`

Run it (it starts the scene on :2214 itself):

    python test/event_driven_system/input_signals_browser_test.py

Just serve the scene, to look at it in a browser:

    python test/event_driven_system/input_signals_browser_test.py --scene
"""

import subprocess
import sys
import time
from typing import Any

import streamlit_canary as sc
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

v3 = sc.v3

PORT = 2214
URL = 'http://localhost:{}'.format(PORT)

# The log is a `Text`, so the browser reads it back as the raw markdown source
# (`data-md`). The prefix both marks the element for the selector and keeps the
# text non-empty -- an empty `Text` renders no placeholder at all.
LOG_PREFIX = 'LOG|'
entries: list[str] = []
box: dict[str, Any] = {}


def record(tag: str, text: str) -> None:
    entries.append('{}={}'.format(tag, text))
    box['log'].text.set(LOG_PREFIX + '|'.join(entries))


def scene() -> None:
    box['ti'] = ti = v3.TextInput('Text', key='ti')
    box['ta'] = ta = v3.TextArea('Area', key='ta')
    box['ni'] = ni = v3.NumberInput('Number', step=1, key='ni')
    box['sb'] = sb = v3.Selectbox(
        'Select',
        ('x', 'y'),
        accept_new_option=True,
        format_new_option=lambda text: text,
        key='sb',
    )
    box['log'] = v3.Text('LOG|', key='log')

    ti.on_submit.connect(lambda text: record('ti.submit', text))
    ti.on_editing_finished.connect(
        lambda text: record('ti.editing_finished', text)
    )
    ta.on_submit.connect(lambda text: record('ta.submit', text))
    ta.on_editing_finished.connect(
        lambda text: record('ta.editing_finished', text)
    )
    ni.on_submit.connect(lambda text: record('ni.submit', text))
    ni.on_editing_finished.connect(
        lambda text: record('ni.editing_finished', text)
    )
    sb.on_new_option_submit.connect(
        lambda text: record('sb.new_option_submit', text)
    )
    sb.on_new_option_editing_finished.connect(
        lambda text: record('sb.new_option_editing_finished', text)
    )


# Read the server-side log through the raw markdown source of its `Text`.
_LOG_JS = """
() => {
  const el = document.querySelector('.st-md[data-md^="LOG|"]');
  return el ? el.getAttribute('data-md') : '';
}
"""

_ACTIVE_JS = """
() => (document.activeElement && document.activeElement.className) || ''
"""

_STEPPED_JS = """
() => (document.querySelector('div.st-number-input input') || {}).value || ''
"""


def read_log(page: Page) -> str:
    return page.evaluate(_LOG_JS)


def count(page: Page, needle: str) -> int:
    return read_log(page).count(needle)


def report(label: str, good: bool, detail: str = '') -> bool:
    print('  [{}] {}{}'.format('ok  ' if good else 'FAIL', label, detail))
    return good


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
    page.wait_for_selector('div.st-text-input', timeout=10000)
    # the labels are markdown, filled by page.js on load
    page.wait_for_timeout(800)


def verify() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        errors: list = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        wait_for_scene(page)
        ok = True

        text_box = page.locator('div.st-text-input > input.st-text-input-box')
        text_area = page.locator('div.st-text-area textarea.st-text-area-box')
        number_box = page.locator('div.st-number-input input.st-text-input-box')
        increase = page.locator('div.st-number-input .st-number-step').nth(1)

        print('-- TextInput: Enter submits, the following blur does not --')
        text_box.click()
        text_box.fill('aaa')
        page.keyboard.press('Enter')
        page.wait_for_timeout(400)
        ok = (
            report(
                '`ti.submit=aaa` fired once',
                count(page, 'ti.submit=aaa') == 1,
                ' log={!r}'.format(read_log(page)),
            )
            and ok
        )
        ok = (
            report(
                '`ti.editing_finished=aaa` fired once',
                count(page, 'ti.editing_finished=aaa') == 1,
            )
            and ok
        )
        text_area.click()
        page.wait_for_timeout(400)
        ok = (
            report(
                'the blur after a submit does not fire a second time',
                count(page, 'ti.editing_finished=aaa') == 1,
            )
            and ok
        )

        print('-- TextInput: a blur alone finishes editing --')
        text_box.click()
        text_box.fill('bbb')
        text_area.click()
        page.wait_for_timeout(400)
        ok = (
            report(
                '`ti.submit=bbb` did not fire',
                count(page, 'ti.submit=bbb') == 0,
            )
            and ok
        )
        ok = (
            report(
                '`ti.editing_finished=bbb` fired once',
                count(page, 'ti.editing_finished=bbb') == 1,
            )
            and ok
        )

        print('-- TextArea: plain Enter inserts, Ctrl+Enter submits --')
        text_area.click()
        text_area.fill('ccc')
        page.keyboard.press('Enter')
        page.wait_for_timeout(400)
        ok = (
            report(
                'plain Enter did not submit',
                count(page, 'ta.submit=') == 0,
                ' log={!r}'.format(read_log(page)),
            )
            and ok
        )
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(400)
        ok = (
            report('Ctrl+Enter submitted once', count(page, 'ta.submit=') == 1)
            and ok
        )
        ok = (
            report(
                'the submit also finished editing',
                count(page, 'ta.editing_finished=ccc') == 1,
            )
            and ok
        )

        print('-- NumberInput: Enter submits --')
        number_box.click()
        number_box.fill('42')
        page.keyboard.press('Enter')
        page.wait_for_timeout(400)
        ok = (
            report(
                '`ni.submit=42` fired once', count(page, 'ni.submit=42') == 1
            )
            and ok
        )

        print('-- NumberInput: the stepper keeps the focus in the box --')
        number_box.click()
        page.wait_for_timeout(100)
        # the submit above emitted its own `editing_finished`; the stepper must
        # not add another (only the blur that follows ends the new session)
        before = count(page, 'ni.editing_finished=')
        increase.click()
        page.wait_for_timeout(300)
        active = page.evaluate(_ACTIVE_JS)
        ok = (
            report(
                'the focus stayed in the number box',
                'st-text-input-box' in active,
                ' activeElement={!r}'.format(active),
            )
            and ok
        )
        ok = (
            report(
                'the stepper itself reports no `editing_finished`',
                count(page, 'ni.editing_finished=') == before,
                ' before={} after={}'.format(
                    before, count(page, 'ni.editing_finished=')
                ),
            )
            and ok
        )
        stepped = page.evaluate(_STEPPED_JS)
        text_area.click()
        page.wait_for_timeout(400)
        ok = (
            report(
                'the blur then reports the stepped value',
                count(page, 'ni.editing_finished={}'.format(stepped)) == 1,
                ' stepped={!r}'.format(stepped),
            )
            and ok
        )

        print('-- Selectbox new-option row: Enter submits --')
        selectbox = page.locator('div.st-selectbox')
        selectbox.locator('.st-selectbox-trigger').click()
        page.wait_for_timeout(300)
        new_input = selectbox.locator('.st-selectbox-new-input')
        ok = (
            report('the new-option box is shown', new_input.is_visible()) and ok
        )
        new_input.click()
        new_input.fill('eee')
        page.keyboard.press('Enter')
        page.wait_for_timeout(400)
        ok = (
            report(
                '`sb.new_option_submit=eee` fired once',
                count(page, 'sb.new_option_submit=eee') == 1,
                ' log={!r}'.format(read_log(page)),
            )
            and ok
        )
        ok = (
            report(
                '`sb.new_option_editing_finished=eee` followed',
                count(page, 'sb.new_option_editing_finished=eee') == 1,
            )
            and ok
        )
        trigger_text = selectbox.locator('.st-selectbox-value').text_content()
        ok = (
            report(
                'the option was added and is now the value',
                (trigger_text or '').strip() == 'eee',
                ' value={!r}'.format((trigger_text or '').strip()),
            )
            and ok
        )

        print('-- Selectbox new-option row: a blur only finishes editing --')
        selectbox.locator('.st-selectbox-trigger').click()
        page.wait_for_timeout(300)
        new_input = selectbox.locator('.st-selectbox-new-input')
        new_input.click()
        new_input.fill('fff')
        text_area.click()
        page.wait_for_timeout(400)
        ok = (
            report(
                'a blur does not submit',
                count(page, 'sb.new_option_submit=fff') == 0,
            )
            and ok
        )
        ok = (
            report(
                '`sb.new_option_editing_finished=fff` fired once',
                count(page, 'sb.new_option_editing_finished=fff') == 1,
                ' log={!r}'.format(read_log(page)),
            )
            and ok
        )

        print()
        print('final log:', read_log(page))
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
