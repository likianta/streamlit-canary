"""The two-column browser and its "input + dialog" wrapper."""

import os
import typing as tp

from lk_utils import fs

from .recent import Recent
from ._shared import _TreeNav, T, _call, _filter_func
from ..base import Width
from ..buttons import Button
from ..buttons import IconButton
from ..inputs import PathInput
from ..inputs import RadioGroup
from ..inputs import Selectbox
from ..inputs import TextInput
from ..layouts import Column
from ..layouts import Container
from ..layouts import Dialog
from ..layouts import Popover
from ..layouts import Row
from ..status import Info
from ..texts import Text
from ...kernel import Property
from ...kernel import Signal


class TreeSelectDualPane(Container):
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

    # TODO: give this pane the "enter" arrow too (see `_NavigationGroup`). It
    # still navigates on a single click, so the two browsers speak different
    # gestures.

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
                accept_new_option=True,
                format_new_option=lambda x: x.strip(),
            )
            with Row():
                with Column(weight=3.5):
                    with Container(height=height):
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
                        self._new_folder_panel = Container(
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
                    with Container(height=height):
                        self._preview_panel = Container(
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
        path = fs.abspath(path)
        if not fs.exist(path):
            return
        if not fs.isdir(path):
            path = fs.parent(path)
        self._nav.directory = path
        self._nav.dirnames(path)
        self._after_move()


class TreeSelectDualPaneWithInput(Container):
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
        start_directory: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        node_type: `'file'` (default) or `'folder'`.
        dialog_title: the dialog's title (default: derived from `node_type`).
        tree_panel_height: height of the tree's columns inside the dialog.
        custom: optional builder hooks, mirroring v1's customization points.
            Recognized keys: `'place0'`..`'place3'` are called (with no
            arguments) around the path input / recent / browse buttons.
        width: see `Container`.

    Properties:
        value: str — the committed path ('' while nothing is committed).

    Signals:
        on_value (via `sel['on_value']` or `sel.value.on_change`)
    """

    def __init__(
        self,
        label: str,
        start_directory: str = '',
        *,
        filter: T.Filter = None,
        show_recent: bool = False,
        node_type: T.NodeType = 'file',
        dialog_title: str = '',
        tree_panel_height: int = 500,
        custom: tp.Optional[dict] = None,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        custom = custom or {}
        first_path = start_directory or os.getcwd()
        if node_type == 'file':
            result = fs.abspath(first_path) if fs.isfile(first_path) else ''
        else:
            result = (
                fs.abspath(first_path)
                if fs.isdir(first_path)
                else fs.parent(fs.abspath(first_path))
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
        # set while `_refresh_recent` adopts the newest path into the dropdown:
        # that is a display update, not a pick, so `_commit` must not run
        self._recent_quiet = False
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
            if self._recent_quiet:
                return
            self._commit(str(self._recent['value']))

        @self._path_input.value.on_change
        def _on_path_typed() -> None:
            path = self._path_input.value.get()
            self._commit(path) if path else self.value.set('')

        self._refresh_recent()

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        path = path.strip()
        if not path:
            self.value.set('')
            return
        path = fs.abspath(path)
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
        self._path_input.value.set(path)
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        recent = list(self._nav.recent)
        self._has_recent.set(bool(recent) and self._show_recent)
        self._recent.options.set(recent)
        if recent and self._recent['value'] not in recent:
            # show the newest entry without *picking* it -- see the guard's
            # note in `__init__`
            self._recent_quiet = True
            try:
                self._recent.value.set(recent[0])
            finally:
                self._recent_quiet = False
