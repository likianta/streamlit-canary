import typing as tp
from collections import deque

from lk_utils import fs

from .._shared import _Submittable
from ..base import Width
from ..inputs import TextInput
from ..layouts import Container
from ...kernel import Property


def _history_capacity(seed_size: int) -> int:
    """How many paths a `PathInput` may end up remembering.

    At least 20, so even a tiny seed has room to grow; a bigger seed rounds
    up to the next ten (23 -> 30), so the memory is not full the moment the
    first new path arrives.
    """
    return max(20, (seed_size + 9) // 10 * 10)


class PathInput(_Submittable, Container):
    """A text input whose text is resolved into a path.

    The path is absolute and forward-slash when it names something that is
    on disk. Text that names nothing yet -- a folder being named, say -- is
    kept too, with only its separators straightened: a path that does not
    exist is still a path, and a caller can read it as "where this would
    go". Only blank text resolves to `""`.

    Fields:
        value: str -- the resolved path, `""` when the box is blank.
            Bindable.
        input_history: list[str] | Property | None -- the suggestions behind
            the box, the same field `TextInput` takes, but with a memory of
            its own. A plain sequence seeds that memory: every path this box
            holds joins it (newest first, no duplicates), up to a capacity of
            at least 20 -- a larger seed rounds up to the next ten
            (23 -> 30) -- and the panel lists whatever it holds in
            alphabetical order. Hand in a `Property` to own the list
            yourself (nothing is remembered then), or `None` for no panel.

    Signals:
        on_submit / on_editing_finished -- relayed from the inner `TextInput`
            (see `_Submittable`); both carry the text as typed.
    """

    def __init__(
        self,
        label: str = '',
        value: str = '',
        *,
        width: Width | None = None,
        input_history: tp.Iterable[str] | Property | None = None,
        accept_new_option: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)
        self._init_submittable()
        self.value = Property('')
        # The memory behind `input_history`, and only for a literal sequence:
        # it is `None` when the caller hands in a `Property` (theirs to fill)
        # or nothing at all (no panel to fill).
        self._memory: tp.Optional[tp.Deque[str]] = None
        if input_history is None or isinstance(input_history, Property):
            source: tp.Any = input_history
        else:
            # materialize, so a one-shot iterable does not go stale
            seed = list(input_history)
            self._memory = deque(seed, maxlen=_history_capacity(len(seed)))
            source = self._history_listing()
        self.input_history = Property(tp.cast(tp.Optional[tp.List[str]], None))
        self.input_history.set_or_bind(source)
        with self:
            self._input = TextInput(
                label,
                value=value,
                width='stretch',
                input_history=self.input_history,
                accept_new_option=accept_new_option,
                # a path is read from its tail: the file or folder name at the
                # end is what tells one path from another
                truncate_start=True,
            )

        @self._input.value.on_change
        def _validate() -> None:
            self.value.set(self._resolve(str(self._input['value'])))

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

        @self.value.on_change
        def _remember() -> None:
            self._add_to_history(self.value.get())

        @self.value.on_change
        def _follow() -> None:
            self._show(self.value.get())

        self.value.set(self._resolve(str(value)))

    def show(self, path: str) -> None:
        """Make `path` the value, and make the box read it.

        `value.set` on its own only re-writes the box when the value actually
        changes; this also covers a box that is already on that path, spelled
        some other way -- with backslashes, a trailing separator, a `..`.
        """
        self.value.set(path)
        self._show(path)

    def _show(self, path: str) -> None:
        """Write a resolved path into the box, if the box reads otherwise.

        Only a resolved path is written back: an empty one means the text is
        still incomplete, and must be left alone.
        """
        if path and str(self._input['value']) != path:
            self._input.value.set(path)

    def _add_to_history(self, path: str) -> None:
        """Remember a path the box holds, and refresh the panel.

        Whatever the box holds is worth keeping -- a path that is not on disk
        yet included, a folder being named being one the user will come back
        to; blank text is `""`, which is nothing to keep. The memory must
        exist, though -- a caller-supplied `Property` is theirs to fill. A
        path already remembered is left where it is, so the memory never
        reorders itself; each new one goes in front, and past the capacity
        the oldest drops off the back, so it stays a window of recent paths.
        """
        if self._memory is None or not path or path in self._memory:
            return
        self._memory.appendleft(path)
        self.input_history.set(self._history_listing())

    def _history_listing(self) -> tp.List[str]:
        """What the panel lists: the memory, in alphabetical order.

        The memory itself is ordered by when each path was met (newest
        first); today we hand the panel a sorted copy. TODO: a second
        ordering style could offer the memory's own order instead.
        """
        if self._memory is None:
            return []
        return sorted(self._memory)

    @staticmethod
    def _resolve(raw: str) -> str:
        text = str(raw).strip()
        if not text:
            return ''
        path = fs.abspath(text)
        if fs.exist(path):
            return path
        # the text names something that is not on disk yet (a folder about to
        # be made, say). `abspath` cannot say what it will turn into, so only
        # the separators are straightened and the text is kept -- a caller
        # decides for itself what a path that does not exist yet means.
        return text.replace('\\', '/')


class PathSelect(PathInput):
    """A `PathInput` that also carries a navigation ladder.

        with v3.PathSelect(
            'Go to', '.', ladder=['C:/', 'C:/work', 'C:/work/app']
        ) as box:
            ...
            path = box.value.get()

    The look is `PathInput`'s -- the same editable box in a `Selectbox`-style
    frame, with the same `input_history` panel and caret -- plus:

    - a click anywhere in the box unfolds the *ladder*: the rungs above the
      folder on show (the drives, then every ancestor), each a pick that
      fills the box in exactly as a history pick does. That is the
      `Current location` bar of `PathInputPopup`, folded into the box, and
      the **last** rung -- the folder on show -- is drawn as the selected
      one.
    - the caret unfolds `input_history`, and stays greyed out while that
      history is empty (there is nothing to remember yet).

    Both close on a click outside the frame or on Escape, the way a
    `Selectbox` does, and neither draws an "Add: ..." row: `PathSelect` takes
    no `accept_new_option`, since a click on the box already opens the panel
    and typing into it plus Enter already resolves the path.

    Args:
        ladder: the rungs, the folder on show **last** (that is the one drawn
            as selected). A plain sequence or a `Property`; the host keeps it
            in step with its own panel, since the box has no folder to build
            a ladder from by itself.

    Fields: as `PathInput`, plus:
        ladder: list[str] | None -- the rungs as they now stand. Bindable.
    """

    def __init__(
        self,
        label: str = '',
        value: str = '',
        *,
        ladder: tp.Iterable[str] | Property | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, value, accept_new_option=False, **kwargs)
        # A plain sequence is materialized -- a `Property` is the host's to
        # keep up to date as its panel moves.
        self.ladder = Property(tp.cast(tp.Optional[tp.List[str]], None))
        if ladder is None or isinstance(ladder, Property):
            rungs = tp.cast(tp.Optional[tp.List[str]], ladder)
        else:
            rungs = list(ladder)
        self.ladder.set_or_bind(rungs)
