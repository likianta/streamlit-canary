"""`sc.bind` with several sources: what the transform sees, and whether the
order of the sources changes the target.

Run: python test/event_driven_system/bind_multi_source.py

Read `Property.bind` (`streamlit_canary/kernel/property.py`) alongside this:
every rule below comes straight out of what it does with the source list.

Short version:

1. One source hands the transform that source's *value*; several sources hand
   it an *accessor*, and the tuple order is the accessor order -- so the order
   plainly decides which slot each source fills.
2. Outside a transaction the final value never depends on that order: each
   source change syncs the target straight away, so the last sync reads every
   source settled. Two things *are* ordered: the number of transform calls
   (one per source change), and -- via the bind order, not the tuple order --
   whether a half-updated pair is ever *published* at all.
3. Inside a `with sc.pending_updates():` block the values are written at
   once and only the *notification* is batched, so the value is again
   order-independent while a target syncs at least once, at the last declared
   source that is still waiting for its turn.
4. That last rule only uses the declared order to pick *which* source asks
   for the sync, and "in the batch" means "still to be notified". So a source
   that moves during the flush on its own -- a derived property, never queued
   -- is fine. Sections 8 and 9 keep that honest: this used to trip an
   `assert` inside the batch loop, and the loop swallowed the error back then
   (it collects listener errors now and raises them once the batch is done --
   see `bind_forced_notify.py`), so the target went stale and the rest of that
   property's listeners were skipped. Later the target would settle on a stale
   value whenever the already-notified source was declared last.
"""

import streamlit_canary as sc


def show(label: str, value: object) -> None:
    print('{:<48} {}'.format(label, value))


def trace(prop: sc.Property) -> list:
    """Record every value `prop` takes from now on."""
    seen: list = []
    prop.on_change.connect(lambda: seen.append(prop.get()))
    return seen


# == 1. what the transform receives ==========================================

print('== 1. the transform payload ==')

cnt = sc.Property(1)
a = sc.bind(cnt, lambda x: 'a' * x)
b = sc.bind(a, lambda x: x + 'b' * cnt.get())
show('cnt / a / b', (cnt.get(), a.get(), b.get()))

accessor_kinds: list = []


def _pair(acc):
    accessor_kinds.append(type(acc).__name__)
    return '<{}|{}>'.format(acc[0], acc[1])


several = sc.bind((a, b), _pair)
show('one source   -> transform got', 'the value itself')
show('several ones -> transform got', accessor_kinds[-1])
show('acc[0] / acc[1] read', (a.get(), b.get()))

# == 2. the tuple order is the accessor order ================================

print()
print('== 2. swapping the tuple swaps the slots ==')

forward = sc.bind((a, b), lambda acc: '<{}|{}>'.format(acc[0], acc[1]))
backward = sc.bind((b, a), lambda acc: '<{}|{}>'.format(acc[0], acc[1]))
show('bind((a, b), f), f = <acc[0]|acc[1]>', forward.get())
show('bind((b, a), f), f = <acc[0]|acc[1]>', backward.get())
assert forward.get() == '<{}|{}>'.format(a.get(), b.get())
assert backward.get() == '<{}|{}>'.format(b.get(), a.get())

# == 3. one change, counted through both orderings ===========================

print()
print('== 3. `cnt.set(2)`: how often does each target sync? ==')

cnt2 = sc.Property(1)
a2 = sc.bind(cnt2, lambda x: 'a' * x)
b2 = sc.bind(a2, lambda x: x + 'b' * cnt2.get())

# `b2` is derived from `a2`, so a change of `cnt2` moves `a2` first, then
# `b2`; both are sources of the two targets below.
reads = {'(a2, b2)': [], '(b2, a2)': []}


def _logging(name):
    def transform(acc):
        reads[name].append((acc[0], acc[1]))
        return acc[0] + '+' + acc[1]

    return transform


c2 = sc.bind((a2, b2), _logging('(a2, b2)'))
d2 = sc.bind((b2, a2), _logging('(b2, a2)'))
c2_seen = trace(c2)
d2_seen = trace(d2)

