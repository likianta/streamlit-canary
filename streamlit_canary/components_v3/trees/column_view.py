"""The column browser: a Finder-style stack of folders, one level per column.

`ColumnView` borrows macOS Finder's column view. The leftmost column lists
the folder the panel opened on; a click on a folder there opens its contents
in a new column to the right, and a click on a file simply marks it.
Walking back in is a click on any folder in a column further left -- that
column's contents replace everything to its right -- so the whole trail
stays on show at once and the panel needs no "go up" row of its own.

    [ /current/folder v ] [home] [refresh]        <- toolbar
    +---------+ +---------+ +---------+
    | alpha/  | | one.py  | | a.txt   |
    | beta/   | | two.py  | | b.txt   |
    +---------+ +---------+ +---------+

`value` is single-select, like the flat panel's: it names the node picked in
the rightmost column, or -- while nothing inside that column is picked -- the
folder the column is showing. A column view always has a current folder, so
`value` is never empty.

At most `max_columns` columns are on show; walking deeper than that scrolls
the earlier ones out of the strip, so the mounted groups stay a fixed set
(a component cannot be born after the tree is built). The window is the
*last* `max_columns` folders of the trail, which keeps the column the user
just opened in view; the toolbar's location ladder and `home` reach any
ancestor in a single pick, so nothing becomes unreachable.

The panel itself carries no path input -- see `path_inputs_ex.py` for the
`PathInput` + panel pairings, and `path_inputs_ex`'s `_make_panel`, which
dresses this one for its host exactly like the other three browsers.
"""

import typing as tp

from lk_utils import fs

from ._shared import T
from ._shared import _TreeNav
from ._shared import _filter_func
from ._shared import _location_options
from ._shared import _path_label
from ._shared import entry_label
from .._shared import _Labeled
from ..base import Width
from ..buttons import Button
from ..buttons import IconButton
from ..inputs import RadioGroup
from ..inputs import Selectbox
from ..layouts import Container
from ..layouts import FloatingContainer
from ..layouts import Row
from ...kernel import Property
from ...kernel import Signal


_COLUMN_WIDTH = 190
"""How wide one column is, in px. Narrow enough that several fit side by
side while a folder name still reads; a wider one just scrolls the strip."""

_MODE_SINGLE = 'single'


def _child_path(directory: str, option: tp.Any) -> str:
    """The absolute path a row of `directory` stands for.

    Rows are bare names relative to the column's own folder (folders carry a
    trailing `'/'` -- see `listing_options`), so this is just the join that
    `_TreeNav.child` would do for the folder on show. It is written out here
    because every column has a folder of its own, not the panel's one.
    """
    name = str(option)
    bare = name[:-1] if name.endswith('/') else name
    return '{}/{}'.format(directory.rstrip('/'), bare)


class _ColumnStrip(Row):
    """The strip the columns sit in -- a `Row` marked for its own CSS.

    `Row` gives it the flex layout; the marker class is what lets
    `60-misc.css` turn that row into a horizontal scroller of fixed-width
    columns (`flex-wrap: nowrap`, `overflow-x: auto`) without touching any
    other row on the page. The renderer reads `_css_class` for that.
    """

    _css_class = ' st-columnview'


