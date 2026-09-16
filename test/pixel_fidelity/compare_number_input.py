"""
Compare `st.number_input` (Streamlit) with `v3.NumberInput`
(Streamlit Canary): geometry of the stepper gadget, its sequence, its hover
state and its disabled state at the two bounds.

The two apps under test (start them first):

    # :2202 (Streamlit)
    python -m streamlit run --browser.gatherUsageStats false \\
        --runner.magicEnabled false --server.headless true \\
        --server.port 2202 test/pixel_fidelity/ui_scene_st.py

    # :2203 (Streamlit Canary)
    python test/pixel_fidelity/ui_scene_sc.py

Then run this comparison:

    python test/pixel_fidelity/compare_number_input.py

Pseudo-code (the spec this script implements):

    1. The stepper gadget is placed in the right side horizontally.
    2. The stepper sequence is "-" then "+".
    3. When mouse hovers, the stepper background changes to theme color.
    4. When value hits min_value, the stepper "-" is disabled (mouse cursor
       shape is "forbidden").
    5. When value hits max_value, the stepper "+" is disabled (mouse cursor
       shape is "forbidden").
"""

from __future__ import annotations

import re
import sys
import time

from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

ST_URL = 'http://localhost:2202'
SC_URL = 'http://localhost:2203'

# Streamlit's right-top "⋮" menu and its theme entries.
ST_MENU_BUTTON = '[data-testid="stMainMenuButton"]'
ST_THEME_DARK = '[data-testid="stMainMenuItem-theme-Dark"]'

ST_SELECTORS = {
    'container': '[data-testid="stNumberInputContainer"]',
    'field': '[data-testid="stNumberInputField"]',
    'stepper': '[data-testid="stNumberInputContainer"] > div',
    'down': '[data-testid="stNumberInputStepDown"]',
    'up': '[data-testid="stNumberInputStepUp"]',
}
SC_SELECTORS = {
    'container': '.st-number-box',
    'field': '.st-number-box > .st-text-input-box',
    'stepper': '.st-number-stepper',
    'down': '.st-number-step:nth-child(1)',
    'up': '.st-number-step:nth-child(2)',
}

_READ_JS = """
([container, field, stepper, down, up]) => {
  const cs = (e) => getComputedStyle(e);
  const rect = (e) => e.getBoundingClientRect();
  const shape = (e) => ({
    width: rect(e).width,
    height: rect(e).height,
    left: rect(e).left,
    top: rect(e).top,
    background: cs(e).backgroundColor,
    color: cs(e).color,
    cursor: cs(e).cursor,
    radius: cs(e).borderTopLeftRadius,
    disabled: !!e.disabled,
  });
  const attr = (name) => (field.dataset[name] !== undefined
    ? field.dataset[name] : field[name]);
  const icon = down.querySelector('svg');
  return {
    container: {
      width: rect(container).width,
      height: rect(container).height,
      background: cs(container).backgroundColor,
      border_width: cs(container).borderTopWidth,
      border_color: cs(container).borderTopColor,
      radius: cs(container).borderTopLeftRadius,
    },
    field: {
      width: rect(field).width,
      right: rect(field).right,
      value: field.value,
      min: attr('min'),
      max: attr('max'),
      step: attr('step'),
    },
    stepper: {
      direction: cs(stepper).flexDirection,
      width: rect(stepper).width,
      height: rect(stepper).height,
      left: rect(stepper).left,
    },
    down: shape(down),
    up: shape(up),
    icon: icon ? { width: rect(icon).width, height: rect(icon).height } : null,
  };
}
"""

_RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')
EPS = 0.6


def parse_color(value: str) -> tuple[float, ...]:
    """Normalize a computed color to `(r, g, b, a)` for comparison."""
    match = _RGBA_RE.search(value)
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


def is_dark_theme(page: Page) -> bool:
    bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
    r, g, b = parse_color(bg)[:3]
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance < 0.5


