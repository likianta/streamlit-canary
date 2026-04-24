import os
import streamlit as st
import typing as tp
from collections import namedtuple
from functools import partial
from lk_utils import fs
from .typing import T as T0
from ...duplicate_key_resolver import UniqueKeyGenerator
from ...session import init_state


class T(T0):
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    QueryParams = namedtuple(
        'QueryParams', ('start_directory', 'filter', 'node_type', 'callback')
    )
    Result = T0.SingleSelectResult


@init_state
class State:
    keygen: tp.Optional[UniqueKeyGenerator] = None
    parent_to_dirnames: tp.Dict[str, tp.Optional[tp.List[str]]] = {
        d.replace('\\', '/'): None for d in os.listdrives()
    }
    parent_to_filenames: tp.Dict[str, tp.Sequence[str]] = {}
    query_params: tp.Optional[T.QueryParams] = None
    result: T.Result = None
    temp_new_folder_name: str = ''
    # temp_holding_dialog_opened: bool = False
    tree_select_index_0: int = 0
    tree_select_index_1: int = 0
    __version__ = 3


def single_select_dialog(
    start_directory: str,
    filter: T.Filter = None,
    node_type: T.NodeType = 'file',
    callback: tp.Optional[tp.Callable[[T.Result], None]] = None,
    key: str = '',
    **dialog_options,
) -> T.Result:
    State.query_params = T.QueryParams(
        start_directory, filter, node_type, callback or _do_nothing
    )
    State.keygen = UniqueKeyGenerator(
        key or '_:tree_select:single:{}:{}'.format(start_directory, node_type)
    )

    if 'title' not in dialog_options:
        dialog_options['title'] = 'Tree select'
    if 'width' not in dialog_options:
        dialog_options['width'] = 'medium'
    st.dialog(**dialog_options)(_dialog)()

    return State.result


def _dialog() -> None:
    assert State.query_params
    start_directory = State.query_params.start_directory
    node_type = State.query_params.node_type
    keygen = tp.cast(UniqueKeyGenerator, State.keygen)

    if start_directory not in State.parent_to_dirnames:
        parts = start_directory.split('/')
        temp_str = parts[0]
        for p in parts[1:]:
            temp_str += '/' + p
            State.parent_to_dirnames[temp_str] = None
        State.tree_select_index_0 = sorted(
            State.parent_to_dirnames.keys()
        ).index(start_directory)

    currdir = _current_location()

    cols = st.columns((4, 6))
    with cols[0]:
        with st.container(height=600):
            _subdir_navigation(currdir)
    with cols[1]:
        with st.container(height=600):
            with st.container(height='stretch'):
                x = _single_select(currdir, node_type)
                # print('you select', x, ':v')
            if st.button(
                'Confirm',
                type='primary',
                key=keygen('confirm'),
                on_click=partial(State.query_params.callback, x),
            ):
                State.result = x
                st.rerun()


def _current_location() -> str:
    x = st.selectbox(
        'Current location',
        sorted(State.parent_to_dirnames.keys()),
        accept_new_options=True,
        index=State.tree_select_index_0,
        key=State.keygen(  # type: ignore
            'currdir_location',
            str(sorted(State.parent_to_dirnames.keys())),
            str(State.tree_select_index_0),
        ),
    )
    if x in State.parent_to_dirnames:
        currdir = x
        if State.parent_to_dirnames[currdir] is None:
            _index_new_directory(currdir, focus=False)
    else:  # user enters a new path
        assert fs.exist(x)
        if fs.isdir(x):
            currdir = fs.abspath(x)
        else:
            currdir = fs.abspath(fs.parent(x))
        _index_new_directory(currdir)
    return currdir


def _single_select(parent: str, node_type: T.NodeType = 'file') -> T.Result:
    node_names: tp.Sequence[str]
    if node_type == 'folder':
        node_names = tp.cast(tp.List[str], State.parent_to_dirnames[parent])
    else:
        if parent not in State.parent_to_filenames:
            State.parent_to_filenames[parent] = tuple(
                fs.find_file_names(parent)
            )
        if node_type == 'file':
            node_names = State.parent_to_filenames[parent]
        else:
            node_names = (
                *State.parent_to_filenames[parent],
                *State.parent_to_dirnames[parent],  # type: ignore
            )
        if State.query_params.filter:
            node_names = tuple(
                name
                for name in node_names
                if name.endswith(State.query_params.filter)
            )

    # st.markdown(parent)
    st.info('Current path: **{}**'.format(parent))

    # st.markdown('**Select {}s from the list**'.format(node_type))
    # return [
    #     '{}/{}'.format(parent, name) for name in node_names if st.checkbox(name)
    # ]

    selected = st.radio(
        'Select {}'.format(
            node_type == 'both'
            and 'file or folder'
            or 'one {}'.format(node_type)
        ),
        node_names,
    )
    return '{}/{}'.format(parent, selected)


def _subdir_navigation(parent: str):
    sub_dirnames = tp.cast(tp.List[str], State.parent_to_dirnames[parent])

    row1 = st.container(height='stretch')
    row2 = st.empty()
    row3 = st.container(horizontal=True)

    with row3:
        do_back = st.button(
            ':material/arrow_back:', help='Back', disabled=parent.endswith(':/')
        )
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
                _index_new_directory(dirpath)
            if relocate_subdir_name:
                State.tree_select_index_1 = State.parent_to_dirnames[
                    dirpath
                ].index(relocate_subdir_name)
            else:
                State.tree_select_index_1 = 0
            st.rerun(scope='fragment')

        if do_back:
            a, b = parent.rsplit('/', 1)
            if a[-1] == ':':
                a += '/'
            change_dir(a, relocate_subdir_name=b)
        elif do_enter and result != parent:
            change_dir(result)
        # else:
        #     a, b = result.rsplit('/', 1)
        #     st.markdown('You selected: **{}/:blue[{}]**'.format(a, b))


def _do_nothing():
    pass


def _index_new_directory(dirpath: str, focus: bool = True) -> None:
    State.parent_to_dirnames[dirpath] = fs.find_dir_names(dirpath)
    if focus:
        State.tree_select_index_0 = sorted(State.parent_to_dirnames).index(
            dirpath
        )
