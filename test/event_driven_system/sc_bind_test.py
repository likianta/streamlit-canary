"""What a `Property` starts out as, and what `sc.bind` does with it at once.

Run: python test/event_driven_system/sc_bind_test.py

Read `kernel/state.py` (`PropertyHost` / `_zero_of`) and
`kernel/property.py` (`Property.bind` / `Property._evaluate`) alongside this:
every rule below comes straight out of what they do.

Short version:

1. A `Property[T]` annotation whose `T` is primitive starts from that type's
   zero value (`int` -> 0, `str` -> '', `list` -> [], ...), so a transform
   bound to it has something to run on right away. Any other `T` -- a class
   of your own, a union such as `bool | None` -- keeps `sc._undefined`:
   "nothing has been set yet" stays distinguishable from a made-up value.
   The zero value is built per instance, so two states never share a list.
2. `sc.bind` runs the transform at once. A transform that cannot handle the
   current value raises out of `bind` -- at the line that wrote it -- instead
   of leaving the property on its default and failing later.
3. `default=` turns that failure into a value: the derived property holds the
   default, now and whenever the transform fails again. That is the shorthand
   for a guard written inside the transform.
"""

import streamlit_canary as sc


def show(label: str, value: object) -> None:
    print('{:<48} {}'.format(label, value))


class Person:
    name: str
    age: int


class _State(sc.State):
    aaa: sc.Property[int]
    bbb: sc.Property[str]
    ccc: sc.Property[list]
    ddd: sc.Property[dict]
    eee: sc.Property[bool | None]
    fff: sc.Property[Person]


state = _State()

# == 1. a primitive-typed field starts from its zero value ===================

print('== 1. primitive types start from their zero value ==')

show(
    'int / str / list / dict',
    (state.aaa.get(), state.bbb.get(), state.ccc.get(), state.ddd.get()),
)
assert state.aaa.get() == 0
assert state.bbb.get() == ''
assert state.ccc.get() == []
assert state.ddd.get() == {}

# a union and a class of the caller's own have no obvious zero
show('bool | None / Person', (state.eee.get(), state.fff.get()))
assert state.eee.get() is sc._undefined
assert state.fff.get() is sc._undefined


class _ListState(sc.State):
    items: sc.Property[list]


first, second = _ListState(), _ListState()
first.items.get().append('x')
show('one list mutated, the other one', (first.items.get(), second.items.get()))
assert second.items.get() == [], 'the zero list was shared between instances'

# == 2. the transform runs at once, and a broken one crashes here ============

print()
print('== 2. `bind` runs the transform at once ==')

# the source is an empty list, so `x[0]` cannot work: the error belongs to
# the `bind` call, not to some click that happens later
try:
    sc.bind(state.ccc, lambda x: x[0])
except IndexError as error:
    show('a broken transform raised at bind time', repr(error))
else:
    raise AssertionError('the broken transform did not raise')

show('a working transform is already applied', sc.bind(state.aaa, str).get())
assert sc.bind(state.aaa, str).get() == '0'

# `x or ...` is the guard-inside-the-transform form: the empty string of
# `bbb` is falsy, so the transform itself picks the fallback
show(
    'guard inside the transform',
    sc.bind(state.bbb, lambda x: x or 'EMPTY').get(),
)
assert sc.bind(state.bbb, lambda x: x or 'EMPTY').get() == 'EMPTY'

# a source that still holds nothing has nothing to transform: the immediate
# run is skipped, so even a transform that would choke on `_undefined` is
# accepted at bind time
unset = sc.Property()
skipped = sc.bind(unset, lambda x: x['name'])
show('an unset source skips the first run', skipped.get())
assert skipped.get() is sc._undefined

# == 3. `default=` stands in for a failing transform =========================

print()
print('== 3. `default=` is used when the transform fails ==')

safe = sc.bind(state.ccc, lambda x: x[0], default='')
show('empty list -> default', repr(safe.get()))
assert safe.get() == ''

state.ccc.set(['alpha', 'beta'])
show('a filled list -> the transform', repr(safe.get()))
assert safe.get() == 'alpha'

state.ccc.set([])
show('empty again -> the default again', repr(safe.get()))
assert safe.get() == ''

# the same guard, spelled inside the transform (the long form of `default=`)
guarded = sc.bind(state.ccc, lambda x: x[0] if x else '')
show('the guard form agrees', repr(guarded.get()))
assert guarded.get() == safe.get()

# == 4. a widget mirrors the derived property ================================

print()
print('== 4. a widget handed a bound property ==')

with sc.TextInput('MMM', sc.bind(state.ccc, lambda x: x[0], default='')) as box:
    pass
show('the box shows the derived value', repr(box.value.get()))
assert box.value.get() == ''

state.ccc.set(['alpha'])
show('... and follows a change', repr(box.value.get()))
assert box.value.get() == 'alpha'

print()
print('all assertions passed.')
