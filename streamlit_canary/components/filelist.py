import typing as t

import streamlit as st
from lk_utils import fs
from lk_utils.textwrap import dedent

from .button import long_button
from .. import session

_state = session.init(lambda: {'tree_cache': {}})


# TODO: fragment, with callback param.
# @st.fragment
def filelist(
    title: str,
    dir: str,
    suffix: t.Optional[str] = None,
    *,
    multiple_selection: bool = False,
    explicit_confirm: bool = False,
    show_index_to_files: bool = True,
) -> t.Union[t.Optional[str], t.List[str]]:
    # _state = session.init(lambda: {'tree_cache': {}})
    
    uid = '{}:__filelist'.format(session.get_last_frame_id())
    if dir not in _state['tree_cache']:
        _state['tree_cache'][dir] = {}
    
    with st.expander(title, expanded=True):
        cols = st.columns((2, 1))
        with cols[0]:
            top10 = st.toggle(
                'Show top 10 files',
                True,
                key=f'{uid}:top10'
            )
        with cols[1]:
            sort_by = st.radio(
                'Sort by',
                ('name :small_red_triangle:', 'time :small_red_triangle_down:'),
                index=1,
                horizontal=True,
                key=f'{uid}:sort_by',
                label_visibility='collapsed'
            )
            sort_by = sort_by[:4]
        
        if (suffix, sort_by) not in _state['tree_cache'][dir]:
            _state['tree_cache'][dir][(suffix, sort_by)] = tuple(
                _init_tree(dir, suffix, sort_by)
            )
        files = _state['tree_cache'][dir][(suffix, sort_by)]
        
        if files:
            if top10:
                files = files[:10]
            if multiple_selection:
                out = []
                for index, (name, path) in enumerate(files, 1):
                    if st.checkbox(
                        ':blue[{:02}.] {}'
                        .format(index, name.replace('__', '\\_\\_'))
                        if show_index_to_files else
                        name.replace('__', '\\_\\_'),
                        key=f'{uid}:checkbox:{name}'
                    ):
                        out.append(path)
            else:
                selected_index = st.radio(
                    'Select a file',
                    range(len(files)),
                    format_func=lambda i: (
                        ':blue[{:02}.] {}'
                        .format(i + 1, files[i][0].replace('__', '\\_\\_'))
                        if show_index_to_files else
                        files[i][0].replace('__', '\\_\\_')
                    ),
                    key=f'{uid}:select_file',
                    label_visibility='collapsed'
                )
                out = [files[selected_index][1]]
        else:
            st.write(dedent(
                '''
                No files found in the directory! Please check your path and
                suffix, or click "Refresh" button to reload the list.
                
                Your directory is:
                
                ```
                {}
                ```
                '''.format(fs.abspath(dir))
            ))
            out = []
        
        if explicit_confirm:
            cols = st.columns(4)
            with cols[2]:
                if long_button('Refresh', key=f'{uid}:refresh'):
                    _state['tree_cache'].pop(dir)
                    st.rerun()
            with cols[3]:
                if long_button(
                    'Apply',
                    type='primary',
                    key=f'{uid}:apply',
                    disabled=not out,
                ):
                    return (
                        out if multiple_selection else
                        out[0] if out else None
                    )
                else:
                    return [] if multiple_selection else None
        else:
            if long_button('Refresh', key=f'{uid}:refresh2'):
                _state['tree_cache'].pop(dir)
                st.rerun()
            return out if multiple_selection else out[0] if out else None


def _init_tree(dir: str, suffix: t.Optional[str], sort_by: str = 'time'):
    for f in fs.find_files(dir, suffix, sort_by=sort_by):
        yield f.name, f.path
