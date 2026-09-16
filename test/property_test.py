import streamlit_canary as sc

count = sc.Property(0)


@count.on_change
def aaa():
    print('aaa', count.get())


@count.on_change.partial('abc')
def bbb(word):
    assert word == 'abc'
    print('bbb', word)


@count.on_change.partial(sc._self)
def ccc(cnt: sc.Property):
    assert isinstance(cnt, sc.Property)
    print('ccc', cnt.get())


@count.on_change.partial(sc._value)
def ddd(cnt: int):
    assert isinstance(cnt, int)
    print('ddd', cnt)


count.set(42)

# -- fields declared by annotation -----------------------------------------
# `PropertyHost` builds a `Property` for every `sc.Property[...]` annotation,
# so a state class does not have to repeat its fields in `__init__`.


class _AnnotatedState(sc.StateV2):
    name: sc.Property[str]
    age: sc.Property[int] = 0
    scope: str = 'not a property'

    def __init__(self):
        super().__init__()
        self['age'] = 30


class _SubState(_AnnotatedState):
    busy: sc.Property[bool]


first = _AnnotatedState()
second = _AnnotatedState()
assert isinstance(first.name, sc.Property)
assert first.name.get() is sc._undefined
assert first.age.default == 0 and first.age.get() == 30
assert not isinstance(first.scope, sc.Property)
assert first.scope == 'not a property'
assert first.name is not second.name  # one handle per instance
assert isinstance(_SubState().busy, sc.Property)
first['name'] = 'abc'
assert first.name.get() == 'abc'  # ... even through the sugar
print('annotated state', repr(first))


class _ClassLevelState(sc.StateV2):
    count: sc.Property[int] = sc.Property(5)


bumped = _ClassLevelState()
bumped['count'] = 7
assert bumped.count.get() == 7
assert _ClassLevelState().count.get() == 5  # default copied, not shared
print('annotated state (class-level default)', repr(bumped))
