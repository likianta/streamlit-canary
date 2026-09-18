"""Forced notification: `set(v, notify=True)` as a *re-render request*, and how
it travels.

Run: python test/event_driven_system/bind_forced_notify.py

Read `Property.set` / `Property._emit` and `kernel/pending_updates.py`
alongside this: every rule below comes straight out of what they do.

Short version:

1. A plain `set(v)` says "the value moved". A forced one -- `set(v,
   notify=True)`, or any `Signal` source of a `bind` -- says "re-render, the
   value is beside the point", so it notifies even when the value it writes
   compares equal to the one already held.
2. That is the only way to tell a bound property that something *rendered*
   from the value changed: a dict mutated in place never compares unequal, and
   a widget's `format` may read state that is not part of the option values at
   all.
3. The force has to survive a binding chain, because a widget never listens to
   the property it was handed -- `set_or_bind` gives it its own one and mirrors
   yours, so there is always at least one hop in between. A hop that ate the
   force would leave the widget stale (sections 1 and 2).
4. Inside a `with sc.pending_updates():` block the batch settles first: the
   changes are delivered in the order they were made, the re-render requests
   after them (section 4). A request reports what the batch settled on, so it
   cannot go out early (section 6), and a property that both changed and was
   requested is told once, forced (section 5).
5. A listener that raises does not stop the batch: the error is held until
   every property has been told and then raised -- several of them come out as
   an `ExceptionGroup` (section 7).
"""

import streamlit_canary as sc


def show(label: str, value: object) -> None:
    print('{:<48} {}'.format(label, value))


def trace(prop: sc.Property) -> list:
    """Record every value `prop` takes from now on."""
    seen: list = []
    prop.on_change.connect(lambda: seen.append(prop.get()))
    return seen


# == 1. a forced set that changes nothing ====================================

print('== 1. `notify=True` re-renders an unchanged value ==')

state = sc.Property({'version': '0.4.0a19'})
options = sc.bind(state, lambda d: list(d.keys()))
renders = trace(options)

state.get()['version'] = '0.4.0a20'  # mutated in place, so it compares equal
state.set(state.get(), notify=True)
show('options re-rendered with', renders)
assert renders == [['version']], 'the force was eaten on the way'

# the very same write, unforced: there is nothing to tell, because the value
# still equals the one held -- which is what the default stays for.
renders.clear()
state.set(state.get())
show('the same write, unforced', renders)
assert renders == []

# == 2. the force crosses the widget hop =====================================

print()
print('== 2. a widget mirrors the property it is handed ==')

# a widget does not listen to the property it is given: `options=...` goes
# through `set_or_bind`, which gives the widget its own property and mirrors
# yours from then on. That hop is where the force used to die.
widget = sc.Property()
widget.set_or_bind(options)
delivered = trace(widget)

state.get()['version'] = '0.4.0a21'
state.set(state.get(), notify=True)
show('the widget was re-rendered with', delivered)
assert delivered == [['version']], 'the force died at the widget hop'

# == 3. a Signal source is a trigger, not a value ============================

print()
print('== 3. a Signal beside a Property ==')

names = sc.Property({'a': 1, 'b': 2})
reloaded = sc.Signal()
triggered = sc.bind((names, reloaded), lambda acc: list(acc[0].keys()))
trigger_renders = trace(triggered)

names.get()['a'] = 9  # a version-like edit in place
reloaded.emit()  # "reload": no value, just the fact
show('re-rendered on the Signal', trigger_renders)
assert trigger_renders == [['a', 'b']]

# a Signal occupies no slot in the accessor, so a Property declared *after* it
# is still `acc[0]`
reversed_order = sc.bind((reloaded, names), lambda acc: acc[0]['a'])
show('Signal declared first, acc[0]', reversed_order.get())
assert reversed_order.get() == 9

for wrong_source in (reloaded, (reloaded,)):
    try:
        sc.bind(wrong_source, lambda acc: acc)
    except TypeError as error:
        show('rejected: {!r}'.format(wrong_source), repr(error))
    else:
        raise AssertionError('{!r} must not be accepted'.format(wrong_source))

# == 4. in a batch the changes go first ======================================

print()
print('== 4. a request waits for the batch to settle ==')

log: list = []
changed = sc.Property('c')
changed.on_change.connect(lambda: log.append('change'))
requested = sc.Property('r')
requested.on_change.connect(lambda: log.append('request'))

with sc.pending_updates():
    requested.set('r', notify=True)  # asked for *first* ...
    changed.set('c2')  # ... but delivered last
show('delivery order', log)
assert log == ['change', 'request'], 'a request went out mid-batch'

# == 5. changed *and* requested: one telling, forced =========================

print()
print('== 5. a property both changed and requested ==')

told: list = []
both = sc.Property('B')
both.on_change.connect(lambda: told.append(both.get()))
hop = sc.Property()
hop.set_or_bind(both)  # a stand-in for a widget's own property
hopped = trace(hop)
hopped.clear()

with sc.pending_updates():
    both.set('B2')  # a move ...
    both.set('B2', notify=True)  # ... and a request for the same property
show('the property was told', told)
show('the hop past it re-rendered', hopped)
assert told == ['B2'], 'told once, not once per pass'
assert hopped == ['B2'], 'the single telling still carried the force'

# == 6. a request that moves the value still waits ===========================

print()
print('== 6. a request that also moves the value ==')

settled: list = []
late = sc.Property('start')
late.on_change.connect(lambda: settled.append(late.get()))

with sc.pending_updates():
    late.set('v1', notify=True)  # a request that moves the value ...
    late.set('v2')  # ... and a plain change after it
show('the property was told', settled)
assert settled == ['v2'], 'one telling, carrying the settled value'

# == 7. a listener that raises ===============================================

print()
print('== 7. a listener that raises ==')


def boom() -> None:
    raise ValueError('listener failed')


others: list = []
first = sc.Property(0)
second = sc.Property(0)
first.on_change.connect(boom)
second.on_change.connect(lambda: others.append(second.get()))

try:
    with sc.pending_updates():
        first.set(1)
        second.set(1)
except ValueError as error:
    show('the error came out of the batch', repr(error))
else:
    raise AssertionError('the batch raised nothing')

# the other property was still told: that is what holding the error back buys
show('the other listener still ran', others)
assert others == [1]

# two failures at once, one per property
second.on_change.connect(boom)
try:
    with sc.pending_updates():
        first.set(2)
        second.set(2)
except ExceptionGroup as group:
    show('two failures came out as', [repr(e) for e in group.exceptions])
else:
    raise AssertionError('expected an ExceptionGroup')

# an error raised by the block itself survives, with the batch's own errors
# attached as notes rather than replacing it
try:
    with sc.pending_updates():
        first.set(3)
        raise KeyError('the block failed')
except KeyError as error:
    show('the block error survived', repr(error))
    show('  with the batch error noted', error.__notes__)
    assert error.__notes__, 'the batch error was dropped'
else:
    raise AssertionError('expected the block error')

print()
print('all assertions passed.')
