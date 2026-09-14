import streamlit as st
import sys
import streamlit_canary as sc


def st_thick_button():
    st.button('Bump version\n\n(:red[0.1.0] -> :green[0.2.0])')


def sc_thick_button():
    sc.v3.Button('Bump version\n\n(:red[0.1.0] -> :green[0.2.0])')


if __name__ == '__main__':
    if sys.argv[1] == 'st':
        # python -m streamlit run --server.headless true --server.port 3002 \
        #   test/pixel_fidelity/thick_button.py st
        st_thick_button()
    elif sys.argv[1] == 'sc':
        # python test/pixel_fidelity/thick_button.py sc
        sc.run(sc_thick_button, port=3003)

"""
Comparison in browser:
    st_app = open_browser(localhost:3002)
    st_btn = st_app.find_element(bump_version_button)

    sc_app = open_browser(localhost:3003)
    sc_btn = sc_app.find_element(bump_version_button)
    assert sc_btn.width == st_btn.width
    assert sc_btn.height == st_btn.height
    assert sc_btn.text_html_struct is similar to st_btn.text_html_struct
    assert there are two lines in both buttons
    assert sc_btn.text.font_size == st_btn.text.font_size
"""
