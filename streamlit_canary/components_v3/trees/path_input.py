"""A text input whose text is resolved into an existing path."""

import typing as tp

from lk_utils import fs

from ._shared import _norm
from .._shared import _Submittable
from ..base import Width
from ..inputs import TextInput
from ..layouts import Column
from ...kernel import Property


class PathInput(_Submittable, Column):
    """
    A text input whose text is resolved into an existing path.
    Path is always absolute, forward-slash form.
    """

    def __init__(
        self,
        label: str = '',
        value: str = '',
        *,
        width: Width | None = None,
        candidates: tp.Iterable[str] | Property | None = None,
        accept_new_option: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        self._init_submittable()
        self.path = Property('')
        if candidates is None or isinstance(candidates, Property):
            source: tp.Any = candidates
        else:
            # materialize, so a one-shot iterable does not go stale
            source = list(candidates)
        self.candidates = Property(tp.cast(tp.Optional[tp.List[str]], None))
        self.candidates.set_or_bind(source)
        with self:
            self._input = TextInput(
                label,
                value=value,
                width='stretch',
                candidates=self.candidates,
                accept_new_option=accept_new_option,
            )

        @self._input.value.on_change
        def _validate() -> None:
            self.path.set(self._resolve(str(self._input['value'])))

        # The inner box owns the send / blur detection; these two just relay
        # it outwards under this wrapper's own name.
        @self._input.on_submit
        def _relay_submit(text: str) -> None:
            # a submit ends the typing, so this is when the box can be tidied:
            # a path pasted with backslashes, or with a `..` inside it, ends up
            # shown in the form it resolved to
            self._show(self._resolve(text))
            self.on_submit.emit(text)

        @self._input.on_editing_finished
        def _relay_editing_finished(text: str) -> None:
            self.on_editing_finished.emit(text)

        @self.path.on_change
        def _follow() -> None:
            self._show(self.path.get())

        self.path.set(self._resolve(str(value)))

    def show(self, path: str) -> None:
        """Make `path` the value, and make the box read it.

        `path.set` on its own only re-writes the box when the value actually
        changes; this also covers a box that is already on that path, spelled
        some other way -- with backslashes, a trailing separator, a `..`.
        """
        self.path.set(path)
        self._show(path)

    def _show(self, path: str) -> None:
        """Write a resolved path into the box, if the box reads otherwise.

        Only a resolved path is written back: an empty one means the text is
        still incomplete, and must be left alone.
        """
        if path and str(self._input['value']) != path:
            self._input.value.set(path)

    @staticmethod
    def _resolve(raw: str) -> str:
        text = str(raw).strip()
        if not text:
            return ''
        path = _norm(text)
        return path if fs.exist(path) else ''
