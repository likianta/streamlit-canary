"""A path input backed by a tree panel.

`PathInputBrowse` pairs a `PathInput` with one of the tree panels and wires
the two the same way, whichever panel style it is wearing:

- a path typed into the box (Enter / blur) moves the panel onto the folder
  that holds it, and joins the panel's selection, so `value` -- and everything
  bound to it -- sees what was typed;
- a pick in the panel comes back out through `value`;
- the box also keeps the paths it has held (`PathInput.input_history`), which
  is what v1's "Recent" dropdown used to offer here.

`panel_style` says where the panel lives:

    'popup'   in a `Browse` popover, with its own toolbar and a Confirm
              button -- Confirm folds the popover away and writes the choice
              into the box (the default)
    'fold'    under the box, unfolded by a fold button: no popover and no
              Confirm, just a show / hide of the rows, and the box follows
              the panel's pick live
    'inline'  under the box, always on show

`tree_style` picks the panel:

    'single_list'  one folder on show at a time, `..` to walk up
    'tree_view'    every level in one listing, folders fold in place
    'dual_pane'    two columns, subfolders left and files right
    'column_view'  a Finder-style stack of columns, one level per column

The fold and inline styles host a single-column panel and take over its
toolbar row: a `PathSelect` leads that row -- a click on the box unfolds the
navigation ladder, a click on its caret the box's own history -- and the fold
button closes it, so `home`, `refresh`, the bucket and the mode control sit
between the two. The dual-pane panel has a toolbar of its own (back / forward
/ refresh / new folder), so only the popup style takes it. The column view has
a toolbar too, but takes the same `leading` / `trailing` a single-column panel
does, so every style accepts it.
"""

import os
import typing as tp

from lk_utils import fs

from ._shared import _MODE_SINGLE
from ._shared import _TreeNav
from ._shared import T
from ._shared import _check_selection_mode
from ._shared import _is_under
from ._shared import _location_options
from .column_view import ColumnView
from .dual_pane import DualTreeSelect
from .file_tree_view import FileTreeView
from .path_inputs import PathInput
from .path_inputs import PathSelect
from .single_list import SingleTreeSelect
from ..base import Width
from ..buttons import IconButton
from ..layouts import Container
from ..layouts import Popover
from ..layouts import Row
from ...kernel import Property
from ...kernel import _value
from ...kernel import bind

# what the fold button shows: pointing down while the rows are away, up while
# they are on show
_FOLD_ARROWS = {False: ':material/expand_more:', True: ':material/expand_less:'}

_STYLES_INLINE = ('single_list', 'tree_view', 'column_view')
_STYLES_POPUP = ('single_list', 'tree_view', 'dual_pane', 'column_view')
_PANEL_STYLES = ('popup', 'fold', 'inline')


def _check_tree_style(tree_style: str, allowed: tp.Tuple[str, ...]) -> None:
    if tree_style not in allowed:
        raise ValueError(
            'tree_style must be one of {}, got {!r}'.format(
                ', '.join(repr(s) for s in allowed), tree_style
            )
        )


def _check_panel_style(panel_style: str) -> None:
    if panel_style not in _PANEL_STYLES:
        raise ValueError(
            'panel_style must be one of {}, got {!r}'.format(
                ', '.join(repr(s) for s in _PANEL_STYLES), panel_style
            )
        )


def _ladder_for(directory: str) -> tp.List[str]:
    """The rungs a `PathSelect` offers, the folder on show **last**.

    `_location_options` puts the drives in front of the chain, so a folder
    that *is* a drive root sits in that front block rather than at the tail.
    The dropdown marks its last row as "you are here", so that one rung is
    moved to the tail -- the panel's own location bar keeps the original
    order, since it marks its value instead of its tail.
    """
    rungs = _location_options(directory)
    if rungs and rungs[-1] != directory:
        rungs = [rung for rung in rungs if rung != directory] + [directory]
    return rungs


