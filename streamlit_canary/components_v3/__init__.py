"""
Event-driven (v3) component model.

Pure-Python components used by the event-driven runtime. No Streamlit
dependency here — the frontend bridge is added in a later phase.

The components are grouped into modules the way Streamlit groups its API
reference (the category list is taken from
`references/streamlit_api_reference_categories.html`):

    texts    Streamlit's "Text elements" (`api-reference/text`)
    data     Streamlit's "Data elements" (`api-reference/data`)
    charts   Streamlit's "Chart elements" (`api-reference/charts`)
    buttons  Streamlit's "Input widgets" (`api-reference/widgets`), buttons
    inputs   Streamlit's "Input widgets", the value inputs
    layouts  Streamlit's "Layouts and containers" (`api-reference/layout`)
    status   Streamlit's "Status elements" (`api-reference/status`)

Its "Input widgets" page is broad, so we split it into `buttons` and
`inputs`. `trees` is ours (a folder browser) and keeps its own module;
the private bases the modules share live in `_shared`.
"""

from .base import Component

from .buttons import Button
from .buttons import IconButton
from .buttons import MenuButton

from .charts import AltairChart

from .data import Table

from .inputs import CheckGroup
from .inputs import Checkbox
from .inputs import Multiselect
from .inputs import NumberInput
from .inputs import Radio
from .inputs import RadioGroup
from .inputs import ReducibleGroup
from .inputs import SegmentedControl
from .inputs import SelectSlider
from .inputs import Selectbox
from .inputs import TextArea
from .inputs import TextInput
from .inputs import Toggle

from .layouts import BottomContainer
from .layouts import Cell
from .layouts import Column
from .layouts import Container
from .layouts import Dialog
from .layouts import Expander
from .layouts import Floating
from .layouts import FloatingContainer
from .layouts import Grid
from .layouts import Popover
from .layouts import Row
from .layouts import Space
from .layouts import Tabs

from .status import Callout
from .status import Error
from .status import Info
from .status import Progress
from .status import Spinner
from .status import Success
from .status import Toast
from .status import Warning

from .texts import Caption
from .texts import Code
from .texts import Markdown
from .texts import Text
from .texts import Title

from .trees import TreeSelect
from .trees import TreeSelectDualPane
from .trees import TreeSelectDualPaneWithInput
from .trees import TreeSelectWithInput
