import streamlit as st
import streamlit_canary as sc

@sc.init_state
class State:
    name: str
    code: int = 0
    data: list = ['Teens']
    __version__ = 3
    
def main():
    State.name = st.text_input('Name')
    if st.button('Submit', disabled=not State.name):
        State.data.append(State.name)
    st.radio(
        'Select name',
        State.data
    )

if __name__ == '__main__':
    main()
