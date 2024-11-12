import streamlit as st
import streamlit_canary as sc


def main():
    path = st.text_input('Path', 'streamlit_canary/components')
    result = sc.filelist('Select file', path)
    print(':l', result)


if __name__ == '__main__':
    main()
