import streamlit as st
import typing as t
from collections import defaultdict
from inspect import currentframe
from functools import wraps


# def init(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs) -> dict:
#         if func.__qualname__ not in st.session_state:
#             print('init session', func.__qualname__, func, ':vp')
#             st.session_state[func.__qualname__] = func(*args, **kwargs)
#         return st.session_state[func.__qualname__]
#     return wrapper


def init(
    fallback: t.Callable[[], dict] = None,
    version: t.Union[int, str] = None
) -> dict:
    last_frame = currentframe().f_back
    module_name = last_frame.f_globals['__name__']
    if module_name in st.session_state:
        if st.session_state[module_name].get('__version') != version:
            print('re-init session', module_name, version)
            st.session_state[module_name] = fallback()
            st.session_state[module_name]['__version'] = version
    else:
        if fallback is None:
            st.session_state[module_name] = {'__version': version}
        else:
            st.session_state[module_name] = fallback()
            st.session_state[module_name]['__version'] = version
    return st.session_state[module_name]


get = init


class SessionHost:
    def __init__(self) -> None:
        self._sessions = defaultdict(dict)  # {frame_name: dict, ...}
    
    def __getitem__(self, key: str) -> t.Any:
        last_frame = currentframe().f_back
        name = last_frame.f_globals['__name__']
        return self._sessions[name][key]
    
    def __setitem__(self, key: str, value: t.Any) -> None:
        last_frame = currentframe().f_back
        name = last_frame.f_globals['__name__']
        self._sessions[name][key] = value
    
    # used as decorator
    def init(self, func: t.Callable[[], dict]) -> None:
        last_frame = currentframe().f_back
        name = last_frame.f_globals['__name__']
        if name not in self._sessions:
            print('init session', name)
            self._sessions[name] = func()
    
    def get(self, frame_name: str = None) -> dict:
        if frame_name is None:
            frame_name = currentframe().f_back.f_globals['__name__']
        return self._sessions[frame_name]


session_host = SessionHost()
