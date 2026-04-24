import os
import streamlit as st
import typing as tp
from lk_utils import fs
from ...session import init_state


@init_state
class State:
    query_params: tp.Optional[dict] = None
    parent_to_dirnames: tp.Dict[str, tp.Optional[tp.List[str]]] = {
        d.replace('\\', '/'): None for d in os.listdrives()
    }
    parent_to_filenames: tp.Dict[str, tp.List[str]] = {}
    result: tp.Optional[tp.Sequence[str]] = None
    temp_new_folder_name: str = ''
    tree_select_index_0: int = 0
    tree_select_index_1: int = 0
    __version__ = 1


@st.dialog('Tree select', width='medium')
def multiselect_dialog(
    # start_directory: str, node_type: tp.Literal['file', 'folder'] = 'file'
):
    assert State.query_params
    start_directory = State.query_params['start_directory']
    node_type = State.query_params['node_type']

    if start_directory not in State.parent_to_dirnames:
        parts = start_directory.split('/')
        temp_str = parts[0]
        for p in parts[1:]:
            temp_str += '/' + p
            State.parent_to_dirnames[temp_str] = None
        State.tree_select_index_0 = sorted(
            State.parent_to_dirnames.keys()
        ).index(start_directory)

    currdir = st.selectbox(
        'Current location',
        sorted(State.parent_to_dirnames.keys()),
        index=State.tree_select_index_0,
    )

    cols = st.columns((4, 6))
    with cols[0]:
        with st.container(height=600):
            _subdir_navigation(currdir)
    with cols[1]:
        with st.container(height=600):
            State.result = _multiselect(currdir, node_type)


def _multiselect(
    parent: str, node_type: tp.Literal['file', 'folder'] = 'file'
) -> tp.Sequence[str]:
    if node_type == 'file':
        if parent not in State.parent_to_filenames:
            State.parent_to_filenames[parent] = fs.find_file_names(parent)
        node_names = State.parent_to_filenames[parent]
    else:
        node_names = tp.cast(tp.List[str], State.parent_to_dirnames[parent])

    # st.markdown(parent)
    st.info('Current path: **{}**'.format(parent))

    # st.markdown('**Select {}s from the list**'.format(node_type))
    # return [
    #     '{}/{}'.format(parent, name) for name in node_names if st.checkbox(name)
    # ]

    selected = st.multiselect('Select {}s'.format(node_type), node_names)
    if selected:
        st.markdown('You selected {} {}s.'.format(len(selected), node_type))
        return tuple('{}/{}'.format(parent, name) for name in selected)
    else:
        return ()


def _subdir_navigation(parent: str):
    if State.parent_to_dirnames[parent] is None:
        State.parent_to_dirnames[parent] = fs.find_dir_names(parent)
    sub_dirnames = tp.cast(tp.List[str], State.parent_to_dirnames[parent])

    row1 = st.container(height='stretch')
    row2 = st.empty()
    row3 = st.container(horizontal=True)

    with row3:
        do_back = st.button(':material/arrow_back:', help='Back')
        do_enter = st.button(':material/arrow_forward:', help='Enter')
        do_refresh = st.button(':material/refresh:', help='Refresh tree')
        do_new_folder = st.button(
            ':material/create_new_folder:', help='Create new folder'
        )

        if do_refresh:
            sub_dirnames.clear()
            sub_dirnames.extend(fs.find_dir_names(parent))

        if do_new_folder:

            def _sync_new_folder_name() -> None:
                State.temp_new_folder_name = st.session_state[
                    'new_folder_input'
                ]

            with row2:
                new_folder_name = st.text_input(
                    'Input folder name',
                    label_visibility='collapsed',
                    key='new_folder_input',
                    on_change=_sync_new_folder_name,
                )
        else:
            new_folder_name = State.temp_new_folder_name
            State.temp_new_folder_name = ''

        if new_folder_name:
            if new_folder_name in sub_dirnames:
                st.toast(
                    ':red[Failed to create new folder: duplicate name!]',
                    duration='long',
                )
                State.tree_select_index_1 = sub_dirnames.index(new_folder_name)
            else:
                fs.make_dir('{}/{}'.format(parent, new_folder_name))
                st.toast(':green[Folder "{}" created.]'.format(new_folder_name))
                sub_dirnames.append(new_folder_name)
                sub_dirnames.sort()
                State.tree_select_index_1 = sub_dirnames.index(new_folder_name)
                st.rerun()

    with row1:
        target_dirname = st.radio(
            'Navigate to subfolder',
            sub_dirnames,
            index=State.tree_select_index_1,
            format_func=lambda x: x + '/',
        )
        result = (
            target_dirname is None
            and parent
            or '{}/{}'.format(parent, target_dirname)
        )

        def change_dir(dirpath: str, relocate_subdir_name: str = '') -> None:
            if State.parent_to_dirnames.get(dirpath) is None:
                State.parent_to_dirnames[dirpath] = fs.find_dir_names(dirpath)
            State.tree_select_index_0 = sorted(State.parent_to_dirnames).index(
                dirpath
            )
            if relocate_subdir_name:
                State.tree_select_index_1 = State.parent_to_dirnames[
                    dirpath
                ].index(relocate_subdir_name)
            else:
                State.tree_select_index_1 = 0
            st.rerun()

        if do_back:
            a, b = parent.rsplit('/', 1)
            change_dir(a, relocate_subdir_name=b)
        elif do_enter and result != parent:
            change_dir(result)
        # else:
        #     a, b = result.rsplit('/', 1)
        #     st.markdown('You selected: **{}/:blue[{}]**'.format(a, b))
