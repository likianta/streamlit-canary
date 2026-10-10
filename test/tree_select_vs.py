"""Drive `./tree_select_sc.py` with Playwright.

The scene holds the three path inputs, and this walks the *expanded* one --
the folded-in-place `TreeView` behind `v3.PathInputExpanded`, rooted at
`streamlit_canary`, so the rows under test are its own subpackage: the folder
`components_v3/`, the nested folder `trees/` inside it, and the files beside
them. This folds folders open, ticks rows, and watches the readout under the
panel.

The last sections turn to the other hosts -- the expander's fold button and
the popup's `Browse` / Confirm pair -- and then to the column view: the bare
`ColumnView` is drilled through column by column, and the wrapped one (a
`PathInputExpanded` with `tree_style='column_view'`) is checked to feed its
box a pick as it happens.

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

# The expander's own rows are the `single`-mode `TreeView` rows that are *not*
# the column view's (both are `.st-radio` lists). The columns carry
# `.st-columnview`, so a visible-row count that skips the ones inside it is
# the expander's alone -- the popup's panel is behind a closed popover, and
# the expanded panel below is a `.st-check-group`.
EXPANDER_ROWS_JS = """
() => Array.from(
  document.querySelectorAll('.st-radio .st-radio-item')
).filter((el) => el.offsetParent !== null
  && !el.closest('.st-columnview')).length
