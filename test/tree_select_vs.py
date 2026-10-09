"""Drive `./tree_select_sc.py` with Playwright.

The scene holds the three path inputs, and this walks the *expanded* one --
the folded-in-place `TreeView` behind `v3.PathInputExpanded`, rooted at
`streamlit_canary`, so the rows under test are its own subpackage: the folder
`components_v3/`, the nested folder `trees/` inside it, and the files beside
them. This folds folders open, ticks rows, and watches the readout under the
panel.

The last section turns to the other two hosts: the expander's fold button and
the popup's `Browse` / Confirm pair.

Everything it checks lives in the DOM the server sent -- the inset, the
chevron, the half-ticked box -- plus the compact pick that comes back out of
`value` on the page. (The rows also carry Material-icon ligature names in
their `textContent`, e.g. `keyboard_arrow_rightfolder trees/arrow_forward`,
so the row labels are matched by substring throughout.)

It starts the scene itself, so :2201 must be free. Run it from the repo root:

    python test/tree_select_vs.py
"""

import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

URL = 'http://localhost:2201'
SCENE = 'test/tree_select_sc.py'

HERE = os.path.abspath('.').replace('\\', '/')
SUBPKG = HERE + '/streamlit_canary'
FOLDER = SUBPKG + '/components_v3'
TREES = FOLDER + '/trees'

# the expander's own rows: a `single`-mode panel, so its radio list is the
# visible one (the expanded panel below it is in `multiple`, whose radio list
# is hidden, and the popup's panel is inside a closed popover)
EXPANDER_ROWS = '.st-radio .st-radio-item:visible'

# Every panel builds a hidden option list for the mode it is not in, so each
# query here side-steps the invisible ones: among the three, the expanded
# panel is the only one whose check group is on show (`:visible` for the
# locators, a filter on `offsetParent` for the `evaluate` calls).
STATE_JS = """
(label) => {
  const item = Array.from(
    document.querySelectorAll('.st-check-group .st-radio-item')
  ).filter((el) => el.offsetParent !== null)
   .find((el) => el.textContent.includes(label));
  if (!item) return null;
  const input = item.querySelector('input');
  const box = item.querySelector('.st-checkbox-box');
  const row = item.querySelector('.st-radio-item-row');
  const toggle = item.querySelector('.st-row-toggle');
  const icon = toggle ? toggle.querySelector('.st-icon') : null;
  return {
    checked: input.checked,
    half: input.hasAttribute('data-indeterminate'),
    dash: getComputedStyle(box, '::after').width,
    fill: getComputedStyle(box).backgroundColor,
    depth: getComputedStyle(row).getPropertyValue('--st-tree-depth').trim(),
    box_x: Math.round(box.getBoundingClientRect().left),
    toggle: !!item.querySelector('.st-row-toggle:not(.is-empty)'),
    expanded: toggle ? toggle.classList.contains('is-expanded') : false,
    chevron: icon ? getComputedStyle(icon).transform : null,
    label: toggle ? toggle.getAttribute('aria-label') : null,
  };
}
"""

ROWS_JS = """
() => Array.from(
  document.querySelectorAll('.st-check-group .st-radio-item')
).filter((el) => el.offsetParent !== null)
 .map((el) => (el.textContent || '').trim())
"""

READOUT_JS = """
() => {
  const els = Array.from(document.querySelectorAll('.st-plain'));
  const hit = els.find((el) => el.textContent.startsWith('Expanded:'));
  return hit ? hit.textContent.trim() : null;
}
"""


def check(label, good):
    print('  [{}] {}'.format('ok  ' if good else 'FAIL', label))
    return bool(good)


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, SCENE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    good = True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1100, 'height': 1000})
            deadline = time.time() + 40
            while True:
                try:
                    page.goto(URL, wait_until='domcontentloaded', timeout=2000)
                    break
                except Exception:
                    if time.time() > deadline:
                        raise SystemExit('the scene never came up')
                    time.sleep(0.5)
            page.wait_for_selector('.st-check-group:visible .st-radio-item')
            page.wait_for_timeout(1000)

            good = walk(page) and good
            browser.close()
    finally:
        server.terminate()

    print('')
    print('RESULT:', 'ok' if good else 'FAILED')
    return 0 if good else 1


def state(page, label):
    return page.evaluate(STATE_JS, label)


def field(page, label, key):
    """One field of a row's state, or `None` if the row is not on show."""
    st = state(page, label)
    return None if st is None else st.get(key)


def click_box(page, label):
    _item(page, label).locator('.st-checkbox-box').click()
    page.wait_for_timeout(500)


def click_toggle(page, label):
    _item(page, label).locator('.st-row-toggle').click()
    page.wait_for_timeout(500)


