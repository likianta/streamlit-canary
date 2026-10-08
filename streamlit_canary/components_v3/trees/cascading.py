"""The cascading tree: the single-pane browser with every level on show.

`ClassicTreeSelect` is `SingleTreeSelect` plus one axis -- a folder row can be
folded open *in place*, so a whole hierarchy is walkable without re-rooting
the panel.  That is the shape a file dialog has been wearing since Windows
95, hence "classic", as opposed to the flat one-folder-at-a-time listing the
single pane draws.

Everything else is inherited, and deliberately so: the toolbar (the location
ladder, `home`, `refresh`, the bucket, the mode control), the row gestures (a
click ticks, `->` walks in, `..` walks up), the `single` / `multiple` /
`multicross` modes and the Confirm bar all behave exactly as they do in the
flat panel.  What changes is only what `single_pane.py`'s row model leaves
open:

    rows     a row is an absolute path rather than a name relative to the
             folder on show, so several levels can share one listing --
             `_listing_options` walks the folders in `_open` depth first.
    indent   a row knows how far below the panel's folder it sits
             (`_depth_of`), which `render.py` turns into a
             `--st-tree-depth` custom property and `35-choice.css` into a
             left inset.
    toggle   a folder with something inside carries a collapse / expand
             button left of its box (`_expandable` / `_is_expanded`); its
             chevron turns a quarter turn while the folder is open.
    ticks    in the multi modes a folder stands for its whole subtree, so a
             box has three states and a folder with only *part* of its
             subtree picked draws half-ticked (`_is_indeterminate`).

The tick model is the one real piece of arithmetic.  `value` keeps *covering*
picks -- one path may stand for everything under it -- and the invariant is
that no pick sits inside another:

    tick a folder       drop the picks it covers, then add it
    tick a file         just add it
    fold a subtree      once every child of a folder is picked, the picks are
                        replaced by the folder itself, so a subtree that is
                        wholly ticked reads as one tick instead of as
                        "something is going on in there"
    un-tick a row       a row covered by a pick lives *inside* that pick: the
                        pick is opened one level at a time until the row is
                        its own child, and that child is simply left out.
                        Un-ticking one file therefore keeps the rest of the
                        subtree ticked -- which is exactly what the
                        half-ticked box above it then reports.

`_apply_ticks` diffs what the client hands back against what the rows were
drawn with (recomputed from `value`, so nothing extra is remembered), which
is what separates "the user ticked this row" from "this row is merely covered
by a pick": only the first is a change.

For the args, the properties and the signals, see `SingleTreeSelect`, which
this subclasses -- the difference is entirely in what the listing shows.
"""

import typing as tp

from lk_utils import fs

from ._shared import NAV_UP
from ._shared import _as_picked
from ._shared import _is_multi
from ._shared import _is_under
from .single_pane import SingleTreeSelect


