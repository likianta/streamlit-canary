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

from .buttons import Button
from .buttons import IconButton

from .inputs import CheckGroup
from .inputs import RadioGroup
from .inputs import ReducibleGroup
from .inputs import SegmentedControl
from .inputs import Selectbox
from .inputs import TextInput

from .layouts import Column
from .layouts import Dialog
from .layouts import FloatingContainer
from .layouts import Popover
from .layouts import Row

from .status import Info

from .texts import Text


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
"""A listing row standing for the parent folder. It is a place to go, not a
node to pick, so `_is_nav_up` freezes its box; and the click that a frozen box
leaves over goes to the row itself -- `_NavigationGroup`'s `body_opens` turns
it into the walk-up gesture, which is why `..` carries no "enter" arrow."""


def entry_label(option: tp.Any) -> str:
    """Render a listing row: `'..'` / `'<name>/'` / `'<name>'`.

    Folders carry a trailing `'/'` (see `listing_options`); the nav row gets
    an orange folder icon plus a gray hint, so it reads as an action rather
    than as a node.
    """
    name = str(option)
    if name == NAV_UP:
        return ':orange[:material/folder:] .. :gray[goto parent]'
    escaped = name.replace('__', '\\_\\_')
    if escaped.endswith('/'):
        return ':material/folder: {}'.format(escaped)
    return ':material/description: {}'.format(escaped)


def _path_label(path: str) -> str:
    """A folder path as selectbox text (`__` is escaped for markdown)."""
    return path.replace('__', '\\_\\_')


def _call(hook: tp.Optional[tp.Callable]) -> None:
    """Run a v1-style `custom` builder hook, if given."""
    if hook is not None:
        hook()


