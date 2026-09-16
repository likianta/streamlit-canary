"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit app.
"""

import streamlit as st


def main():
    st.button('Start eye monitor', type='primary')

    st.table(
        {
            'Link status': ':green[ON]',
            'PRBS error counter': ':red[123]',
            'Server connected': 'Fake device',
        },
        width='content',
    )
    st.table(
        {
            'File name': 'droo1.mat',
            'File size': '28.19KB',
            'MATLAB version': '7.3',
        },
        width='stretch',  # default
    )


if __name__ == '__main__':
    # python -m streamlit run --runner.magicEnabled false \
    #   --server.headless true --server.port 2202 \
    #   test/pixel_fidelity/ui_scene_st.py
    main()
