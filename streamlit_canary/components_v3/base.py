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

# ---------------------------------------------------------------------------
# Size scheme
# ---------------------------------------------------------------------------
# Every component accepts a uniform `width` / `height` argument. The value is
# either an explicit pixel count or one of Streamlit's sizing keywords; these
# aliases mirror `streamlit/elements/lib/layout_utils.py` so our public surface
# matches the upstream API.
#
#   'stretch'  fill the parent (Streamlit's usual default for widgets)
#   'content'  hug the element's own content, capped by the parent
#   'auto'     defer to CSS (markdown family: stretch when vertical,
#              content when horizontal)
#   int        a fixed pixel size
#
# `None` is accepted when passed by a caller and means "keep the component's
# own default" (see `Component._default_width`); it is deliberately not part
# of the aliases, matching Streamlit.
Width: tp.TypeAlias = int | tp.Literal['stretch', 'content']
WidthWithoutContent: tp.TypeAlias = int | tp.Literal['stretch']
AutoWidth: tp.TypeAlias = Width | tp.Literal['auto']
Height: tp.TypeAlias = int | tp.Literal['stretch', 'content']
HeightWithoutContent: tp.TypeAlias = int | tp.Literal['stretch']

_SIZE_KEYWORDS: tp.Final[tuple[str, ...]] = ('stretch', 'content', 'auto')


def _validate_size(value: tp.Any, name: str) -> None:
    """Reject a `width` / `height` that is neither a positive int nor a
    known sizing keyword (mirrors Streamlit's `validate_width` /
    `validate_height`)."""
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a positive int, got {value!r}')
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f'{name} must be > 0, got {value!r}')
        return
    if isinstance(value, str) and value in _SIZE_KEYWORDS:
        return
    raise ValueError(
        f'{name} must be a positive int or one of {_SIZE_KEYWORDS}, '
        f'got {value!r}'
    )


class Component(PropertyHost):
    """
    Base class for all v3 components.

    Subclasses are typically used as context managers:
        with Row() as row:
            with Text('hi') as txt:
                ...

    While inside a `with` block, newly constructed components are
    auto-parented to the top of the context stack.

    Declare visual properties as instance attributes inside `__init__`
    (after `super().__init__()`):
        class Text(Component):
            def __init__(self, text='', **kwargs):
                super().__init__(**kwargs)
                self.text = Property('')
                self.text.set_or_bind(text)

    They are read/written the same way as state properties:
        txt.text.get()
        txt.text.set('hello')
        txt.text.on_change.connect(...)
        txt.text.on_change.partial(sc._self)   # handler receives the handle
        txt['text']            # alias of .get()
        txt['text'] = 'hi'     # alias of .set()
        txt['on_text']         # alias of .on_change

    Every component also accepts the uniform `width` / `height` keyword (see
    the size scheme above). A component either declares a default through
    `_default_width` / `_default_height`, or opts out with `None` (its
    renderer then ignores the value). The stored value is read back as
    `comp._width` / `comp._height`, so a renderer that needs special handling
    (a flex weight, a semantic dialog size) can still branch on it.
    """

    # stack of components currently inside their `with` block; used to wire up
    # parent/child relationships automatically.
    _context_stack: tp.ClassVar[list[Component]] = []
    # the runtime that is currently building the component tree; components
    # register themselves with it during construction. `None` when no build is
    # in progress (e.g. in unit tests).
    _active_runtime: tp.ClassVar[tp.Any] = None
    # Default sizing applied when the caller passes no explicit `width` /
    # `height`. `None` means "not sized" -- the renderer ignores the value.
    _default_width: tp.ClassVar[AutoWidth | None] = None
    _default_height: tp.ClassVar[Height | None] = None

    def __init__(
        self,
        *,
        key: str | None = None,
        width: AutoWidth | None = None,
        height: Height | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(**kwargs)
        # `key` is an optional stable identifier (Streamlit-style). When
        # provided, it is used as the component id verbatim, so external
        # tools (tests, HTTP queries) can reference the element by name.
        self._id: str = key if key else uuid()
        self._children: list[Component] = []
        self._parent: Component | None = None
        # An explicit `width` / `height` overrides the class default (and is
        # validated); `None` falls back to `_default_width` / `_default_height`.
        if width is None:
            self._width: AutoWidth | None = self._default_width
        else:
            _validate_size(width, 'width')
            self._width = width
        if height is None:
            self._height: Height | None = self._default_height
        else:
            _validate_size(height, 'height')
            self._height = height
        # auto-attach to the enclosing component, if any.
        if Component._context_stack:
            self._parent = Component._context_stack[-1]
            self._parent._children.append(self)
        # register with the active runtime, if any.
        if Component._active_runtime is not None:
            Component._active_runtime._register_component(self)

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
    def key(self) -> str:
        """Stable identifier alias (matches Streamlit's `.key` convention)."""
        return self._id

    @property
    def parent(self) -> Component | None:
        return self._parent

    @property
    def children(self) -> tuple[Component, ...]:
        return tuple(self._children)

    def __repr__(self) -> str:
        return f'<{type(self).__name__} id={self._id[:8]}>'
