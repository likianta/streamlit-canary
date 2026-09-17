"""Tree-style file selectors (v3).

Two symmetric pairs.  Each one splits a browser *panel* from the "input +
panel" wrapper that drives it:

    TreeSelect / TreeSelectWithInput
        the single-pane browser -- a folder listing with a home / up / enter
        / refresh toolbar -- plus a path input whose "Browse" trigger opens
        the panel in a `Popover`.

    TreeSelectDualPane / TreeSelectDualPaneWithInput
        the two-column browser, plus a path input whose "Browse" trigger
        opens the panel in a modal `Dialog`.

The two wrappers share the same pieces: `PathInput` (a text input that
resolves what was typed into an existing path) and `Recent` (the "Recent"
dropdown).  Only `TreeSelect` and `TreeSelectWithInput` are exported from
`components_v3`; the rest are building blocks, importable from this module.

Everything is driven through `Property` fields instead of a rerun, so a
caller reads the picked path from `.value` at any time and can react to
`value.on_change`.

Ported from the v1 `streamlit_canary/components/tree_select/` package, which
was written against Streamlit's rerun model.  Where v1 needed Streamlit-only
primitives, the v3 build uses:

    st.dialog         -> `Dialog` (✕ / backdrop / Esc also dismiss it)
    st.menu_button    -> a `Popover` holding a single-choice list
    st.radio + st.container(height) -> `RadioGroup(max_height=...)`
    st.button(':material/...')      -> `IconButton`

    st.segmented_control (`node_type='both'`) is not implemented; only
    `node_type='file'` and `'folder'` are supported.
"""

import os
import typing as tp
from collections import deque

from lk_utils import fs

from ..kernel import Property
from ..kernel import Signal
from .base import Width
from .widgets import Button
from .widgets import Caption
from .widgets import Column
from .widgets import Dialog
from .widgets import IconButton
from .widgets import Info
from .widgets import Popover
from .widgets import RadioGroup
from .widgets import Row
from .widgets import Selectbox
from .widgets import Text
from .widgets import TextInput


class T:
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    NodeType = tp.Literal['file', 'folder']


def _norm(path: str) -> str:
    return fs.abspath(path).replace('\\', '/')


def _filter_func(filter: T.Filter) -> tp.Callable[[str], bool]:
    """`'.txt'` / `('.txt', '.csv')` -> a name predicate (`None` keeps all)."""
    if not filter:
        return lambda _name: True
    return lambda name: name.endswith(filter)


def _entry_label(entry: tp.Any) -> str:
    """Format a `('d' | 'f', name)` listing entry as a radio label."""
    if not (isinstance(entry, tuple) and len(entry) == 2):
        return str(entry)
    kind, name = entry
    escaped = str(name).replace('__', '\\_\\_')
    if kind == 'd':
        return ':material/folder: {}/'.format(escaped)
    return ':material/description: {}'.format(escaped)


def _location_label(directory: str) -> str:
    """Captain text for a folder path (`__` is escaped for markdown)."""
    return ':gray[{}]'.format(directory.replace('__', '\\_\\_'))


def _call(hook: tp.Optional[tp.Callable]) -> None:
    """Run a v1-style `custom` builder hook, if given."""
    if hook is not None:
        hook()


class _TreeNav:
    """Per-selector navigation state.

    v1 kept this in a session dictionary keyed by the widget key; a v3
    component is built once, so each instance simply owns its own state.
    Listings are cached per folder and re-read on demand.
    """

    def __init__(self, start_directory: str) -> None:
        self.start_directory = _norm(start_directory or os.getcwd())
        self.directory = self.start_directory
        self.parent_to_dirnames: dict[str, tp.List[str]] = {}
        self.parent_to_filenames: dict[str, tp.List[str]] = {}
        self.recent: deque = deque(maxlen=20)

    # -- listings ---------------------------------------------------------

    def dirnames(self, directory: str | None = None) -> tp.List[str]:
        directory = directory or self.directory
        if directory not in self.parent_to_dirnames:
            self.parent_to_dirnames[directory] = sorted(
                fs.find_dir_names(directory)
            )
        return self.parent_to_dirnames[directory]

    def filenames(self, directory: str | None = None) -> tp.List[str]:
        directory = directory or self.directory
        if directory not in self.parent_to_filenames:
            self.parent_to_filenames[directory] = sorted(
                fs.find_file_names(directory)
            )
        return self.parent_to_filenames[directory]

    # -- navigation -------------------------------------------------------

    def child(self, name: str) -> str:
        return '{}/{}'.format(self.directory.rstrip('/'), name)

    def parent_of(self, directory: str | None = None) -> str:
        directory = directory or self.directory
        up = fs.parent(directory)
        return up if up and up != directory else directory

    def reload(self, directory: str | None = None) -> None:
        directory = directory or self.directory
        self.parent_to_dirnames.pop(directory, None)
        self.parent_to_filenames.pop(directory, None)

    def remember(self, path: str) -> None:
        if not path:
            return
        if path in self.recent:
            if self.recent[0] == path:
                return
            self.recent.remove(path)
        self.recent.appendleft(path)


