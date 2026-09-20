"""
Verification for the `_Submittable` signals on the input widgets.

Builds a small tree, dispatches the client events a browser would send
(`submit` / `editing_finished` / `new_option` / `new_option_editing_finished`)
and checks the payloads, the emission order, and the value commit. Also checks
that the renderers wire the matching DOM handlers. Pure Python -- no browser.

Run:
    python test/event_driven_system/input_signals_test.py
"""

import typing as tp

from streamlit_canary import components_v3 as v3
from streamlit_canary.components_v3.trees import PathInput
from streamlit_canary.kernel import Signal
from streamlit_canary.runtime.render import render_tree
from streamlit_canary.runtime.runtime import Runtime

passed = 0
failed = 0
log: list[tuple[str, tp.Any]] = []


def check(label: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f'  [PASS] {label}')
    else:
        failed += 1
        print(f'  [FAIL] {label}')


box: dict[str, tp.Any] = {}


def app() -> None:
    box['text'] = ti = v3.TextInput('Text', key='ti')
    box['area'] = ta = v3.TextArea('Area', key='ta')
    box['number'] = ni = v3.NumberInput('Number', step=1, key='ni')
    box['multi'] = ms = v3.Multiselect('Multi', ('a', 'b'), key='ms')
    box['select'] = sb = v3.Selectbox(
        'Select',
        ('x', 'y'),
        accept_new_options=True,
        format_new_option=lambda text: text,
        key='sb',
    )
    box['plain'] = v3.Selectbox('Plain', ('x', 'y'), key='plain')
    box['path'] = pi = PathInput('Path', key='pi')

    for name, widget in (('ti', ti), ('ta', ta), ('ni', ni), ('ms', ms)):
        widget.on_submit.connect(_recorder(f'{name}.submit'))
        widget.on_editing_finished.connect(
            _recorder(f'{name}.editing_finished')
        )
    sb.on_new_option_submit.connect(_recorder('sb.new_option_submit'))
    sb.on_new_option_editing_finished.connect(
        _recorder('sb.new_option_editing_finished')
    )
    pi.on_submit.connect(_recorder('path.submit'))
    pi.on_editing_finished.connect(_recorder('path.editing_finished'))


def _recorder(tag: str) -> tp.Callable[[str], None]:
    def record(text: str) -> None:
        log.append((tag, text))

    return record


runtime = Runtime(app)
runtime.build()


def fire(component_id: str, event: str, value: tp.Any = None) -> list:
    log.clear()
    runtime.on_event(component_id, event, value)
    return list(log)


# ---------------------------------------------------------------------------
# 1. every text-editing widget carries the pair
# ---------------------------------------------------------------------------
print('1. `on_submit` / `on_editing_finished` exist where expected')

for name in ('text', 'area', 'number', 'multi'):
    widget = box[name]
    check(f'{name}: has on_submit (Signal[str])', isinstance(widget.on_submit, Signal))
    check(
        f'{name}: on_submit declares one str payload',
        widget.on_submit._args == (str,),
    )
    check(
        f'{name}: has on_editing_finished',
        isinstance(widget.on_editing_finished, Signal),
    )

check('selectbox: no plain on_submit', not hasattr(box['select'], 'on_submit'))
check(
    'selectbox: has on_new_option_submit',
    hasattr(box['select'], 'on_new_option_submit'),
)
check(
    'plain selectbox: no on_new_option_submit',
    not hasattr(box['plain'], 'on_new_option_submit'),
)

# ---------------------------------------------------------------------------
# 2. TextInput: submit commits the value and emits both signals
# ---------------------------------------------------------------------------
print('2. TextInput submit')

result = fire('ti', 'submit', 'hello')
check('value committed to "hello"', box['text'].value.get() == 'hello')
check(
    'on_submit fired with the text',
    ('ti.submit', 'hello') in result,
)
check(
    'on_editing_finished followed',
    ('ti.editing_finished', 'hello') in result,
)
check(
    'on_submit came first',
    result.index(('ti.submit', 'hello'))
    < result.index(('ti.editing_finished', 'hello')),
)

# ---------------------------------------------------------------------------
# 3. TextInput: blur only finishes editing
# ---------------------------------------------------------------------------
print('3. TextInput blur (editing_finished alone)')

result = fire('ti', 'editing_finished', 'world')
check('value untouched by a blur', box['text'].value.get() == 'hello')
check('on_submit did not fire', not any(t == 'ti.submit' for t, _ in result))
check(
    'on_editing_finished fired with the text',
    result == [('ti.editing_finished', 'world')],
)

# ---------------------------------------------------------------------------
# 4. TextArea / NumberInput submit
# ---------------------------------------------------------------------------
print('4. TextArea / NumberInput submit')

result = fire('ta', 'submit', 'line 1')
check('textarea value committed', box['area'].value.get() == 'line 1')
check('textarea on_submit fired', ('ta.submit', 'line 1') in result)

result = fire('ni', 'submit', '0x29')
check('number value parsed from the text', box['number'].value.get() == 41)
check('number on_submit carries the raw text', ('ni.submit', '0x29') in result)

# ---------------------------------------------------------------------------
# 5. Selectbox accept_new_options: its own pair
# ---------------------------------------------------------------------------
print('5. Selectbox new-option row')

result = fire('sb', 'new_option', 'z')
check(
    'on_new_option_submit fired',
    ('sb.new_option_submit', 'z') in result,
)
check(
    'on_new_option_editing_finished followed',
    ('sb.new_option_editing_finished', 'z') in result,
)
check('the new option was appended', 'z' in box['select'].options.get())
check('the new option was selected', box['select'].value.get() == 'z')

result = fire('sb', 'new_option_editing_finished', 'q')
check(
    'blur only finishes editing',
    result == [('sb.new_option_editing_finished', 'q')],
)
check('a blur adds nothing', 'q' not in box['select'].options.get())

# ---------------------------------------------------------------------------
# 6. PathInput relays its inner box's pair
# ---------------------------------------------------------------------------
print('6. PathInput relays the inner box')

path_input = box['path']
result = fire(path_input._input.id, 'submit', 'x')
check('on_submit relayed with the text', ('path.submit', 'x') in result)
check(
    'on_editing_finished relayed too',
    ('path.editing_finished', 'x') in result,
)

result = fire(path_input._input.id, 'editing_finished', 'y')
check(
    'blur relayed as editing_finished only',
    result == [('path.editing_finished', 'y')],
)

# ---------------------------------------------------------------------------
# 7. renderers wire the DOM handlers
# ---------------------------------------------------------------------------
print('7. rendered markup carries the handlers')

html = render_tree(runtime.roots)
check(
    'text input: Enter + blur + input reset',
    'onkeydown="scSubmitKey(event, this)"' in html
    and 'onblur="scSendEditingFinished(this)"' in html
    and 'oninput="this._scSubmitted=false"' in html,
)
check(
    'text area: Ctrl+Enter submit',
    'onkeydown="scSubmitAreaKey(event, this)"' in html,
)
check(
    'number stepper (x2) + new-option row (x1) keep focus in their box',
    html.count('onmousedown="event.preventDefault()"') == 3,
)
check(
    'selectbox new-option row: blur handler',
    'onblur="scNewOptionBlur(this)"' in html,
)

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
print()
print(f'=== {passed} passed, {failed} failed ===')
if failed:
    raise SystemExit(1)
