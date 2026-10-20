"""The cascading tree: the single-pane browser with every level on show.

`TreeView` is `SingleTreeSelect` plus one axis -- a folder row can be
folded open *in place*, so a whole hierarchy is walkable without re-rooting
the panel.  That is the shape a file dialog has been wearing since Windows
95, hence "classic", as opposed to the flat one-folder-at-a-time listing the
single pane draws.

Everything else is inherited, and deliberately so: the toolbar (the location
ladder, `home`, `refresh`, the bucket, the mode control), the row gestures (a
click ticks, `->` walks in, `..` walks up), the `single` / `multiple` /
`multicross` modes and the Confirm bar all behave exactly as they do in the
flat panel.  What changes is only what `single_list.py`'s row model leaves
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

from ._shared import NAV_UP
from ._shared import T
from ._shared import _as_picked
from ._shared import _is_multi
from ._shared import _is_under
from .single_list import SingleTreeSelect
from ...kernel import Property


class _CascadingTree(SingleTreeSelect):
    """The listing engine of a cascading tree ("classic": every level in one
    listing, folders folding open in place).

    Everything here is inherited behavior plus an overridable data source: the
    engine reads its rows through `_dirnames` / `_filenames` / `_parent_of`
    (see `SingleTreeSelect`), which default to the filesystem. A panel that
    lists something else overrides them -- `TreeView` drives them from a
    static model, `FileTreeView` leaves them on the filesystem.

    Subclasses only have to hand this a root folder to open on, as
    `start_directory` (`_nav.directory`), and they get the whole classic tree:
    the toolbar, the row gestures, the fold / unfold buttons, the tick model
    (`'single'` / `'multiple'` / `'multicross'`) and the Confirm bar.
    """

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
        out = [self._join(directory, n) for n in self._dirnames(directory)]
        out += [
            self._join(directory, n)
            for n in self._filenames(directory)
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

    def _is_at_root(self) -> bool:
        """Whether the panel sits on the topmost folder it may show.

        There `..` would lead out of the panel's world -- a model root has no
        outside, and a confined filesystem tree stops at its
        `root_directory` -- so it is not drawn.  False here: the base engine
        has no top of its own; a subclass that does overrides this.
        """
        return False

    def _listing_options(self) -> list:
        """The rows of the panel: the tree, led by `..` unless at the top.

        Sitting on the top folder draws no `..` (see `_is_at_root`); a level
        down it comes back, to climb back within the tree.
        """
        options = self._walk(self._nav.directory)
        if not self._is_at_root():
            options = [NAV_UP] + options
        return options

    def _walk(self, directory: str) -> list:
        """`directory`'s rows, each open folder expanded under its own row."""
        out: list = []
        for name in self._dirnames(directory):
            path = self._join(directory, name)
            out.append(path + '/')
            if path in self._open:
                out += self._walk(path)
        for name in self._filenames(directory):
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
        if self._parent_of(target) == cover:
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
        node = self._parent_of(path)
        while node and node != self._nav.directory:
            children = self._child_paths(node)
            if children and all(
                self._covered(c, set(picked)) for c in children
            ):
                picked = self._tick(picked, node)
            node = self._parent_of(node)
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


class _Model:
    """A static tree: `{name: subdict | None}`, folders and leaves.

    A `dict` value is a folder (`{}` an empty one), `None` a leaf. Node paths
    are the names joined with `/` -- the separator the filesystem also uses,
    which is what lets the engine spell a cascading row as a plain path
    (`A/D/G`) and read it back with nothing but string work.
    """

    def __init__(self, data: tp.Optional[dict]) -> None:
        self._data = data if isinstance(data, dict) else {}
        if not self._data:
            # nothing to show yet: a panel can be built around an empty model
            # (and fed one later), it just lists no rows
            self.root = ''
            return
        roots = list(self._data)
        if len(roots) != 1:
            raise ValueError(
                'data needs exactly one root node, got {!r}'.format(roots)
            )
        self.root: str = roots[0]

    def chain(self, path: str) -> tp.List[str]:
        """The rungs from the root down to `path`, itself last."""
        text = str(path).strip('/')
        if not text:
            return []
        parts = text.split('/')
        return ['/'.join(parts[: i + 1]) for i in range(len(parts))]

    def dirnames(self, path: str) -> tp.List[str]:
        node = self.node(path) or {}
        return sorted(n for n, v in node.items() if isinstance(v, dict))

    def filenames(self, path: str) -> tp.List[str]:
        node = self.node(path) or {}
        return sorted(n for n, v in node.items() if v is None)

    def node(self, path: str) -> tp.Optional[dict]:
        """The folder `path` names, `None` when it is a leaf or unknown."""
        data: tp.Any = self._data
        for name in str(path).rstrip('/').split('/'):
            if not name or not isinstance(data, dict):
                return None
            data = data.get(name)
        return data if isinstance(data, dict) else None

    def parent(self, path: str) -> str:
        path = str(path).rstrip('/')
        return path.rsplit('/', 1)[0] if '/' in path else path


