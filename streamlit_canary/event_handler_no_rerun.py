"""
usage:
    from streamlit_sugar import evt
    st.text_input('Name', key=str(evtkey := evt.auto_key()))
    evtkey.set('new value')
"""

import streamlit as st


def _get_session() -> dict:
    if __name__ not in st.session_state:
        st.session_state[__name__] = {'auto_id': 0}
    return st.session_state[__name__]


class EventDispatcher:
    def __init__(self) -> None:
        self._auto_id = 0
        # self._auto_id = _get_session()['auto_id']
    
    def auto_key(self) -> 'EventKey':
        self._auto_id += 1
        return EventKey('_st_auto_id_{}'.format(self._auto_id))


class EventKey:
    def __init__(self, key: str) -> None:
        self.key = key
    
    def __str__(self) -> str:
        return self.key
    
    def set(self, data):
        st.session_state[self.key] = data


evt = EventDispatcher()
