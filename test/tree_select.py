import streamlit as st
import streamlit_canary as sc
from functools import partial
from lk_utils import fs


@sc.init_state
class State:
    result = None
    __version__ = 1


def main():
    print(':i')
    if st.button('Browse'):
        sc.single_select_dialog(
            start_directory=fs.abspath('streamlit_canary'),
            filter='.py',
            callback=_set_result
        )
    # if st.button('Refresh result'):
    #     print('refreshed', State.result)
    st.write(State.result)

def _set_result(result):
    print(result)
    State.result = result

main()