class _NavigationGroup:
    """Mixin: a listing whose folder rows carry an "enter" arrow.

    `TreeSelect` needs two gestures on one row: a single click on the row body
    ticks / picks it -- the box's own label wraps the whole row, so the
    browser does that by itself -- while a folder floats a small `->` just
    right of its text once the pointer is over the row. 32px of clearance, not
    the row's own 8px `gap`: the extra air keeps the tick area (box + name)
    from crowding the arrow. The text underlines while the pointer rests on
    that arrow, so the pair reads as one link, and clicking it walks into the
    folder. The arrow answers over a little slack to its right as well: the
    whole icon plus 30px counts as the arrow for hovering *and* clicking,
    since the pointer has to be aimed at a 20px glyph otherwise. Past that
    the far right of the row still belongs to the row itself.

    A row whose box is frozen (`box_disabled`) has no tick to give, so its own
    click is free to be the gesture: `body_opens` marks those rows, and a
    click anywhere on them walks in exactly like the arrow would. That is what
    `..` uses -- it is a place, not a node, and an arrow on top of that would
    only clutter a row that has nothing else to do.

    The arrow is deliberately *not* a `CheckGroup` feature: it is opinionated
    about what a row means -- a folder, a place to go -- which is
    `TreeSelect`'s business rather than a widget's. Hence these subclasses,
    which only `TreeSelect` builds, plus the other half of the contract in
    `render.py` (`_row_enter_html`, and the `navigable` / `body_opens` index
    lists an `options` patch carries for the JS rebuild).

    Args:
        navigable: marks the options that stand for a folder, and so draw the
            arrow (see `_is_enterable`).
        body_opens: marks the options a click on the row itself walks into,
            with no arrow involved (see `_is_nav_up`).

    Signals:
        on_open (via `group.on_open`) — a row was entered, through its arrow
            or, for a `body_opens` row, through the click on the row itself;
            the payload is the row index. The gesture is its own event, so
            walking into a folder never doubles as a tick of that row.
    """

    def __init__(
        self,
        *args: tp.Any,
        navigable: tp.Callable[[tp.Any], bool] | None = None,
        body_opens: tp.Callable[[tp.Any], bool] | None = None,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.on_open: Signal = Signal(int)
        self._navigable = navigable
        self._body_opens = body_opens

    def _on_open(self, value: tp.Any) -> None:
        """Relay a row's "enter" arrow to `on_open` (see `scOpenRow`)."""
        try:
            index = int(value)
        except (TypeError, ValueError):
            return
        self.on_open.emit(index)


class _NavCheckGroup(_NavigationGroup, CheckGroup):
    """A `CheckGroup` whose folder rows carry the "enter" arrow."""


class _NavRadioGroup(_NavigationGroup, RadioGroup):
    """A `RadioGroup` whose folder rows carry the "enter" arrow."""


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
    """The rows of a folder listing: the nav row, folders, then files.

    Folders carry a trailing `'/'`, files do not.  `'..'` leads the listing:
    it is the way back up, and a single click on its body walks there -- its
    box is frozen, so the click has nothing else to do (see `_is_nav_up`).
    """
    options = [NAV_UP]
    options += [name + '/' for name in nav.dirnames()]
    options += [name for name in nav.filenames() if keeps(name)]
    return options


def option_path(nav: _TreeNav, option: tp.Any) -> str:
    """The absolute path a listing row stands for.

    `..` is a pure action, not a node, so it maps to `''`.
    """
    name = str(option)
    if name == NAV_UP:
        return ''
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


def _is_enterable(option: tp.Any) -> bool:
    """Whether a listing row carries the "enter" arrow: a folder, and only a
    folder.

    A file opens nowhere, so it gets no arrow.  `..` gets none either: it is
    entered by clicking its own body (`_is_nav_up`), and it is already the
    row a pointer reaches for, so an arrow would only add noise.
    """
    return str(option).endswith('/')


def _is_nav_up(option: tp.Any) -> bool:
    """`..` is a pure navigation target -- never a node to tick.

    It drives two things at once: the frozen box (nothing to tick, drawn
    dimmed) and the body click that walks up (`body_opens`).
    """
    return str(option) == NAV_UP


def _as_picked(value: tp.Any) -> list:
    """`TreeSelect.value` as a list of paths (the multi modes' shape)."""
    if isinstance(value, list):
        return list(value)
    return [value] if value else []


def _bucket_text(value: tp.Any) -> str:
    """The bucket trigger's label: a bucket icon plus how many are in it."""
    return ':material/bucket_check: {}'.format(len(_as_picked(value)))


def _check_selection_mode(mode: str) -> str:
    """Validate a `selection_mode` keyword."""
    if mode not in _MODES + (_MODE_ANY,):
        raise ValueError(
            'selection_mode must be one of {}, got {!r}'.format(
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
            `None` (the default) draws no caret -- a plain text box.

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
        # The radio runs its own `_auto_select` whenever the list changes,
        # which takes the first entry. That is a list refresh, not a pick --
        # but it looks exactly like one to `_sync_value`, and a listener
        # treating it as a pick would move the panel. So remember the entry
        # the radio is about to take on its own.
        self._adopting = ''
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
            # same test as `_auto_select`, so the guess below is exact
            if options_ and self._radio['value'] not in options_:
                self._adopting = str(options_[0])
            self._radio.options.set(options_)

        @self._radio.value.on_change
        def _sync_value() -> None:
            picked = str(self._radio['value'])
            if picked and picked == self._adopting:
                self._adopting = ''
                return
            self.value.set(picked)

        if initial:
            self._radio.value.set(initial[0])


class TreeSelect(Column):
    """The single-pane tree browser: a folder listing that navigates itself.

        with Popover('Browse', panel_align='row', panel_max_height=500):
            tree = v3.TreeSelect(filter='.txt')
        ...
        picked = tree.value.get()

    Layout::

        [ /current/folder v ] [refresh] [bucket] [mode]  <- toolbar row
        ..   (goto parent)            <- one click walks up, no arrow
        subfolder/                              ->
        another-file.txt                 <- scrolls past `height` px
                                         [ Confirm ]  <- floats bottom-right

    The toolbar is a row across the top of the panel: a location selectbox
    listing every ancestor of the folder on show -- itself included, so any
    parent is one pick away -- and then the actions.  The Confirm button rides
    in a `FloatingContainer`, so it stays put in the panel's corner while the
    listing scrolls beneath it -- and, being sticky, it keeps its place in the
    flow, so no row can end up hidden under it for good.

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

    `selection_mode` settles how much may be picked at once (see `value`);
    only `'multicross'` (or `'any'`) draws the bucket, and only `'any'` draws
    the segmented control that switches between the three.

    Args:
        start_directory: the folder to open (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        height: optional cap in px on the listing, after which it scrolls.
            Left `None` when an enclosing `Popover` does the scrolling.
        width: see `Column`.
        selection_mode: `'single'` (one node, the default), `'multiple'`
            (nodes of the folder being browsed -- leaving it drops them),
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
            refreshed -- walking into a row (its arrow, or `..`'s own click),
            a `_goto` from a wrapper, or the initial build. Anything derived
            from the current folder (a path input's candidate list, say)
            should be refreshed from here.
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
        selection_mode: str = _MODE_SINGLE,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(width=width, **kwargs)

        selection_mode = _check_selection_mode(selection_mode)
        initial_mode = (
            selection_mode if selection_mode in _MODES else _MODE_SINGLE
        )
        keeps = _filter_func(filter)
        nav = _TreeNav(start_directory)
        self._nav = nav
        self._keeps = keeps
        self._selection_mode = selection_mode
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
        crosses = selection_mode in (_MODE_MULTICROSS, _MODE_ANY)
        switchable = selection_mode == _MODE_ANY

        with self:
            # The toolbar is a row across the panel's top. The location
            # selectbox leads: it lists every ancestor of the folder on show,
            # itself last, so the ladder doubles as "you are here" and any
            # parent is one pick away. It is the only child that stretches, so
            # the row needs no `Space`.
            with Row('center'):
                self._location = Selectbox(
                    'Current location',
                    options=_path_chain(nav.directory),
                    value=nav.directory,
                    format=_path_label,
                    label_visibility='collapsed',
                )
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
            # A Confirm button floats in the bottom-right corner. It is the
            # panel's "done" action: a wrapper hooks `on_submit` to fold the
            # popover away (the panel itself must not know about its parent).
            with FloatingContainer('bottom-right'):
                self._confirm_btn = Button('Confirm', type='primary')

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
        self._syncing = True
        try:
            self._single_list.options.set(options)
            self._multi_list.options.set(options)
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
            self._location.options.set(_path_chain(nav.directory))
        finally:
            self._syncing = False
        self.on_navigate.emit(nav.directory)

    def _set_mode(self, mode: str) -> None:
        """Switch the active mode (only `selection_mode='any'` allows this)."""
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

    Typing (or picking) a folder points the panel there; a file joins the
    panel's selection.  The selection survives browsing -- `clear()` drops it.

    Args:
        label: the path input's label.
        initial_path: the starting file or folder (default: the cwd).
        filter: a suffix (`'.txt'`) or a tuple of suffixes to keep.
        show_recent: keep a "Recent" dropdown of the picked paths.
        height: max height of the "Browse" panel in px (default 500).
        width: see `Column`.
        selection_mode: how the panel lets nodes be picked -- see `TreeSelect`.

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
        selection_mode: str = _MODE_SINGLE,
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
        # set while `_refresh_recent` adopts the newest path into the dropdown:
        # that is a display update, not a pick, so `_commit` must not run
        self._recent_quiet = False

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
                        nav.directory,
                        filter=filter,
                        height=None,
                        selection_mode=selection_mode,
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
        def _on_tree_submitted() -> None:
            # the panel's Confirm is a "done" action: fold the popover away
            # (the panel has no idea it lives in one; we own it, so we close
            # it). The pick itself already sits in `_tree.value`, which
            # `value` mirrors.
            self._browse_popover.close()

        self._refresh_recent()

    # -- public api ---------------------------------------------------------

    def clear(self) -> None:
        """Drop the panel's selection (see `TreeSelect.clear`)."""
        self._tree.clear()

    def reload(self) -> None:
        """Re-read the browsed folder from disk (same as the panel's button)."""
        self._tree.reload()

    # -- internals ----------------------------------------------------------

    def _commit(self, path: str) -> None:
        """Resolve a typed / picked path into a selection or a jump.

        A folder moves the panel there, while a file joins the panel's
        selection (`single` replaces it, the multi modes add it).
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
            # show the newest entry without *picking* it: `_on_recent_picked`
            # runs `_commit`, which navigates for a folder -- and displaying a
            # path in the dropdown is not a pick
            self._recent_quiet = True
            try:
                self._recent.value.set(recent[0])
            finally:
                self._recent_quiet = False


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
        # see `TreeSelectWithInput.__init__` -- here the adopt only re-enters
        # `_commit`, but the guard is the same
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
            # show the newest entry without *picking* it -- see the guard's
            # note in `__init__`
            self._recent_quiet = True
            try:
                self._recent.value.set(recent[0])
            finally:
                self._recent_quiet = False
