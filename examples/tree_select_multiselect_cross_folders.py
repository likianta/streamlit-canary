"""
Demo: Tree select with single / multi / cross-folder multi selection.

`v3.TreeSelectWithInput` already gives a path input, a "Recent" dropdown and a
"Browse" popover holding the folder listing. This example extends it into a
custom widget whose panel offers three selection modes:

    Single select       pick one folder or file node (`v3.RadioGroup`).
    Multi select        tick several nodes of the current folder
                        (`v3.CheckGroup`).
    Multi-cross select  every ticked node also drops into a floating
                        "bucket"; navigate to other folders to gather more,
                        then open the bucket to review the haul and remove
                        entries one by one (`v3.CheckGroup` + a bucket panel).

The bucket is a `v3.ReducibleGroup`: its rows are plain HTML (written by the
renderer, rebuilt by an `options` patch), so nothing here needs pre-allocated
component slots -- the runtime builds the tree exactly once.

Run it with:

    python examples/tree_select_multiselect_cross_folders.py

and open http://127.0.0.1:2201 in a browser.
"""

import json
import typing as tp

from lk_utils import fs

import streamlit_canary as sc
from streamlit_canary.components_v3.base import Width

v3 = sc.v3

_SINGLE = 'Single select'
_MULTI = 'Multi select'
_CROSS = 'Multi-cross select'

_Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]


def _norm(path: str) -> str:
    return fs.abspath(path).replace('\\', '/')


def _node_label(entry: tp.Any) -> str:
    """Format a `('d' | 'f', name)` listing entry as a widget label."""
    if not (isinstance(entry, tuple) and len(entry) == 2):
        return str(entry)
    kind, name = entry
    escaped = str(name).replace('__', '\\_\\_')
    if kind == 'd':
        return ':material/folder: {}/'.format(escaped)
    return ':material/description: {}'.format(escaped)


def _location_label(directory: str) -> str:
    return ':gray[{}]'.format(directory.replace('__', '\\_\\_'))


def _bucket_label(path: str, root: str) -> str:
    """Show a bucketed node relative to the widget's starting folder."""
    prefix = root.rstrip('/') + '/'
    short = path[len(prefix) :] if path.startswith(prefix) else path
    kind = 'd' if fs.isdir(path) else 'f'
    return _node_label((kind, short))


