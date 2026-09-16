"""
Compare the `:material/..:` icons (Streamlit vs Streamlit Canary).

Streamlit ships the 'Material Symbols Rounded' font and renders the icon
*name* in it: the font's ligatures turn e.g. `adjust` into the slider glyph.
Canary bundles the very same font file, so the two apps have to draw the same
glyph, from the same box, at the same place.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_material_icons.py

Pseudo-code (the spec this script implements):

    1. `:material/<name>:` draws a glyph -- not the icon name, not a stand-in
       character -- using the 'Material Symbols Rounded' font, which must
       actually be loaded (an icon is exactly `1em` wide, so a fallback font
       would blow the box up to the width of the name).
    2. The icon is an inline-block of the *inherited* font size pinned to the
       bottom of the line (16px inside a paragraph, 14px inside the popover
       trigger's label) and it inherits the axis' colour, so
       `:orange[:material/brightness_auto:]` tints it.
    3. The icons sit at the same x/y in both apps, i.e. the sentence around
       them advances by exactly the same amount.
    4. The markdown block itself keeps its content width inside a horizontal
       container, like Streamlit's element container.
    5. The trigger chevron is the same glyph too: `expand_more` closed,
       `expand_less` open -- swapped, never rotated.

Note that Streamlit draws its *other* chrome icons (the selectbox arrow, the
number-input steppers, the checkbox tick, the code copy button, the `help`
glyph) as inline SVGs, so those stay SVGs here as well; only the markdown
icons and the two chevrons come from the font.

The selectors differ per app (Streamlit's markdown carries test ids, ours
carry classes), so they are given per app just like in the sibling scripts.
"""

from __future__ import annotations

import re
import sys

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit's right-top "⋮" menu and its theme entries.
ST_MENU_BUTTON = '[data-testid="stMainMenuButton"]'
ST_THEME_DARK = '[data-testid="stMainMenuItem-theme-Dark"]'

ST_SELECTORS = {
    # The sentence is one of several markdown blocks in the scene, so it is
    # located by the icons it holds rather than by position. Streamlit marks
    # an inline icon with `role="img"` (the name it draws carries an
    # `aria-label` of "<name> icon").
    'markdown': '[data-testid="stMarkdown"]',
    'icon': 'span[role="img"]',
    'popover_icon': '[data-testid="stPopoverButton"] span[role="img"]',
    # The chevron of the trigger is an "UI" icon, so it does carry the test id.
    'popover_chevron': '[data-testid="stPopoverButton"] '
    '[data-testid="stIconMaterial"]',
}
SC_SELECTORS = {
    'markdown': '.st-markdown',
    'icon': '.st-icon',
    'popover_icon': '.st-popover-trigger .st-popover-trigger-label .st-icon',
    'popover_chevron': '.st-popover-trigger .st-popover-chevron',
}

ICON_FONT = 'Material Symbols Rounded'
EPS = 0.6

# The icon names the scene asks for, in order.
EXPECTED_NAMES = ('adjust', 'settings_backup_restore', 'brightness_auto')

_READ_JS = """
(a) => {
  const iconsOf = (el) => Array.from(el.querySelectorAll(a.icon));
  let host = null;
  document.querySelectorAll(a.markdown).forEach((el) => {
    if (!host && iconsOf(el).length) host = el;
  });
  const pick = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return {
      width: +box.width.toFixed(2),
      height: +box.height.toFixed(2),
      left: +box.left.toFixed(2),
      top: +box.top.toFixed(2),
      font_size: cs.fontSize,
      line_height: cs.lineHeight,
      font_family: cs.fontFamily,
      color: cs.color,
      display: cs.display,
      vertical_align: cs.verticalAlign,
    };
  };
  const icon = (el) => {
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return {
      name: (el.textContent || '').trim(),
      width: +box.width.toFixed(2),
      height: +box.height.toFixed(2),
      left: +box.left.toFixed(2),
      top: +box.top.toFixed(2),
      font_size: cs.fontSize,
      font_weight: cs.fontWeight,
      line_height: cs.lineHeight,
      font_family: cs.fontFamily,
      color: cs.color,
      display: cs.display,
      vertical_align: cs.verticalAlign,
      transform: cs.transform,
      translate: el.getAttribute('translate'),
    };
  };
  const icons = host ? iconsOf(host).map(icon) : [];
  return {
    font_loaded: document.fonts.check('16px "' + a.font + '"'),
    markdown: pick(host),
    icons,
    names: icons.map((it) => it.name),
    popover_icon: document.querySelector(a.popover_icon)
      ? icon(document.querySelector(a.popover_icon)) : null,
    popover_chevron: document.querySelector(a.popover_chevron)
      ? icon(document.querySelector(a.popover_chevron)) : null,
  };
}
"""

_RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')