class PathInput(Column):
    """A text input whose text is resolved into an existing path.

        with PathInput('Batch file', 'references/.../classic.txt') as box:
            ...
        path = box.path.get()

    `path` is the absolute, forward-slash form of what was typed, or '' when
    the text is empty or names nothing that exists.  It is re-evaluated on
    every keystroke, so a half-typed path is simply not a value yet.

    Args:
        label: the text input's label.
        value: the initial text.
        width: see `Column`.

    Properties:
        path: str — the resolved absolute path ('' when it does not exist).
            Setting it re-writes the text, so callers can push a picked path
            into the box without touching the input directly.

    Signals:
        on_path (via `box['on_path']` or `box.path.on_change`)
    """

    def __init__(
        self,
        label: str = '',
        value: str = '',
        *,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        self.path = Property('')
        with self:
            self._input = TextInput(label, value=value, width='stretch')

        @self._input.value.on_change
        def _validate() -> None:
            self.path.set(self._resolve(str(self._input['value'])))

        @self.path.on_change
        def _follow() -> None:
            # Only a resolved path is written back: an empty one means the
            # text is still incomplete, and must be left alone.
            path = self.path.get()
            if path and str(self._input['value']) != path:
                self._input.value.set(path)

        self.path.set(self._resolve(str(value)))

    @staticmethod
    def _resolve(raw: str) -> str:
        text = str(raw).strip()
        if not text:
            return ''
        path = _norm(text)
        return path if fs.exist(path) else ''


class Recent(Popover):
    """The "Recent" dropdown: the last picked paths, newest first.

        recent = Recent('Recent', options=[], visible=has_history)
        ...
        @recent.value.on_change
        def _on_pick(): ...

    The caller owns the list: assign `options` to replace it (usually from its
    own `_TreeNav`) and bind `visible` to whether there is any history.  A
    pick mirrors into `value`.

    Args:
        label: the trigger's label.
        options: the remembered paths (bindable).
        max_height: cap in px on the list, after which it scrolls.
        visible: whether the trigger is shown (default False — a history
            dropdown has nothing to show until the caller fills it in).

    Properties:
        options: list — the remembered paths (bindable).
        value: str — the picked path ('' while nothing is picked).

    Signals:
        on_value (via `recent['on_value']` or `recent.value.on_change`)
    """

    def __init__(
        self,
        label: str = 'Recent',
        options: tp.Sequence[str] = (),
        *,
        max_height: int = 280,
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, visible=visible, **kwargs)

        initial = list(options)
        self.options = Property(initial)
        self.value = Property('')
        with self:
            self._radio = RadioGroup(
                label,
                options=initial,
                label_visibility='collapsed',
                max_height=max_height,
            )

        @self.options.on_change
        def _sync_options() -> None:
            options_ = list(self.options.get() or [])
            self._radio.options.set(options_)
            if options_ and self._radio['value'] not in options_:
                self._radio.value.set(options_[0])

        @self._radio.value.on_change
        def _sync_value() -> None:
            self.value.set(str(self._radio['value']))

        if initial:
            self._radio.value.set(initial[0])


class TreeSelect(Column):
    """The single-pane tree browser: the folder listing plus its toolbar.

        with Popover('Browse', panel_align='row', panel_max_height=500):
            tree = v3.TreeSelect(filter='.txt')
        ...
        path = tree.value.get()

    Layout::

        /current/folder
        (o) subfolder/
        ( ) another-file.txt          <- scrolls past `height` px
        [home] [up] [enter] [refresh]

    Picking a *file* row is what updates `value`; a folder row is only
    highlighted -- use "enter" to move into it (or "up" to come back), which
    clears `value` again.  `TreeSelectWithInput` wires this panel to a path
    input and a "Browse" trigger for you.

    Args:
        start_directory: the folder to open (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        height: optional cap in px on the listing, after which it scrolls.
            Left `None` when an enclosing `Popover` does the scrolling.
        width: see `Column`.

    Properties:
        value: str — the picked file path ('' while nothing is picked).

    Signals:
        on_value (via `tree['on_value']` or `tree.value.on_change`)
    """

    def __init__(
        self,
        start_directory: str = '',
        *,
        filter: T.Filter = None,
        height: int | None = None,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        keeps = _filter_func(filter)
        nav = _TreeNav(start_directory)
        self._nav = nav
        self._keeps = keeps

        self.value = Property('')

        with self:
            self._location = Caption(_location_label(nav.directory))
            self._list = RadioGroup(
                'Folder contents',
                options=(),
                format=_entry_label,
                label_visibility='collapsed',
                max_height=height,
            )
            with Row('center'):
                self._home_btn = IconButton(
                    'home', help='Go to the initial folder'
                )
                self._up_btn = IconButton('arrow_upward', help='Parent folder')
                self._enter_btn = IconButton(
                    'arrow_forward', help='Enter the highlighted folder'
                )
                self._refresh_btn = IconButton('refresh', help='Refresh')

        # -- handlers -------------------------------------------------------

        @self._list.value.on_change
        def _on_select() -> None:
            selected = self._list['value']
            if not (isinstance(selected, tuple) and selected):
                return
            kind, name = selected
            if kind != 'f':
                return
            self.value.set(self._nav.child(name))

        @self._home_btn.on_click
        def _go_home() -> None:
            self._nav.directory = self._nav.start_directory
            self._refresh_listing()

        @self._up_btn.on_click
        def _go_up() -> None:
            self._nav.directory = self._nav.parent_of()
            self._refresh_listing()

        @self._enter_btn.on_click
        def _go_into() -> None:
            selected = self._list['value']
            if isinstance(selected, tuple) and selected and selected[0] == 'd':
                self._nav.directory = self._nav.child(selected[1])
                self._refresh_listing()

        @self._refresh_btn.on_click
        def _reload() -> None:
            self._nav.reload()
            self._refresh_listing()

        self._refresh_listing()

    # -- internals ----------------------------------------------------------

    def _goto(self, directory: str) -> None:
        """Point the panel at a folder (used by the wrappers)."""
        directory = _norm(directory) if directory else ''
        if directory and fs.isdir(directory):
            self._nav.directory = directory
        self._refresh_listing()

    def _refresh_listing(self) -> None:
        nav = self._nav
        options: list = [('d', name) for name in nav.dirnames()]
        options += [
            ('f', name) for name in nav.filenames() if self._keeps(name)
        ]
        self._list.options.set(options)
        self._location.text.set(_location_label(nav.directory))


class TreeSelectWithInput(Column):
    """A path input plus the single-pane browser in a "Browse" popover.

        sel = v3.TreeSelectWithInput(
            'Batch file', 'references/.../classic.txt', filter='.txt'
        )
        ...
        path = sel.value.get()

    Layout::

        [ path input ..................... ] [ Recent ] [ Browse v ]
        +-- "Browse" popover (spans the header row) ------------------+
        | /current/folder                                             |
        | (o) subfolder/                                              |
        | ( ) another-file.txt          <- scrolls past `height` px   |
        +-------------------------------------------------------------+
        | [home] [up] [enter] [refresh]   <- pinned to the panel foot |
        +-------------------------------------------------------------+

    The panel is a `TreeSelect`; the popover stretches it from the path
    input's left edge to the header row's right edge.

    Typing a file path commits it; typing a folder points the panel there and
    clears `value` (pick a file inside to commit again).  Picking a file in
    the panel or from "Recent" fills the input back in.

    Args:
        label: the path input's label.
        initial_path: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        height: max height of the "Browse" panel in px (default 500).
        width: see `Column`.

    Properties:
        value: str — the committed file path ('' while nothing is committed).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
    """

    def __init__(
        self,
        label: str = '',
        initial_path: str = '',
        *,
        filter: T.Filter = None,
        show_recent: bool = True,
        height: int = 500,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        first_path = initial_path or os.getcwd()
        initial_is_file = bool(initial_path) and fs.isfile(first_path)
        nav = _TreeNav(fs.parent(first_path) if initial_is_file else first_path)
        self._nav = nav
        self._keeps = _filter_func(filter)
        self._show_recent = show_recent

        self.value = Property('')
        self._has_recent = Property(False)
        if initial_is_file:
            self.value.set(_norm(first_path))
            nav.remember(self.value.get())

        with self:
            with Row('bottom'):
                self._path_input = PathInput(label, first_path)
                self._recent = Recent(
                    'Recent', visible=self._has_recent, max_height=280
                )
                self._browse_popover = Popover(
                    'Browse', panel_align='row', panel_max_height=height
                )
                with self._browse_popover:
                    self._tree = TreeSelect(
                        nav.directory, filter=filter, height=None
                    )

        # -- handlers -------------------------------------------------------

        @self._path_input.path.on_change
        def _on_path_typed() -> None:
            path = self._path_input.path.get()
            self._commit(path) if path else self.value.set('')

        @self._tree.value.on_change
        def _on_tree_picked() -> None:
            self._commit(self._tree['value'])

        @self._recent.value.on_change
        def _on_recent_picked() -> None:
            self._commit(str(self._recent['value']))

        self._refresh_recent()

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        """Resolve a path into `value` + the panel's folder."""
        path = path.strip()
        if not path:
            self.value.set('')
            return
        path = _norm(path)
        if not fs.exist(path):
            # A half-typed path is not an error, just not a value yet.
            self.value.set('')
            return
        if fs.isdir(path):
            self._nav.directory = path
            self.value.set('')
        else:
            self._nav.directory = fs.parent(path)
            self.value.set(path)
            self._nav.remember(path)
        self._path_input.path.set(path)
        self._tree._goto(self._nav.directory)
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        recent = list(self._nav.recent)
        self._has_recent.set(bool(recent) and self._show_recent)
        self._recent.options.set(recent)
        if recent and self._recent['value'] not in recent:
            self._recent.value.set(recent[0])


class TreeSelectDualPane(Column):
    """The two-column tree browser.

    Left column navigates subfolders (back / forward / refresh / new folder);
    the right column lists the files, optionally previewing the highlighted
    folder's subfolders, with a Confirm button underneath.

    Args:
        start_directory: the folder to open (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        height: height of both columns in px, after which they scroll.
        node_type: `'file'` selects a file (default), `'folder'` a folder.
        preview_subfolders: also list the highlighted subfolder's contents,
            so a single click enters it.
        show_confirm_button: render the Confirm button (default True).

    Properties:
        value: str — the currently highlighted path (live).

    Signals:
        on_confirm: emitted when Confirm is clicked.
    """

    def __init__(
        self,
        start_directory: str = '',
        *,
        filter: T.Filter = None,
        height: int = 500,
        node_type: T.NodeType = 'file',
        preview_subfolders: bool = True,
        show_confirm_button: bool = True,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        keeps = _filter_func(filter)
        nav = _TreeNav(start_directory)
        nav.dirnames()  # index the starting folder
        self._nav = nav
        self._keeps = keeps
        self._node_type = node_type
        self._preview_subfolders = preview_subfolders

        self.value = Property('')
        self._has_subfolder_preview = Property(False)
        self._new_folder_open = Property(False)

        with self:
            self._location = Selectbox(
                'Current location',
                options=tuple(sorted(nav.parent_to_dirnames)),
                value=nav.directory,
                accept_new_options=True,
                format_new_option=lambda x: x.strip(),
            )
            with Row():
                with Column(weight=3.5):
                    with Column(height=height):
                        with Row('center'):
                            self._back_btn = IconButton(
                                'arrow_back', help='Back'
                            )
                            self._enter_btn = IconButton(
                                'arrow_forward', help='Enter the subfolder'
                            )
                            self._refresh_btn = IconButton(
                                'refresh', help='Refresh tree'
                            )
                            self._new_folder_btn = IconButton(
                                'create_new_folder', help='Create new folder'
                            )
                        self._new_folder_panel = Column(
                            visible=self._new_folder_open, animated=True
                        )
                        with self._new_folder_panel:
                            self._new_folder_input = TextInput(
                                'Input folder name',
                                value='',
                                label_visibility='collapsed',
                            )
                        self._subdir_radio = RadioGroup(
                            'Navigate to subfolder',
                            options=('.',),
                            max_height=height - 96,
                        )
                with Column(weight=6.5):
                    with Column(height=height):
                        self._preview_panel = Column(
                            border=True, visible=self._has_subfolder_preview
                        )
                        with self._preview_panel:
                            self._preview_radio = RadioGroup(
                                'Subfolders',
                                options=(),
                                label_visibility='collapsed',
                                max_height=int(height / 2) - 40,
                            )
                        self._file_radio = RadioGroup(
                            'Select one file'
                            if node_type == 'file'
                            else 'Select one folder',
                            options=(),
                            max_height=height - 80,
                        )
                        with Row('bottom'):
                            self._confirm_btn = Button(
                                'Confirm',
                                type='primary',
                                width='stretch',
                                enabled=False,
                            )
                            with Popover(':material/location_on:'):
                                Text('Current location:')
                                self._location_info = Info(nav.directory)
            self.on_confirm: Signal = Signal(_owner_factory=lambda: self)

        # -- handlers -------------------------------------------------------

        @self._location.value.on_change
        def _on_location_changed() -> None:
            self._goto(str(self._location['value']))

        @self._subdir_radio.value.on_change
        def _on_subdir_highlighted() -> None:
            self._refresh_right_panel()

        @self._preview_radio.value.on_change
        def _on_preview_picked() -> None:
            name = str(self._preview_radio['value'])
            if name:
                self._nav.directory = self._nav.child(name)
                self._after_move()

        @self._file_radio.value.on_change
        def _on_file_highlighted() -> None:
            self._sync_value()

        @self._back_btn.on_click
        def _go_back() -> None:
            self._nav.directory = self._nav.parent_of()
            self._after_move()

        @self._enter_btn.on_click
        def _go_into() -> None:
            name = str(self._subdir_radio['value'])
            if name and name != '.':
                self._nav.directory = self._nav.child(name)
                self._after_move()

        @self._refresh_btn.on_click
        def _reload() -> None:
            self._nav.reload()
            self._after_move(keep_selection=True)

        @self._new_folder_btn.on_click
        def _toggle_new_folder() -> None:
            self._new_folder_open.set(not self._new_folder_open.get())

        @self._new_folder_input.value.on_change
        def _create_folder() -> None:
            name = str(self._new_folder_input['value']).strip()
            if not name:
                return
            target = self._nav.child(name)
            if fs.exist(target):
                return
            fs.make_dir(target)
            self._nav.reload()
            self._new_folder_input.value.set('')
            self._new_folder_open.set(False)
            self._after_move(keep_selection=True)

        @self._confirm_btn.on_click
        def _confirm() -> None:
            self.on_confirm.emit()

        self._after_move(keep_selection=True)

    # -- internals ----------------------------------------------------------

    def _after_move(self, keep_selection: bool = False) -> None:
        """Re-render everything after the current folder changed."""
        nav = self._nav
        self._location_info.text.set(nav.directory)
        locations = sorted(set(nav.parent_to_dirnames) | {nav.directory})
        self._location.options.set(list(locations))
        if self._location['value'] not in locations:
            self._location.value.set(nav.directory)
        self._subdir_radio.options.set(['.'] + list(nav.dirnames()))
        if not keep_selection:
            self._subdir_radio.value.set('.')
        self._refresh_right_panel()

    def _refresh_right_panel(self) -> None:
        nav = self._nav
        highlighted = str(self._subdir_radio['value'])
        preview = bool(
            self._preview_subfolders and highlighted and highlighted != '.'
        )
        if preview:
            target = nav.child(highlighted)
            self._preview_radio.options.set(list(nav.dirnames(target)))
        self._has_subfolder_preview.set(preview)

        options: list
        if self._node_type == 'folder':
            if highlighted and highlighted != '.':
                options = list(nav.dirnames(nav.child(highlighted)))
            else:
                options = ['.'] + list(nav.dirnames())
        else:
            directory = nav.child(highlighted) if preview else nav.directory
            options = [
                name for name in nav.filenames(directory) if self._keeps(name)
            ]
        self._file_radio.options.set(options)
        self._sync_value()

    def _sync_value(self) -> None:
        """Mirror the highlighted list item into `value`."""
        highlighted = str(self._subdir_radio['value'])
        selected = str(self._file_radio['value'])
        nav = self._nav
        if self._node_type == 'folder':
            if highlighted and highlighted != '.':
                directory = nav.child(highlighted)
            else:
                directory = nav.directory
            value = (
                directory
                if selected in ('', '.')
                else '{}/{}'.format(directory.rstrip('/'), selected)
            )
        else:
            directory = (
                nav.child(highlighted)
                if highlighted and highlighted != '.'
                else nav.directory
            )
            value = (
                '{}/{}'.format(directory.rstrip('/'), selected)
                if selected
                else ''
            )
        self.value.set(value)
        self._confirm_btn.enabled.set(bool(value))

    def _goto(self, path: str) -> None:
        path = path.strip()
        if not path:
            return
        path = _norm(path)
        if not fs.exist(path):
            return
        if not fs.isdir(path):
            path = fs.parent(path)
        self._nav.directory = path
        self._nav.dirnames(path)
        self._after_move()


class TreeSelectDualPaneWithInput(Column):
    """A path input plus the two-column browser in a modal dialog.

        sel = v3.TreeSelectDualPaneWithInput('Waveform file', 'a.mat')
        ...
        path = sel.value.get()

    Layout::

        [ path input ......... ] [ Recent ] [ Browse ]
        (Browse opens a modal dialog holding the two-column
        `TreeSelectDualPane`)

    Args:
        label: the path input's label.
        initial_path: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        node_type: `'file'` (default) or `'folder'`.
        dialog_title: the dialog's title (default: derived from `node_type`).
        tree_panel_height: height of the tree's columns inside the dialog.
        custom: optional builder hooks, mirroring v1's customization points.
            Recognized keys: `'place0'`..`'place3'` are called (with no
            arguments) around the path input / recent / browse buttons.
        width: see `Column`.

    Properties:
        value: str — the committed path ('' while nothing is committed).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
    """

    def __init__(
        self,
        label: str,
        initial_path: str = '',
        *,
        filter: T.Filter = None,
        show_recent: bool = True,
        node_type: T.NodeType = 'file',
        dialog_title: str = '',
        tree_panel_height: int = 500,
        custom: tp.Optional[dict] = None,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        custom = custom or {}
        first_path = initial_path or os.getcwd()
        if node_type == 'file':
            result = _norm(first_path) if fs.isfile(first_path) else ''
        else:
            result = (
                _norm(first_path)
                if fs.isdir(first_path)
                else fs.parent(_norm(first_path))
            )
        nav = _TreeNav(
            first_path if fs.isdir(first_path) else fs.parent(first_path)
        )

        self._nav = nav
        self._node_type = node_type
        self._show_recent = show_recent

        self.value = Property('')
        self._browsing = Property(False)
        self._has_recent = Property(False)
        if result:
            self.value.set(result)
            nav.remember(result)

        with self:
            with Row('bottom'):
                _call(custom.get('place0'))
                self._path_input = PathInput(label, first_path)
                _call(custom.get('place1'))
                self._recent = Recent(
                    'Recent', visible=self._has_recent, max_height=280
                )
                _call(custom.get('place2'))
                self._browse_btn = Button('Browse')
                _call(custom.get('place3'))

            title = dialog_title or 'Select {}'.format(
                'file' if node_type == 'file' else 'folder'
            )
            self._dialog = Dialog(title, visible=self._browsing, width='large')
            with self._dialog:
                self._tree = TreeSelectDualPane(
                    nav.directory,
                    filter=filter,
                    height=tree_panel_height,
                    node_type=node_type,
                )

        # -- handlers -------------------------------------------------------

        @self._browse_btn.on_click
        def _open_dialog() -> None:
            self._tree._after_move(keep_selection=True)
            self._browsing.set(True)

        @self._dialog.on_close
        def _on_dialog_closed() -> None:
            self._browsing.set(False)

        @self._tree.on_confirm
        def _commit_from_tree() -> None:
            self._commit(self._tree['value'])
            self._browsing.set(False)

        @self._recent.value.on_change
        def _on_recent_picked() -> None:
            self._commit(str(self._recent['value']))

        @self._path_input.path.on_change
        def _on_path_typed() -> None:
            path = self._path_input.path.get()
            self._commit(path) if path else self.value.set('')

        self._refresh_recent()

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        path = path.strip()
        if not path:
            self.value.set('')
            return
        path = _norm(path)
        if not fs.exist(path):
            # A half-typed path is not an error, just not a value yet.
            self.value.set('')
            return
        if self._node_type == 'file' and fs.isdir(path):
            self.value.set('')
            self._nav.directory = path
        else:
            self.value.set(path)
            self._nav.remember(path)
            self._nav.directory = path if fs.isdir(path) else fs.parent(path)
        self._path_input.path.set(path)
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        recent = list(self._nav.recent)
        self._has_recent.set(bool(recent) and self._show_recent)
        self._recent.options.set(recent)
        if recent and self._recent['value'] not in recent:
            self._recent.value.set(recent[0])