def toggle_dark_theme(page: Page) -> None:
    page.click(ST_MENU_BUTTON)
    page.click(ST_THEME_DARK)
    page.wait_for_timeout(800)


def read_state(page: Page, selectors: dict) -> dict:
    handles = []
    for key in ('container', 'field', 'stepper', 'down', 'up'):
        handle = page.locator(selectors[key]).first.element_handle()
        assert handle is not None, 'not found: {}'.format(selectors[key])
        handles.append(handle)
    return page.evaluate(_READ_JS, handles)


def center_of(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None, 'no box: {}'.format(selector)
    return box['x'] + box['width'] / 2, box['y'] + box['height'] / 2


def hover_state(page: Page, selectors: dict, key: str) -> dict:
    """Hover one arrow and read its background colour and icon colour."""
    x, y = center_of(page, selectors[key])
    page.mouse.move(x, y)
    page.wait_for_timeout(250)
    return page.evaluate(
        """(e) => ({
          background: getComputedStyle(e).backgroundColor,
          color: getComputedStyle(e).color,
        })""",
        page.locator(selectors[key]).first.element_handle(),
    )


def wait_for_value(
    page: Page, selector: str, expected: str, timeout: float = 10.0
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = page.locator(selector).first.input_value()
        if value == expected:
            return True
        page.wait_for_timeout(120)
    return False


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


def collect(page: Page, selectors: dict) -> dict:
    state = read_state(page, selectors)
    hovering_up = hover_state(page, selectors, 'up')
    hovering_down = hover_state(page, selectors, 'down')
    state['hover_up_background'] = hovering_up['background']
    state['hover_up_color'] = hovering_up['color']
    state['hover_down_background'] = hovering_down['background']
    # Leave the pointer away from the widget before the next step.
    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    return state


def click_step_up(page: Page, selectors: dict, times: int) -> None:
    field = page.locator(selectors['field']).first
    for _ in range(times):
        before = field.input_value()
        x, y = center_of(page, selectors['up'])
        page.mouse.click(x, y)
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if field.input_value() != before:
                break
            page.wait_for_timeout(120)
        page.wait_for_timeout(150)


def main() -> int:
    report = Report()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        st_page = context.new_page()
        st_page.goto(ST_URL)
        st_page.wait_for_selector(ST_SELECTORS['up'], timeout=20000)
        if not is_dark_theme(st_page):
            toggle_dark_theme(st_page)
        assert is_dark_theme(st_page), 'failed to switch Streamlit to dark'

        sc_page = context.new_page()
        sc_page.goto(SC_URL)
        sc_page.wait_for_selector(SC_SELECTORS['up'], timeout=20000)
        assert is_dark_theme(sc_page), 'streamlit-canary is not dark themed'

        st = collect(st_page, ST_SELECTORS)
        sc = collect(sc_page, SC_SELECTORS)

        # -- 1. the gadget sits on the right, horizontally --------------
        report.add_predicate(
            'stepper is right of the field',
            st['stepper']['left'] >= st['field']['right'] - 1,
            sc['stepper']['left'] >= sc['field']['right'] - 1,
        )
        report.add(
            'stepper flex-direction',
            st['stepper']['direction'],
            sc['stepper']['direction'],
        )
        report.add_predicate(
            'both arrows share one row',
            abs(st['down']['top'] - st['up']['top']) < 1,
            abs(sc['down']['top'] - sc['up']['top']) < 1,
        )
        report.add(
            'stepper width', st['stepper']['width'], sc['stepper']['width']
        )
        report.add(
            'stepper height', st['stepper']['height'], sc['stepper']['height']
        )
        report.add('arrow width', st['down']['width'], sc['down']['width'])
        report.add('arrow height', st['down']['height'], sc['down']['height'])
        report.add('icon size', st['icon']['width'], sc['icon']['width'])
        report.add('field width', st['field']['width'], sc['field']['width'])

        # -- 2. "-" then "+" -------------------------------------------
        report.add_predicate(
            '"-" comes before "+"',
            st['down']['left'] < st['up']['left'],
            sc['down']['left'] < sc['up']['left'],
        )
        report.add('"-" left', st['down']['left'], sc['down']['left'])
        report.add('"+" left', st['up']['left'], sc['up']['left'])

        # -- 3. hover changes the background to a theme colour ---------
        report.add_predicate(
            'hover changes the enabled arrow background',
            st['hover_up_background'] != st['up']['background'],
            sc['hover_up_background'] != sc['up']['background'],
        )
        report.add(
            'hovered arrow background',
            st['hover_up_background'],
            sc['hover_up_background'],
            same_color,
        )
        report.add(
            'hovered arrow colour',
            st['hover_up_color'],
            sc['hover_up_color'],
            same_color,
        )
        report.add_predicate(
            'hover does not touch the disabled arrow',
            st['hover_down_background'] == st['down']['background'],
            sc['hover_down_background'] == sc['down']['background'],
        )

        # -- 4. value == min_value: "-" is disabled --------------------
        report.add_predicate(
            '"-" is disabled at min_value',
            st['down']['disabled'],
            sc['down']['disabled'],
        )
        report.add(
            '"-" cursor at min_value',
            st['down']['cursor'],
            sc['down']['cursor'],
        )
        report.add(
            '"-" colour at min_value',
            st['down']['color'],
            sc['down']['color'],
            same_color,
        )
        report.add_predicate(
            '"+" is enabled at min_value',
            not st['up']['disabled'],
            not sc['up']['disabled'],
        )
        report.add(
            '"+" cursor at min_value', st['up']['cursor'], sc['up']['cursor']
        )
        report.add(
            '"+" colour at min_value',
            st['up']['color'],
            sc['up']['color'],
            same_color,
        )

        # -- 5. value == max_value: "+" is disabled --------------------
        max_value = float(st['field']['max'])
        min_value = float(st['field']['min'])
        step = float(st['field']['step'])
        clicks = int(round((max_value - min_value) / step))
        click_step_up(st_page, ST_SELECTORS, clicks)
        click_step_up(sc_page, SC_SELECTORS, clicks)
        assert wait_for_value(
            st_page, ST_SELECTORS['field'], str(int(max_value))
        ), 'streamlit value did not reach max_value'
        assert wait_for_value(
            sc_page, SC_SELECTORS['field'], str(int(max_value))
        ), 'canary value did not reach max_value'

        st_max = read_state(st_page, ST_SELECTORS)
        sc_max = read_state(sc_page, SC_SELECTORS)
        report.add(
            'value after stepping up',
            st_max['field']['value'],
            sc_max['field']['value'],
        )
        report.add_predicate(
            '"+" is disabled at max_value',
            st_max['up']['disabled'],
            sc_max['up']['disabled'],
        )
        report.add(
            '"+" cursor at max_value',
            st_max['up']['cursor'],
            sc_max['up']['cursor'],
        )
        report.add(
            '"+" colour at max_value',
            st_max['up']['color'],
            sc_max['up']['color'],
            same_color,
        )
        report.add_predicate(
            '"-" is enabled at max_value',
            not st_max['down']['disabled'],
            not sc_max['down']['disabled'],
        )

        # -- container / field chrome ----------------------------------
        report.add(
            'container background',
            st['container']['background'],
            sc['container']['background'],
            same_color,
        )
        report.add(
            'container border colour',
            st['container']['border_color'],
            sc['container']['border_color'],
            same_color,
        )
        report.add(
            'container border width',
            st['container']['border_width'],
            sc['container']['border_width'],
        )
        report.add(
            'container radius',
            st['container']['radius'],
            sc['container']['radius'],
        )
        report.add(
            'container height',
            st['container']['height'],
            sc['container']['height'],
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
