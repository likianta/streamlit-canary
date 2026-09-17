"""Tree-style file selectors (v3).

Two symmetric pairs.  Each one splits a browser *panel* from the "input +
panel" wrapper that drives it:

    TreeSelect / TreeSelectWithInput
        the single-pane browser -- a folder listing that navigates itself
        (its toolbar only carries refresh / bucket / mode) -- plus a path
        input whose "Browse" trigger opens the panel in a `Popover`.

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
from ..kernel import bind
from .base import Width
from .widgets import Button
from .widgets import Caption
from .widgets import CheckGroup
from .widgets import Column
from .widgets import Dialog
from .widgets import FloatingContainer
from .widgets import IconButton
from .widgets import Info
from .widgets import Popover
from .widgets import RadioGroup
from .widgets import ReducibleGroup
from .widgets import Row
from .widgets import SegmentedControl
from .widgets import Selectbox
from .widgets import Text
from .widgets import TextInput


class T:
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    NodeType = tp.Literal['file', 'folder']


def _norm(path: str) -> str:
    return fs.abspath(path).replace('\\', '/')


def _path_chain(path: str) -> tp.List[str]:
    """Every ancestor of `path`, itself included, outermost first.

    `C:/x/y` -> `['C:/', 'C:/x', 'C:/x/y']`; `/x/y` -> `['/', '/x', '/x/y']`.
    This is the ladder v1 built for the browse dialog's "Current location"
    selectbox (`start_directory.split('/')`, accumulated), which is what makes
    every ancestor reachable in one jump.
    """
    if not path:
        return []
    parts = _norm(path).split('/')
    out = [parts[0] + '/']
    acc = out[0]
    for part in parts[1:]:
        if not part:
            continue
        acc += part
        out.append(acc)
        acc += '/'
    return out


def _filter_func(filter: T.Filter) -> tp.Callable[[str], bool]:
    """`'.txt'` / `('.txt', '.csv')` -> a name predicate (`None` keeps all)."""
    if not filter:
        return lambda _name: True
    return lambda name: name.endswith(filter)


NAV_UP = '..'
"""A listing row standing for the parent folder."""

NAV_HERE = '.'
"""A listing row standing for the current folder. Picking it sets that folder
as the value instead of moving -- v1's "This folder" entry. `option_path`
resolves it to the folder itself, so it is a real node."""


def entry_label(option: tp.Any) -> str:
    """Render a listing row: `'..'` / `'.'` / `'<name>/'` / `'<name>'`.

    Folders carry a trailing `'/'` (see `listing_options`); the two nav rows
    get an orange folder icon plus a gray hint, so they read as actions rather
    than as nodes.
    """
    name = str(option)
    if name == NAV_UP:
        return ':orange[:material/folder:] .. :gray[goto parent]'
    if name == NAV_HERE:
        return ':orange[:material/folder:] . :gray[(this folder)]'
    escaped = name.replace('__', '\\_\\_')
    if escaped.endswith('/'):
        return ':material/folder: {}'.format(escaped)
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


def listing_options(nav: _TreeNav, keeps: tp.Callable[[str], bool]) -> list:
    """The rows of a folder listing: the nav rows, folders, then files.

    Folders carry a trailing `'/'`, files do not.  The two leading rows are
    the whole navigation now that the toolbar's arrows are gone: `'..'` moves
    up and `'.'` picks the current folder, both in a single click.
    """
    options = [NAV_UP, NAV_HERE]
    options += [name + '/' for name in nav.dirnames()]
    options += [name for name in nav.filenames() if keeps(name)]
    return options


def option_path(nav: _TreeNav, option: tp.Any) -> str:
    """The absolute path a listing row stands for.

    `..` is a pure action, not a node, so it maps to `''`; `.` stands for the
    current folder, so ticking it picks that folder (v1's "This folder").
    """
    name = str(option)
    if name == NAV_UP:
        return ''
    if name == NAV_HERE:
        return nav.directory
    if name.endswith('/'):
        return nav.child(name[:-1])
    return nav.child(name)


_MODE_SINGLE = 'single'
_MODE_MULTIPLE = 'multiple'
_MODE_MULTICROSS = 'multicross'
_MODE_ANY = 'any'

_MODES = (_MODE_SINGLE, _MODE_MULTIPLE, _MODE_MULTICROSS)

_MODE_LABELS = {
    _MODE_SINGLE: 'Single select',
    _MODE_MULTIPLE: 'Multi select',
    _MODE_MULTICROSS: 'Multi-cross select',
}


def _as_picked(value: tp.Any) -> list:
    """`TreeSelect.value` as a list of paths (the multi modes' shape)."""
    if isinstance(value, list):
        return list(value)
    return [value] if value else []


def _bucket_text(value: tp.Any) -> str:
    """The bucket trigger's label: a bucket icon plus how many are in it."""
    return ':material/bucket_check: {}'.format(len(_as_picked(value)))


def _check_select_mode(mode: str) -> str:
    """Validate a `select_mode` keyword."""
    if mode not in _MODES + (_MODE_ANY,):
        raise ValueError(
            'select_mode must be one of {}, got {!r}'.format(
                ', '.join(repr(m) for m in _MODES + (_MODE_ANY,)), mode
            )
        )
    return mode


def _empty_value(mode: str) -> tp.Any:
    """`''` when a mode picks one node, `[]` when it picks several."""
    return '' if mode == _MODE_SINGLE else []


def _is_multi(mode: str) -> bool:
    return mode != _MODE_SINGLE


def _is_multicross(mode: str) -> bool:
    return mode == _MODE_MULTICROSS


def _is_single(mode: str) -> bool:
    return mode == _MODE_SINGLE


def bucket_label(path: str, root: str) -> str:
    """Show a bucketed path relative to the tree's starting folder."""
    prefix = root.rstrip('/') + '/'
    short = path[len(prefix) :] if path.startswith(prefix) else path
    return entry_label(short + '/' if fs.isdir(path) else short)


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
        candidates: the box's suggestions (bindable); see `TextInput`.
            `TreeSelectWithInput` fills it with the ancestors of the folder
            being browsed -- that is what gives `PathInput` its dropdown.

    Properties:
        path: str — the resolved absolute path ('' when it does not exist).
            Setting it re-writes the text, so callers can push a picked path
            into the box without touching the input directly.
        candidates: list[str] | None — the box's dropdown suggestions.

    Signals:
        on_path (via `box['on_path']` or `box.path.on_change`)
        on_submit: emitted whenever the committed text changes, i.e. the box
            was submitted (blur / Enter). Refresh anything derived from the
            text -- a candidate list, say -- from here.
    """

    def __init__(
        self,
        label: str = '',
        value: str = '',
        *,
        width: Width | None = None,
        candidates: tp.Iterable[str] | Property | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        self.path = Property('')
        self.on_submit: Signal = Signal()
        if candidates is None or isinstance(candidates, Property):
            source: tp.Any = candidates
        else:
            # materialize, so a one-shot iterable does not go stale
            source = list(candidates)
        self.candidates = Property(tp.cast(tp.Optional[tp.List[str]], None))
        self.candidates.set_or_bind(source)
        with self:
            self._input = TextInput(
                label, value=value, width='stretch', candidates=self.candidates
            )

        @self._input.value.on_change
        def _validate() -> None:
            self.path.set(self._resolve(str(self._input['value'])))
            self.on_submit.emit()

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
    """The single-pane tree browser: a folder listing that navigates itself.

        with Popover('Browse', panel_align='row', panel_max_height=500):
            tree = v3.TreeSelect(filter='.txt')
        ...
        picked = tree.value.get()

    Layout::

        [                ] [refresh] [bucket] [mode]  <- floats top-right
        /current/folder
        ..  (goto parent)
        .   (this folder)
        subfolder/
        another-file.txt                 <- scrolls past `height` px
                                         [ Confirm ]  <- floats bottom-right

    The toolbar and the Confirm button ride in `FloatingContainer`s, so they
    stay put in their corners of the panel while the listing scrolls beneath
    them -- and, being sticky, they keep their place in the flow, so no row
    can end up hidden under either one for good.

    No arrow toolbar: every row is a click target, and what a click does
    depends on the row --

        `..`        move to the parent folder
        `.`         stay put, and take the current folder
        `name/`     enter that subfolder
        `name`      take that file

    -- so one click moves in either direction.  In the multi modes a row shows
    a box as well: the box ticks the node while its body acts on it (a
    folder's body enters it, a file's body ticks it).

    `select_mode` settles how much may be picked at once (see `value`); only
    `'multicross'` (or `'any'`) draws the bucket, and only `'any'` draws the
    segmented control that switches between the three.

    Args:
        start_directory: the folder to open (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        height: optional cap in px on the listing, after which it scrolls.
            Left `None` when an enclosing `Popover` does the scrolling.
        width: see `Column`.
        select_mode: `'single'` (one node, the default), `'multiple'` (nodes
            of the folder being browsed -- leaving it drops them),
            `'multicross'` (nodes gathered across folders into a bucket), or
            `'any'` (all three, switched from a segmented control).

    Properties:
        value: str | list[str] — the selection. `single` keeps one path (`''`
            while nothing is picked); the multi modes keep a list of paths --
            `multiple` holds the folder being browsed, `multicross` holds the
            whole bucket. Prefer `select` / `clear` over writing it: those
            keep the listing in step.
        mode: str — the active mode (never `'any'`).

    Signals:
        on_value (via `tree['on_value']` or `tree.value.on_change`)
        on_navigate: emitted with the new folder every time the listing is
            refreshed -- a row click, a `_goto` from a wrapper, or the initial
            build. Anything derived from the current folder (a path input's
            candidate list, say) should be refreshed from here.
        on_submit: emitted when the Confirm button in the bottom-right corner
            is clicked. A wrapper such as `TreeSelectWithInput` listens for it
            to dismiss the popover it opened.

    Call `reload()` to re-read the folder from disk, `select(path)` to add a
    path that is not in the listing, and `clear()` to drop the selection.
    """

    def __init__(
        self,
        start_directory: str = '',
        *,
        filter: T.Filter = None,
        height: int | None = None,
        width: Width | None = None,
        select_mode: str = _MODE_SINGLE,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        select_mode = _check_select_mode(select_mode)
        initial_mode = select_mode if select_mode in _MODES else _MODE_SINGLE
        keeps = _filter_func(filter)
        nav = _TreeNav(start_directory)
        self._nav = nav
        self._keeps = keeps
        self._select_mode = select_mode
        # guards every pick handler while the listing is rebuilt: re-listing
        # swaps `options`, which resets `focused_index` and makes a radio fall
        # back to another row
        self._syncing = False

        self.value = Property(
            tp.cast(tp.Union[str, tp.List[str]], _empty_value(initial_mode))
        )
        self.mode = Property(initial_mode)
        self.on_navigate: Signal = Signal(str)
        self.on_submit: Signal = Signal()

        # only the modes that can cross folders get a bucket, and only `any`
        # gets the control that switches between them -- so `single` and
        # `multiple` build neither
        crosses = select_mode in (_MODE_MULTICROSS, _MODE_ANY)
        switchable = select_mode == _MODE_ANY

        with self:
            # The toolbar floats in the panel's top-right corner, so it stays
            # reachable while the listing scrolls. Its own right edge is
            # `align-self: flex-end` (see `.st-floating`); no `Space` needed.
            with FloatingContainer('top-right'):
                self._refresh_btn = IconButton('refresh', help='Refresh')
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
                    self._mode_control = SegmentedControl(
                        'Selection mode',
                        options=_MODES,
                        value=initial_mode,
                        format=lambda m: _MODE_LABELS[m],
                        label_visibility='collapsed',
                    )
            self._location = Caption(_location_label(nav.directory))
            with Column(visible=bind(self.mode, _is_single)):
                self._single_list = RadioGroup(
                    'Folder contents',
                    options=(),
                    format=entry_label,
                    label_visibility='collapsed',
                    max_height=height,
                )
            with Column(visible=bind(self.mode, _is_multi)):
                self._multi_list = CheckGroup(
                    'Folder contents',
                    options=(),
                    format=entry_label,
                    full_body_click=False,
                    label_visibility='collapsed',
                    max_height=height,
                )
            # A Confirm button floats in the bottom-right corner. It is the
            # panel's "done" action: a wrapper hooks `on_submit` to fold the
            # popover away (the panel itself must not know about its parent).
            with FloatingContainer('bottom-right'):
                self._confirm_btn = Button('Confirm', type='primary')

        # -- handlers -------------------------------------------------------

        @self._single_list.value.on_change
        def _on_single_pick() -> None:
            # clicking a row *is* the navigation here; the radio's selection is
            # only a signal, so it never carries the picked node itself
            if self._syncing:
                return
            option = str(self._single_list.value.get())
            if not option:
                return
            if option == NAV_UP:
                self._jump(self._nav.parent_of())
            elif option == NAV_HERE:
                self.value.set(self._nav.directory)
            elif option.endswith('/'):
                self._jump(self._nav.child(option[:-1]))
            else:
                self.value.set(self._nav.child(option))

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

        @self._multi_list.focused_index.on_change
        def _on_multi_body_click() -> None:
            self._activate_focused()

        @self._refresh_btn.on_click
        def _on_refresh() -> None:
            self.reload()

        @self._confirm_btn.on_click
        def _on_confirm() -> None:
            self.on_submit.emit()

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

    def reload(self) -> None:
        """Re-read the current folder from disk and refresh the listing."""
        self._nav.reload()
        self._refresh_listing()

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

    def _activate_focused(self) -> None:
        """Act on the row whose *body* was clicked in a multi mode.

        The box ticks (`full_body_click=False`); the body instead moves the
        panel when the row is a folder (or `..`), and ticks it when the row is
        a file (or `.`, "this folder"). The row is highlighted client-side
        either way.
        """
        if self._syncing:
            return
        options = list(self._multi_list.options.get() or ())
        index = self._multi_list.focused_index.get()
        if not (isinstance(index, int) and 0 <= index < len(options)):
            return
        option = str(options[index])
        if option == NAV_UP:
            self._jump(self._nav.parent_of())
        elif option.endswith('/'):
            self._jump(self._nav.child(option[:-1]))
        elif option:
            # a file (or `.`): highlight plus tick
            ticked = list(self._multi_list.value.get() or ())
            if option not in ticked:
                self._multi_list.value.set(ticked + [option])

    def _goto(self, directory: str) -> None:
        """Point the panel at a folder and re-list it (used by the wrappers)."""
        directory = _norm(directory) if directory else ''
        if directory and fs.isdir(directory):
            self._nav.directory = directory
        self._refresh_listing()

    def _jump(self, directory: str) -> None:
        """Move the panel into `directory` and re-list it.

        `multiple` drops its picks on the way out -- they belong to the folder
        being left. `multicross` keeps the bucket, which is the whole point of
        crossing folders, and `single` keeps the picked path.
        """
        if self.mode.get() == _MODE_MULTIPLE:
            self.value.set([])
        self._nav.directory = directory
        self._refresh_listing()

    def _listed_paths(self) -> set:
        """The absolute paths of every node the listing currently shows."""
        nav = self._nav
        options = self._multi_list.options.get() or ()
        return {p for p in (option_path(nav, o) for o in options) if p}

    def _refresh_listing(self) -> None:
        nav = self._nav
        options = listing_options(nav, self._keeps)
        picked = set(_as_picked(self.value.get()))
        self._syncing = True
        try:
            self._single_list.options.set(options)
            self._multi_list.options.set(options)
            # the radio's selection doubles as the click signal, so a fresh
            # listing starts with nothing (and never a nav row) selected --
            # otherwise clicking the pre-selected row would not register
            self._single_list.value.set('')
            # the check group re-ticks what was picked before, so walking back
            # into a folder shows its ticks again
            self._multi_list.value.set(
                [o for o in options if option_path(nav, o) in picked]
            )
        finally:
            self._syncing = False
        self._location.text.set(_location_label(nav.directory))
        self.on_navigate.emit(nav.directory)

    def _set_mode(self, mode: str) -> None:
        """Switch the active mode (only `select_mode='any'` allows this)."""
        if mode not in _MODES or mode == self.mode.get():
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

        [ path input .................. v ] [ Recent ] [ Browse v ]
        +-- "Browse" popover (spans the header row) ------------------+
        |                  [refresh] [bucket] [mode] <- floats top    |
        | /current/folder                                             |
        | ..        (goto parent)                                     |
        | .         (this folder)                                     |
        | subfolder/                                                  |
        | another-file.txt              <- scrolls past `height` px   |
        |                              [ Confirm ]   <- floats bottom |
        +-------------------------------------------------------------+

    The panel is a `TreeSelect`; the popover stretches it from the path
    input's left edge to the header row's right edge.  The panel navigates by
    clicking a row (no arrows); its toolbar -- refresh, plus the bucket and
    the mode control when `select_mode` calls for them -- floats in the
    top-right corner, and its Confirm button in the bottom-right one, so both
    stay reachable while the listing scrolls.  Confirm folds this popover away
    (through `TreeSelect.on_submit`).

    The path input also carries a candidate dropdown: every ancestor of the
    folder the panel shows, so any parent is one pick away. It follows the
    panel -- a row jump or a submitted path refreshes it (see
    `_refresh_candidates`).

    Typing (or picking) a folder points the panel there; a file joins the
    panel's selection.  The selection survives browsing -- `clear()` drops it.

    Args:
        label: the path input's label.
        initial_path: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        height: max height of the "Browse" panel in px (default 500).
        width: see `Column`.
        select_mode: how the panel lets nodes be picked -- see `TreeSelect`.

    Properties:
        value: str | list[str] — the panel's selection; this mirrors
            `TreeSelect.value`, so `'single'` holds one path and the multi
            modes hold a list. Write through the panel (`select` / `clear`).
        mode: str — the panel's active mode (mirrors `TreeSelect.mode`).

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
        select_mode: str = _MODE_SINGLE,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        first_path = initial_path or os.getcwd()
        initial_is_file = bool(initial_path) and fs.isfile(first_path)
        nav = _TreeNav(fs.parent(first_path) if initial_is_file else first_path)
        self._nav = nav
        self._keeps = _filter_func(filter)
        self._show_recent = show_recent

        # `value` / `mode` mirror the panel's, so a caller reads the selection
        # right here; writes go through the panel (`select` / `clear`).
        self.value = Property(tp.cast(tp.Union[str, tp.List[str]], ''))
        self.mode = Property(_MODE_SINGLE)
        self._has_recent = Property(False)

        with self:
            with Row('bottom'):
                # `candidates` starts empty, so the caret is drawn (disabled)
                # from the first paint and only its contents change later.
                self._path_input = PathInput(label, first_path, candidates=[])
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
                        select_mode=select_mode,
                    )
        self.value.bind(self._tree.value)
        self.mode.bind(self._tree.mode)

        if initial_is_file:
            self._tree.select(_norm(first_path))
            nav.remember(_norm(first_path))

        # -- handlers -------------------------------------------------------

        @self._path_input.path.on_change
        def _on_path_typed() -> None:
            self._commit(self._path_input.path.get())

        @self._recent.value.on_change
        def _on_recent_picked() -> None:
            self._commit(str(self._recent['value']))

        @self._tree.value.on_change
        def _on_panel_picked() -> None:
            # the panel's picks feed "Recent" (a tick is a pick too)
            for path in _as_picked(self._tree.value.get()):
                self._nav.remember(path)
            self._refresh_recent()

        @self._path_input.on_submit
        def _on_path_submitted() -> None:
            self._refresh_candidates()

        @self._tree.on_navigate
        def _on_tree_navigated(directory: str) -> None:
            # the panel drives the folder, so mirror it onto our own nav --
            # that is what `_refresh_candidates` reads
            self._nav.directory = directory
            self._refresh_candidates()

        @self._tree.on_submit
        def _on_tree_submitted() -> None:
            # the panel's Confirm is a "done" action: fold the popover away
            # (the panel has no idea it lives in one; we own it, so we close
            # it). The pick itself already sits in `_tree.value`, which
            # `value` mirrors.
            self._browse_popover.close()

        self._refresh_recent()
        self._refresh_candidates()

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Drop the panel's selection (see `TreeSelect.clear`)."""
        self._tree.clear()

    def reload(self) -> None:
        """Re-read the browsed folder from disk (same as the panel's button)."""
        self._tree.reload()

    # -- internals ----------------------------------------------------------

    def _refresh_candidates(self) -> None:
        """Offer every ancestor of the current folder in the path input.

        The dropdown is a jump list: picking an entry puts that folder's path
        into the box, which `_commit` then resolves. Callers that drive the
        panel themselves (instead of through `TreeSelect`) re-run this after
        moving the folder.
        """
        self._path_input.candidates.set(_path_chain(self._nav.directory))

    def _commit(self, path: str) -> None:
        """Resolve a typed / picked path into a selection or a jump.

        A folder moves the panel there -- so picking an ancestor candidate
        navigates, the way v1's "Current location" selectbox did -- while a
        file joins the panel's selection (`single` replaces it, the multi
        modes add it).
        """
        path = path.strip()
        if not path:
            self._tree.clear()
            return
        path = _norm(path)
        if not fs.exist(path):
            # A half-typed path is not an error, just not a value yet.
            self._tree.clear()
            return
        self._path_input.path.set(path)
        if fs.isdir(path):
            self._tree._goto(path)
        else:
            self._tree.select(path)
            self._nav.remember(path)
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
