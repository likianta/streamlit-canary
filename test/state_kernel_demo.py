"""
Kernel verification for Property / Signal / StateV2.

This script exercises the event-driven kernel in isolation (no Streamlit, no
frontend). It validates the six accessors derived from `sc.Property`, the
on_change signal passing the Property handle directly, version handling, and
the end-to-end click counter logic from `test/demo_click_counter.py`.

Run:
    python test/state_kernel_demo.py
"""

from streamlit_canary.kernel import Property
from streamlit_canary.kernel import Signal
from streamlit_canary.kernel import StateV2

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
# 1. StateV2 + Property: the six derived accessors
# ---------------------------------------------------------------------------
print('1. Property six accessors')


class _State(StateV2):
    count = Property(0)
    name = Property('init')
    __version__ = 2


state = _State()

# 1. state.count.get()
check('count.get() == 0', state.count.get() == 0)
check('name.get() == "init"', state.name.get() == 'init')

# 2. state.count.set(value)
state.count.set(5)
check('count.set(5) -> get() == 5', state.count.get() == 5)

# 3. state.count.on_change is a Signal
check('count.on_change is a Signal', isinstance(state.count.on_change, Signal))

# 4. state['count'] (alias of .get())
check("state['count'] == 5", state['count'] == 5)

# 5. state['count'] = value (alias of .set())
state['count'] = 10
check("state['count'] = 10 -> get() == 10", state.count.get() == 10)

# 6. state['on_count'] (alias of .on_change)
check(
    "state['on_count'] is state.count.on_change",
    state['on_count'] is state.count.on_change,
)

# `state['count'] += 1` sugar (get + 1, then set)
state['count'] += 1
check("state['count'] += 1 -> 11", state['count'] == 11)

# bound handle identity is stable
check('state.count returns same handle', state.count is state.count)

# version from __version__
check('version == 2 (from __version__)', state.version == 2)

# version from explicit kwarg overrides class __version__
state2 = _State(version=99)
check('version == 99 (explicit kwarg)', state2.version == 99)

# ---------------------------------------------------------------------------
# 2. Signal: decorator + connect + emit
# ---------------------------------------------------------------------------
print('2. Signal basics')

calls: list = []
sig = Signal()


@sig
def handler(x):
    calls.append(x)


sig.emit(42)
check('@sig decorator registers handler', calls == [42])

sig.disconnect(handler)
sig.emit(7)
check('disconnect stops handler', calls == [42])

# multiple handlers
calls2: list = []
sig2 = Signal()
sig2.connect(lambda: calls2.append('a'))
sig2.connect(lambda: calls2.append('b'))
sig2.emit()
check('multiple handlers fire in order', calls2 == ['a', 'b'])

# ---------------------------------------------------------------------------
# 3. on_change passes the Property handle directly; generic partial
# ---------------------------------------------------------------------------
print('3. on_change passes handle + generic partial')

state_a = _State()
received: list = []


@state_a.count.on_change
def h3(cnt: Property):
    received.append(cnt)


state_a.count.set(7)
check(
    'on_change passes the Property handle as arg',
    isinstance(received[0], Property) and received[0].get() == 7,
)
check(
    'the received handle is the same as state.count',
    received[0] is state_a.count,
)

# generic partial: binds static args in front of emitted args
sig4 = Signal()
received4: list = []


@sig4.partial('prefix')
def h4(prefix, val):
    received4.append((prefix, val))


sig4.emit('val1')
check(
    'partial binds static arg in front of emitted arg',
    received4 == [('prefix', 'val1')],
)

# ---------------------------------------------------------------------------
# 4. Property.on_change fires on set; same value does not fire
# ---------------------------------------------------------------------------
print('4. Property.on_change emission')

state3 = _State()
change_count = [0]


@state3.count.on_change
def _(_cnt: Property):
    change_count[0] += 1


state3.count.set(1)
check('on_change fires on real change', change_count[0] == 1)

state3.count.set(1)  # same value
check('on_change does NOT fire for same value', change_count[0] == 1)

state3.count.set(2)
check('on_change fires again on new value', change_count[0] == 2)

# ---------------------------------------------------------------------------
# 5. End-to-end: click counter logic (no UI)
#    Mirrors test/demo_click_counter.py but with mock components.
# ---------------------------------------------------------------------------
print('5. Click counter end-to-end')


class _CounterState(StateV2):
    count = Property(0)


counter = _CounterState()


# mock Text component: holds a `text` attribute
class MockText:
    def __init__(self, text):
        self.text = text


txt = MockText('Click count: 0')


@counter.count.on_change
def _update_text(cnt: Property):
    txt.text = 'Click count: {}'.format(cnt.get())


# mock Button: has on_click signal
class MockButton:
    def __init__(self):
        self.on_click = Signal()


btn = MockButton()


@btn.on_click
def _increase():
    counter['count'] += 1


# simulate clicks
btn.on_click.emit()
check('after 1 click, count == 1', counter.count.get() == 1)
check('after 1 click, txt updated', txt.text == 'Click count: 1')

btn.on_click.emit()
btn.on_click.emit()
check('after 3 clicks, count == 3', counter.count.get() == 3)
check('after 3 clicks, txt updated', txt.text == 'Click count: 3')

# verify the handler received the Property handle (not raw value)
received_handle: list = []
counter.count.on_change.disconnect(_update_text)
counter.count.on_change(lambda c: received_handle.append(c))
counter.count.set(100)
check(
    'on_change passes the Property handle',
    isinstance(received_handle[0], Property)
    and received_handle[0].get() == 100,
)

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
print()
print(f'=== {passed} passed, {failed} failed ===')
if failed:
    raise SystemExit(1)