class ColumnView(_Labeled, Container):
    """The column browser: a folder listing that opens one column per level.

        with v3.ColumnView('Pick a file', 'data/sample') as tree:
            ...
            path = tree.value.get()

    Args:
        start_directory: the folder the first column opens on (default: the
            cwd).
        label: the widget label, drawn above the panel the way an input's
            label is.
        label_visibility: `'auto'` (the default) | `'visible'` | `'hidden'`
            | `'collapsed'`. See `inputs.T.LabelVisibility`.
        help: optional markdown tooltip shown next to the label.
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep -- files
            the filter drops are not listed; folders are always shown.
        height: the height of every column in px, after which a column
            scrolls on its own (default 500).
        max_columns: how many columns are on show at once (default 4); a
            deeper trail is windowed to its last `max_columns` folders.
        home_directory: where the `home` button goes back to; left out it is
            `start_directory`.
        show_location: whether the toolbar leads with the location ladder
            (`_location_options`). Left `None` it follows `leading`: a caller
            that leads the row with a widget of its own (a `PathSelect`,
            which carries the same ladder) needs no second one.
        accept_new_option: whether the location bar also offers a typed-in
            path (its "Add" row), which jumps the panel there -- mirrors
            `SingleTreeSelect.accept_new_option`.
        leading: a builder run at the head of the toolbar row, so a wrapper
            can put its own path box in front of `home` (see
            `path_inputs_ex.py`).
        trailing: a builder run at the tail of the toolbar row (the
            expander's fold button).
        rows_visible: whether the strip of columns is drawn (bindable); a
            wrapper that folds the panel gates it with this while the
            toolbar row stays put.
        show_confirm_button: whether the Confirm button is shown.
        width: see `Container`.

    Properties:
        value: str -- the selection. The node picked in the rightmost
            column, or that column's folder while nothing inside it is
            picked. Never empty (a column view always has a current folder).
            Prefer `select` / `clear` over writing it.
        mode: str -- always `'single'`; kept so a wrapper can mirror it the
            way it mirrors the sibling panels'.
        directory: str -- the folder the rightmost column shows (read-only).

    Signals:
        on_navigate: emitted with the current folder every time the columns
            are redrawn (a click, a `_jump`, the initial build). A wrapper's
            path box refreshes its own ladder from here.
        on_submit: emitted when Confirm is clicked, carrying `resolve()`.

    Call `reload()` to re-read the folders from disk, `select(path)` to set
    the selection (moving the panel onto the path's folder), `clear()` to go
    back to the starting folder, and `resolve()` for the paths Confirm
    reports.
    """

    def __init__(
        self,
        label: str | Property = '',
        start_directory: str = '',
        *,
        accept_new_option: bool = False,
        border: bool | None = None,
        filter: T.Filter = None,
        height: int = 500,
        help: str | Property = '',
        home_directory: str = '',
        label_visibility: str = 'auto',
        leading: tp.Optional[tp.Callable[[], None]] = None,
        max_columns: int = 4,
        rows_visible: tp.Union[bool, Property] = True,
        show_confirm_button: bool = True,
        show_location: tp.Optional[bool] = None,
        trailing: tp.Optional[tp.Callable[[], None]] = None,
        width: Width | None = None,
        _vendored: bool = False,
        **kwargs: tp.Any,
    ) -> None:
        if border is None:
            # a standalone panel frames itself; one delivered inside a
            # wrapper's frame (a popover) would only nest a second frame
            border = not _vendored
        if show_location is None:
            # a caller leading the row with a widget of its own has no use for
            # the ladder -- that widget *is* the way in (see `_make_panel`)
            show_location = leading is None
        super().__init__(
            label,
            label_visibility=label_visibility,
            help=help,
            width=width,
            border=border,
            **kwargs,
        )
        self._vendored = _vendored
        nav = _TreeNav(start_directory)
        self._nav = nav
        self._keeps = _filter_func(filter)
        # the trail of folders, outermost first; the last one is the folder
        # the panel is "in", and the one the toolbar and `directory` report
        self._dirs: tp.List[str] = [nav.directory]
        # the node picked in the rightmost column -- a file, or a folder
        # named from outside; `''` while only a folder is on show
        self._pick = ''
        self._start = nav.start_directory
        self._home_dir = (
            fs.abspath(home_directory)
            if home_directory
            else nav.start_directory
        )
        self._max_columns = max(1, int(max_columns))
        # guards the pick handlers while the columns are rebuilt: re-listing
        # swaps `options`, which makes a radio fall back to another row
        self._syncing = False
        self._location: tp.Optional[Selectbox] = None

        self.value = Property('')
        # a constant, so a wrapper that mirrors `mode` (see `_PathInputTree`)
        # has something to bind to; the column view is single-select only
        self.mode = Property(_MODE_SINGLE)
        # whether the strip shows at all; a wrapper that folds the panel
        # (an expander-like path input) gates the columns with it while the
        # toolbar row stays put
        self.rows_visible = Property(True)
        self.rows_visible.set_or_bind(rows_visible)
        self.on_navigate: Signal = Signal(str)
        self.on_submit: Signal = Signal(tp.Iterable[str])

        with self:
            # The toolbar is a row across the panel's top: the location
            # selectbox leads -- listing every ancestor of the folder on show,
            # so the ladder doubles as "you are here" and any parent (or drive)
            # is one pick away -- and then the actions.
            with Row('center'):
                if leading is not None:
                    leading()
                if show_location:
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
                        truncate_start=True,
                    )
                self._home_btn = IconButton('home')
                self._refresh_btn = IconButton('refresh')
                if trailing is not None:
                    trailing()

            # The columns themselves: a fixed set of groups (a component
            # cannot be born after the tree is built), toggled in and out of
            # view as the trail grows and shrinks. Each is a plain radio list
            # -- a click picks the row, which is the whole gesture here -- kept
            # in a bordered, fixed-width, self-scrolling box.
            self._strip = _ColumnStrip(visible=self.rows_visible)
            with self._strip:
                self._col_boxes: tp.List[Container] = []
                self._col_groups: tp.List[RadioGroup] = []
                for _position in range(self._max_columns):
                    box = Container(
                        border=True,
                        width=_COLUMN_WIDTH,
                        height=height,
                        visible=False,
                    )
                    with box:
                        group = RadioGroup(
                            '',
                            options=(),
                            format=self._entry_label,
                            label_visibility='collapsed',
                        )
                    self._col_boxes.append(box)
                    self._col_groups.append(group)

            # The bottom bar, exactly as the other panels build it: a vendored
            # panel floats it into the corner, a standalone one keeps it under
            # the columns (and, being built around a `Row`, is somewhere a
            # caller can add its own actions).
            if _vendored:
                with FloatingContainer('bottom-right'):
                    bottom_bar = Row('center', hide_when_empty=True)
            else:
                bottom_bar = Row('center', hide_when_empty=True)
            with bottom_bar:
                self._confirm_btn = Button(
                    'Confirm',
                    width=None if _vendored else 'stretch',
                    visible=show_confirm_button,
                )
            self.widgets: tp.Dict[str, tp.Any] = {
                'bottom_bar': bottom_bar,
                'confirm_button': self._confirm_btn,
            }

        # -- handlers -------------------------------------------------------

        for position, group in enumerate(self._col_groups):
            self._wire_column(group, position)

        if self._location is not None:

            @self._location.value.on_change
            def _on_location_picked() -> None:
                if self._syncing:
                    return
                directory = str(self._location.value.get())
                if directory and directory != self._dirs[-1]:
                    self._jump(directory)

        @self._home_btn.on_click
        def _on_home() -> None:
            self._jump(self._home_dir)

        @self._refresh_btn.on_click
        def _on_refresh() -> None:
            self.reload()

        if show_confirm_button:

            @self._confirm_btn.on_click
            def _on_confirm() -> None:
                self.on_submit.emit(self.resolve())

        self._refresh()

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Go back to the starting folder, dropping any pick."""
        self._dirs = [self._start]
        self._pick = ''
        self._refresh()

    @property
    def directory(self) -> str:
        """The folder the rightmost column shows (read-only)."""
        return self._dirs[-1]

    def reload(self) -> None:
        """Re-read every folder on show from disk and redraw."""
        for directory in self._dirs:
            self._nav.reload(directory)
        self._refresh()

    def resolve(self) -> tp.Tuple[str, ...]:
        """The selection as one absolute path, for the Confirm button.

        Single-select, so this is a one-element tuple -- or empty when there
        is somehow nothing to name (there always is a current folder, so a
        wrapper falls back to `directory`'s own habit only as a safeguard).
        """
        value = self.value.get()
        return (str(value),) if value else ()

    def select(self, path: str) -> None:
        """Set the selection to `path`.

        A folder becomes the current column: an ancestor already on show is
        revealed by dropping the columns to its right, and an unrelated one
        (a fresh start) becomes a lone column. A file marks its row in the
        column that holds it, which is reached from the start if it is not
        already on show. A path that is not on disk yet has no folder to
        reach, so it is kept as the pick alone (`value` still reports it).
        """
        path = str(path).strip()
        if not path:
            return
        if fs.isdir(path):
            if path == self._dirs[-1]:
                pass
            elif path in self._dirs:
                last = len(self._dirs) - 1 - self._dirs[::-1].index(path)
                self._dirs = self._dirs[: last + 1]
            else:
                self._dirs = [path]
            self._pick = ''
        else:
            directory = fs.parent(path)
            if (
                directory
                and fs.isdir(directory)
                and (directory != self._dirs[-1])
            ):
                self._dirs = [directory]
            self._pick = path
        self._refresh()

    # -- panel plumbing (what a wrapper's path box drives) ------------------

    def _jump(self, directory: str) -> None:
        """Point the panel at `directory` as a fresh lone column.

        A wrapper's typed path and the location ladder both land here: the
        folder named becomes the whole trail, so the columns above it are
        rebuilt from it rather than guessed at.
        """
        target = fs.abspath(directory) if directory else ''
        if not (target and fs.isdir(target)):
            return
        self._dirs = [target]
        self._pick = ''
        self._refresh()

    def _take_typed_path(self, text: str) -> None:
        """The location bar's new-option row: go where the text says.

        The ladder already offers every place the panel knows, so this row
        exists for the one it does not -- a path typed in from outside. A
        file lands on the folder that holds it and is picked, the way a typed
        path always has.
        """
        path = fs.abspath(str(text).strip()) if text else ''
        if not (path and fs.exist(path)):
            return
        if fs.isdir(path):
            self._jump(path)
        else:
            self._jump(fs.parent(path))
            self.select(path)

    # -- columns ------------------------------------------------------------

    def _entry_label(self, option: tp.Any) -> str:
        """How a row is drawn (the column groups' `format`)."""
        return entry_label(option)

    def _focus_option(
        self, position: int, window: tp.List[str], options: list
    ) -> str:
        """Which row of a column carries the highlight, if any.

        Every column but the rightmost points at the folder it opened (the
        next column along); the rightmost points at the pick. A target that
        is not one of the rows -- the folder the column is already showing,
        say -- leaves the column unmarked.
        """
        if position < len(window) - 1:
            target = window[position + 1]
        else:
            target = self._pick
        if not target:
            return ''
        directory = window[position]
        for option in options:
            if _child_path(directory, option) == target:
                return str(option)
        return ''

    def _listing(self, directory: str) -> list:
        """The rows of one column: its folders, then the files kept."""
        out = [name + '/' for name in self._nav.dirnames(directory)]
        out += [
            name for name in self._nav.filenames(directory) if self._keeps(name)
        ]
        return out

    def _on_column_picked(self, position: int) -> None:
        """React to a row being picked in the column at `position`.

        A folder opens its contents in a new column, dropping whatever stood
        to the right; a file is the selection, and likewise drops the columns
        to the right (there is nothing beyond a file to show).
        """
        window = self._window()
        if not (0 <= position < len(window)):
            return
        option = str(self._col_groups[position].value.get())
        if not option:
            return
        absolute = self._window_start() + position
        path = _child_path(window[position], option)
        if option.endswith('/'):
            self._dirs = self._dirs[: absolute + 1] + [path]
            self._pick = ''
        else:
            self._dirs = self._dirs[: absolute + 1]
            self._pick = path
        self._refresh()

    def _refresh(self) -> None:
        """Redraw every column out of the trail, then mirror it outwards."""
        self._nav.directory = self._dirs[-1]
        window = self._window()
        self._syncing = True
        try:
            for position, group in enumerate(self._col_groups):
                box = self._col_boxes[position]
                if position < len(window):
                    box.visible.set(True)
                    options = self._listing(window[position])
                    # `notify=True`: the rows are rebuilt out of this patch, so
                    # the highlight has to reach the client even when the
                    # options are the ones it already had
                    group.options.set(options, notify=True)
                    group.value.set(
                        self._focus_option(position, window, options)
                    )
                else:
                    box.visible.set(False)
                    group.options.set([])
                    group.value.set('')
            if self._location is not None:
                self._location.value.set(self._dirs[-1])
                self._location.options.set(_location_options(self._dirs[-1]))
        finally:
            self._syncing = False
        self.value.set(self._pick or self._dirs[-1])
        self.on_navigate.emit(self._dirs[-1])

    def _wire_column(self, group: RadioGroup, position: int) -> None:
        @group.value.on_change
        def _on_picked() -> None:
            if self._syncing:
                return
            self._on_column_picked(position)

    def _window(self) -> tp.List[str]:
        """The folders actually on show: the last `max_columns` of the trail."""
        return self._dirs[self._window_start() :]

    def _window_start(self) -> int:
        return max(0, len(self._dirs) - self._max_columns)
