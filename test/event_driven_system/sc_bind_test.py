"""What a `Property` starts out as, and what `sc.bind` does with it at once.

Run: python test/event_driven_system/sc_bind_test.py

Read `kernel/state.py` (`PropertyHost` / `_zero_of`) and
`kernel/property.py` (`Binding` / `Property.bind` / `Property._evaluate`)
alongside this: every rule below comes straight out of what they do.

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
3. `default` settles the *starting* value and nothing else: it is taken as is
   (the transform does not run), and the binding stays live, so the source's
   next change takes over. A source that already had a value at bind time
   loses to the default until it changes again.
4. `fallback` stands in while there is nothing usable: an unset source, or a
   transform that fails on the initial value. Later failures raise.
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

# ... and the failed `bind` left no listener behind: this change is quiet
state.ccc.set(['alpha'])
show('the failed bind left no listener', state.ccc.get())
state.ccc.set([])

show('a working transform is already applied', sc.bind(state.aaa, str).get())
assert sc.bind(state.aaa, str).get() == '0'
assert isinstance(sc.bind(state.aaa, str), sc.Binding)
assert isinstance(sc.bind(state.aaa, str), sc.Property)

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

# == 3. `fallback=` stands in while there is nothing usable ==================

print()
print('== 3. `fallback=` covers the starting value ==')

safe = sc.bind(state.ccc, lambda x: x[0], fallback='-')
show('empty list -> fallback', repr(safe.get()))
assert safe.get() == '-'

state.ccc.set(['alpha', 'beta'])
show('a filled list -> the transform', repr(safe.get()))
assert safe.get() == 'alpha'

# the fallback is a starting value, not a permanent net: a failure after
# that raises, since a value that only turned bad at runtime is a bug
try:
    state.ccc.set([])
except IndexError as error:
    show('a later failure raises', repr(error))
else:
    raise AssertionError('the later failure did not raise')

# without a transform, `fallback` covers "the source has no value yet"
fresh = sc.Property()
waiting = sc.bind(fresh, fallback='(anonymous)')
show('unset source -> fallback (no transform)', repr(waiting.get()))
assert waiting.get() == '(anonymous)'
fresh.set('Alice')
show('... and the source takes over', repr(waiting.get()))
assert waiting.get() == 'Alice'

# with a transform, the same
fresh2 = sc.Property()
waiting2 = sc.bind(fresh2, lambda x: x.upper(), fallback='?')
assert waiting2.get() == '?'
fresh2.set('bob')
show('unset source -> fallback (transform)', repr(waiting2.get()))
assert waiting2.get() == 'BOB'

# == 4. `default=` seeds the value, and the binding stays live ===============

print()
print('== 4. `default=` is the starting value only ==')

state.bbb.set('')
seeded = sc.bind(state.bbb, str.upper, default='(anonymous)')
show('the default wins at bind time', repr(seeded.get()))
assert seeded.get() == '(anonymous)'

state.bbb.set('alice')
show('a source change takes over', repr(seeded.get()))
assert seeded.get() == 'ALICE'

state.bbb.set('')
show('... and the transform keeps running', repr(seeded.get()))
assert seeded.get() == ''

# the default also wins over a source that already holds a value; that
# source only takes over from its *next* change
state.bbb.set('bob')
late = sc.bind(state.bbb, str.upper, default='(anonymous)')
show('default beats an existing source value', repr(late.get()))
assert late.get() == '(anonymous)'
state.bbb.set('carol')
show('... until the source changes', repr(late.get()))
assert late.get() == 'CAROL'

# without a transform the binding mirrors the source after the seeded start
state.bbb.set('dave')
plain = sc.bind(state.bbb, default='(anonymous)')
assert plain.get() == '(anonymous)'
state.bbb.set('erin')
show('default + identity transform', repr(plain.get()))
assert plain.get() == 'erin'

# == 5. a widget mirrors the binding ========================================

print()
print('== 5. a widget handed a binding ==')

with sc.TextInput(
    'MMM', sc.bind(state.ccc, lambda x: x[0], fallback='')
) as box:
    pass
show('the box shows the fallback', repr(box.value.get()))
assert box.value.get() == ''

state.ccc.set(['alpha'])
show('... and follows the source', repr(box.value.get()))
assert box.value.get() == 'alpha'

with sc.TextInput(
    'SEED', sc.bind(state.bbb, str.upper, default='(none)')
) as seeded_box:
    pass
show('the box shows the default', repr(seeded_box.value.get()))
assert seeded_box.value.get() == '(none)'  # the default is not transformed

state.bbb.set('frank')
show('... but is not frozen on it', repr(seeded_box.value.get()))
assert seeded_box.value.get() == 'FRANK'

print()
print('all assertions passed.')