class ClassicTreeSelect(SingleTreeSelect):
    def __init__(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        # The folders that are showing their children, by absolute path.
        # Built before `super().__init__`, which draws the listing out of it.
        self._open: tp.Set[str] = set()
        super().__init__(*args, **kwargs)

        # The collapse / expand button is the one gesture the flat panel has
        # no use for, so it is wired up here rather than in the base: the base
        # builds both groups, this attaches to the signal they already carry.
        @self._single_list.on_toggle
        def _on_single_row_toggle(index: int) -> None:
            self._toggle_row(self._single_list, index)

        @self._multi_list.on_toggle
        def _on_multi_row_toggle(index: int) -> None:
            self._toggle_row(self._multi_list, index)

    # -- rows ---------------------------------------------------------------

    def _child_paths(self, directory: str) -> tp.List[str]:
        """The nodes `directory` holds, folders first.

        The rows `_walk` would draw one level down: every folder (a folder is
        always worth listing), and the files the filter keeps -- those are the
        nodes this panel deals in, so a tick covering a folder means the same
        set of paths here as it does in the listing.
        """
        out = [self._join(directory, n) for n in self._nav.dirnames(directory)]
        out += [
            self._join(directory, n)
            for n in self._nav.filenames(directory)
            if self._keeps(n)
        ]
        return out

    def _depth_of(self, option: tp.Any) -> int:
        """How many levels below the panel's folder a row sits."""
        path = self._option_path(option)
        if not path:
            return 0
        rest = path[len(self._nav.directory) :]
        return max(0, rest.count('/') - 1)

    def _expandable(self, option: tp.Any) -> bool:
        """Whether a row draws the collapse / expand button: a folder with
        something to show.

        An empty folder (or one whose only files the filter drops) gets no
        button rather than a button that does nothing -- so the row also
        needs no indent below it, and the eye is not sent looking.
        """
        if not str(option).endswith('/'):
            return False
        return bool(self._child_paths(self._option_path(option)))

    @staticmethod
    def _join(directory: str, name: str) -> str:
        return '{}/{}'.format(directory.rstrip('/'), name)

    def _listing_options(self) -> list:
        """The rows of the panel: `..`, then the tree from the top."""
        return [NAV_UP] + self._walk(self._nav.directory)

    def _walk(self, directory: str) -> list:
        """`directory`'s rows, each open folder expanded under its own row."""
        out: list = []
        for name in self._nav.dirnames(directory):
            path = self._join(directory, name)
            out.append(path + '/')
            if path in self._open:
                out += self._walk(path)
        for name in self._nav.filenames(directory):
            if self._keeps(name):
                out.append(self._join(directory, name))
        return out

    # -- ticks --------------------------------------------------------------

    def _apply_ticks(self) -> None:
        """Fold the ticked rows back into the selection.

        The client hands back every ticked row, which is the *whole* state
        (a pick covers its subtree, so a covered row is drawn ticked too), so
        the change has to be found by diffing: the rows we last drew ticked
        are recomputed from `value`, and whatever differs is what the user
        just did -- ticked, or un-ticked.
        """
        picked = _as_picked(self.value.get())
        options = list(self._multi_list.options.get() or ())
        was = {str(o) for o in options if self._is_ticked(o, set(picked))}
        now = {str(o) for o in (self._multi_list.value.get() or ())}
        for option in now - was:
            path = self._option_path(option)
            # a row a pick already covers needs no pick of its own: ticking a
            # folder and one of its children in one go must not leave a pick
            # nested inside a pick
            if path and not self._covered(path, set(picked)):
                picked = self._fold(self._tick(picked, path), path)
        # deepest first: un-ticking a row *inside* a covered subtree has to
        # open that pick before the pick itself is looked at, whichever order
        # the client happened to list the rows in (a set has none)
        for option in sorted(was - now, key=lambda o: -self._depth_of(o)):
            path = self._option_path(option)
            if path:
                picked = self._untick(picked, path)
        self.value.set(picked)
        self._refresh_listing()

    def _break_cover(self, cover: str, target: str) -> tp.List[str]:
        """The picks that mean "everything `cover` held, bar `target`".

        The pick is opened one level at a time -- each level replaced by its
        own children -- until `target` is a child of the level being opened,
        and that level simply omits it.  A level is only ever listed, never
        descended into, so un-ticking one row costs one reading per level of
        the path, not a walk of the subtree.
        """
        children = self._child_paths(cover)
        if fs.parent(target) == cover:
            return [c for c in children if c != target]
        out: tp.List[str] = []
        for child in children:
            if _is_under(target, child):
                out += self._break_cover(child, target)
            else:
                out.append(child)
        return out

    @staticmethod
    def _covered(path: str, picked: tp.Set[str]) -> bool:
        """Whether some picked path covers `path` (is it, or holds it)."""
        return any(p == path or _is_under(path, p) for p in picked)

    def _fold(self, picked: tp.List[str], path: str) -> tp.List[str]:
        """Replace a folder's picks by the folder, once they cover it all.

        Walks up from the row that was just ticked: a folder whose every
        child is now picked is a folder that is entirely selected, so it
        becomes the pick and the children fall out as covered.  It stops at
        the panel's own folder -- that one is never a row, so folding into it
        would produce a pick nothing on screen could un-tick.
        """
        node = fs.parent(path)
        while node and node != self._nav.directory:
            children = self._child_paths(node)
            if children and all(
                self._covered(c, set(picked)) for c in children
            ):
                picked = self._tick(picked, node)
            node = fs.parent(node)
        return picked

    def _is_expanded(self, option: tp.Any) -> bool:
        """Whether a folder row is showing its children."""
        return self._option_path(option) in self._open

    def _is_indeterminate(self, option: tp.Any) -> bool:
        """Whether a row's box is drawn half-ticked.

        A folder that is not itself picked (nor covered by a pick) but has
        something picked inside it.  Radios have no third state, so this is
        `False` in `single` mode -- the row model still asks, and the answer
        is simply not to draw one.
        """
        if not _is_multi(self.mode.get()):
            return False
        if not str(option).endswith('/'):
            return False
        path = self._option_path(option)
        if not path:
            return False
        picked = set(_as_picked(self.value.get()))
        if self._covered(path, picked):
            return False
        return any(_is_under(p, path) for p in picked)

    def _is_ticked(self, option: tp.Any, picked: tp.Set[str]) -> bool:
        return self._covered(self._option_path(option), picked)

    def _row_extras(self) -> dict:
        return {
            'depth_of': self._depth_of,
            'expandable': self._expandable,
            'expanded': self._is_expanded,
            'indeterminate': self._is_indeterminate,
        }

    @staticmethod
    def _tick(picked: tp.List[str], path: str) -> tp.List[str]:
        """Add `path`, dropping the picks it covers."""
        kept = [p for p in picked if p != path and not _is_under(p, path)]
        return kept + [path]

    def _toggle_row(self, group: tp.Any, index: tp.Any) -> None:
        """Open or fold the folder a row stands for, and redraw.

        Nothing about the selection moves: the button reports its own event
        (see `_NavigationGroup.on_toggle`), so folding a folder cannot be
        mistaken for ticking it.  The row is kept highlighted, though -- it
        is the one the pointer is on, and redrawing the rows would otherwise
        drop the mark.
        """
        options = list(group.options.get() or ())
        if not (isinstance(index, int) and 0 <= index < len(options)):
            return
        path = self._option_path(options[index])
        if not path:
            return
        if path in self._open:
            self._open.discard(path)
        else:
            self._open.add(path)
        self._point_at = path
        self._refresh_listing()

    def _untick(self, picked: tp.List[str], path: str) -> tp.List[str]:
        """Drop `path` from the picks, opening whatever covered it."""
        out: tp.List[str] = []
        for p in picked:
            if p == path:
                continue
            if _is_under(path, p):
                out += self._break_cover(p, path)
            else:
                out.append(p)
        return out
