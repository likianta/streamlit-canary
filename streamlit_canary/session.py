import streamlit as st
import typing as t
from collections import defaultdict
from inspect import currentframe
from threading import current_thread

_invalid_session_states = defaultdict(dict)


def get_state(version: int = 0, callback: t.Callable[[], dict] = None) -> dict:
    """
    usage:
        style 1:
            import streamlit_canary as sc
            if not (state := sc.session.get_state(<target_version>)):
                state.update({...})
        style 2:
            # good for IDE's autocomplete
            import streamlit_canary as sc
            if not (x := sc.session.get_state(<target_version>)):
                x.update(state := {...})
            else:
                state = x
    """
    last_frame = currentframe().f_back
    module_name = last_frame.f_globals['__name__']
    if hasattr(current_thread(), 'streamlit_script_run_ctx'):
        module_version = '{}:version'.format(module_name)
        if module_version in st.session_state:
            if st.session_state[module_version] != version:
                print('rebuild session data', module_name, version)
                st.session_state[module_name] = callback() if callback else {}
                st.session_state[module_version] = version
        else:
            # print('init session data', module_name, version)
            st.session_state[module_name] = callback() if callback else {}
            st.session_state[module_version] = version
        return st.session_state[module_name]
    else:
        return _invalid_session_states[module_name]


# def get_last_frame(fback_level: int = 1) -> FrameType:
#     frame = currentframe().f_back
#     for _ in range(fback_level):
#         frame = frame.f_back
#     return frame
#
#
# def get_last_frame_id(fback_level: int = 1) -> str:
#     return get_last_frame(fback_level + 1).f_globals['__name__']