class TreeView(_CascadingTree):
    """A classic tree over a static model, with no filesystem behind it.

        with sc.TreeView('Distribution', {
            'A': {
                'B': None,   # a leaf -- no "enter" arrow
                'C': {},     # an empty folder
                'D': {'E': None, 'G': {}},
            }
        }) as tree:
            ...
            node = tree.value.get()

    `data` is one `{name: subdict | None}` map: a `dict` value is a folder,
    `None` a leaf; the map's single key is the root. Node paths are the names
    joined with `/` (`A/D/G`), which is what the toolbar's location bar reads
    off: it opens at `['A']` and, once you walk into `G`, shows
    `['A', 'A/D', 'A/D/G']`. `..` walks back up (it is absent while you sit
    on the root, which has no outside); a folder's chevron folds it open in
    place.

    Everything else is `FileTreeView`'s -- the row gestures, the modes, the
    Confirm bar, the bucket -- and deliberately so: this is the same engine,
    fed by a model instead of by `lk_utils.fs`.

    Args:
        data: the model (bindable).
        (the rest as `FileTreeView`)

    Properties / Signals: as `FileTreeView`.
    """

    def __init__(
        self,
        label: str | Property = '',
        data: tp.Optional[dict] = None,
        *,
        filter: T.Filter = None,
        **kwargs: tp.Any,
    ) -> None:
        # `data` is bindable: setting a new model re-roots the tree (see
        # `_resettle_model`). That is what lets a tree mirror something that
        # changes -- a selection elsewhere, say -- without a rebuild.
        self.data = Property(data)
        self._model = _Model(data)
        super().__init__(label, self._model.root, filter=filter, **kwargs)
        # `_TreeNav` reads its starting folder as a filesystem path; a model
        # root is not one, so it is settled here and the listing redrawn
        # against it. The first drawing (inside `super`) is the throwaway.
        self._settle_model()
        self.data.on_change.connect(self._resettle_model)

    def _resettle_model(self) -> None:
        """Re-root the tree on a fresh `data` and redraw.

        The pick set is dropped along the way: those node paths belonged to
        the old model. `_Model` checks the new model's shape, so a bad one
        raises here instead of quietly drawing nothing.
        """
        self._model = _Model(self.data.get())
        self._settle_model()

    def _settle_model(self) -> None:
        self._nav.directory = self._model.root
        self._nav.start_directory = self._model.root
        self._home_dir = self._model.root
        self.value.set([] if _is_multi(self.mode.get()) else '')
        self._open.clear()
        self._refresh_listing()

    # -- data source --------------------------------------------------------

    @staticmethod
    def _basename(path: str) -> str:
        path = str(path).rstrip('/')
        return path.rsplit('/', 1)[1] if '/' in path else path

    def _dirnames(self, directory: str) -> tp.List[str]:
        return self._model.dirnames(directory)

    def _exists(self, path: str) -> bool:
        path = str(path).rstrip('/')
        return path == self._model.root or self._is_dir(path)

    def _filenames(self, directory: str) -> tp.List[str]:
        return self._model.filenames(directory)

    def _is_dir(self, path: str) -> bool:
        return self._model.node(path) is not None

    def _ladder(self, directory: str) -> tp.List[str]:
        return self._model.chain(directory)

    def _is_at_root(self) -> bool:
        """Whether the panel sits on the model's root (so draws no `..`).

        True on the root itself -- whether the model is empty (nothing to
        walk, and nothing to walk up to) or just resting on its one top node.
        Descend a level and `..` comes back, to climb back within the model.
        """
        return not self._model.root or self._nav.directory == self._model.root

    def _normalize(self, path: str) -> str:
        return str(path).strip().replace('\\', '/').strip('/')

    def _option_path(self, option: tp.Any) -> str:
        name = str(option)
        return '' if name == NAV_UP else name.rstrip('/')

    def _parent_of(self, path: str) -> str:
        return self._model.parent(path)