"""

# any dropdown on show (they all carry the `hidden` attribute when folded)
OPEN_DROPDOWNS = '.st-selectbox-dropdown:not([hidden])'
# a `PathSelect` frame holds two: the ladder (opened by the box) and the
# history (opened by the caret)
LADDER_OPEN = '.st-text-input-ladder:not([hidden])'
HISTORY_OPEN = '.st-text-input-history:not([hidden])'

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

# Every column view's boxes, in DOM order: their on-show flag, geometry, the
# rows each holds, and the row carrying the trail's mark (`input.checked`).
COLUMNVIEWS_JS = """
() => Array.from(
  document.querySelectorAll('.st-columnview')
).map((cv) => Array.from(cv.children).map((box) => ({
  visible: box.offsetParent !== null,
  x: Math.round(box.getBoundingClientRect().left),
  width: Math.round(box.getBoundingClientRect().width),
  items: Array.from(
    box.querySelectorAll('.st-radio-item')
  ).map((it) => (it.textContent || '').trim()),
  checked: Array.from(
    box.querySelectorAll('.st-radio-item')
  ).filter((it) => it.querySelector('input').checked)
   .map((it) => (it.textContent || '').trim()),
})))
"""

READOUT_NAME_JS = """
(name) => {
  const hit = Array.from(document.querySelectorAll('.st-plain'))
    .find((el) => el.textContent.startsWith(name + ':'));
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


def columns(page, index):
    """The boxes of the column view at `index`, in DOM order."""
    return page.evaluate(COLUMNVIEWS_JS)[index]


def visible_columns(page, index):
    return [col for col in columns(page, index) if col['visible']]


def readout(page, name):
    """The `'<name>: ...'` plain-text readout under a path input."""
    return page.evaluate(READOUT_NAME_JS, name)


def click_in_column(page, view, col, label):
    """Pick the row `label` in column `col` of the column view at `view`."""
    (
        page.locator('.st-columnview')
        .nth(view)
        .locator('.st-radio')
        .nth(col)
        .locator('.st-radio-item')
        .filter(has_text=label)
        .first.click()
    )
    page.wait_for_timeout(600)


def folders_before_files(items):
    """True while no folder row follows a file row."""
    seen_file = False
    for item in items:
        if item.endswith('/'):
            if seen_file:
                return False
        else:
            seen_file = True
    return True


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
            field(page, 'single_list.py', 'checked'),
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
            'the expander starts folded', page.evaluate(EXPANDER_ROWS_JS) == 0
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
            'pressing it unfolds the rows', page.evaluate(EXPANDER_ROWS_JS) > 0
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

    # == 8. PathSelect: one dropdown per gesture ============================
    print('== 8. the inline boxes are PathSelects ==')
    boxes = page.locator('.st-text-input-box')
    good = check('four path boxes on the page', boxes.count() == 4) and good
    good = (
        check(
            'the three inline ones are PathSelects, the popup one is not',
            page.locator('.st-text-select').count() == 3,
        )
        and good
    )
    boxes.first.click()  # the popup's box: a `PathInput`, nothing to unfold
    page.wait_for_timeout(400)
    good = (
        check(
            'clicking the popup box opens nothing',
            page.locator(OPEN_DROPDOWNS).count() == 0,
        )
        and good
    )
    boxes.nth(1).click()  # the expander's box
    page.wait_for_timeout(400)
    good = (
        check(
            'clicking an inline box opens one dropdown',
            page.locator(OPEN_DROPDOWNS).count() == 1,
        )
        and good
    )
    good = (
        check(
            'and the box one is the ladder, not the history',
            page.locator(LADDER_OPEN).count() == 1
            and page.locator(HISTORY_OPEN).count() == 0,
        )
        and good
    )
    rungs = page.evaluate(
        # the first ladder is the expander's; both inline boxes carry one
        '() => Array.from('
        "  document.querySelectorAll('.st-text-input-ladder')[0]"
        "    .querySelectorAll('.st-selectbox-option')"
        ').map(o => o.dataset.value)'
    )
    print('  rungs:', rungs[:3], '...', rungs[-1:])
    good = (
        check(
            'it runs from a drive down to the folder on show',
            bool(rungs) and rungs[0].endswith(':/') and rungs[-1] == HERE,
        )
        and good
    )
    # and that last rung is drawn as the current one, the way a `Selectbox`
    # draws its value (the accent colour, `34-selectbox.css`)
    marked = page.evaluate(
        '() => {'
        "  const ladder = document.querySelectorAll('.st-text-input-ladder')[0];"
        '  const rows = Array.from('
        "    ladder.querySelectorAll('.st-selectbox-option')"
        '  );'
        '  const color = (o) => getComputedStyle('
        "    o.querySelector('.st-selectbox-option-inner')"
        '  ).color;'
        '  return {'
        "    marked: rows.filter(o => o.hasAttribute('data-selected'))"
        '      .map(o => o.dataset.value),'
        '    first: color(rows[0]),'
        '    last: color(rows[rows.length - 1]),'
        '  };'
        '}'
    )
    good = (
        check(
            'the folder on show is the one marked as current',
            marked['marked'] == [HERE],
        )
        and good
    )
    good = (
        check(
            'and it is drawn in the accent colour',
            marked['last'] != marked['first']
            and marked['last'] == 'rgb(255, 75, 75)',
        )
        and good
    )
    page.locator('.st-plain').first.click()  # anywhere outside the frame
    page.wait_for_timeout(400)
    good = (
        check(
            'a click outside closes it again',
            page.locator(OPEN_DROPDOWNS).count() == 0,
        )
        and good
    )
    # the caret speaks for the box's own history instead
    page.locator('.st-text-input-candidates-toggle').nth(1).click()
    page.wait_for_timeout(400)
    good = (
        check(
            'the caret opens the history instead',
            page.locator(HISTORY_OPEN).count() == 1
            and page.locator(LADDER_OPEN).count() == 0,
        )
        and good
    )
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    good = (
        check('Escape closes it too', page.locator(OPEN_DROPDOWNS).count() == 0)
        and good
    )

    # == 9. the enter arrow owns the row's tail =============================
    print('== 9. the enter arrow answers over the whole tail ==')
    item = _item(page, 'components_v3/')
    item_box = item.bounding_box()
    arrow_box = item.locator('.st-row-open').bounding_box()
    good = (
        check(
            "the arrow button reaches the row's right edge",
            item_box['x']
            + item_box['width']
            - (arrow_box['x'] + arrow_box['width'])
            <= 10,
        )
        and good
    )
    # the `..` row's folder icon is the yardstick for the amber: same colour,
    # or the pair is off. (`:visible` is a Playwright thing -- in the page,
    # the rows on show are the ones with an `offsetParent`.)
    amber = page.evaluate(
        '() => {'
        '  const rows = Array.from('
        "    document.querySelectorAll('.st-check-group .st-radio-item')"
        '  ).filter((el) => el.offsetParent !== null);'
        "  return getComputedStyle(rows[0].querySelector('.st-icon')).color;"
        '}'
    )
    # park the pointer near the arrow's own right edge -- the far end of the
    # row's tail, well away from the 20px glyph -- and the arrow still reveals
    # itself, with the row's pair marked
    page.mouse.move(
        arrow_box['x'] + arrow_box['width'] - 4,
        item_box['y'] + item_box['height'] / 2,
    )
    page.wait_for_timeout(400)
    tail = item.evaluate(
        '(el) => ({'
        '  opacity: getComputedStyle('
        "    el.querySelector('.st-row-open')"
        '  ).opacity,'
        '  underline: getComputedStyle('
        "    el.querySelector('.st-radio-markdown')"
        '  ).textDecorationLine,'
        '  color: getComputedStyle('
        "    el.querySelector('.st-radio-markdown p')"
        '  ).color,'
        '})'
    )
    print('  tail:', tail, 'amber:', amber)
    good = (
        check('hovering the tail reveals the arrow', tail['opacity'] == '1')
        and good
    )
    good = (
        check(
            'and the row is underlined and turned the same amber as `..`',
            tail['underline'] == 'underline' and tail['color'] == amber,
        )
        and good
    )
    page.mouse.move(0, 0)
    page.wait_for_timeout(300)

    # == 10. the column view ================================================
    print('== 10. the column view ==')
    good = (
        check(
            'two column views on the page',
            page.locator('.st-columnview').count() == 2,
        )
        and good
    )
    cols = visible_columns(page, 0)
    print(
        '  columns:', [len(col['items']) for col in cols], cols[0]['items'][:3]
    )
    good = check('it opens with one column', len(cols) == 1) and good
    items = cols[0]['items']
    good = (
        check(
            'no `..` row: walking back is a click to the left',
            not any('(goto parent)' in item for item in items),
        )
        and good
    )
    good = (
        check(
            'the listing leads with the folders',
            bool(items) and items[0].endswith('/'),
        )
        and good
    )
    good = (
        check(
            'a folder of the root is on show',
            any('components_v3/' in item for item in items),
        )
        and good
    )
    good = (
        check(
            'a script beside it too',
            any(item.endswith('.py') for item in items),
        )
        and good
    )
    good = (
        check(
            'and the files come after every folder', folders_before_files(items)
        )
        and good
    )

    click_in_column(page, 0, 0, 'components_v3/')
    print('  readout:', readout(page, 'Column'))
    cols = visible_columns(page, 0)
    good = (
        check('clicking a folder opens a column to its right', len(cols) == 2)
        and good
    )
    good = (
        check('and it steps further right', cols[1]['x'] > cols[0]['x'])
        and good
    )
    good = (
        check(
            'the folder is marked as the trail',
            cols[0]['checked'] == ['folder components_v3/'],
        )
        and good
    )
    good = (
        check(
            'the new column lists that folder',
            any('trees/' in item for item in cols[1]['items'])
            and any('base.py' in item for item in cols[1]['items']),
        )
        and good
    )
    good = (
        check(
            'so the readout names the folder now',
            readout(page, 'Column') == 'Column: {}'.format(FOLDER),
        )
        and good
    )

    click_in_column(page, 0, 1, 'base.py')
    print('  readout:', readout(page, 'Column'))
    cols = visible_columns(page, 0)
    good = check('clicking a file opens no column', len(cols) == 2) and good
    good = (
        check(
            'it marks the file row instead',
            cols[1]['checked'] == ['description base.py'],
        )
        and good
    )
    good = (
        check(
            'the trail above stays marked',
            cols[0]['checked'] == ['folder components_v3/'],
        )
        and good
    )
    good = (
        check(
            'and the readout names the file',
            readout(page, 'Column') == 'Column: {}/base.py'.format(FOLDER),
        )
        and good
    )

    click_in_column(page, 0, 1, 'trees/')
    print('  readout:', readout(page, 'Column'))
    cols = visible_columns(page, 0)
    good = (
        check('a folder under the file opens a third column', len(cols) == 3)
        and good
    )
    good = (
        check(
            'the middle column now marks that folder',
            cols[1]['checked'] == ['folder trees/'],
        )
        and good
    )
    good = (
        check(
            'and the readout is the folder again',
            readout(page, 'Column') == 'Column: {}'.format(TREES),
        )
        and good
    )

    click_in_column(page, 0, 0, 'kernel/')
    print('  readout:', readout(page, 'Column'))
    cols = visible_columns(page, 0)
    good = (
        check(
            'walking back in a left column drops the ones to its right',
            len(cols) == 2,
        )
        and good
    )
    good = (
        check(
            'and shows that folder instead',
            any('property.py' in item for item in cols[1]['items']),
        )
        and good
    )
    good = (
        check(
            'the readout follows',
            readout(page, 'Column') == 'Column: {}/kernel'.format(SUBPKG),
        )
        and good
    )
    good = (
        check(
            'the columns share one width',
            len({col['width'] for col in cols}) == 1,
        )
        and good
    )

    # == 11. the wrapped column view ========================================
    print('== 11. the wrapped column view ==')
    good = (
        check(
            'it reads its folder out of the box at rest',
            readout(page, 'Wrapped') == 'Wrapped: {}'.format(SUBPKG),
        )
        and good
    )
    click_in_column(page, 1, 0, 'components_v3/')
    click_in_column(page, 1, 1, 'base.py')
    page.wait_for_timeout(300)
    print('  readout:', readout(page, 'Wrapped'))
    cols = visible_columns(page, 1)
    good = (
        check('it opens a column the way the bare one does', len(cols) == 2)
        and good
    )
    box_value = page.evaluate(
        "() => document.querySelectorAll('.st-text-input-box')[3].value"
    )
    print('  box:', box_value)
    good = (
        check(
            'a pick comes straight back into the box',
            box_value == '{}/base.py'.format(FOLDER),
        )
        and good
    )
    good = (
        check(
            'and the readout follows',
            readout(page, 'Wrapped') == 'Wrapped: {}/base.py'.format(FOLDER),
        )
        and good
    )

    return good


if __name__ == '__main__':
    sys.exit(main())