cnt2.set(2)
show(
    'transform ran (incl. the initial sync)',
    {k: len(v) for k, v in reads.items()},
)
show('  (a2, b2) read', reads['(a2, b2)'])
show('  (b2, a2) read', reads['(b2, a2)'])
show('values *published* by c2', c2_seen)
show('values *published* by d2', d2_seen)
show('final c2 / d2', (c2.get(), d2.get()))
assert c2.get() == 'aa' + '+' + 'aabb'
assert d2.get() == 'aabb' + '+' + 'aa'
# both orderings settle on the same (correct) value; only the slots differ
assert {len(v) for v in reads.values()} == {3}
assert c2_seen == ['aa+aabb'] and d2_seen == ['aabb+aa']

# == 4. the glitch depends on the bind order, not on the tuple order =========

print()
print('== 4. who listens first decides whether a glitch shows ==')


def _diamond(counter, sibling_first: bool):
    """`aa` -> `bb`, plus a target reading both. Returns what it published."""
    published: list = []
    aa = sc.bind(counter, lambda x: 'a' * x)
    bb = sc.Property('?')
    if sibling_first:
        # `bb` starts listening to `aa` first, so it is up to date by the time
        # the target reads the pair
        bb.bind(aa, lambda x: x + 'b' * counter.get())
        target = sc.bind((aa, bb), lambda acc: acc[0] + '+' + acc[1])
    else:
        # the target listens to `aa` first, so it reads `aa` new / `bb` old
        target = sc.bind((aa, bb), lambda acc: acc[0] + '+' + acc[1])
        bb.bind(aa, lambda x: x + 'b' * counter.get())
    target.on_change.connect(lambda: published.append(target.get()))
    counter.set(1)  # 0 -> 1, moves `aa` and then `bb`
    return published


show(
    'sibling bound first (reads a *settled* pair)',
    _diamond(sc.Property(0), sibling_first=True),
)
show(
    'target bound first  (reads a *half* pair)',
    _diamond(sc.Property(0), sibling_first=False),
)

# == 5. a source that still holds nothing ====================================

print()
print('== 5. a source that still holds nothing ==')

unset = sc.Property()
ready = sc.Property('R')
pair = sc.bind((unset, ready), lambda acc: (repr(acc[0]), acc[1]))
show('straight after bind()  (no initial sync)', repr(pair.get()))
ready.set('R2')
show('after only `ready` moved', repr(pair.get()))
assert pair.get() == ('sc._undefined', 'R2')

# == 6. the transaction api ==================================================

print()
print('== 6. `with sc.pending_updates():` ==')

show('sc.pending_updates', type(sc.pending_updates).__name__)
show('sc.pending_updates()', type(sc.pending_updates()).__name__)

batched: list = []
batched_prop = sc.Property(0)
batched_prop.on_change.connect(lambda: batched.append(batched_prop.get()))
with sc.pending_updates():
    batched_prop.set(1)
    batched_prop.set(2)
    batched_prop.set(3)
show('three sets in one block -> notifications', batched)
assert batched == [3], 'the batch should notify once, with the last value'

# a nested block joins the outer transaction: it must not commit on its own
nested: list = []
nested_prop = sc.Property(0)
nested_prop.on_change.connect(lambda: nested.append(nested_prop.get()))
with sc.pending_updates():
    nested_prop.set(1)
    with sc.pending_updates():
        nested_prop.set(2)
    assert nested == [], 'the inner block committed on its own'
show('a nested block joins the outer one', nested)
assert nested == [2]

flush_order: list = []
x = sc.Property('')
y = sc.Property('')
x.on_change.connect(lambda: flush_order.append('x=' + x.get()))
y.on_change.connect(lambda: flush_order.append('y=' + y.get()))
with sc.pending_updates():
    x.set('1')
    y.set('1')
    x.set('2')  # re-setting moves `x` to the *end* of the flush order
show('notification order (first set first)', flush_order)
assert flush_order == ['y=1', 'x=2']

# == 7. inside a transaction: the values are already written =================

print()
print('== 7. inside a transaction: one sync, on settled values ==')

