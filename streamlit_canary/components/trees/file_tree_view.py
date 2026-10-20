"""The filesystem-backed cascading tree.

`FileTreeView` is `TreeView` (the classic cascading engine, see
`tree_view.py`) with its data source left on the filesystem and a path api
bolted on: `start_directory` says where to open, `root_directory` says the
top it may not pass, `open_path` lands on what a path names, and either of
the first two may be a `Property`, so a caller can move the panel by moving
that value.

The location bar reads the machine's drives followed by the ancestors of the
folder on show, itself last::

    ['C:/', 'D:/', 'E:/', 'C:/Likianta', ..., <start_directory>]

which is what keeps any parent -- and any other drive -- one pick away. Set
`root_directory` and the ladder is confined to it: the rungs start at the
root, no drive leads them and no ancestor sits above them, and `..` is gone
while the panel stands on the root -- so there is nowhere above it to go.
"""

import os
import typing as tp

from lk_utils import fs

from ._shared import _is_under
from ._shared import _root_path
from .tree_view import _CascadingTree
from ..base import Width
from ...kernel import Property
from ...kernel import bind


def _check_root(root: str, start: str) -> None:
    """`root` must hold `start` -- it is the top the panel may not pass."""
    if not root or root == '/':
        return
    if start == root or _is_under(start, root):
        return
    raise ValueError(
        'root_directory {!r} does not contain start_directory {!r}'.format(
            root, start
        )
    )


class FileTreeView(_CascadingTree):
    """A classic tree rooted on a real folder.

        with sc.FileTreeView('Source', start_directory='./data') as tree:
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
        root_directory: the folder navigation may not leave -- `..` and the
            location ladder both stop there (default: `/`, the whole
            machine). `start_directory` must be the root or somewhere under
            it. On Windows the default `/` leaves every drive a pick away on
            the ladder; a real root drops the drives and the root's own
            ancestors, so the ladder runs from the root down. A `Property`
            is followed the way `start_directory` is.
        home_directory: where the `home` button goes back to (default: the
            root while confined, else `start_directory`).
        (the rest as `SingleTreeSelect`)

    Properties:
        value, mode, directory, rows_visible -- see `SingleTreeSelect`.
        start_directory: str -- the folder the panel is rooted on.
        root_directory: str -- the top the panel may not pass (`/` for the
            whole machine).

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
        root_directory: tp.Union[str, Property] = '/',
        home_directory: str = '',
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        source = start_directory
        root_source = root_directory
        # The root is settled before `super`, which draws the first listing
        # out of `_root_dir` -- it is what decides whether that listing leads
        # with `..`.
        self.root_directory = Property(
            _root_path('' if isinstance(root_source, Property) else root_source)
        )
        super().__init__(
            label,
            '' if isinstance(source, Property) else source,
            home_directory=home_directory,
            width=width,
            **kwargs,
        )
        # only a pair of plain paths can be checked here; a bound one lands
        # later, when its value does (see `_follow_root` / `_follow_start`)
        if not isinstance(source, Property) and not isinstance(
            root_source, Property
        ):
            _check_root(self.root_directory.get(), self._nav.directory)
        self._explicit_home = bool(home_directory)
        if not self._explicit_home:
            # a confined panel's natural home is its root; unconfined, it is
            # the folder we opened on, as in the base
            self._home_dir = self._root_dir() or self._nav.start_directory
        self.start_directory = Property(self._nav.directory)
        if isinstance(source, Property):
            # a caller who owns the value drives the panel with it; left a
            # plain string, the panel's own walking moves `start_directory`
            self.start_directory.set_or_bind(bind(source, self._normalize))
            self.start_directory.on_change.connect(self._follow_start)
        if isinstance(root_source, Property):
            # connected before the first sync, so a root the source already
            # carries clamps the ladder right away (the initial listing was
            # drawn unconfined)
            self.root_directory.on_change.connect(self._follow_root)
            self.root_directory.set_or_bind(
                bind(root_source, self._normalize_root)
            )

    def _follow_root(self) -> None:
        """Re-clamp the panel onto a freshly set `root_directory`.

        The ladder follows on the redraw. So does the panel itself when it
        happens to stand outside the new root (a root that moved past where it
        was): it is re-rooted onto the top, since that is now the nearest
        place inside.
        """
        root = self._root_dir()
        if not self._explicit_home:
            self._home_dir = root or self._nav.start_directory
        directory = self._nav.directory
        if root and directory != root and not _is_under(directory, root):
            self._goto(root)
            return
        self._refresh_listing()

    def _follow_start(self) -> None:
        """Re-root the panel onto the folder `start_directory` now names.

        A start the current root does not hold is refused (see `_check_root`):
        the root is the stronger promise, and moving past it would leave the
        panel outside its own world.
        """
        directory = self.start_directory.get()
        if not (directory and self._is_dir(directory)):
            return
        _check_root(self.root_directory.get(), directory)
        self._goto(directory)

    def _goto(self, directory: str, point_at: tp.Union[str, int] = '') -> None:
        if directory and not self._within_root(self._normalize(directory)):
            return
        super()._goto(directory, point_at)
        # the panel is standing somewhere new: keep the mirror in step
        if self.start_directory.get() != self._nav.directory:
            self.start_directory.set(self._nav.directory)

    def _is_at_root(self) -> bool:
        """Whether the panel stands on `root_directory` (so draws no `..`)."""
        root = self._root_dir()
        return bool(root) and self._nav.directory == root

    def _jump(self, directory: str) -> None:
        if not self._within_root(directory):
            return
        super()._jump(directory)
        if self.start_directory.get() != self._nav.directory:
            self.start_directory.set(self._nav.directory)

    def _normalize(self, path: str) -> str:
        return fs.abspath(path or os.getcwd())

    @staticmethod
    def _normalize_root(path: str) -> str:
        return _root_path(path or '/')

    def _root_dir(self) -> str:
        """The top the panel may not pass (`''` when it may go anywhere).

        `''` and `/` both mean the whole machine. A root that is not a real
        folder confines nothing either: there is nothing there to stop at,
        and the panel would only try to list a folder that is not on disk.
        """
        root = self.root_directory.get()
        if root in ('', '/'):
            return ''
        return root if self._is_dir(root) else ''

    def _within_root(self, directory: str) -> bool:
        """Whether `directory` is the root or somewhere under it."""
        root = self._root_dir()
        if not root:
            return True
        return directory == root or _is_under(directory, root)