def parse_color(value) -> tuple[float, ...]:
    """Normalize a computed color to `(r, g, b, a)` for comparison."""
    match = _RGBA_RE.search(value) if isinstance(value, str) else None
    if match is None:
        return (float('nan'),) * 4
    parts = [x.strip() for x in match.group(1).split(',')]
    rgba = [float(x) for x in parts[:3]]
    rgba.append(float(parts[3]) if len(parts) > 3 else 1.0)
    return tuple(rgba)


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= EPS
    return str(a) == str(b)


def same_color(a: str, b: str) -> bool:
    return parse_color(a) == parse_color(b)


def uses_icon_font(value: str) -> bool:
    """True when the only font asked for is the icon font."""
    return ICON_FONT in str(value)


def is_dark_theme(page: Page) -> bool:
    bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
    r, g, b = parse_color(bg)[:3]
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance < 0.5


def toggle_dark_theme(page: Page) -> None:
    page.click(ST_MENU_BUTTON)
    page.click(ST_THEME_DARK)
    page.wait_for_timeout(800)


def dismiss_rerun_notice(page: Page) -> None:
    """Dismiss the dev-time "source file changed" notice, if present.

    While it is visible the page reserves 76px of top padding for it, which
    would shift the whole app down and skew every vertical measurement.
    """
    close = page.locator('#sc-rerun-toast .st-rerun-close')
    if close.count() == 0 or not close.first.is_visible():
        return
    close.first.click()
    page.wait_for_selector('body.sc-rerun-visible', state='detached')
    page.wait_for_timeout(200)


def read(page: Page, selectors: dict) -> dict:
    data = page.evaluate(_READ_JS, dict(selectors, font=ICON_FONT))
    assert data['markdown'] is not None, 'no markdown block with icons found'
    assert len(data['icons']) == len(EXPECTED_NAMES), (
        'expected {} icons, got {}'.format(
            len(EXPECTED_NAMES), len(data['icons'])
        )
    )
    return data


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, bool]] = []

    def add(self, label: str, st_val, sc_val, cmp=same) -> None:
        self.rows.append(
            (label, str(st_val), str(sc_val), bool(cmp(st_val, sc_val)))
        )

    def add_predicate(self, label: str, st_ok, sc_ok) -> None:
        self.rows.append(
            (
                label,
                str(bool(st_ok)),
                str(bool(sc_ok)),
                bool(st_ok) and bool(sc_ok),
            )
        )

    def print(self) -> None:
        width = max(len(row[0]) for row in self.rows)
        print('')
        print(
            '{:<{w}} {:<30} {:<30} {}'.format(
                'check', 'streamlit (:2202)', 'canary (:2203)', 'ok', w=width
            )
        )
        print('-' * 110)
        for label, st_val, sc_val, ok in self.rows:
            print(
                '{:<{w}} {:<30} {:<30} {}'.format(
                    label, st_val, sc_val, 'YES' if ok else 'NO', w=width
                )
            )

    @property
    def failures(self) -> list[tuple[str, str, str]]:
        return [
            (label, st_val, sc_val)
            for label, st_val, sc_val, ok in self.rows
            if not ok
        ]


