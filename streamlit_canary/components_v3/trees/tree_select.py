"""The single-pane browser and its "input + panel" wrapper."""

import os
import typing as tp

from lk_utils import fs

from ._shared import (
    _MODE_LABELS,
    _MODE_MULTICROSS,
    _MODE_MULTIPLE,
    _MODE_SINGLE,
    _NavCheckGroup,
    _NavRadioGroup,
    _TreeNav,
    NAV_UP,
    T,
    _location_options,
    _filter_func,
    _path_label,
    _is_enterable,
    _is_nav_up,
    _is_under,
    _as_picked,
    _bucket_text,
    _check_initial_mode,
    _check_selection_mode,
    _empty_value,
    _is_multi,
    _is_multicross,
    _is_single,
    bucket_label,
    entry_label,
    listing_options,
    option_path,
)
from .recent import Recent
from .._shared import _Labeled
from ..base import Component
from ..base import Width
from ..buttons import Button
from ..buttons import IconButton
from ..inputs import CheckGroup
from ..inputs import PathInput
from ..inputs import RadioGroup
from ..inputs import ReducibleGroup
from ..inputs import Selectbox
from ..layouts import Column
from ..layouts import FloatingContainer
from ..layouts import Popover
from ..layouts import Row
from ...kernel import Property
from ...kernel import Signal
from ...kernel import bind


