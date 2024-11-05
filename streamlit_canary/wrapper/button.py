import streamlit as st

from lk_utils import Signal
from ..compositor import Compositor
from ..flow import post_events


class Button(Compositor):
    on_click: Signal
    
    def compose(self, label: str) -> None:
        self.on_click = Signal()
        # self.value = st.button(label, on_click=self.on_click.emit)
        self.value = st.button(
            label, on_click=lambda: post_events.append(self.on_click.emit)
        )

    # def on_click(self):
    #     post_events.append(func)