src1 = sc.Property('1')
src2 = sc.Property('2')
paired = {'(src1, src2)': [], '(src2, src1)': []}


def _paired(name):
    def transform(acc):
        paired[name].append((acc[0], acc[1]))
        return acc[0] + acc[1]

    return transform


same = sc.bind((src1, src2), _paired('(src1, src2)'))
rev = sc.bind((src2, src1), _paired('(src2, src1)'))
show('before', (same.get(), rev.get()))
for entries in paired.values():
    entries.clear()

with sc.pending_updates():
    src1.set('A')
    src2.set('B')
    show('  inside the block: src1 / src2', (src1.get(), src2.get()))
    show(
        '  inside the block: syncs so far',
        {k: len(v) for k, v in paired.items()},
    )
show('syncs during the batch', {k: len(v) for k, v in paired.items()})
show('  (src1, src2) read', paired['(src1, src2)'])
show('  (src2, src1) read', paired['(src2, src1)'])
show('final', (same.get(), rev.get()))
# The value is written the moment `set()` runs, only the *notify* waits for
# the batch -- so every read below is a settled pair, whichever order the
# tuple was in, and both targets end on the right value.
assert same.get() == 'AB' and rev.get() == 'BA'
assert set(paired['(src1, src2)']) == {('A', 'B')}
assert set(paired['(src2, src1)']) == {('B', 'A')}
# `(src1, src2)` matches the flush order, so it syncs exactly once. Reversed,
# the target also syncs when its *last declared* source has had its turn --
# a redundant call with the same settled read (harmless, and it is what keeps
# the final value right when a source moves during the flush -- see 8 and 9).
assert len(paired['(src1, src2)']) == 1

# == 8. a transaction whose source is derived ================================

print()
print('== 8. transaction where a source is derived (never queued) ==')

cnt3 = sc.Property(1)
a3 = sc.bind(cnt3, lambda x: 'a' * x)
plain = sc.Property('P')
merged = sc.bind((a3, plain), lambda acc: acc[0] + acc[1])

# `sc.bind` above connected `_lazy_sync` to `a3.on_change`; this probe is
# registered *after* it, so it only runs if that handler returned normally.
probe: list = []
a3.on_change.connect(lambda: probe.append(a3.get()))
show('before', repr(merged.get()))

with sc.pending_updates():
    cnt3.set(3)
show(
    'cnt3 / a3 / plain / merged',
    (cnt3.get(), a3.get(), plain.get(), repr(merged.get())),
)
show('  `merged` should be', repr('aaa' + plain.get()))
show('  `a3` did move', a3.get() == 'aaa')
show('  other handlers on `a3` ran', probe)

# Regression test. `_lazy_sync` used to assert that a changing source was
# part of the batch, so a *derived* source -- which moves during the flush
# without being queued -- blew up inside the batch loop, which swallowed the
# exception and carried on. The target silently kept its old value and the
# rest of that property's listeners were skipped.
assert merged.get() == 'aaa' + plain.get()
assert probe == ['aaa']

# the same change outside a transaction is fine
cnt3.set(4)
show('the same change outside a transaction', repr(merged.get()))
assert merged.get() == 'aaaa' + plain.get()

# == 9. a batch where the derived source settles =============================

print()
print('== 9. a derived source that settles inside a batch ==')

cnt4 = sc.Property(1)
label = sc.Property('')
mixed = sc.bind((label, cnt4), lambda acc: '{} / {}'.format(acc[0], acc[1]))
published = trace(mixed)
label.bind(cnt4, lambda n: '{} row(s)'.format(n))
published.clear()

with sc.pending_updates():
    cnt4.set(3)
show('values published during the batch', published)
show('mixed settled on', repr(mixed.get()))

# `cnt4` is declared *after* a source that moves during the flush, and it has
# already had its turn by then -- so the target must not wait for it, or it
# would keep the half-updated read as its final value. (Popping the queue as
# it is flushed is what lets `bind` tell the two apart.)
assert mixed.get() == '{} row(s) / 3'.format(cnt4.get())
assert published[-1] == mixed.get()