def _item(page, label):
    return (
        page.locator('.st-check-group:visible .st-radio-item')
        .filter(has_text=label)
        .first
    )


def walk(page) -> bool:
    good = True

    # == 1. the top level ===================================================
    print('== 1. the top level ==')
    rows = page.evaluate(ROWS_JS)
    print('  rows:', rows)
    good = check('`..` leads the listing', rows[0].endswith('(goto parent)'))
    good = (
        check(
            'the root folder is on show',
            any('components_v3/' in r for r in rows),
        )
        and good
    )
    good = (
        check(
            'a file of the same level is on show',
            any('session.py' in r for r in rows),
        )
        and good
    )

    print('  folder:', state(page, 'components_v3/'))
    print('  file:  ', state(page, 'session.py'))
    good = (
        check(
            'a folder carries a chevron',
            field(page, 'components_v3/', 'toggle'),
        )
        and good
    )
    good = (
        check('it starts folded', not field(page, 'components_v3/', 'expanded'))
        and good
    )
    good = (
        check(
            'its chevron points right',
            field(page, 'components_v3/', 'chevron') == 'none',
        )
        and good
    )
    good = (
        check(
            'it says "Expand"',
            field(page, 'components_v3/', 'label') == 'Expand',
        )
        and good
    )
    good = (
        check('a file has no chevron', not field(page, 'session.py', 'toggle'))
        and good
    )
    good = (
        check(
            'the boxes of one level share one x (the empty cell holds the place)',
            field(page, 'components_v3/', 'box_x')
            == field(page, 'session.py', 'box_x'),
        )
        and good
    )
    good = (
        check(
            'nothing is half-ticked yet',
            not field(page, 'components_v3/', 'half'),
        )
        and good
    )

    # == 2. folding a folder open ===========================================
    print('== 2. folding a folder open ==')
    click_toggle(page, 'components_v3/')
    print('  folder:', state(page, 'components_v3/'))
    print('  child: ', state(page, 'trees/'))
    good = (
        check('it reads as open', field(page, 'components_v3/', 'expanded'))
        and good
    )
    good = (
        check(
            'and says "Collapse"',
            field(page, 'components_v3/', 'label') == 'Collapse',
        )
        and good
    )
    good = (
        check(
            'its chevron turned a quarter turn',
            field(page, 'components_v3/', 'chevron') != 'none',
        )
        and good
    )
    good = (
        check(
            'its child folder is now a row',
            field(page, 'trees/', 'depth') == '1',
        )
        and good
    )
    good = (
        check(
            'so its box sits further right',
            field(page, 'trees/', 'box_x')
            > field(page, 'components_v3/', 'box_x'),
        )
        and good
    )
    good = (
        check(
            'the child folder carries its own chevron',
            field(page, 'trees/', 'toggle'),
        )
        and good
    )
    good = (
        check('and starts folded too', not field(page, 'trees/', 'expanded'))
        and good
    )
    good = (
        check(
            'a file inside is on the same line as the child folder',
            field(page, 'base.py', 'box_x') == field(page, 'trees/', 'box_x'),
        )
        and good
    )

    # == 3. ticking a folder ================================================
    print('== 3. ticking a folder ==')
    click_box(page, 'components_v3/')
    print('  folder:', state(page, 'components_v3/'))
    print('  readout:', page.evaluate(READOUT_JS))
    good = (
        check('the folder is ticked', field(page, 'components_v3/', 'checked'))
        and good
    )
    good = (
        check('and not half-ticked', not field(page, 'components_v3/', 'half'))
        and good
    )
    good = (
        check(
            'a folder inside it reads as ticked too',
            field(page, 'trees/', 'checked'),
        )
        and good
    )
    good = (
        check(
            'and a file inside it does too', field(page, 'base.py', 'checked')
        )
        and good
    )
    good = (
        check(
            'a file outside it is untouched',
            not field(page, 'session.py', 'checked'),
        )
        and good
    )
    good = (
        check(
            'the pick that comes out is the folder itself',
            page.evaluate(READOUT_JS) == "Expanded: ['{}']".format(FOLDER),
        )
        and good
    )

    # == 4. un-ticking one file inside it ===================================
    print('== 4. un-ticking a row inside it ==')
    click_box(page, 'base.py')
    print('  folder:', state(page, 'components_v3/'))
    print('  readout:', page.evaluate(READOUT_JS))
    good = (
        check(
            'the folder is half-ticked now',
            field(page, 'components_v3/', 'half'),
        )
        and good
    )
    good = (
        check(
            'its box is filled like a ticked one',
            field(page, 'components_v3/', 'fill') == 'rgb(255, 75, 75)',
        )
        and good
    )
    good = (
        check(
            'and the mark is a dash, not a checkmark',
            field(page, 'components_v3/', 'dash') == '8px',
        )
        and good
    )
    good = (
        check(
            'the folder itself is not "checked"',
            not field(page, 'components_v3/', 'checked'),
        )
        and good
    )
    good = (
        check(
            'the folder pick was opened up (it is no longer an element)',
            "'{}'".format(FOLDER) not in (page.evaluate(READOUT_JS) or ''),
        )
        and good
    )
    good = (
        check(
            'a folder inside is still a pick',
            "'{}'".format(TREES) in (page.evaluate(READOUT_JS) or ''),
        )
        and good
    )
    good = (
        check(
            'a row inside it is still ticked', field(page, 'trees/', 'checked')
        )
        and good
    )

    # == 5. deeper: a covered subfolder opens up when one of its rows leaves ==
    print('== 5. two levels deep ==')
    click_toggle(page, 'trees/')
    print('  deep:', state(page, 'tree_view.py'))
    good = (
        check('the nested folder is ticked', field(page, 'trees/', 'checked'))
        and good
    )
    good = (
        check(
            'its boxes sit one level deeper again',
            field(page, 'tree_view.py', 'depth') == '2',
        )
        and good
    )
    good = (
        check(
            'so they step further right',
            field(page, 'tree_view.py', 'box_x')
            > field(page, 'trees/', 'box_x'),
        )
        and good
    )
    good = (
        check(
            'a file inside it reads as ticked',
            field(page, 'tree_view.py', 'checked'),
        )
        and good
    )
    click_box(page, 'tree_view.py')
    print('  nested:', state(page, 'trees/'))
    print('  readout:', page.evaluate(READOUT_JS))
    good = (
        check(
            'the nested folder is half-ticked now',
            field(page, 'trees/', 'half'),
        )
        and good
    )
    good = (
        check(
            'but its other files are still ticked',
            field(page, 'recent.py', 'checked'),
        )
        and good
    )
    good = (
        check(
            'the file that left is out',
            not field(page, 'tree_view.py', 'checked'),
        )
        and good
    )
    good = (
        check(
            'and it left the pick (the folder opened into its rows)',
            "'{}/tree_view.py'".format(TREES)
            not in (page.evaluate(READOUT_JS) or ''),
        )
        and good
    )

    # == 6. folding it back up ==============================================
    print('== 6. folding it back ==')
    before = len(page.evaluate(ROWS_JS))
    click_toggle(page, 'components_v3/')
    after = len(page.evaluate(ROWS_JS))
    print('  rows: {} -> {}'.format(before, after))
    good = check('the rows below it are gone', after < before) and good
    good = (
        check(
            'it reads as folded', not field(page, 'components_v3/', 'expanded')
        )
        and good
    )
    good = (
        check(
            'and half-ticked still (the pick did not move)',
            field(page, 'components_v3/', 'half'),
        )
        and good
    )
    good = (
        check(
            'the child rows are not in the listing any more',
            state(page, 'trees/') is None,
        )
        and good
    )

    # == 7. the expander and the popup ======================================
    print('== 7. the expander and the popup ==')
    good = (
        check(
            'the expander starts folded',
            page.locator(EXPANDER_ROWS).count() == 0,
        )
        and good
    )
    # `.st-btn-icon` tells the fold button from the popup's trigger, whose
    # own chevron carries the same ligature name
    fold = page.locator('.st-btn-icon', has_text='expand_more')
    good = check('its fold button points down', fold.count() == 1) and good
    fold.click()
    page.wait_for_timeout(600)
    good = (
        check(
            'pressing it unfolds the rows',
            page.locator(EXPANDER_ROWS).count() > 0,
        )
        and good
    )
    good = (
        check(
            'and turns the glyph up',
            page.locator('.st-btn-icon', has_text='expand_less').count() == 1,
        )
        and good
    )

    browse = page.locator('.st-popover-trigger', has_text='Browse')
    good = check('the popup offers a Browse', browse.count() == 1) and good
    browse.click()
    page.wait_for_timeout(700)
    panel = page.locator('.st-popover-panel:visible')
    good = check('it opened a panel', panel.count() == 1) and good
    panel.locator('.st-radio .st-radio-item:visible').filter(
        has_text='streamlit_canary/'
    ).first.click()
    page.wait_for_timeout(400)
    panel.locator('.st-btn', has_text='Confirm').click()
    page.wait_for_timeout(700)
    box = page.evaluate(
        "() => document.querySelector('.st-text-input-box').value"
    )
    print('  popup box:', box)
    good = check('Confirm wrote the pick into the box', box == SUBPKG) and good
    good = (
        check(
            'and folded the popover away',
            page.locator('.st-popover-panel:visible').count() == 0,
        )
        and good
    )

    return good


if __name__ == '__main__':
    sys.exit(main())
