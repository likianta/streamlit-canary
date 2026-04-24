import streamlit as st
import streamlit_canary as sc
from time import sleep

place = st.empty()
if st.button('Start progress'):
    with place:
        with sc.progress('Processing', total=10) as prog:
            for i in range(10):
                prog.update('Processing {}'.format(i))
                sleep(0.5)
