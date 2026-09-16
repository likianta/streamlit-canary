"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit app.
"""

import streamlit as st


def main():
    st.button('Start eye monitor', type='primary')


if __name__ == '__main__':
    # python -m streamlit run --runner.magicEnabled false \
    #   --server.headless true --server.port 2202 \
    #   test/pixel_fidelity/ui_scene_st.py
    main()
