import typing as t

import streamlit as st

from lk_utils import fs
from lk_utils.textwrap import dedent
from . import scope


def _get_session(dir: str, suffix: str) -> dict:
    if __name__ not in st.session_state:
        st.session_state[__name__] = {}
    if scope.scope.key not in st.session_state[__name__]:
        st.session_state[__name__][scope.scope.key] = {
            'names'         : refresh(dir, suffix, 10),
            'selected_index': 0,
            'show_top10': None,
        }
    return st.session_state[__name__][scope.scope.key]


def refresh(dir: str, suffix: str, max_count: int = None) -> list:
    out = []
    for i, f in enumerate(fs.find_files(dir, suffix, sort_by='time')):
        if max_count and i >= max_count: break
        out.append(f.name)
    return out


def pick_file(
    dir: str,
    suffix: str,
    title: str = 'Pick a file from list',
    default_expanded: bool = True,
    scope_key: str = __name__,
) -> t.Optional[str]:
    def _refresh(top10: bool = True) -> None:
        session['names'] = refresh(dir, suffix, 10 if top10 else None)
        st.rerun()
    
    with scope.scope(scope_key):
        session = _get_session(dir, suffix)
        
        with st.expander(title, default_expanded):
            top10 = scope.checkbox(
                'Show only latest 10 files',
                True,
                # on_change=_refresh,
                key='top10'
            )
            if session['show_top10'] != top10:
                session['show_top10'] = top10
                _refresh(top10)
            
            if session['names']:
                name = scope.radio(
                    'Select file',
                    session['names'],
                    index=session['selected_index'],
                    key='file_select'
                )
            else:
                name = None
                st.warning(dedent(
                    '''
                    No file found in target directory! Please check your path
                    or click "Refresh" button to re-index.
    
                    ```
                    {}
                    ```
                    '''.format(fs.abspath(dir))
                ))
            
            if scope.button('Refresh', key='refresh'):
                _refresh(top10)
            if not name:
                return
            if _rename('{}/{}'.format(dir, name)):
                _refresh(top10)
    
    return '{}/{}'.format(dir, name)


def _rename(old_file: str) -> str:
    dir, stem, ext = fs.split(old_file, 3)
    temp = scope.text_input('Rename file', stem)
    if temp == stem:
        return ''
    
    new_file = '{}/{}.{}'.format(dir, temp, ext)
    if ext == 'xlsx' or ext == 'pkl':  # TEST: temp solution
        fs.move(old_file, new_file, True)
        fs.move(
            fs.replace_ext(old_file, 'csv'),
            fs.replace_ext(new_file, 'csv'),
            True
        )
    else:
        fs.move(old_file, new_file, True)
    
    return '{}.{}'.format(temp, ext)
