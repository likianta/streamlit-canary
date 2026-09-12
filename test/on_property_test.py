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
