from functools import partial

import streamlit as st

long_button = partial(st.button, width='stretch')
