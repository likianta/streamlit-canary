"""Tests for `sc.toast(...)`.

The first half runs in-process (no browser): it checks that the runtime hands
out exactly one toast stack -- the app's own if it declared one, a made-up one
otherwise -- and that `sc.toast` writes to it.

The second half drives a real page: both buttons of the demo share that one
stack, it sits in the top-right corner clear of the toolbar, the newest toast
takes the top of the pile, `duration` is honoured, and the ✕ dismisses.

Run:  python test/toast_test.py
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from playwright.sync_api import sync_playwright
from streamlit_canary.components_v3.status import Toast
from streamlit_canary.runtime import Runtime
from streamlit_canary.runtime import get_current_runtime

v3 = sc.v3

PORT = 2217
URL = 'http://localhost:{}'.format(PORT)


def _app_declaring_a_toast() -> None:
    v3.Toast()
    v3.Text('hello')


def _app_declaring_nothing() -> None:
    v3.Text('hello')


def scene() -> None:
    sc.set_page_config('Toast demo')

    with v3.Button('Make toast') as btn:

        @btn.on_click
        def _() -> None:
            sc.toast('AAA')

    with v3.Button('Make toast 2') as btn2:

        @btn2.on_click
        def _() -> None:
            sc.toast('BBB')

    with v3.Button('Icon + infinite') as btn3:

        @btn3.on_click
        def _() -> None:
            sc.toast('Saved!', icon=':material/check:', duration='infinite')


# ---------------------------------------------------------------------------
# in-process (no browser)
# ---------------------------------------------------------------------------


def phase_python() -> bool:
    print('-- in-process --')
    ok = True

    r1 = Runtime(_app_declaring_a_toast)
    r1.build()
    hosts = [c for c in r1._components.values() if isinstance(c, Toast)]
    ok = report('an app-declared Toast is the only one', len(hosts) == 1) and ok
    declared = hosts[0]
    ok = report(
        'the declared element is kept (not the auto one)',
        declared.id != 'sc-toast',
    ) and ok
    r1.toast('hi', icon=':material/check:')
    msgs = declared.messages.get()
    ok = report(
        'r1.toast() wrote to the declared element',
        len(msgs) == 1 and msgs[0]['text'] == 'hi',
    ) and ok
    ok = report(
        'icon and default duration travel along',
        msgs[0]['icon'] == ':material/check:' and msgs[0]['duration'] == 4,
    ) and ok

    r2 = Runtime(_app_declaring_nothing)
    r2.build()
    hosts = [c for c in r2._components.values() if isinstance(c, Toast)]
    ok = report(
        'an app that declares none still gets exactly one',
        len(hosts) == 1,
    ) and ok
    auto = hosts[0]
    ok = report(
        'the auto host has the stable key',
        auto.id == 'sc-toast',
    ) and ok
    ok = report('the auto host became a root', auto in r2._roots) and ok

    r2.toast('yo', duration='infinite')
    msgs = auto.messages.get()
    ok = report(
        "duration='infinite' maps to None (no countdown)",
        len(msgs) == 1 and msgs[0]['duration'] is None,
    ) and ok

    # the client ✕ arrives as a `dismiss` event on the stack's own id
    r2.on_event(auto.id, 'dismiss', msgs[0]['id'])
    ok = report('a dismiss event clears that toast', auto.messages.get() == []) and ok

    try:
        r2.toast('bad', duration='nope')
        ok = report('a bad duration is rejected', False) and ok
    except ValueError:
        ok = report('a bad duration is rejected', True)

    ok = report(
        'get_current_runtime() is the newest runtime',
        get_current_runtime() is r2,
    ) and ok
    sc.toast('via sc')
    ok = report(
        'sc.toast() reaches that newest runtime',
        [m['text'] for m in auto.messages.get()] == ['via sc'],
    ) and ok

    return ok


# ---------------------------------------------------------------------------
# browser
# ---------------------------------------------------------------------------

_STACK_JS = """
() => {
  const el = document.querySelector('.st-toast-stack');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {
    id: el.dataset.id,
    hidden: el.hidden,
    count: el.querySelectorAll('.st-toast').length,
    texts: Array.from(el.querySelectorAll('.st-toast'))
      .map(t => t.querySelector('.st-toast-body').textContent.trim()),
    icons: Array.from(el.querySelectorAll('.st-toast'))
      .map(t => t.querySelectorAll('.st-toast-icon').length),
    durations: Array.from(el.querySelectorAll('.st-toast'))
      .map(t => t.dataset.duration || null),
    tops: Array.from(el.querySelectorAll('.st-toast'))
      .map(t => Math.round(t.getBoundingClientRect().top)),
    top: Math.round(r.top),
    right: Math.round(window.innerWidth - r.right),
  };
}
"""


def phase_browser() -> bool:
    print('-- browser --')
    server = subprocess.Popen(
        [sys.executable, __file__, '--scene'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        return _browse()
    finally:
        server.terminate()


def _browse() -> bool:
    ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        deadline = time.time() + 40
        while True:
            try:
                page.goto(URL, wait_until='domcontentloaded', timeout=2000)
                break
            except Exception:
                if time.time() > deadline:
                    raise SystemExit('the scene never came up')
                time.sleep(0.5)
        page.wait_for_selector('.st-toast-stack', state='attached')
        page.wait_for_timeout(500)

        ok = report(
            'exactly one toast stack is rendered',
            page.evaluate(
                "() => document.querySelectorAll('.st-toast-stack').length"
            )
            == 1,
        ) and ok
        info = page.evaluate(_STACK_JS)
        print('  initial:', info)
        ok = report('it starts empty and hidden', info['hidden'] is True) and ok
        ok = report('it is the runtime-made host', info['id'] == 'sc-toast') and ok

        page.locator('button', has_text='Make toast 2').first.click()
        page.wait_for_timeout(600)
        info = page.evaluate(_STACK_JS)
        print('  after BBB:', info)
        ok = report(
            'the second button wrote to the same stack',
            info['count'] == 1 and info['texts'] == ['BBB'],
        ) and ok
        ok = report('the stack is no longer hidden', info['hidden'] is False) and ok
        ok = report(
            'it is pinned to the top-right, clear of the toolbar',
            (info['top'], info['right']) == (56, 16),
        ) and ok

        page.locator('button', has_text='Make toast').first.click()
        page.wait_for_timeout(600)
        info = page.evaluate(_STACK_JS)
        print('  after AAA:', info)
        ok = report(
            'both buttons share one stack (2 toasts, oldest first)',
            info['count'] == 2 and info['texts'] == ['BBB', 'AAA'],
        ) and ok
        ok = report(
            'the newest toast sits on top of the pile',
            info['tops'][1] < info['tops'][0],
        ) and ok

        print('  waiting out the 4s auto-dismiss...')
        page.wait_for_timeout(5200)
        info = page.evaluate(_STACK_JS)
        print('  after the countdown:', info)
        ok = report(
            "both 'short' toasts expired",
            info['count'] == 0 and info['hidden'] is True,
        ) and ok

        page.locator('button', has_text='Icon + infinite').first.click()
        page.wait_for_timeout(600)
        info = page.evaluate(_STACK_JS)
        print('  after infinite:', info)
        ok = report(
            'the icon and the "infinite" duration came through',
            info['count'] == 1
            and info['texts'] == ['Saved!']
            and info['icons'] == [1]
            and info['durations'] == [None],
        ) and ok
        page.wait_for_timeout(3000)
        info = page.evaluate(_STACK_JS)
        ok = report(
            'an infinite toast stays put',
            info['count'] == 1,
        ) and ok

        page.locator('.st-toast-close').first.click()
        page.wait_for_timeout(800)
        info = page.evaluate(_STACK_JS)
        print('  after the ✕:', info)
        ok = report('the ✕ dismisses it', info['count'] == 0) and ok

        browser.close()
    return ok


def report(label: str, good: bool) -> bool:
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return good


def main() -> int:
    if '--scene' in sys.argv:
        sc.run(scene, port=PORT)
        return 0
    ok_py = phase_python()
    ok_web = phase_browser()
    ok = ok_py and ok_web
    print('RESULT:', 'ok' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
