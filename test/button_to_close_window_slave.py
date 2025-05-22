import os
import streamlit as st
import streamlit_canary as sc


def main():
    st.write(os.getpid())
    st.write(os.environ['SC_WINDOW_PID_FOR_PORT_3001'])
    st.write(st.get_option('server.port'))
    # st.write(type(st.get_option('server.port')) is int)
    if st.button('Close app'):
        sc.kill()


if __name__ == '__main__':
    main()
