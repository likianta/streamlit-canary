"""
░█▀▀░▀█▀░█▀▄░█▀▀░█▀█░█▄█░█░░░▀█▀░▀█▀░░░░░█▀▀░█▀█░█▀█░█▀█░█▀▄░█░█
░▀▀█░░█░░█▀▄░█▀▀░█▀█░█░█░█░░░░█░░░█░░▄▄▄░█░░░█▀█░█░█░█▀█░█▀▄░░█░
░▀▀▀░░▀░░▀░▀░▀▀▀░▀░▀░▀░▀░▀▀▀░▀▀▀░░▀░░░░░░▀▀▀░▀░▀░▀░▀░▀░▀░▀░▀░░▀
"""

# fmt: off
if 1: import neoprint as _np; _np.setup()  # noqa
# fmt: on

# from . import components
from . import components_v2 as v2
from . import components_v3 as v3
from . import keygen
from . import opener
from . import session
from .components import *
from .compositor import Compositor
from .event_loop import event_loop
from .flow import post_events
from .kernel import Property
from .kernel import Signal
from .kernel import StateV2
from .kernel import _self
from .kernel import _undefined
from .kernel import _value
from .kernel import bind
from .keygen import generate_keygen
from .opener import open_file
from .opener import open_folder
from .page import pages
from .runner import kill
from .runtime import add_watch_file
from .runtime import add_watch_folder
from .runtime import run
from .runtime import set_page_config
from .session import dump_state
from .session import init_shared_data
from .session import init_state
from .session import init_state as get_state
from .session import init_state_v2
from .session import is_session_init
from .session import shared_data
from .text import *

__version__ = '0.4.0'
