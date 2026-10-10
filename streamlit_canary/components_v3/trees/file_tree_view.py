"""The filesystem-backed cascading tree.

`FileTreeView` is `TreeView` (the classic cascading engine, see
`tree_view.py`) with its data source left on the filesystem and a path api
bolted on: `start_directory` says where to open, `open_path` lands on what a
path names, and `start_directory` may be a `Property`, so a caller can move
the panel by moving that value.

The location bar reads the machine's drives followed by the ancestors of the
folder on show, itself last::

    ['C:/', 'D:/', 'E:/', 'C:/Likianta', ..., <start_directory>]

which is what keeps any parent -- and any other drive -- one pick away.
"""

import os
import typing as tp

from lk_utils import fs

from .tree_view import _CascadingTree
from ..base import Width
from ...kernel import Property
from ...kernel import bind


class FileTreeView(_CascadingTree):
    """A classic tree rooted on a real folder.

        with v3.FileTreeView('Source', start_directory='./data') as tree:
            ...
            picked = tree.value.get()

    Every row is a real file or folder (`lk_utils.fs` lists each folder's
    children on demand), so the `filter`, the tick model and the tuple
    `resolve()` reports are all about paths on disk. Everything else -- the
    toolbar (the location ladder, `home`, `refresh`, the bucket, the mode
    control), the row gestures (`->` walks into a folder, `..` walks up, a
    click ticks), folding a folder open in place, and the Confirm bar -- is
    the shared classic tree, described in `tree_view.py`.

    Args:
        label: the widget label, drawn above the panel.
        start_directory: the folder to open (`'.'` and `''` both mean the
            cwd). A `Property` is followed: the panel re-roots when it
            changes, which is how a caller drives it from its own state.
        home_directory: where the `home` button goes back to (default:
            `start_directory`).
        (the rest as `SingleTreeSelect`)

    Properties:
        value, mode, directory, rows_visible -- see `SingleTreeSelect`.
        start_directory: str -- the folder the panel is rooted on.

    Signals:
        on_navigate / on_submit -- see `SingleTreeSelect`.

    Call `open_path(path)` to land on what a path names, `reload()` to re-read
    the folder from disk, `select(path)` / `clear()` to move the selection.
    """

    def __init__(
        self,
        label: str | Property = '',
        start_directory: tp.Union[str, Property] = '',
        *,
        home_directory: str = '',
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        source = start_directory
        super().__init__(
            label,
            '' if isinstance(source, Property) else source,
            home_directory=home_directory,
            width=width,
            **kwargs,
        )
        self.start_directory = Property(self._nav.directory)
        if isinstance(source, Property):
            # a caller who owns the value drives the panel with it; left a
            # plain string, the panel's own walking moves `start_directory`
            self.start_directory.set_or_bind(bind(source, self._normalize))
            self.start_directory.on_change.connect(self._follow_start)

    def _follow_start(self) -> None:
        """Re-root the panel onto the folder `start_directory` now names."""
        directory = self.start_directory.get()
        if directory and self._is_dir(directory):
            self._goto(directory)

    def _goto(self, directory: str, point_at: tp.Union[str, int] = '') -> None:
        super()._goto(directory, point_at)
        # the panel is standing somewhere new: keep the mirror in step
        if self.start_directory.get() != self._nav.directory:
            self.start_directory.set(self._nav.directory)

    def _jump(self, directory: str) -> None:
        super()._jump(directory)
        if self.start_directory.get() != self._nav.directory:
            self.start_directory.set(self._nav.directory)

    def _normalize(self, path: str) -> str:
        return fs.abspath(path or os.getcwd())
