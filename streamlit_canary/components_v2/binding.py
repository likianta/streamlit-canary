import inspect
import typing as tp

import streamlit as st


class Binding:
    key: str
    value: tp.Any
    _listeners: tp.List[tp.Tuple[object, str]]

    def __init__(self, key: str) -> None:
        self.key = key
        self._listeners = []

    def trigger(self) -> None:
        for obj, attr in self._listeners:
            setattr(obj, attr, st.session_state[self.key])

    def bind(self, obj: object, attr: str) -> tp.Self:
        self._listeners.append((obj, attr))
        return self


# DELETE: deprecate to use.
def bind(obj, attr, component_name, *args, **kwargs):
    last_frame = inspect.currentframe().f_back
    frame_id = '{}:{}'.format(
        last_frame.f_code.co_filename, last_frame.f_lineno
    )
    return getattr(st, component_name)(
        *args,
        key=frame_id,
        on_change=lambda: setattr(obj, attr, st.session_state[frame_id]),
        **kwargs,
    )
