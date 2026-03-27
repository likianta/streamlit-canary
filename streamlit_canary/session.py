import streamlit as st
import typing as t
from inspect import currentframe
from threading import current_thread

_ClassType = t.TypeVar('_ClassType', bound=type)
_plain_state = {}


def init_state(
    default: t.Union[_ClassType, t.Callable[[], dict], dict] = None,
    #   explain the annotation:
    #   https://chatgpt.com/share/69c63662-8c98-8324-8817-b81394dd7a5b
    version: int = 0
) -> t.Union[dict, _ClassType]:
    """
    usage:
        # -- a
        @init_state()
        class State:
            name: str
            code: int
            flag: bool = False
            __version__ = 0
        
        # -- b1
        state = init_state(
            lambda: {
                'name': '',
                'code': 0,
                'flag': False,
            }
        )
        
        # -- b2
        if not (state := init_state(version=...)):
            state.update({
                'name': '',
                'code': 0,
                'flag': False,
            })
        
        # -- c
        state = init_state({
            'name': '',
            'code': 0,
            'flag': False,
        })
    """
    if _is_running_in_streamlit():
        session_state = st.session_state
    else:
        session_state = _plain_state
    last_frame = currentframe().f_back
    module_name = last_frame.f_globals['__name__']
    module_version_key = '{}:version'.format(module_name)
    if isinstance(default, type):
        version = getattr(default, '__version__', version)
        _init_class_attrs(default)
    if module_version_key in session_state:
        if session_state[module_version_key] != version:
            print('rebuild session data', module_name, version)
            session_state[module_name] = (
                {} if default is None else
                default if isinstance(default, (dict, type)) else
                default()  # noqa
            )
            session_state[module_version_key] = version
    else:
        # print('init session data', module_name, version)
        session_state[module_name] = (
            {} if default is None else
            default if isinstance(default, (dict, type)) else
            default()  # noqa
        )
        session_state[module_version_key] = version
    return session_state[module_name]


def _init_class_attrs(cls: type):
    current_fields = frozenset(cls.__dict__.keys())
    for name, type_ in cls.__annotations__.items():
        if name not in current_fields:
            setattr(cls, name, type_())


def _is_running_in_streamlit() -> bool:
    return hasattr(current_thread(), 'streamlit_script_run_ctx')


if _is_running_in_streamlit():
    if '_shared_data' not in st.session_state:
        st.session_state['_shared_data'] = {}
        st.session_state['_shared_data:version'] = 0
    shared_data = st.session_state['_shared_data']
else:
    shared_data = {}


def init_shared_data(version: int = 0):
    if _is_running_in_streamlit():
        if st.session_state['_shared_data:version'] != version:
            st.session_state['_shared_data:version'] = version
            shared_data.clear()
