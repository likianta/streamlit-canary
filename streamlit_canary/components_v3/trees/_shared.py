"""Shared pieces of the tree family: the nav model, the listing, the
two nav groups and the small helpers the panels are built from.
"""

import os
import typing as tp
from collections import deque

from lk_utils import fs

from ..inputs import CheckGroup
from ..inputs import RadioGroup
from ...kernel import Signal


class T:
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    NodeType = tp.Literal['file', 'folder']
    SelectionMode = tp.Literal['single', 'multiple', 'multicross']


_DRIVES: tp.Optional[tp.Tuple[str, ...]] = None
"""Every drive root on this machine, once `_list_drives` has looked."""


def _path_chain(path: str) -> tp.List[str]:
    """Every ancestor of `path`, itself included, outermost first.

    `C:/x/y` -> `['C:/', 'C:/x', 'C:/x/y']`; `/x/y` -> `['/', '/x', '/x/y']`.
    This is the ladder v1 built for the browse dialog's "Current location"
    selectbox (`start_directory.split('/')`, accumulated), which is what makes
    every ancestor reachable in one jump.
    """
    if not path:
        return []
    parts = fs.abspath(path).split('/')
    out = [parts[0] + '/']
    acc = out[0]
    for part in parts[1:]:
        if not part:
            continue
        acc += part
        out.append(acc)
        acc += '/'
    return out


def _list_drives() -> tp.Tuple[str, ...]:
    """Every drive root on this machine, e.g. `('C:/', 'D:/')`.

    Cached in `_DRIVES` on first use: a drive letter does not come and go
    while the app runs, and finding them is a syscall each time.  Empty where
    there are no drive letters (a POSIX system) -- the path chain there
    already starts at the only root, `/`.
    """
    global _DRIVES
    if _DRIVES is None:
        lister = getattr(os, 'listdrives', None)  # windows only
        try:
            roots = lister() if lister else ()
        except OSError:
            roots = ()
        _DRIVES = tuple(fs.abspath(root) + '/' for root in roots)
    return _DRIVES


def _location_options(directory: str) -> tp.List[str]:
    """The ladder the location bar offers: the other drives, then the chain.

    `['C:/', 'D:/', 'E:/', 'C:/A', 'C:/A/B', 'C:/A/B/C']` for `C:/A/B/C`:
    every ancestor (`_path_chain`), so any parent stays one pick away, with
    the rest of the machine's drives in front of them, so another drive is
    reachable without typing it out.  The chain's own root is already in the
    drive list, so it is not repeated.
    """
    chain = _path_chain(directory)
    drives = list(_list_drives())
    return drives + [rung for rung in chain if rung not in drives]


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
        return ':orange[:material/folder:] .. :gray[(goto parent)]'
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
        self.start_directory = fs.abspath(start_directory or os.getcwd())
        self.directory = self.start_directory
        self.parent_to_dirnames: dict[str, tp.List[str]] = {}
        self.parent_to_filenames: dict[str, tp.List[str]] = {}
        self.recent: deque = deque(maxlen=20)
        # the row a node last had in its parent's listing, remembered for
        # every folder that was listed: walking back up reads it to highlight
        # the row it came from (see `TreeSelect._focus_index`)
        self.node_index: dict[str, int] = {}

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


def _is_under(path: str, folder: str) -> bool:
    """Whether `path` is a strict descendant of `folder` (a folder path)."""
    return path.startswith(folder.rstrip('/') + '/')


def _as_picked(value: tp.Any) -> list:
    """`TreeSelect.value` as a list of paths (the multi modes' shape)."""
    if isinstance(value, list):
        return list(value)
    return [value] if value else []


def _bucket_text(value: tp.Any) -> str:
    """The bucket trigger's label: a bucket icon plus how many are in it."""
    return ':material/bucket_check: {}'.format(len(_as_picked(value)))


def _check_initial_mode(mode: tp.Optional[str], modes: tuple) -> str:
    """Settle which of `modes` a panel opens in.

    Left out, it is the first entry of `selection_mode`. A mode the panel
    no longer offers falls back to that first entry rather than raising: an
    `initial_mode` is a *preference*, and the usual caller hands back what
    was saved last time (see `TreeSelect(initial_mode=)`) -- a panel whose
    `selection_mode` has since changed should open, not refuse to start.
    """
    if mode is None or mode not in modes:
        return modes[0]
    return mode


def _check_selection_mode(mode: tp.Union[str, tp.Iterable[str]]) -> tuple:
    """Normalize a `selection_mode` keyword into the modes to offer.

    A lone literal (the usual case) becomes a one-element tuple, so the rest
    of the class only ever deals with a tuple: the first entry is the mode
    the panel starts in (`initial_mode` overrides that), and more than one
    entry gets the segmented control that switches between them. Repeats are
    dropped, order is kept.
    """
    modes = (mode,) if isinstance(mode, str) else tuple(mode)
    if not modes:
        raise ValueError('selection_mode must name at least one mode')
    for one in modes:
        if one not in _MODES:
            raise ValueError(
                'selection_mode must be one of {}, or a tuple of them, '
                'got {!r}'.format(', '.join(repr(m) for m in _MODES), mode)
            )
    return tuple(dict.fromkeys(modes))


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