def main() -> int:
    report = Report()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_SELECTORS['markdown'], timeout=20000)
        st_page.wait_for_timeout(1400)
        if not is_dark_theme(st_page):
            toggle_dark_theme(st_page)
        assert is_dark_theme(st_page), 'failed to switch Streamlit to dark'

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_SELECTORS['markdown'], timeout=20000)
        sc_page.wait_for_timeout(1400)
        dismiss_rerun_notice(sc_page)
        assert is_dark_theme(sc_page), 'streamlit-canary is not dark themed'

        # The icon font has to be in place before anything is measured.
        for page in (st_page, sc_page):
            page.evaluate('document.fonts.ready')
        st_page.wait_for_timeout(400)
        sc_page.wait_for_timeout(400)

        st = read(st_page, ST_SELECTORS)
        sc = read(sc_page, SC_SELECTORS)

        # -- 1. the icons are glyphs of the bundled font -----------------
        report.add_predicate(
            'the icon font is loaded', st['font_loaded'], sc['font_loaded']
        )
        report.add_predicate(
            'the icon spans use that font',
            uses_icon_font(st['icons'][0]['font_family']),
            uses_icon_font(sc['icons'][0]['font_family']),
        )
        report.add('icon names', ', '.join(st['names']), ', '.join(sc['names']))
        report.add(
            'icon names as expected',
            ', '.join(EXPECTED_NAMES) == ', '.join(st['names']),
            ', '.join(EXPECTED_NAMES) == ', '.join(sc['names']),
        )
        report.add_predicate(
            'the icon is `1em` wide (a glyph, not the name)',
            same(st['icons'][0]['width'], 16),
            same(sc['icons'][0]['width'], 16),
        )
        report.add_predicate(
            'the name is off for translators',
            st['icons'][0]['translate'] == 'no',
            sc['icons'][0]['translate'] == 'no',
        )

        # -- 2. the icon follows its surroundings ------------------------
        report.add_predicate(
            'the icon is an inline-block on the line bottom',
            st['icons'][0]['display'] == 'inline-block'
            and st['icons'][0]['vertical_align'] == 'bottom',
            sc['icons'][0]['display'] == 'inline-block'
            and sc['icons'][0]['vertical_align'] == 'bottom',
        )
        report.add(
            'icon font size',
            st['icons'][0]['font_size'],
            sc['icons'][0]['font_size'],
        )
        report.add(
            'icon font weight',
            st['icons'][0]['font_weight'],
            sc['icons'][0]['font_weight'],
        )
        report.add(
            'icon line height',
            st['icons'][0]['line_height'],
            sc['icons'][0]['line_height'],
        )
        report.add(
            'tinted icon colour',
            st['icons'][2]['color'],
            sc['icons'][2]['color'],
            same_color,
        )
        report.add_predicate(
            'the tint differs from the plain icon',
            not same_color(st['icons'][2]['color'], st['icons'][0]['color']),
            not same_color(sc['icons'][2]['color'], sc['icons'][0]['color']),
        )

        # -- 3. the sentence lays out identically -----------------------
        for i, name in enumerate(EXPECTED_NAMES):
            report.add(
                'icon[{}] position'.format(i),
                '{}, {}'.format(st['icons'][i]['left'], st['icons'][i]['top']),
                '{}, {}'.format(sc['icons'][i]['left'], sc['icons'][i]['top']),
                cmp=lambda a, b: all(
                    same(float(x), float(y))
                    for x, y in zip(a.split(', '), b.split(', '))
                ),
            )
        report.add(
            'icon box height',
            st['icons'][0]['height'],
            sc['icons'][0]['height'],
        )

        # -- 4. the markdown block keeps its content width --------------
        report.add(
            'markdown block width',
            st['markdown']['width'],
            sc['markdown']['width'],
        )
        report.add(
            'markdown block height',
            st['markdown']['height'],
            sc['markdown']['height'],
        )
        report.add(
            'markdown font size',
            st['markdown']['font_size'],
            sc['markdown']['font_size'],
        )

        # -- 5. an icon inside a widget label inherits its size ---------
        report.add_predicate(
            'the popover label draws an icon too',
            st['popover_icon'] is not None,
            sc['popover_icon'] is not None,
        )
        if st['popover_icon'] and sc['popover_icon']:
            report.add(
                'popover icon size',
                st['popover_icon']['font_size'],
                sc['popover_icon']['font_size'],
            )
            report.add(
                'popover icon width',
                st['popover_icon']['width'],
                sc['popover_icon']['width'],
            )

        # -- 6. the trigger's chevron: same glyph, swapped on open -------
        st_chev = st['popover_chevron']
        sc_chev = sc['popover_chevron']
        report.add_predicate(
            'the trigger chevron is an icon glyph',
            st_chev is not None,
            sc_chev is not None,
        )
        if st_chev and sc_chev:
            report.add(
                'trigger chevron (closed)', st_chev['name'], sc_chev['name']
            )
            report.add(
                'trigger chevron font size / box',
                '{} / {}x{}'.format(
                    st_chev['font_size'], st_chev['width'], st_chev['height']
                ),
                '{} / {}x{}'.format(
                    sc_chev['font_size'], sc_chev['width'], sc_chev['height']
                ),
            )
            report.add_predicate(
                'the chevron is not rotated (the glyph is swapped)',
                st_chev['transform'] == 'none',
                sc_chev['transform'] == 'none',
            )

            # Park the pointer in a corner first: a tooltip left open by an
            # earlier hover would otherwise swallow the click (in either app).
            for page in (st_page, sc_page):
                page.mouse.move(4, 4)
                page.wait_for_timeout(400)
            st_page.click(ST_SELECTORS['popover_chevron'])
            sc_page.click(SC_SELECTORS['popover_chevron'])
            st_page.wait_for_timeout(500)
            sc_page.wait_for_timeout(500)
            st_open = read(st_page, ST_SELECTORS)['popover_chevron']
            sc_open = read(sc_page, SC_SELECTORS)['popover_chevron']
            report.add(
                'trigger chevron (open)', st_open['name'], sc_open['name']
            )
            report.add_predicate(
                'the open glyph differs from the closed one',
                st_open['name'] != st_chev['name'],
                sc_open['name'] != sc_chev['name'],
            )
            report.add(
                'open chevron box',
                '{}x{}'.format(st_open['width'], st_open['height']),
                '{}x{}'.format(sc_open['width'], sc_open['height']),
            )

        report.print()
        browser.close()

    if report.failures:
        print('')
        print('FAILED ({} mismatch(es)):'.format(len(report.failures)))
        for label, st_val, sc_val in report.failures:
            print(
                '  {label}: streamlit={st} canary={sc}'.format(
                    label=label, st=st_val, sc=sc_val
                )
            )
        return 1

    print('')
    print('PASSED: all asserted props match.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except AssertionError as e:
        print('')
        print('ERROR: {}'.format(e))
        sys.exit(2)
