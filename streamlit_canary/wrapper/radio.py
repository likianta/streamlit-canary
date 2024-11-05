from functools import partial

import streamlit as st

from lk_utils import Signal
from ..compositor import Compositor
from ..flow import post_events


class Radio(Compositor):
    on_change: Signal[str]
    _key: str
    
    def compose(self, label: str, options: dict):
        self.on_change = Signal()
        self._key = 'radio:{}'.format(label)
        # self._options = options
        st.radio(
            label,
            tuple(options.keys()),
            format_func=lambda x: options[x],
            on_change=self._push_event,
            key=self._key,
        )
        
    @property
    def value(self) -> str:
        return st.session_state[self._key]
    
    def _push_event(self):
        # value = st.session_state[self._key]
        # print(self.value, value, ':v')
        post_events.append(partial(self.on_change.emit, self.value))
