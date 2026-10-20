"""
░█▀▀░▀█▀░█▀▄░█▀▀░█▀█░█▄█░█░░░▀█▀░▀█▀░░░░░█▀▀░█▀█░█▀█░█▀█░█▀▄░█░█
░▀▀█░░█░░█▀▄░█▀▀░█▀█░█░█░█░░░░█░░░█░░▄▄▄░█░░░█▀█░█░█░█▀█░█▀▄░░█░
░▀▀▀░░▀░░▀░▀░▀▀▀░▀░▀░▀░▀░▀▀▀░▀▀▀░░▀░░░░░░▀▀▀░▀░▀░▀░▀░▀░▀░▀░▀░░▀
"""

# fmt: off
if 1: import neoprint as _np; _np.setup()  # noqa
# fmt: on

import typing as tp
import warnings

from . import components
from . import keygen
from . import opener
from . import session
from .components import *
from .event_loop import event_loop
from .kernel import Property
from .kernel import Signal
from .kernel import StateV2
from .kernel import _self
from .kernel import _undefined
from .kernel import _value
from .kernel import bbind
from .kernel import bind
from .kernel import pending_updates
from .keygen import generate_keygen
from .opener import open_file
from .opener import open_folder
from .page import pages
from .runner import legacy_run
from .runner import run
from .runtime import add_watch_file
from .runtime import add_watch_folder
from .runtime import set_page_config
from .runtime import toast
from .session import dump_state
from .session import init_shared_data
from .session import init_state
from .session import init_state as get_state
from .session import init_state_v2
from .session import is_session_init
from .session import shared_data
from .text import blue
from .text import bold
from .text import dim
from .text import gray
from .text import green
from .text import MONOSPACE
from .text import magenta
from .text import orange
from .text import red
from .text import yellow

__version__ = '0.5.0'

# ---------------------------------------------------------------------------
# compatibility
#
# The event-driven components are the API now: they are exported above as
# plain `sc.<Name>`. Two things stay behind for the transition:
#
#   sc.v3.*   still works, but warns -- the prefix goes away in a later
#             release;
#   the v1 / v2 entries are gone; asking for one raises an AttributeError
#   that says so, instead of a bare "no attribute".
# ---------------------------------------------------------------------------

_V1_NAMES = frozenset({
    'AnyComponent',
    'AnyContainer',
    'anynum_input',
    'card',
    'column',
    'columns',
    'filelist',
    'hex_input',
    'long_button',
    'path_input',
    'progress',
    'radio',
    'row',
    'toggle_button',
    'tree_select',
    'tree_select_dialog',
    'tree_select_with_input',
    'void_column',
    'void_container',
    'void_row',
})


def __getattr__(name: str) -> tp.Any:
    if name == 'v3':
        warnings.warn(
            'sc.v3 is deprecated; the components are now plain `sc.<Name>` '
            '(e.g. `sc.Button`). The `v3.` prefix is dropped in a later '
            'release.',
            DeprecationWarning,
            stacklevel=2,
        )
        return components
    if name == 'v2':
        raise AttributeError(
            'sc.v2 was removed in 0.5.0: the v2 components are gone, and the '
            'event-driven components are the only API now, as plain '
            '`sc.<Name>`.'
        )
    if name in _V1_NAMES:
        raise AttributeError(
            'sc.{0} was removed in 0.5.0: the v1 components are no longer '
            'exported. The event-driven components are plain `sc.<Name>`; '
            'see docs/user-manual/src/components-v1/migration-to-v3.md for '
            'the mapping.'.format(name)
        )
    raise AttributeError(
        'module {!r} has no attribute {!r}'.format(__name__, name)
    )