class PathInputBrowse(Container):
    """A path input plus a tree panel, in one of three panel styles.

        with v3.PathInputBrowse(
            'Select a file',
            'data/sample',
            filter='.txt',  # or multi-filter: filter=('.txt', '.csv')
        ) as tree:
            ...
            path = tree.value.get()

    The box is the panel's other half. A path it resolves to -- typed, pasted,
    or handed in as `start_directory` -- moves the panel (and the panel's own
    location ladder) onto the folder that holds it; a path that is not on disk
    yet names no folder, so the panel is left where it was.

    Where the panel lives is `panel_style` (see the module docstring). In the
    popup style, Confirm closes the popover and writes the choice into the
    box: the panel's pick, or -- with nothing ticked -- the folder it ended on
    (v1 spelled that folder out as a "This folder" row, and a folder chooser
    reads the same way). That choice also joins the selection (`select`), so
    `value` carries it too.

    Args:
        label: the path box's label.
        start_directory: the path the box shows and the panel opens on. `'.'`
            (the default) means the cwd for both; `''` opens the panel on the
            cwd too, but leaves the box blank ("nothing picked yet"); any other
            value is shown in the box, the panel opening on its folder when it
            names a file, else on the value itself.
        panel_style: `'popup'` (default) / `'fold'` / `'inline'`.
        expanded: whether a foldable panel starts on show (the `'fold'`
            style's starting state; ignored by the others).
        tree_style: which panel to hold.
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        initial_mode / selection_mode: the modes to offer and to open in.
        input_history: seeds the box's own history (see `PathInput`).
        node_type: `'file'` (default) or `'folder'`; the dual-pane panel only.
        panel_height: cap on the panel's height in px.

    Properties:
        value: str | list[str] -- the panel's selection. Bindable.
        mode: str -- the panel's active mode.
        directory: str -- the folder the panel shows.
        input_history: list[str] | None -- the paths the box has held.
    """

    def __init__(
        self,
        label: str = '',
        start_directory: str = '.',
        *,
        expanded: bool = False,
        filter: T.Filter = None,
        initial_mode: tp.Optional[str] = None,
        input_history: tp.Iterable[str] | Property | None = (),
        node_type: T.NodeType = 'file',
        panel_height: int = 500,
        panel_style: str = 'popup',
        selection_mode: tp.Union[
            T.SelectionMode, tp.Tuple[T.SelectionMode, ...]
        ] = _MODE_SINGLE,
        tree_style: tp.Literal[
            'column_view', 'dual_pane', 'single_list', 'tree_view'
        ] = 'single_list',
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)
        _check_panel_style(panel_style)
        self._popup = panel_style == 'popup'
        self._foldable = panel_style == 'fold'
        _check_tree_style(
            tree_style, _STYLES_POPUP if self._popup else _STYLES_INLINE
        )

        # `start_directory` carries two sentinels: `''` leaves the box blank
        # ("nothing picked yet") while still opening the panel on the cwd, and
        # `'.'` (the default) means the cwd for both the box and the panel. Any
        # other value is a path the box shows, the panel opening on its folder
        # when it names a file, else on the path itself.
        if start_directory == '':
            open_at = os.getcwd()
            self._first_path = ''
            initial_is_file = False
        else:
            shown = os.getcwd() if start_directory == '.' else start_directory
            initial_is_file = fs.isfile(shown)
            open_at = fs.parent(shown) if initial_is_file else shown
            self._first_path = shown
        self._nav = _TreeNav(open_at)
        self._initial_is_file = initial_is_file
        self._label = label
        self._filter = filter
        self._initial_mode = initial_mode
        self._node_type = node_type
        self._panel_height = panel_height
        self._selection_mode = _check_selection_mode(selection_mode)
        self._input_history = input_history
        self._tree_style = tree_style
        # `'dual_pane'` is the odd one out: its panel owns a toolbar, has no
        # modes, and `value` is the row under the cursor rather than a pick
        self._dual = tree_style == 'dual_pane'
        # the column view has modes of its own (one) and a toolbar it shares
        # with the single-column panels, so it needs only a small branch
        self._column = tree_style == 'column_view'
        # set while this wrapper writes the box itself: that write is not the
        # user typing, so it must not echo back into the panel (see
        # `_on_path_typed`)
        self._quiet = False
        # the fold state only means something to the foldable style; a
        # `Property` either way, so `rows_visible` has something to bind to
        self._expanded = Property(bool(expanded) if self._foldable else True)

        # `value` / `mode` mirror the panel's, so a caller reads the selection
        # right here; writes go through the panel (`select` / `clear`).
        self.value = Property(tp.cast(tp.Union[str, tp.List[str]], ''))
        self.mode = Property(_MODE_SINGLE)

        with self:
            self._build()

        self.value.bind(self._tree.value)
        if not self._dual:
            self.mode.bind(self._tree.mode)
        # the box's own history, reachable from the wrapper (a mirror, so the
        # same `Property` is not listed twice in `_iter_properties`)
        self.input_history = Property(tp.cast(tp.Optional[tp.List[str]], None))
        self.input_history.bind(self._path_input.input_history)

        # -- handlers -------------------------------------------------------

        @self._path_input.value.on_change.partial(_value)
        def _on_path_typed(norm_path: str) -> None:
            # `norm_path` is `''` only while the box is blank; a path that is
            # not on disk yet reaches here too (a folder being named), so
            # nothing below may assume it exists. `_quiet` marks a write made
            # by this wrapper: that is not a typed path, so it must not walk
            # the panel off to that folder -- which would also drop a
            # `multiple` pick.
            if not norm_path or self._quiet:
                return
            self._send_to_panel(norm_path)

        if not self._popup:
            # the inline ones have no Confirm: the box is simply what the
            # panel picks (the popup keeps its Confirm as the moment of truth)
            @self._tree.value.on_change
            def _on_panel_picked() -> None:
                if self._quiet:
                    return
                picked = self._picked_path()
                if not picked:
                    # nothing picked, or the pick was dropped: leave the box
                    # as it is rather than blanking what the user may have
                    # typed
                    return
                self._quiet = True
                try:
                    self._path_input.show(picked)
                finally:
                    self._quiet = False

            # a `PathSelect`'s ladder belongs to the panel, so every move
            # re-seeds it (`on_navigate` also speaks on the first listing, but
            # this subscription is wired after that, hence the seed in
            # `_mount_box`)
            @self._tree.on_navigate
            def _on_navigated(directory: str) -> None:
                self._path_input.ladder.set(_ladder_for(directory))

        self._wire_host()

    # -- layout -------------------------------------------------------------

    def _build(self) -> None:
        """Put the box and the panel where `panel_style` wants them."""
        if self._popup:
            with Row('bottom'):
                self._mount_box()
                self._browse_popover = Popover(
                    'Browse',
                    panel_align='row',
                    panel_max_height=self._panel_height,
                )
                with self._browse_popover:
                    self._tree = self._make_panel(confirm=True)
            return
        if self._foldable:
            self._tree = self._make_panel(
                confirm=False,
                leading=self._mount_box,
                trailing=self._mount_fold,
                rows_visible=self._expanded,
            )
            return
        self._tree = self._make_panel(confirm=False, leading=self._mount_box)

    def _make_panel(
        self,
        *,
        confirm: bool = True,
        leading: tp.Optional[tp.Callable[[], None]] = None,
        rows_visible: tp.Any = True,
        trailing: tp.Optional[tp.Callable[[], None]] = None,
    ) -> tp.Any:
        """Build the panel `tree_style` asks for, dressed for its host."""
        if self._dual:
            return DualTreeSelect(
                self._nav.directory,
                filter=self._filter,
                height=self._panel_height,
                node_type=self._node_type,
                show_confirm_button=confirm,
            )
        if self._column:
            # the column view takes the same `leading` / `trailing` /
            # `rows_visible` a single-column panel does, so it drops into all
            # three wrappers; only its `start_directory` and column height are
            # its own (`SingleTreeSelect`'s first positional is a label, hence
            # the keyword).
            return ColumnView(
                start_directory=self._nav.directory,
                filter=self._filter,
                height=self._panel_height,
                leading=leading,
                trailing=trailing,
                rows_visible=rows_visible,
                show_confirm_button=confirm,
                show_location=leading is None,
                accept_new_option=self._popup,
                _vendored=True,
                border=False,
            )
        if self._tree_style == 'tree_view':
            cls = FileTreeView
        else:
            cls = SingleTreeSelect
        return cls(
            # keyword: `SingleTreeSelect`'s first positional is its `label`, so
            # the folder would land on the wrong field there
            start_directory=self._nav.directory,
            filter=self._filter,
            height=None,
            initial_mode=self._initial_mode,
            selection_mode=self._selection_mode,
            leading=leading,
            trailing=trailing,
            rows_visible=rows_visible,
            show_confirm_button=confirm,
            # the box in the toolbar row resolves a typed path as well as the
            # ladder does; the popup's panel has no box inside it, so it keeps
            # the ladder's own `accept_new_option` row instead
            accept_new_option=self._popup,
            show_location=leading is None,
            # this panel rides inside a host that draws the frame: skip the
            # panel's own border, and float its (hidden) Confirm bar
            _vendored=True,
            border=False,
        )

    def _mount_box(self) -> None:
        """Build the path box -- the head of the toolbar, or of the row.

        The inline ones lead the panel's toolbar, which keeps no location bar
        of its own, so their box is a `PathSelect`: a click on it unfolds the
        navigation ladder, a click on its caret the box's own history.
        """
        cls = PathInput if self._popup else PathSelect
        extra: tp.Dict[str, tp.Any] = {}
        if not self._popup:
            # the ladder is the panel's, and the panel does not exist yet --
            # this seeds the folder it opens on (`_nav`), and `_on_navigated`
            # keeps it in step from there
            extra['ladder'] = _ladder_for(self._nav.directory)
        self._path_input = cls(
            self._label,
            self._first_path,
            input_history=self._input_history,
            width='stretch',
            **extra,
        )

    def _mount_fold(self) -> None:
        """Build the fold / unfold button that closes the inline panel."""
        self._browse_btn = IconButton(
            bind(self._expanded, lambda on: _FOLD_ARROWS[bool(on)]),
            help='Browse',
        )

        @self._browse_btn.on_click
        def _toggle_fold() -> None:
            self._expanded.set(not self._expanded.get())

    def _wire_host(self) -> None:
        """Hook up what the popup style adds: its Confirm button."""
        if not self._popup:
            return
        if self._dual:

            @self._tree.on_confirm
            def _on_panel_confirmed() -> None:
                self._commit(self._picked_path())

        else:

            @self._tree.on_submit
            def _on_panel_submitted(paths: tp.Iterable[str]) -> None:
                self._commit(self._confirmed_pick(tuple(paths)))

    def _confirmed_pick(self, resolved: tp.Tuple[str, ...]) -> str:
        """The pick Confirm commits, out of the panel's resolved paths.

        Only a pick that sits inside the folder on show is the user's answer.
        A pick left over from an earlier confirm, in a folder they have since
        walked away from, is not: `Confirm` then means the folder itself,
        which is where the panel is pointed (and returning to that earlier
        folder restores its pick). The first pick inside the folder wins, so
        the order the user picked in is kept.
        """
        directory = self._tree.directory
        for path in resolved:
            if _is_under(path, directory):
                return path
        return directory

    def _commit(self, choice: str) -> None:
        """Take the choice: fold the popover away and write the box.

        Writing the box is a commit, not a typed path, so it must leave the
        panel where it is; the choice also joins the panel's selection, which
        `value` mirrors.
        """
        self._browse_popover.close()
        if not choice:
            return
        self._quiet = True
        try:
            self._path_input.show(choice)
        finally:
            self._quiet = False
        if not self._dual:
            self._tree.select(choice)

    # -- panel plumbing -----------------------------------------------------

    def _picked_path(self) -> str:
        """The panel's pick as one path (its first, when it holds several)."""
        if self._dual:
            return str(self._tree.value.get())
        resolved = tuple(self._tree.resolve())
        return resolved[0] if resolved else ''

    def _send_to_panel(self, norm_path: str) -> None:
        """Take a typed path to the panel: move it there, then pick it."""
        if self._dual:
            # `_goto` reads the path itself (a file names its folder) and
            # quietly does nothing when there is nothing to point at
            self._tree._goto(norm_path)
            return
        if fs.isdir(norm_path):
            self._tree._jump(norm_path)
        elif fs.exist(norm_path):
            # a file: show the folder that holds it
            self._tree._jump(fs.parent(norm_path))
        # a path that is not on disk yet names no folder, so the panel is left
        # where it was rather than sent anywhere. Either way the path joins
        # the selection (`select` is exactly the door for a path the listing
        # does not hold), and `_jump` goes first: in `multiple` it clears the
        # picks, which would otherwise swallow this one.
        self._tree.select(norm_path)

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Drop the panel's selection."""
        if self._dual:
            # the dual pane keeps no pick of its own: `value` there is the row
            # under the cursor, re-derived from the highlight on every listing
            self._tree.value.set('')
            return
        self._tree.clear()

    @property
    def directory(self) -> str:
        """The folder the panel shows."""
        return self._tree.directory

    def reload(self) -> None:
        """Re-read the browsed folder from disk (the panel's own button)."""
        self._tree.reload()

    def resolve(self) -> tp.Tuple[str, ...]:
        """The panel's selection as absolute paths (see `SingleTreeSelect`).

        A ticked folder stands for everything under it, so a pick another
        pick already covers is dropped. Not defined for the dual-pane panel,
        whose `value` is the row under the cursor rather than a pick.
        """
        return tuple(self._tree.resolve())

    @property
    def widgets(self) -> tp.Dict[str, tp.Any]:
        """The panel's own sub-components, reached through the wrapper.

        This is the panel's `widgets` dict (see `SingleTreeSelect`), so a
        caller can extend the panel -- `bottom_bar` being the usual door --
        without having to know which panel `tree_style` built::

            with v3.PathInputBrowse(...) as tree:
                with tree.widgets['bottom_bar']:
                    v3.Button('Open input folder')

        The dual-pane panel keeps no such dict of its own.
        """
        return self._tree.widgets
