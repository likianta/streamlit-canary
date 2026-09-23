"""
Verification for the v3 component model (Row / Text / Button).

Exercises the context-manager tree, Property fields (same model as state)
with change notification, and the button click signal — all in pure Python
(no Streamlit, no frontend). Also wires up the full click-counter flow from
`test/demo_click_counter.py` to prove the components and kernel compose.

Run:
    python test/components_v3_demo.py
"""

import streamlit_canary as sc

from streamlit_canary.kernel import Property
from streamlit_canary.kernel import Signal
from streamlit_canary.kernel import StateV2

# v3 components are intentionally kept under `sc.v3` so they don't pollute the
# stable v1 namespace while the event-driven model is still evolving.
Row = sc.v3.Row
Text = sc.v3.Text
Button = sc.v3.Button

passed = 0
failed = 0


def check(label: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f'  [PASS] {label}')
    else:
        failed += 1
        print(f'  [FAIL] {label}')


# ---------------------------------------------------------------------------
# 1. Context-manager builds the component tree
# ---------------------------------------------------------------------------
print('1. Component tree via context manager')

with Row() as row:
    with Text('hello') as txt:
        pass
    with Button('click') as btn:
        pass

check('Row has 2 children', len(row.children) == 2)
check('first child is Text', isinstance(row.children[0], Text))
check('second child is Button', isinstance(row.children[1], Button))
check('Text parent is Row', txt.parent is row)
check('Button parent is Row', btn.parent is row)

# ids are unique
check('Row/Text/Button have distinct ids', len({row.id, txt.id, btn.id}) == 3)

# ---------------------------------------------------------------------------
# 2. Text.text is a Property (same model as state): get/set/on_change
# ---------------------------------------------------------------------------
print('2. Text.text Property (get/set/on_change + __getitem__/__setitem__)')

t = Text('init')
check('text default is "init"', t.text.get() == 'init')
check("t['text'] == 'init'", t['text'] == 'init')

changes: list = []
# `t.text.on_change` emits no arguments by default (the owner is not
# injected). Bind `sc._self` if the handler needs the Property handle.
t.text.on_change.connect(lambda: changes.append(t.text.get()))

t.text.set('updated')
check('text.set updates value', t.text.get() == 'updated')
check('on_change fired on change', changes == ['updated'])

# setting the same value does not emit
t.text.set('updated')
check('same value does not re-emit', len(changes) == 1)

# __setitem__ alias
t['text'] = 'via item'
check("t['text'] = value works", t.text.get() == 'via item')

# `on_text` alias points to the same signal
check("t['on_text'] is t.text.on_change", t['on_text'] is t.text.on_change)

# ---------------------------------------------------------------------------
# 3. Button.on_click signal
# ---------------------------------------------------------------------------
print('3. Button.on_click signal')

b = Button('Go', type='primary')
check('label stored', b.text.get() == 'Go')
check('type stored', b.type.get() == 'primary')
check('on_click is a Signal', isinstance(b.on_click, Signal))

clicks = [0]


@b.on_click
def _():
    clicks[0] += 1


b.on_click.emit()
b.on_click.emit()
check('on_click fires handlers', clicks[0] == 2)

# ---------------------------------------------------------------------------
# 4. Full click-counter flow (state + components wired together)
# ---------------------------------------------------------------------------
print('4. Click counter end-to-end')


class _State(StateV2):
    count = Property(0)


state = _State()
display = Text('Click count: 0')
button = Button('Increase counter', type='primary')


@state.count.on_change.partial(sc._self)
def _update(cnt: Property):
    display.text.set('Click count: {}'.format(cnt.get()))


@button.on_click
def _increase():
    state['count'] += 1


# simulate clicks
button.on_click.emit()
check('count == 1 after 1 click', state.count.get() == 1)
check('display updated', display.text.get() == 'Click count: 1')

button.on_click.emit()
button.on_click.emit()
check('count == 3 after 3 clicks', state.count.get() == 3)
check('display updated to 3', display.text.get() == 'Click count: 3')

# the demo's exact nesting shape also works
with Row() as outer:
    with Text('Click count: 0') as demo_txt:

        @state.count.on_change.partial(sc._self)
        def _(cnt: Property):
            demo_txt.text.set('Click count: {}'.format(cnt.get()))

    with Button('Increase counter', type='primary') as demo_btn:

        @demo_btn.on_click
        def _():
            state['count'] += 1


demo_btn.on_click.emit()
check('nested demo: count increments', state.count.get() == 4)
check(
    'nested demo: text patches in place',
    demo_txt.text.get() == 'Click count: 4',
)
check('nested demo: demo_txt is a child of outer Row', demo_txt.parent is outer)

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
print()
print(f'=== {passed} passed, {failed} failed ===')
if failed:
    raise SystemExit(1)
