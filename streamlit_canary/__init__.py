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
from . import legacy_streamlit_wrappers as legacy
from . import opener
from .components import *
from .kernel import Property
from .kernel import Signal
from .kernel import State
from .kernel import _self
from .kernel import _undefined
from .kernel import _value
from .kernel import bbind
from .kernel import bind
from .kernel import pending_updates
from .opener import open_file
from .opener import open_folder
from .runner import run
from .runtime import add_watch_file
from .runtime import add_watch_folder
from .runtime import set_page_config
from .runtime import toast
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
