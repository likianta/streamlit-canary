"""
Demo: Tree select with single / multi / cross-folder multi selection.

`v3.TreeSelectWithInput` already gives a path input, a "Recent" dropdown and a
"Browse" popover holding the folder listing. This example extends it into a
custom widget whose panel offers three selection modes:

    Single select       pick one folder or file node.
    Multi select        tick several nodes of the current folder (inline
                        checkboxes).
    Multi-cross select  every picked node drops into a floating "bucket";
                        navigate to other folders to gather more, then open
                        the bucket to review the haul and remove entries one
                        by one.

The runtime builds the component tree exactly once -- there is no dynamic
child support -- so the inline lists are made of *pre-allocated* component
slots whose `visible` flag is toggled whenever the listing changes.

Run it with:

    python examples/tree_select_multiselect_cross_folders.py

and open http://127.0.0.1:2021 in a browser.
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
_MODES = (_SINGLE, _MULTI, _CROSS)

# how many rows each inline list pre-allocates (a demo-only cap: the tree is
# static, so a list cannot grow past the slots it was built with).
_MAX_SLOTS = 48

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
        self._multi_paths = [''] * _MAX_SLOTS

        # the inherited tree is a plain single-file browser: hide it and put
        # the mode-aware panel in its place (inside the same popover).
        self._tree.visible.set(False)

        with self._browse_popover:
            self._mode_radio = v3.Radio(
                'Selection mode',
                options=_MODES,
                value=_SINGLE,
                horizontal=True,
                label_visibility='collapsed',
            )
            self._location = v3.Caption(_location_label(nav.directory))
            self._single_col = v3.Column()
            with self._single_col:
                self._list = v3.Radio(
                    'Folder contents',
                    options=(),
                    format=_node_label,
                    label_visibility='collapsed',
                )
            self._multi_col = v3.Column(visible=False)
            with self._multi_col:
                self._multi_slots: list = []
                self._multi_boxes: list = []
                for index in range(_MAX_SLOTS):
                    slot = v3.Column(visible=False)
                    with slot:
                        box = v3.Checkbox('')
                    self._multi_slots.append(slot)
                    self._multi_boxes.append(box)
                    box.value.on_change.partial(index)(self._on_multi_toggled)
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

        # the bucket is a floating popover in the header row, so it stays
        # reachable while the "Browse" panel is open.
        header = self._path_input.parent
        assert header is not None
        with header:
            self._bucket_popover = v3.Popover(
                sc.bind(
                    self.bucket,
                    lambda picked: 'Bucket ({})'.format(len(picked)),
                ),
                visible=sc.bind(self.mode, lambda m: m == _CROSS),
            )
            with self._bucket_popover:
                self._bucket_slots: list = []
                self._bucket_texts: list = []
                for index in range(_MAX_SLOTS):
                    slot = v3.Column(visible=False)
                    with slot:
                        with v3.Row('center'):
                            txt = v3.Text('', width='stretch')
                            btn = v3.IconButton(
                                'close', help='Remove from the bucket'
                            )
                    self._bucket_slots.append(slot)
                    self._bucket_texts.append(txt)
                    btn.on_click.partial(index)(self._on_bucket_removed)

        # -- handlers -------------------------------------------------------
        @self._mode_radio.value.on_change
        def _on_mode_changed() -> None:
            mode = str(self._mode_radio['value'])
            self.mode.set(mode)
            self._apply_mode(mode)

        @self._list.value.on_change
        def _on_list_picked() -> None:
            if self._syncing:
                return
            selected = self._list['value']
            if not (isinstance(selected, tuple) and selected):
                return
            path = nav.child(selected[1])
            if self.mode.get() == _CROSS:
                self._add_to_bucket(path)
            else:
                self._commit(path)

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
            selected = self._list['value']
            if isinstance(selected, tuple) and selected and selected[0] == 'd':
                nav.directory = nav.child(selected[1])
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
        """Show the list that belongs to `mode` and refresh it."""
        self._single_col.visible.set(mode != _MULTI)
        self._multi_col.visible.set(mode == _MULTI)
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        """Re-list the current folder for both the radio and the checkboxes."""
        nav = self._nav
        entries: list = [('d', name) for name in nav.dirnames()]
        entries += [
            ('f', name) for name in nav.filenames() if self._keeps(name)
        ]
        self._location.text.set(_location_label(nav.directory))
        self._syncing = True
        try:
            self._list.options.set(entries)
            if self.mode.get() == _CROSS:
                # keep every row clickable: otherwise the radio highlights
                # the first entry and swallows its click (a re-click on the
                # already-checked row emits no change event).
                self._list.value.set('')
            self._fill_multi_slots(entries)
        finally:
            self._syncing = False

    def _fill_multi_slots(self, entries: list) -> None:
        """Map the folder's entries onto the pre-allocated checkbox slots."""
        picked = set(self.multi_selected.get())
        with sc.updating():
            for index in range(_MAX_SLOTS):
                slot = self._multi_slots[index]
                box = self._multi_boxes[index]
                if index < len(entries):
                    kind, name = entries[index]
                    path = self._nav.child(name)
                    self._multi_paths[index] = path
                    slot.visible.set(True)
                    box.label.set(_node_label((kind, name)))
                    box.value.set(path in picked)
                else:
                    self._multi_paths[index] = ''
                    slot.visible.set(False)
                    box.label.set('')
                    box.value.set(False)

    def _on_multi_toggled(self, index: int) -> None:
        if self._syncing:
            return
        path = self._multi_paths[index]
        if not path:
            return
        picked = list(self.multi_selected.get())
        if self._multi_boxes[index]['value']:
            if path not in picked:
                picked.append(path)
        elif path in picked:
            picked.remove(path)
        self.multi_selected.set(picked)

    def _add_to_bucket(self, path: str) -> None:
        picked = list(self.bucket.get())
        if path in picked or len(picked) >= _MAX_SLOTS:
            return
        picked.append(path)
        with sc.updating():
            self.bucket.set(picked)
            self._fill_bucket_slots(picked)

    def _on_bucket_removed(self, index: int) -> None:
        picked = list(self.bucket.get())
        if not (0 <= index < len(picked)):
            return
        picked.pop(index)
        with sc.updating():
            self.bucket.set(picked)
            self._fill_bucket_slots(picked)

    def _fill_bucket_slots(self, picked: list) -> None:
        root = self._nav.start_directory
        with sc.updating():
            for index in range(_MAX_SLOTS):
                slot = self._bucket_slots[index]
                txt = self._bucket_texts[index]
                if index < len(picked):
                    slot.visible.set(True)
                    txt.text.set(_bucket_label(picked[index], root))
                else:
                    slot.visible.set(False)
                    txt.text.set('')


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