class MultiModeTreeSelect(v3.TreeSelectWithInput):
    """A `TreeSelectWithInput` whose panel adds three selection modes.

    The inherited path input, "Recent" dropdown and navigation state are
    reused as-is; only the "Browse" panel is rebuilt, so its listing can
    follow the active mode.

    Args:
        label: the path input's label.
        initial_path: the folder to open (default: the cwd).
        filter: a suffix (`'.py'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked nodes.
        height: max height of the "Browse" panel in px.
        width: see `Column`.

    Properties:
        mode: str — the active mode (`_SINGLE` / `_MULTI` / `_CROSS`).
        value: str — the single-selected path ('' while nothing is picked).
        multi_selected: list[str] — the paths ticked in multi mode.
        bucket: list[str] — the paths gathered in multi-cross mode.
    """

    def __init__(
        self,
        label: str = '',
        initial_path: str = '',
        *,
        filter: _Filter = None,
        show_recent: bool = True,
        height: int = 500,
        width: Width | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(
            label,
            initial_path,
            filter=filter,
            show_recent=show_recent,
            height=height,
            width=width,
            **kwargs,
        )

        nav = self._nav

        # the mode drives which list is shown; the selection lives here
        self.mode = sc.Property(_SINGLE)
        self.multi_selected = sc.Property([])
        self.bucket = sc.Property([])
        # `_syncing` suppresses the pick handlers while the lists are being
        # rebuilt, so a programmatic `value` change is not read as a click.
        self._syncing = False

        # the inherited tree is a plain single-file browser: hide it and put
        # the mode-aware panel in its place (inside the same popover).
        self._tree.visible.set(False)

        with self._browse_popover:
            with v3.Row():
                v3.Space(width='stretch')
                self._mode_control = v3.SegmentedControl(
                    'Selection mode',
                    options=(_SINGLE, _MULTI, _CROSS),
                    value=_SINGLE,
                    label_visibility='collapsed',
                )

            self._location = v3.Caption(_location_label(nav.directory))

            # one node list per mode: a radio for single selection, a check
            # group for the two multi-selection modes. Each column's
            # visibility follows the mode.
            self._col_of_single = v3.Column(
                visible=sc.bind(self.mode, lambda x: x == _SINGLE)
            )
            with self._col_of_single:
                self._list_of_single = v3.RadioGroup(
                    'Folder contents',
                    options=(),
                    format=_node_label,
                    label_visibility='collapsed',
                )
            self._col_of_multi = v3.Column(
                visible=sc.bind(self.mode, lambda x: x == _MULTI)
            )
            with self._col_of_multi:
                self._list_of_multi = v3.CheckGroup(
                    'Folder contents',
                    options=(),
                    format=_node_label,
                    full_body_click=False,
                    label_visibility='collapsed',
                )
            self._col_of_cross = v3.Column(
                visible=sc.bind(self.mode, lambda x: x == _CROSS)
            )
            with self._col_of_cross:
                self._list_of_cross = v3.CheckGroup(
                    'Folder contents',
                    options=(),
                    format=_node_label,
                    full_body_click=False,
                    label_visibility='collapsed',
                )

            with v3.Row('center'):
                self._home_btn = v3.IconButton(
                    'home', help='Go to the initial folder'
                )
                self._up_btn = v3.IconButton(
                    'arrow_upward', help='Parent folder'
                )
                self._enter_btn = v3.IconButton(
                    'arrow_forward', help='Enter the highlighted folder'
                )
                self._refresh_btn = v3.IconButton('refresh', help='Refresh')
                # the bucket tucks into the same bar, pushed to its right edge
                # by the spacer. It stays a `Popover` -- a `MenuButton` is an
                # options widget, not a container -- and every panel is placed
                # with `position: fixed`, so this one floats above the browse
                # panel instead of being clipped by it. Its trigger is inert
                # while the bucket is empty.
                v3.Space(width='stretch')
                self._bucket_popover = v3.Popover(
                    sc.bind(
                        self.bucket,
                        lambda picked: ':material/bucket_check: {}'.format(
                            len(picked)
                        ),
                    ),
                    visible=sc.bind(self.mode, lambda m: m == _CROSS),
                    enabled=sc.bind(self.bucket, bool),
                    panel_max_height=240,
                )
                with self._bucket_popover:
                    # `options` is bound to the bucket, so anything that changes
                    # the bucket (a tick, or an `x` below) redraws this list.
                    self._bucket_group = v3.ReducibleGroup(
                        options=self.bucket,
                        format=lambda path: _bucket_label(
                            path, self._nav.start_directory
                        ),
                    )

        # -- handlers -------------------------------------------------------
        @self._mode_control.value.on_change
        def _on_mode_changed() -> None:
            mode = str(self._mode_control['value'])
            self.mode.set(mode)
            self._apply_mode(mode)

        @self._list_of_single.value.on_change
        def _on_single_picked() -> None:
            if self._syncing:
                return
            selected = self._list_of_single['value']
            if isinstance(selected, tuple) and selected:
                self._commit(nav.child(selected[1]))

        @self._list_of_multi.value.on_change
        def _on_multi_toggled() -> None:
            if self._syncing:
                return
            listed = self._listed_paths(self._list_of_multi)
            # drop this folder's previous picks, then add the ticked ones, so
            # the picks of the other folders survive a folder switch.
            kept = [p for p in self.multi_selected.get() if p not in listed]
            self.multi_selected.set(
                kept + self._ticked_paths(self._list_of_multi)
            )

        @self._list_of_cross.value.on_change
        def _on_cross_toggled() -> None:
            if self._syncing:
                return
            listed = self._listed_paths(self._list_of_cross)
            # the bucket mirrors the ticks of every folder it was filled from
            bucket = [p for p in self.bucket.get() if p not in listed]
            bucket += self._ticked_paths(self._list_of_cross)
            # the bucket panel's `options` are bound to `bucket`, so setting it
            # is all it takes for the list to redraw
            self.bucket.set(bucket)

        @self._bucket_group.on_reduce
        def _on_bucket_reduced(path: str) -> None:
            """Drop the node the user removed from the bucket panel."""
            self.bucket.set([p for p in self.bucket.get() if p != path])
            # its tick in the cross listing follows the bucket
            self._refresh_panel()

        @self._home_btn.on_click
        def _go_home() -> None:
            nav.directory = nav.start_directory
            self._refresh_panel()

        @self._up_btn.on_click
        def _go_up() -> None:
            nav.directory = nav.parent_of()
            self._refresh_panel()

        @self._enter_btn.on_click
        def _go_into() -> None:
            folder = self._first_ticked_folder()
            if folder:
                nav.directory = folder
                self._refresh_panel()

        @self._refresh_btn.on_click
        def _reload() -> None:
            nav.reload()
            self._refresh_panel()

        self._apply_mode(_SINGLE)

    # -- public api ---------------------------------------------------------

    def results(self) -> dict:
        """The current selection, shaped for printing / display."""
        mode = self.mode.get()
        if mode == _MULTI:
            picked = list(self.multi_selected.get())
        elif mode == _CROSS:
            picked = list(self.bucket.get())
        else:
            value = self.value.get()
            picked = [value] if value else []
        return {'mode': mode, 'selected': picked}

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        """Resolve a picked path into `value`.

        Unlike the base implementation a folder is a valid value too, and
        picking one does not navigate away from the current listing.
        """
        path = path.strip()
        if not path:
            self.value.set('')
            return
        path = _norm(path)
        if not fs.exist(path):
            self.value.set('')
            return
        self.value.set(path)
        self._nav.remember(path)
        self._path_input.path.set(path)
        self._refresh_recent()

    def _apply_mode(self, mode: str) -> None:
        """Refresh the listing after a mode switch.

        Each column's `visible` follows `mode` on its own (see `__init__`), so
        there is nothing to show or hide here.
        """
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        """Re-list the current folder for all three node lists."""
        nav = self._nav
        entries: list = [('d', name) for name in nav.dirnames()]
        entries += [
            ('f', name) for name in nav.filenames() if self._keeps(name)
        ]
        self._location.text.set(_location_label(nav.directory))
        picked_multi = set(self.multi_selected.get())
        picked_bucket = set(self.bucket.get())
        self._syncing = True
        try:
            for listing in (
                self._list_of_single,
                self._list_of_multi,
                self._list_of_cross,
            ):
                listing.options.set(entries)
            # the check groups re-tick what was picked before, so walking back
            # into a folder shows its ticks again. The radio lets its own
            # auto-select highlight the first entry instead.
            self._list_of_multi.value.set(
                [e for e in entries if nav.child(e[1]) in picked_multi]
            )
            self._list_of_cross.value.set(
                [e for e in entries if nav.child(e[1]) in picked_bucket]
            )
        finally:
            self._syncing = False

    def _listed_paths(self, listing: tp.Any) -> set:
        """The absolute paths of every node a listing currently shows."""
        return {self._nav.child(e[1]) for e in listing['options'] or ()}

    def _ticked_paths(self, listing: tp.Any) -> list:
        """The absolute paths of a listing's ticked nodes, in listing order."""
        return [self._nav.child(e[1]) for e in listing['value'] or ()]

    def _first_ticked_folder(self) -> str:
        """The folder `->` should open.

        With a radio that is the selected folder; with a check group it is the
        ticked folder that comes first in the listing. Returns '' when no
        folder is picked.
        """
        mode = self.mode.get()
        if mode == _SINGLE:
            selected = self._list_of_single['value']
            entries = [selected] if selected else []
        elif mode == _MULTI:
            entries = list(self._list_of_multi['value'] or ())
        else:
            entries = list(self._list_of_cross['value'] or ())
        for entry in entries:
            if isinstance(entry, tuple) and entry and entry[0] == 'd':
                return self._nav.child(entry[1])
        return ''


def main() -> None:
    sc.set_page_config('Tree Select - Multi / Cross-folders')

    sel = MultiModeTreeSelect('Node', '', filter=None, height=420)

    with v3.Row():
        btn = v3.Button('Print results', type='primary')
    out = v3.Code('')

    @btn.on_click
    def _print_results() -> None:
        data = sel.results()
        print('[tree-select demo] {}'.format(data))
        out.text.set(json.dumps(data, indent=2))


if __name__ == '__main__':
    sc.run(main, port=2201)
