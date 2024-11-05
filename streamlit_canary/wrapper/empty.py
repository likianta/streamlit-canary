import streamlit as st

from ..compositor import Compositor


class Empty(Compositor):
    def compose(self) -> None:
        self.item = st.empty()
