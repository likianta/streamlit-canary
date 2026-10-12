"""
When expander expands/collapses, the window scrollbar changes visibility.
We expect that when scrollbar appears, it should not squeeze the page layout
horizontal space.

Run the scene (to look at it in a browser):

    python test/window_scrollbar_quiver.py run_ui

Run the verification (it starts the scene on :2201 itself):

    python test/window_scrollbar_quiver.py verify

A classic (space-taking) scrollbar shrinks the viewport's `clientWidth` by
its own width, and `#app` centres on that -- so a tall element toggling the
page between "fits" and "overflows" would nudge the whole column sideways by
half a scrollbar each time (the "quiver"). `01-base.css` answers with
`html { scrollbar-gutter: stable }`, which keeps the gutter reserved either
way. The behavioural half of the verification only bites on a browser whose
scrollbar takes space; headless chromium paints overlay scrollbars that take
none, so it also asserts the guard itself is in place.
"""

import subprocess
import sys
import time

import streamlit_canary as sc
from argsense import cli
from playwright.sync_api import sync_playwright
from streamlit_canary import components_v3 as v3

PORT = 2201
URL = 'http://localhost:{}'.format(PORT)


def ui():
    v3.Title('Window Scrollbar Quiver Test')
    v3.Text('Click the expander to trigger scrollbar visibility change.')
    with v3.Expander('Long list layout'):
        # v3.TextArea('', height=2000)
        v3.FileTreeView(start_directory='.venv/Lib/site-packages')


@cli
def run_ui():
    sc.run(ui, port=PORT)


# The geometry of the centred column plus the state of the window's scrollbar
# and of the guard that holds the width steady.
_METRICS_JS = """
() => {
  const root = document.documentElement;
  const rect = document.getElementById('app').getBoundingClientRect();
  const style = getComputedStyle(root);
  return {
    overflows: root.scrollHeight > root.clientHeight,
    clientWidth: root.clientWidth,
    bodyWidth: document.body.clientWidth,
    appLeft: Math.round(rect.left * 100) / 100,
    appWidth: Math.round(rect.width * 100) / 100,
    gutter: style.scrollbarGutter,
    overflowY: style.overflowY,
  };
}
"""


def check(label, good):
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


@cli
def verify():
    server = subprocess.Popen(
        [sys.executable, __file__, 'run_ui'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    good = True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1000, 'height': 500})
            deadline = time.time() + 40
            while True:
                try:
                    page.goto(URL, wait_until='domcontentloaded', timeout=2000)
                    break
                except Exception:
                    if time.time() > deadline:
                        raise SystemExit('the scene never came up')
                    time.sleep(0.5)
            page.wait_for_selector('.st-expander-header')
            page.wait_for_timeout(800)

            collapsed = page.evaluate(_METRICS_JS)
            print('  collapsed: {}'.format(collapsed))
            good = (
                check(
                    'the page fits, so no scrollbar yet',
                    collapsed['overflows'] is False,
                )
                and good
            )

            page.click('.st-expander-header')
            page.wait_for_timeout(800)
            expanded = page.evaluate(_METRICS_JS)
            print('  expanded:  {}'.format(expanded))
            good = (
                check(
                    'expanding overflows, so the scrollbar shows',
                    expanded['overflows'] is True,
                )
                and good
            )
            good = (
                check(
                    'the column is not nudged sideways',
                    expanded['appLeft'] == collapsed['appLeft'],
                )
                and good
            )
            good = (
                check(
                    'its width is unchanged',
                    expanded['appWidth'] == collapsed['appWidth'],
                )
                and good
            )
            good = (
                check(
                    'and the layout width holds (the gutter is reserved)',
                    expanded['bodyWidth'] == collapsed['bodyWidth'],
                )
                and good
            )

            page.click('.st-expander-header')
            page.wait_for_timeout(800)
            back = page.evaluate(_METRICS_JS)
            print('  collapsed: {}'.format(back))
            good = (
                check('collapsing hides it again', back['overflows'] is False)
                and good
            )
            good = (
                check(
                    'and nothing moved on the way back',
                    back['appLeft'] == collapsed['appLeft'],
                )
                and good
            )

            # The behavioural checks can only bite where the scrollbar takes
            # layout space. Headless chromium draws overlay scrollbars that
            # take none, so also assert the guard is in place: the root keeps
            # its gutter reserved (either by `scrollbar-gutter` or by a
            # permanently shown bar), which is what holds the width on a
            # classic-scrollbar browser.
            guarded = (
                collapsed['gutter'] in ('stable', 'stable both-edges')
                or collapsed['overflowY'] == 'scroll'
            )
            good = (
                check(
                    'the window reserves its scrollbar gutter '
                    '(gutter={!r}, overflow-y={!r})'.format(
                        collapsed['gutter'], collapsed['overflowY']
                    ),
                    guarded,
                )
                and good
            )
            browser.close()
    finally:
        server.terminate()

    print('')
    print('RESULT:', 'ok' if good else 'FAILED')
    if not good:
        raise SystemExit(1)


if __name__ == '__main__':
    # python -m test.window_scrollbar_quiver -h
    # python -m test.window_scrollbar_quiver run_ui
    # python -m test.window_scrollbar_quiver verify
    cli.run()
