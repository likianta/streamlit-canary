import streamlit_canary as sc

# -- Signal parameters -----------------------------------------------------
# A Signal declares the types its `emit()` carries: `*args` are positional-only
# parameters, `**kwargs` are named ones -- and a named one is also accepted in
# position order. Declaring nothing leaves the signal free-form (which is how
# the payload-less signals above behave).

state_changed = sc.Signal(bool)
reason_given = sc.Signal(bool, reason=str)
got: list = []


@state_changed
def _on_state(state: bool) -> None:
    got.append((state,))


@reason_given
def _on_reason(state: bool, reason: str) -> None:
    got.append((state, reason))


state_changed.emit(True)
reason_given.emit(False, reason='User clicks connect button.')
reason_given.emit(True, 'User clicks connect button.')
print('signal', got)
assert got == [
    (True,),
    (False, 'User clicks connect button.'),
    (True, 'User clicks connect button.'),
], got

# A wrong call fails at the signal rather than inside a handler.
for label, call in [
    ('missing positional', lambda: state_changed.emit()),
    ('missing named', lambda: reason_given.emit(True)),
    ('unknown keyword', lambda: reason_given.emit(True, 'a', typo='b')),
]:
    try:
        call()
    except TypeError as exc:
        print('signal', label, '->', exc)
    else:
        raise AssertionError('expected a TypeError: ' + label)
