import streamlit as st
import streamlit_canary as sc

@sc.init_state
class State:
    selected_folder = ''

def main():
    st.title('Test File Dialog')
    if st.button('Browse'):
        _file_dialog()
    if State.selected_folder:
        st.markdown('Your selection: {}'.format(State.selected_folder))
    
@st.dialog('Select Folder', width='medium')
def _file_dialog():
    if result := sc.opener.ask_folder():
        print(result)
        State.selected_folder = result
        st.rerun()

if __name__ == '__main__':
    main()