class TreeSelect(_Labeled, Column):
    """The single-pane tree browser: a folder listing that navigates itself.

        with Popover('Browse', panel_align='row', panel_max_height=500):
            tree = v3.TreeSelect(filter='.txt')
        ...
        picked = tree.value.get()

    Layout::

        [ /current/folder v ] [home] [refresh] [bucket] [mode]  <- toolbar
        ..   (goto parent)            <- one click walks up, no arrow
        subfolder/                              ->
        another-file.txt                 <- scrolls past `height` px
        [              Confirm               ]

    The toolbar is a row across the top of the panel: a location selectbox
    listing every ancestor of the folder on show -- itself included, so any
    parent is one pick away -- with the machine's other drives in front of
    them (`_location_options`), and then the actions: `home` returns to the
    starting folder, `refresh` re-reads the folder on show.  Both the trigger
    and the ladder's items clip a path too long for them, and a clipped item
    shows its whole label on hover (`st-truncate-help`).

    `_vendored` settles where the Confirm button goes and what frame the
    panel wears.  Left alone (the default) the panel is a standalone widget:
    the button sits under the listing, in the ordinary flow, and the panel
    draws its own `border`.  A wrapper that already lives inside a frame --
    `TreeSelectWithInput`, inside a popover -- passes `_vendored=True`
    instead: the button rides in a `FloatingContainer` in the panel's
    corner, staying put while the listing scrolls beneath it (and, being
    sticky, keeping its place in the flow, so no row can end up hidden under
    it for good), and `border` falls back to `False` so the popover's own
    frame is not doubled.

    Two gestures live on a row, and neither one waits on the other:

        one click   tick / pick that row -- the whole row is the box's label,
                    so `single` picks the node and the multi modes tick it.
                    Nothing is held back: there is no double click to leave
                    room for, so the tick lands with the click.
        the arrow   walk into that row (`->` to the right of the text, on
                    hover -- see `_NavigationGroup`).  Only a folder draws
                    one; every arrow sits at the same x, past the longest
                    folder name, so the pointer can aim without re-reading
                    -- and the icon plus 30px of slack to its right is the
                    same target, the far right of the row being the row's.

    `..` leads the listing as the way back up.  Its box is frozen -- dimmed
    and never tickable -- because it is a target rather than a node
    (`_is_nav_up`), and that is what frees its own click for the gesture: one
    click anywhere on the row walks up, so it draws no arrow of its own.

    Walking back up marks where the panel came from: leaving `a/b/c` for
    `a/b` -- through `..`, or by picking a rung on the ladder -- leaves `c/`'s
    row highlighted, so the place just left stands out.  The index is
    remembered per node as folders are listed (`_TreeNav.node_index`) and
    resolved back to a row by `_focus_index`, since the client's own click
    highlight is wiped whenever the rows are rebuilt.

    `selection_mode` settles how much may be picked at once (see `value`);
    only a set that includes `'multicross'` draws the bucket, and only a set
    holding more than one draws the segmented control that switches between
    them.

    Args:
        start_directory: the folder to open (default: the cwd).
        label: the widget label, drawn above the panel the way an input's
            label is (same markup / metrics as `TextInput.label`).
        label_visibility: `'auto'` (the default: the label row follows the
            label, so an empty one costs no height) | `'visible'` | `'hidden'`
            | `'collapsed'`. See `inputs.T.LabelVisibility`.
        help: optional markdown tooltip shown next to the label.
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        height: optional cap in px on the listing, after which it scrolls.
            Left `None` when an enclosing `Popover` does the scrolling.
        width: see `Column`.
        selection_mode: `'single'` (one node, the default), `'multiple'`
            (nodes of the folder being browsed -- leaving it drops them), or
            `'multicross'` (nodes gathered across folders into a bucket). A
            tuple of them -- e.g. `('single', 'multicross')` -- offers a
            segmented control over exactly those, starting with the first;
            the sequence is respected whichever way you order it.
        initial_mode: which of `selection_mode` to open in (default: its
            first entry). A mode the tuple no longer offers falls back to
            that first entry, so a remembered mode can be handed straight
            back (see `mode`).
        _vendored: whether the panel is delivered inside a wrapper's frame,
            which also floats the Confirm button into the corner (see the
            Layout note above).  Only `TreeSelectWithInput` passes `True`.
        border: whether the panel draws its own frame.  Left `None` it is
            `not _vendored`, so a standalone panel is framed by default.
        show_confirm_button: whether the Confirm button is shown (default
            `True`). With `False` the button is hidden rather than skipped:
            the bottom bar it lives in stays built, which is what a caller
            hangs its own actions off (see `Widgets`).

    Properties:
        value: str | list[str] — the selection. `single` keeps one path (`''`
            while nothing is picked); the multi modes keep a list of paths --
            `multiple` holds the folder being browsed, `multicross` holds the
            whole bucket. Prefer `select` / `clear` over writing it: those
            keep the listing in step.
        mode: str — the active mode (never `'any'`).
        directory: str — the folder the listing shows (read-only; an
            absolute, forward-slash path). Left alone it is
            `start_directory`; the panel's own walking and a wrapper's jump
            move it. Read it to remember where the user was.

    Signals:
        on_value (via `tree['on_value']` or `tree.value.on_change`)
        on_navigate: emitted with the new folder every time the listing is
            refreshed -- walking into a row (its arrow, or `..`'s own click),
            a `_goto` from a wrapper, or the initial build. Anything derived
            from the current folder (a path input's candidate list, say)
            should be refreshed from here.
        on_submit: emitted when the Confirm button is clicked, carrying the
            resolved absolute paths (see `resolve`);
            a pick another pick already covers is dropped, so a ticked folder
            stands in for everything under it. A wrapper such as
            `TreeSelectWithInput` listens for it to dismiss the popover it
            opened.

    Call `reload()` to re-read the folder from disk, `select(path)` to add a
    path that is not in the listing, `clear()` to drop the selection, and
    `resolve()` for the paths the Confirm button reports.

    Widgets:
        The sub-components worth reaching into, for a caller that wants to
        extend the panel rather than just read it:

            'bottom_bar': the `Row` under the listing that holds the Confirm
                button. Entering it appends siblings to that very row, after
                the button -- a panel's own extra actions, say:

                    with tree.widgets['bottom_bar']:
                        v3.Button('Open input folder')

                It is always built, so it can be entered even when the
                Confirm button is hidden.  A vendored panel wraps the row in
                a `FloatingContainer` (that is what floats it to the corner);
                the row is the same either way.  It is built
                `hide_when_empty`, so a panel whose bar nobody fills in does
                not carry an empty line at its foot.
            'confirm_button': the button itself, built even when hidden, so a
                caller can still reach it (`on_click`, `label`, `visible`).

    Drag-and-drop is deliberately absent: a browser hands a page the dropped
    *entries* -- names, and their contents -- never the path they came from
    (`File.name` has none, `file.path` is Electron-only, and
    `webkitGetAsEntry().fullPath` / `webkitRelativePath` are virtual
    respectively relative).  With no path there is nothing to hand
    `PathInput`, and a bare name belongs to the *client*: over a LAN it
    names a folder the server cannot reach.  A dead end by design, not an
    oversight.
    """

    def __init__(
        self,
        label: str | Property = '',
        start_directory: str = '',
        *,
        accept_new_option: bool = False,
        border: bool | None = None,
        filter: T.Filter = None,
        height: int | None = None,
        help: str | Property = '',
        initial_mode: tp.Optional[str] = None,
        label_visibility: str = 'auto',
        selection_mode: tp.Union[
            T.SelectionMode, tp.Tuple[T.SelectionMode, ...]
        ] = _MODE_SINGLE,
        show_confirm_button: bool = True,
        width: Width | None = None,
        _vendored: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        if border is None:
            # a standalone panel frames itself; one delivered inside a
            # wrapper's frame (a popover) would only nest a second frame
            border = not _vendored
        super().__init__(
            label,
            label_visibility=label_visibility,
            help=help,
            width=width,
            border=border,
            **kwargs,
        )
        self._vendored = _vendored

        selection_mode = _check_selection_mode(selection_mode)
        initial_mode = _check_initial_mode(initial_mode, selection_mode)
        keeps = _filter_func(filter)
        nav = _TreeNav(start_directory)
        self._nav = nav
        self._keeps = keeps
        self._selection_mode = selection_mode
        # guards every pick handler while the listing is rebuilt: re-listing
        # swaps `options`, which resets `focused_index` and makes a radio fall
        # back to another row
        self._syncing = False
        # the folder the panel was in before the current one: coming back up
        # highlights the row that leads there (see `_focus_index`)
        self._came_from = ''
        # a row the next listing should point at instead, for a wrapper's
        # jump that has somewhere definite in mind (`_goto`)
        self._point_at: tp.Union[str, int] = ''

        self.value = Property(
            tp.cast(tp.Union[str, tp.List[str]], _empty_value(initial_mode))
        )
        self.mode = Property(initial_mode)
        self.on_navigate: Signal = Signal(str)
        self.on_submit: Signal = Signal(tp.Iterable[str])

        # only the modes that can cross folders get a bucket, and only a
        # `selection_mode` offering more than one gets the control that
        # switches between them -- so a plain `single` builds neither
        crosses = _MODE_MULTICROSS in selection_mode
        switchable = len(selection_mode) > 1

        with self:
            # The toolbar is a row across the panel's top. The location
            # selectbox leads: it lists every ancestor of the folder on show,
            # itself last, so the ladder doubles as "you are here" and any
            # parent is one pick away. It is the only child that stretches, so
            # the row needs no `Space`. Its `accept_new_option` row is for the
            # place the ladder cannot offer -- a path typed in from outside --
            # and takes the panel *there* rather than growing a rung.
            with Row('center'):
                self._location = Selectbox(
                    'Current location',
                    options=_location_options(nav.directory),
                    format=_path_label,
                    value=nav.directory,
                    accept_new_option=accept_new_option,
                    take_new_option=(
                        self._take_typed_path if accept_new_option else None
                    ),
                    label_visibility='collapsed',
                )
                self._home_btn = IconButton(
                    'home', help='Go to the starting directory'
                )
                self._refresh_btn = IconButton('refresh')
                if crosses:
                    # The bucket holds the cross-folder haul. It rides in a
                    # `Popover` (a `MenuButton` is an options widget, not a
                    # container); panels are `position: fixed`, so this one
                    # floats above the enclosing panel instead of being
                    # clipped by it. Its trigger is inert while it is empty.
                    self._bucket_popover = Popover(
                        bind(self.value, _bucket_text),
                        visible=bind(self.mode, _is_multicross),
                        enabled=bind(self.value, bool),
                        panel_max_height=240,
                    )
                    with self._bucket_popover:
                        # `options` is bound to `value`, so a tick (or the `x`
                        # below) redraws this list by itself.
                        self._bucket_group = ReducibleGroup(
                            options=bind(self.value, _as_picked),
                            format=lambda path: bucket_label(
                                path, nav.start_directory
                            ),
                        )
                if switchable:
                    self._mode_control = Selectbox(
                        'Selection mode',
                        options=selection_mode,
                        index=selection_mode.index(initial_mode),
                        format=lambda m: _MODE_LABELS[m],
                        label_visibility='collapsed',
                        width='content',
                    )
            # The two lists differ only in how many nodes they may pick. Both
            # freeze `..` and route its body click to the walk-up (`_is_nav_up`
            # is both predicates), and both float the "enter" arrow on their
            # folders (`_is_enterable`) -- the arrow is what moves the panel
            # for a node row, so a row's own click is free to just tick it.
            with Column(visible=bind(self.mode, _is_single)):
                self._single_list = _NavRadioGroup(
                    'Folder contents',
                    options=(),
                    format=entry_label,
                    label_visibility='collapsed',
                    max_height=height,
                    box_disabled=_is_nav_up,
                    navigable=_is_enterable,
                    body_opens=_is_nav_up,
                )
            with Column(visible=bind(self.mode, _is_multi)):
                self._multi_list = _NavCheckGroup(
                    'Folder contents',
                    options=(),
                    format=entry_label,
                    label_visibility='collapsed',
                    max_height=height,
                    box_disabled=_is_nav_up,
                    navigable=_is_enterable,
                    body_opens=_is_nav_up,
                )
            # The bottom bar is where the panel's "done" action lives: a
            # wrapper hooks `on_submit` to fold the popover away (the panel
            # itself must not know about its parent). A vendored panel floats
            # the bar into the corner, where it stays put while the listing
            # scrolls; a standalone one keeps it under the listing, in the
            # ordinary flow. Either way it is built, and always *around a
            # `Row`*, so `widgets['bottom_bar']` is somewhere to add siblings
            # -- including when the Confirm button is hidden. That row bows
            # out while it has nothing to show, so a panel nobody extends
            # does not pay for it with a gap it cannot use.
            if _vendored:
                # a floating cluster is a `Column` (it may not sit inside a
                # `Row`) and lays its children out in a row of its own, so the
                # bar rides inside it rather than being it.
                with FloatingContainer('bottom-right'):
                    bottom_bar = Row('center', hide_when_empty=True)
            else:
                bottom_bar = Row('center', hide_when_empty=True)
            with bottom_bar:
                self._confirm_btn = Button(
                    'Confirm',
                    # 'content' in a floating cluster (which hugs it), full
                    # width under the listing, as before
                    width=None if _vendored else 'stretch',
                    visible=show_confirm_button,
                )
            self.widgets: tp.Dict[str, Component] = {
                'bottom_bar': bottom_bar,
                'confirm_button': self._confirm_btn,
            }

        # -- handlers -------------------------------------------------------

        @self._single_list.value.on_change
        def _on_single_pick() -> None:
            if self._syncing:
                return
            option = str(self._single_list.value.get())
            if not option or option == NAV_UP:
                # `..` is frozen, so its box cannot be ticked; the walk-up is
                # its row's own click (`_on_single_open`)
                return
            self.value.set(option_path(self._nav, option))

        @self._multi_list.value.on_change
        def _on_multi_toggle() -> None:
            if self._syncing:
                return
            # drop this folder's previous picks, then add the ticked ones, so
            # picks made in other folders survive -- that is what makes
            # `multicross` a cross-folder gathering
            listed = self._listed_paths()
            kept = [p for p in _as_picked(self.value.get()) if p not in listed]
            self.value.set(kept + self._ticked_paths())

        @self._single_list.on_open
        def _on_single_open(index: int) -> None:
            self._open_row(self._single_list, index)

        @self._multi_list.on_open
        def _on_multi_open(index: int) -> None:
            self._open_row(self._multi_list, index)

        @self._location.value.on_change
        def _on_location_picked() -> None:
            # the ladder only ever holds folders, so a pick is a jump
            if self._syncing:
                return
            directory = str(self._location.value.get())
            if directory and directory != self._nav.directory:
                self._jump(directory)

        @self._home_btn.on_click
        def _on_home() -> None:
            self._jump(self._nav.start_directory)

        @self._refresh_btn.on_click
        def _on_refresh() -> None:
            self.reload()

        if show_confirm_button:

            @self._confirm_btn.on_click
            def _on_confirm() -> None:
                self.on_submit.emit(self.resolve())

        if crosses:

            @self._bucket_group.on_reduce
            def _on_bucket_reduced(path: str) -> None:
                self.value.set(
                    [p for p in _as_picked(self.value.get()) if p != path]
                )
                self._refresh_listing()

        if switchable:

            @self._mode_control.value.on_change
            def _on_mode_changed() -> None:
                self._set_mode(str(self._mode_control.value.get()))

        self._refresh_listing()

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Drop the selection (`''` in `single` mode, `[]` in the others)."""
        self.value.set(_empty_value(self.mode.get()))
        self._refresh_listing()

    @property
    def directory(self) -> str:
        """The folder the listing shows (see `Properties`).

        Read-only: the panel's own walking, and a wrapper's jump, are what
        move it -- writing it behind their back would leave the listing,
        the location bar and the mode control out of step.
        """
        return self._nav.directory

    def open_path(self, path: str) -> None:
        """Land on what `path` names.

        A folder moves the panel into it. A file moves it to the folder that
        holds the file and marks the file's own row, so a path from outside
        lands on the thing it names -- and a kept file joins the selection
        too, the way a typed-in path always has. A file the listing will not
        show has no row to mark, so its folder's listing starts at the top
        and the file is not picked.

        Text that resolves to nothing -- half-typed, or simply not there --
        clears the pick rather than raising.
        """
        text = fs.abspath(path.strip())
        if not text or not fs.exist(text):
            self.clear()
            return
        if fs.isdir(text):
            self._goto(text)
            return
        directory = fs.parent(text)
        keeps = bool(self._keeps(fs.basename(text)))
        if keeps:
            self.select(text)
        # the pick re-lists on its own, so it goes first and this jump has
        # the last word on which row is marked
        self._goto(directory, point_at=text if keeps else 0)

    def reload(self) -> None:
        """Re-read the current folder from disk and refresh the listing."""
        self._nav.reload()
        self._refresh_listing()

    def resolve(self) -> tp.Tuple[str, ...]:
        """The selection as absolute paths, for the Confirm button to report.

        A ticked folder stands for everything under it, so a pick that
        another pick already covers is dropped: the raw picks `['a/b',
        'a/b/c', 'a/b/d.txt', 'a/e']` resolve to `('a/b', 'a/e')`. The panel's
        own pick order is kept, so "the first pick" stays the first one the
        user made.
        """
        picked = _as_picked(self.value.get())
        return tuple(
            path
            for path in picked
            if not any(_is_under(path, other) for other in picked)
        )

    def select(self, path: str) -> None:
        """Add `path` to the selection.

        `single` replaces the value; the multi modes append it, which is how a
        path typed into a wrapper's input joins the picks (or the bucket) even
        though it is not part of the current listing.
        """
        if self.mode.get() == _MODE_SINGLE:
            self.value.set(path)
        else:
            picked = _as_picked(self.value.get())
            if path not in picked:
                picked.append(path)
                self.value.set(picked)
        self._refresh_listing()

    # -- internals ----------------------------------------------------------

    def _carried_row(self, options: list) -> str:
        """The listing row the current pick sits on.

        `single` picks exactly one node, so that node's own row is what the
        radio should mark.  Left blank in the multi modes, where the boxes
        already carry the selection.
        """
        current = self.value.get()
        if not current or self.mode.get() != _MODE_SINGLE:
            return ''
        for option in options:
            if option != NAV_UP and option_path(self._nav, option) == current:
                return str(option)
        return ''

    def _goto(self, directory: str, point_at: tp.Union[str, int] = '') -> None:
        """Point the panel at a folder and re-list it (used by the wrappers).

        `point_at` says which row of the new listing should carry the
        highlight, for a jump that knows where it is going: a path that is one
        of its rows, or leads to one, or a row number when nothing more
        specific can be said. Left out, the listing starts unmarked -- a
        wrapper's jump is not a walk of the panel's own, so it has nothing to
        point back at.
        """
        directory = fs.abspath(directory) if directory else ''
        if directory and fs.isdir(directory):
            self._nav.directory = directory
        self._came_from = ''
        self._point_at = point_at
        self._refresh_listing()

    def _jump(self, directory: str) -> None:
        """Move the panel into `directory` and re-list it.

        `multiple` drops its picks on the way out -- they belong to the folder
        being left. `multicross` keeps the bucket, which is the whole point of
        crossing folders, and `single` keeps the picked path.

        The folder being left is remembered on the way out, so the new listing
        can mark the row that leads back to it (see `_focus_index`).
        """
        self._came_from = self._nav.directory
        self._point_at = ''
        if self.mode.get() == _MODE_MULTIPLE:
            self.value.set([])
        self._nav.directory = directory
        self._refresh_listing()

    def _take_typed_path(self, text: str) -> None:
        """The location bar's new-option row: go where the text says.

        The ladder already offers every place the panel knows, so this row
        exists for the one it does not -- a path typed in from outside -- and
        `open_path` is what becomes of it (see `Selectbox(take_new_option=)`).
        """
        self.open_path(text)

    def _listed_paths(self) -> set:
        """The absolute paths of every node the listing currently shows."""
        nav = self._nav
        options = self._multi_list.options.get() or ()
        return {p for p in (option_path(nav, o) for o in options) if p}

    def _open_row(self, group: RadioGroup | CheckGroup, index: tp.Any) -> None:
        """Walk into the place a row stands for.

        Two gestures land here and both send the same `open` event: the
        "enter" arrow of a folder row, and the row click of a `body_opens` row
        (`..`, which has no arrow). A file reaches neither -- `_is_enterable`
        gives it no arrow, and it has nowhere to go.
        """
        if self._syncing:
            return
        options = list(group.options.get() or ())
        if not (isinstance(index, int) and 0 <= index < len(options)):
            return
        option = str(options[index])
        if option == NAV_UP:
            self._jump(self._nav.parent_of())
        elif option.endswith('/'):
            self._jump(self._nav.child(option[:-1]))

    def _refresh_listing(self) -> None:
        nav = self._nav
        options = listing_options(nav, self._keeps)
        picked = set(_as_picked(self.value.get()))
        # Remember where each node sits in its parent's listing, so walking
        # back up can point at the row it came from (`_focus_index`) even
        # though the client's own highlight is gone by then.
        for position, option in enumerate(options):
            path = option_path(nav, option)
            if path:
                nav.node_index[path] = position
        focus = self._focus_index(options)
        self._syncing = True
        try:
            self._single_list._focus_index = focus
            self._multi_list._focus_index = focus
            # `notify=True`: the rows are rebuilt out of this patch, so the
            # highlight travelling with them has to reach the client even when
            # the options themselves are the ones it already had
            self._single_list.options.set(options, notify=True)
            self._multi_list.options.set(options, notify=True)
            # the radio *is* the pick in `single` mode, so it shows what the
            # panel carries (see `_carried_row`)
            self._single_list.value.set(self._carried_row(options))
            # the check group re-ticks what was picked before, so walking back
            # into a folder shows its ticks again
            self._multi_list.value.set(
                [o for o in options if option_path(nav, o) in picked]
            )
            # the ladder is the panel's location bar: the current folder is
            # the last rung, so a fresh listing reads as "you are here".
            # `value` goes in before `options` so `_auto_select` finds it
            # already present and does not fall back to the drive root.
            self._location.value.set(nav.directory)
            self._location.options.set(_location_options(nav.directory))
        finally:
            self._syncing = False
        self.on_navigate.emit(nav.directory)

    def _focus_index(self, options: list) -> int:
        """The row to draw highlighted: the one leading back where we came from.

        Leaving `a/b/c` for `a/b` (the `..` row, or the ladder) leaves `c/`
        marked, so it is obvious which place was just left.  A jump further
        than one level -- a distant rung of the ladder, or `home` -- cannot
        mark the place itself, since it is not a row of the new listing; the
        row on the way to it is marked instead, which is the path back.

        A wrapper's jump brings a row of its own to mark (`_goto`): a path
        that is one of these rows, or leads to one.  A *number* is taken as
        the row itself, which is the best a jump can say when the path it has
        is not in the listing at all -- a file the filter drops.

        Where a node sat is remembered per node (`_TreeNav.node_index`), but
        the index is re-checked against the fresh listing -- the folder may
        have gained or lost a row since that reading -- and a row found by
        path is used when it no longer lines up.
        """
        target, self._point_at = self._point_at, ''
        if isinstance(target, int):
            return target if 0 <= target < len(options) else -1
        origin = target or self._came_from
        if not origin:
            return -1
        nav = self._nav
        index = nav.node_index.get(origin, -1)
        if 0 <= index < len(options):
            if option_path(nav, options[index]) == origin:
                return index
        for position, option in enumerate(options):
            if option == NAV_UP:
                continue
            path = option_path(nav, option)
            if path and (origin == path or _is_under(origin, path)):
                return position
        return -1

    def _set_mode(self, mode: str) -> None:
        """Switch the active mode -- only to one `selection_mode` offers."""
        if mode not in self._selection_mode or mode == self.mode.get():
            return
        # the selection means something different per mode, so start clean
        self.mode.set(mode)
        self.value.set(_empty_value(mode))
        self._refresh_listing()

    def _ticked_paths(self) -> list:
        """The absolute paths of the ticked rows, in listing order."""
        nav = self._nav
        ticked = self._multi_list.value.get() or ()
        return [p for p in (option_path(nav, o) for o in ticked) if p]


class TreeSelectWithInput(Column):
    """A path input plus the single-pane browser in a "Browse" popover.

        sel = v3.TreeSelectWithInput(
            'Batch file', 'references/.../classic.txt', filter='.txt'
        )
        ...
        path = sel.value.get()

    Layout::

        [ path input .................... ] [ Recent ] [ Browse v ]
        +-- "Browse" popover (spans the header row) ------------------+
        | [ /current/folder v ] [refresh] [bucket] [mode] <- toolbar  |
        | ..        (goto parent)                                     |
        | subfolder/                                                  |
        | another-file.txt              <- scrolls past `height` px   |
        |                              [ Confirm ]   <- floats bottom |
        +-------------------------------------------------------------+

    The panel is a `TreeSelect`; the popover stretches it from the path
    input's left edge to the header row's right edge.  A single click on a row
    ticks / picks it, and the folder rows float an "enter" arrow to walk into
    them (a click on `..` itself walks up; see `TreeSelect`).  The panel
    carries its own toolbar (the location
    selectbox plus refresh, and the bucket and the mode control when
    `selection_mode` calls for them) across its top, with its Confirm
    button in the bottom-right corner, so the Confirm stays reachable while
    the listing scrolls.  Confirm folds this popover away (through
    `TreeSelect.on_submit`).

    The path input is a plain text box: the ancestor ladder rides on the
    panel's location selectbox (see `TreeSelect`), which follows the browsed
    folder by itself -- so there is nothing here to keep in step.

    Typing, pasting (or picking) a folder points the panel there.  A file
    takes the panel to the folder holding it, with its own row marked, and
    joins the panel's selection.  A file the filter drops has no row to mark,
    so the listing simply starts at its top.  The selection survives browsing
    -- `clear()` drops it.

    The path box takes a pasted path from outside as readily as a picked one:
    it offers the text as it stands in its panel (`accept_new_option`), and
    Enter submits it.

    Args:
        label: the path input's label.
        start_directory: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        height: max height of the "Browse" panel in px (default 500).
        width: see `Column`.
        initial_mode: which of `selection_mode` to open in -- see `TreeSelect`.
        selection_mode: how the panel lets nodes be picked -- see `TreeSelect`.

    Properties:
        value: str | list[str] — the panel's selection; this mirrors
            `TreeSelect.value`, so `'single'` holds one path and the multi
            modes hold a list. Write through the panel (`select` / `clear`).
        mode: str — the panel's active mode (mirrors `TreeSelect.mode`).
        directory: str — the folder the panel shows (mirrors
            `TreeSelect.directory`).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
    """

    def __init__(
        self,
        label: str = '',
        start_directory: str = '',
        *,
        filter: T.Filter = None,
        show_recent: bool = False,
        height: int = 500,
        width: Width | None = None,
        initial_mode: tp.Optional[str] = None,
        selection_mode: tp.Union[
            T.SelectionMode, tp.Tuple[T.SelectionMode, ...]
        ] = _MODE_SINGLE,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        first_path = start_directory or os.getcwd()
        initial_is_file = bool(start_directory) and fs.isfile(first_path)
        nav = _TreeNav(fs.parent(first_path) if initial_is_file else first_path)
        self._nav = nav
        self._keeps = _filter_func(filter)
        self._show_recent = show_recent

        # `value` / `mode` mirror the panel's, so a caller reads the selection
        # right here; writes go through the panel (`select` / `clear`).
        self.value = Property(tp.cast(tp.Union[str, tp.List[str]], ''))
        self.mode = Property(_MODE_SINGLE)
        self._has_recent = Property(False)
        # set while `_refresh_recent` adopts the newest path into the dropdown:
        # that is a display update, not a pick, so `_commit` must not run
        self._recent_quiet = False

        with self:
            with Row('bottom'):
                self._path_input = PathInput(
                    label, first_path, accept_new_option=True
                )
                self._recent = Recent(
                    'Recent', visible=self._has_recent, max_height=280
                )
                self._browse_popover = Popover(
                    'Browse', panel_align='row', panel_max_height=height
                )
                with self._browse_popover:
                    self._tree = TreeSelect(
                        nav.directory,
                        filter=filter,
                        height=None,
                        initial_mode=initial_mode,
                        selection_mode=selection_mode,
                        # the path box takes a pasted path as readily as a
                        # picked one, so the panel's own ladder does too
                        accept_new_option=True,
                        # this panel rides inside our `Browse` popover, which
                        # already draws the frame: float the Confirm button
                        # into the corner and skip the panel's own border
                        _vendored=True,
                        border=False,
                    )
        self.value.bind(self._tree.value)
        self.mode.bind(self._tree.mode)

        if initial_is_file:
            self._tree.select(fs.abspath(first_path))
            nav.remember(fs.abspath(first_path))

        # -- handlers -------------------------------------------------------

        @self._path_input.value.on_change
        def _on_path_typed() -> None:
            self._commit(self._path_input.value.get())

        @self._recent.value.on_change
        def _on_recent_picked() -> None:
            if self._recent_quiet:
                return
            self._commit(str(self._recent['value']))

        @self._tree.value.on_change
        def _on_panel_picked() -> None:
            # the panel's picks feed "Recent" (a tick is a pick too)
            for path in _as_picked(self._tree.value.get()):
                self._nav.remember(path)
            self._refresh_recent()

        @self._tree.on_submit
        def _on_tree_submitted(_paths: tp.Iterable[str]) -> None:
            # the panel's Confirm is a "done" action: fold the popover away
            # (the panel has no idea it lives in one; we own it, so we close
            # it). The pick itself already sits in `_tree.value`, which
            # `value` mirrors. The resolved paths stay on the panel
            # (`_tree.resolve()`), so a caller that needs them reads them
            # there rather than through this wrapper.
            self._browse_popover.close()

        self._refresh_recent()

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Drop the panel's selection (see `TreeSelect.clear`)."""
        self._tree.clear()

    @property
    def directory(self) -> str:
        """The folder the panel shows (see `TreeSelect.directory`)."""
        return self._tree.directory

    def reload(self) -> None:
        """Re-read the browsed folder from disk (same as the panel's button)."""
        self._tree.reload()

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        """Show a typed / pasted / picked path, and move the panel onto it.

        The moving is the panel's own (`TreeSelect.open_path`); what belongs
        to this wrapper is the box the caller sees and the "Recent" list. A
        kept file is remembered as a pick, which is what fills that list.
        """
        text = path.strip()
        if not text or not fs.exist(fs.abspath(text)):
            # A half-typed path is not an error, just not a value yet.
            self._tree.clear()
            return
        full = fs.abspath(text)
        self._set_box(full if fs.isdir(full) else fs.parent(full))
        if not fs.isdir(full) and self._keeps(fs.basename(full)):
            self._nav.remember(full)
            self._refresh_recent()
        # last, because it has the last word on which row is marked
        self._tree.open_path(full)

    def _set_box(self, path: str) -> None:
        """Show a resolved path in the path box."""
        self._path_input.show(path)

    def _refresh_recent(self) -> None:
        recent = list(self._nav.recent)
        self._has_recent.set(bool(recent) and self._show_recent)
        self._recent.options.set(recent)
        if recent and self._recent['value'] not in recent:
            # show the newest entry without *picking* it: `_on_recent_picked`
            # runs `_commit`, which navigates for a folder -- and displaying a
            # path in the dropdown is not a pick
            self._recent_quiet = True
            try:
                self._recent.value.set(recent[0])
            finally:
                self._recent_quiet = False
