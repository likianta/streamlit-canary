from functools import partial

import streamlit as st

card = bordered_container = partial(st.container, border=True)
