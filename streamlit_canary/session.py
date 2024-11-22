import typing as t
from collections import defaultdict
from inspect import currentframe
from threading import current_thread
from types import FrameType

import streamlit as st

_invalid_session_states = defaultdict(dict)


def init(
    fallback: t.Callable[[], dict] = None,
    version: t.Union[int, str] = None
) -> dict:
    last_frame = currentframe().f_back
    module_name = last_frame.f_globals['__name__']
    # print(module_name, ':v')
    
    # ref: streamlit.runtime.scriptrunner_utils.script_run_context -
    #   .get_script_run_ctx
    if not hasattr(current_thread(), 'streamlit_script_run_ctx'):
        # print(
        #     ':v6p',
        #     'you are getting an invalid session state since you are not '
        #     'running in streamlit script mode!'
        # )
        return _invalid_session_states[module_name]
    
    if module_name in st.session_state:
        if (
            st.session_state[module_name]
                .get('__session_data_version') != version
        ):
            print('re-init session', module_name, version)
            st.session_state[module_name] = fallback()
            st.session_state[module_name]['__session_data_version'] = version
    else:
        if fallback is None:
            st.session_state[module_name] = {'__session_data_version': version}
        else:
            st.session_state[module_name] = fallback()
            st.session_state[module_name]['__session_data_version'] = version
    return st.session_state[module_name]


def get_last_frame(fback_level: int = 1) -> FrameType:
    frame = currentframe().f_back
    for _ in range(fback_level):
        frame = frame.f_back
    return frame


def get_last_frame_id(fback_level: int = 1) -> str:
    return get_last_frame(fback_level + 1).f_globals['__name__']
