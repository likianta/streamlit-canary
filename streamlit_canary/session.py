import typing as tp
from inspect import currentframe
from threading import current_thread
from types import FrameType

import streamlit as st
from lk_utils import textwrap as tw

_ClassType = tp.TypeVar('_ClassType', bound=type)
_plain_state = {}


def init_state(
    default: tp.Optional[
        tp.Union[_ClassType, tp.Callable[[], dict], dict]
    ] = None,
    #   explain the annotation:
    #   https://chatgpt.com/share/69c63662-8c98-8324-8817-b81394dd7a5b
    version: int = 0,
) -> tp.Union[dict, tp.Any]:
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
    last_frame: FrameType = currentframe().f_back  # type:ignore
    module_name = last_frame.f_globals['__name__']
    #   FIXME: module_name may be `__main__` in the entry point, but when other
    #   module imports it, the module name will be changed.
    #   so we can't use module_name as a global stable unique key.
    module_path = last_frame.f_globals['__file__']

    data_key = module_path
    version_key = '{}:version'.format(module_path)
    if isinstance(default, type):
        version = getattr(default, '__version__', version)
    if version_key in session_state and session_state[version_key] != version:
        print('rebuild session data', module_name, version)
    if (
        version_key not in session_state
        or session_state[version_key] != version
    ):
        if isinstance(default, type):
            _init_class_attrs(default, module_name)
        out = session_state[data_key] = (
            {}
            if default is None
            # default if isinstance(default, dict) else
            else default
            if isinstance(default, (dict, type))
            else default()  # noqa
        )
        # print(module_name, version, id(out), ':v')
        # if isinstance(out, dict):
        #     out['__version__'] = version
        #     out['__path__'] = last_frame.f_globals['__file__']
        session_state[version_key] = version
        return out
    else:
        return session_state[data_key]


def dump_state(state: tp.Union[dict, _ClassType]) -> str:
    if isinstance(state, dict):
        data, version, module_name = state, '', ''
    else:
        data = state.__dict__
        version = getattr(state, '__version__', '')
        module_name = getattr(state, '__module__')
    return tw.wrap(
        """
            <State {} {}
                {}
            >
            """,
        4,
        False,
    ).format(
        version and f'v{version}',
        module_name and f'in `{module_name}`',
        tw.join(
            (
                '{} = {}'.format(k, f'"{v}"' if isinstance(v, str) else v)
                for k, v in data.items()
                if not k.startswith('_')
            ),
            8,
        ),
    )


def _init_class_attrs(cls: type, module_name: str):
    current_fields = frozenset(cls.__dict__.keys())
    for name, type_ in cls.__annotations__.items():
        if name not in current_fields:
            setattr(cls, name, type_())
    setattr(cls, '__module__', module_name)


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


# ------------------------------------------------------------------------------
# v2


class SessionStateV2:
    def __init__(self, origin_class: _ClassType) -> None:
        origin_fields = origin_class.__dict__
        annotations = origin_class.__annotations__
        self.fields = {}
        for key, val in origin_fields.items():
            if not key.startswith('__'):
                self.fields[key] = {'initial_value': val, 'current_value': val}
        for key, type_ in annotations.items():
            if key not in origin_fields:
                value = type_()
                self.fields[key] = {
                    'initial_value': value,
                    'current_value': value,
                }


def init_state_v2(state_class: _ClassType) -> SessionStateV2:
    if _is_running_in_streamlit():
        session_state = st.session_state
    else:
        session_state = _plain_state

    last_frame: FrameType = currentframe().f_back
    module_name = last_frame.f_globals['__name__']
    module_path = last_frame.f_globals['__file__']

    data_key = module_path
    version_key = '{}:version'.format(module_path)
    version = getattr(
        state_class, '__revision__', getattr(state_class, '__version__', 0)
    )
    if version_key in session_state and session_state[version_key] != version:
        print('rebuild session data', module_name, version)
    if (
        version_key not in session_state
        or session_state[version_key] != version
    ):
        out = session_state[data_key] = SessionStateV2(state_class)
        session_state[version_key] = version
        return out
    else:
        return session_state[data_key]
