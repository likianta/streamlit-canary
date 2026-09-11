"""
Component base classes for the event-driven (v3) component model.

A v3 Component is a pure-Python object that:
  * is constructed via a `with` block (`with sc.v3.Row() as row:`),
  * auto-attaches to the enclosing component as its parent,
  * carries a stable `id`,
  * exposes `Property` fields (e.g. `Text.text`) that support the same
    `.get()` / `.set()` / `.on_change` and `__getitem__` / `__setitem__`
    accessors as `StateV2` — state and components share one read/write style.

This module has no Streamlit dependency — the runtime/frontend bridge is added
in a later phase.
"""

from __future__ import annotations

import typing as tp

from lk_utils import uuid

from ..kernel import PropertyHost


class Component(PropertyHost):
    """
    Base class for all v3 components.

    Subclasses are typically used as context managers:
        with Row() as row:
            with Text('hi') as txt:
                ...

    While inside a `with` block, newly constructed components are
    auto-parented to the top of the context stack.

    Declare visual properties as `Property` class attributes:
        class Text(Component):
            text = Property('')

    They are read/written the same way as state properties:
        txt.text.get()
        txt.text.set('hello')
        txt.text.on_change.connect(...)
        txt['text']            # alias of .get()
        txt['text'] = 'hi'     # alias of .set()
        txt['on_text']         # alias of .on_change
    """

    # stack of components currently inside their `with` block; used to wire up
    # parent/child relationships automatically.
    _context_stack: tp.ClassVar[list[Component]] = []

    def __init__(self, **kwargs: tp.Any) -> None:
        # PropertyHost.__init__ sets up `_values` / `_handles` for all
        # declared Property fields.
        super().__init__(**kwargs)
        self._id: str = uuid()
        self._children: list[Component] = []
        self._parent: Component | None = None
        # auto-attach to the enclosing component, if any.
        if Component._context_stack:
            self._parent = Component._context_stack[-1]
            self._parent._children.append(self)

    # -- context manager --------------------------------------------------

    def __enter__(self) -> tp.Self:
        Component._context_stack.append(self)
        return self

    def __exit__(self, *_exc: tp.Any) -> bool:
        if Component._context_stack and Component._context_stack[-1] is self:
            Component._context_stack.pop()
        return False

    # -- tree navigation --------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def parent(self) -> Component | None:
        return self._parent

    @property
    def children(self) -> tuple[Component, ...]:
        return tuple(self._children)

    def __repr__(self) -> str:
        return f'<{type(self).__name__} id={self._id[:8]}>'
