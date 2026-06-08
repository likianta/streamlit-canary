import os
import typing as tp
from functools import partial

import streamlit as st
from lk_utils import fs

from ...duplicate_key_resolver import UniqueKeyGenerator
from ...session import init_state


class T:
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    NodeType = tp.Literal[
        'file', 'folder', 'both', 'both_but_file', 'both_but_folder'
    ]


@init_state
class State:
    parent_to_dirnames: tp.Dict[str, tp.Optional[tp.List[str]]] = {
        d.replace('\\', '/'): None for d in os.listdrives()
    }
    parent_to_filenames: tp.Dict[str, tp.Sequence[str]] = {}
    temp_new_folder_name: str = ''
    # temp_holding_dialog_opened: bool = False
    tree_select_index_0: int = 0
    tree_select_index_1: int = 0
    tree_select_index_2: int = 0
    __version__ = 6


def tree_select(
    start_directory: str = '',
    filter: T.Filter = None,
    *,
    height: int = 600,
    key: str = '',
    multiselect: bool = False,
    node_type: T.NodeType = 'file',
    show_confirm_button: bool = True,
    _callback: tp.Optional[tp.Callable[[str], None]] = None,
    _keygen: tp.Optional[UniqueKeyGenerator] = None,
) -> tp.Optional[str]:
    """
    this component is usually used inside a dialog/container/expander layout.
    """
    if start_directory:
        assert fs.isdir(start_directory)
        start_directory = fs.abspath(start_directory)
    else:
        start_directory = fs.normpath(os.getcwd())

    keygen = _keygen or UniqueKeyGenerator(
        key or '_:tree_select:{}:{}'.format(start_directory, node_type)
    )

    if start_directory not in State.parent_to_dirnames:
        parts = start_directory.split('/')
        temp_str = parts[0]
        for p in parts[1:]:
            temp_str += '/' + p
            State.parent_to_dirnames[temp_str] = None
        State.tree_select_index_0 = sorted(
            State.parent_to_dirnames.keys()
        ).index(start_directory)

    currdir = _current_location(keygen)

    cols = st.columns((3.5, 6.5))
    with cols[0]:
        with st.container(height=height):
            selected_subdir = _subdir_navigation(currdir)
    with cols[1]:
        with st.container(height=height):
            place1 = st.container(height='stretch')
            place2 = st.container(horizontal=True, vertical_alignment='bottom')

            with place2:
                place2_1 = st.empty()
                if node_type == 'both':
                    st.space(size='stretch')
                    node_type = tp.cast(
                        T.NodeType,
                        st.segmented_control(
                            'View mode',
                            options=(
                                'both_but_file',
                                'both_but_folder',
                                'both',
                            ),
                            default='both',
                            format_func=lambda x: (
                                'File'
                                if x == 'both_but_file'
                                else 'Folder'
                                if x == 'both_but_folder'
                                else 'Both'
                            ),
                            key=keygen('node_type_switch'),
                        ),
                    )

            with place1:
                # TODO: refresh tree selection
                result, _ = _single_select(selected_subdir, node_type, filter)
                # np.show('you select', result, ':v')

            if _callback:
                assert show_confirm_button
                if place2_1.button(
                    'Confirm',
                    type='primary',
                    disabled=not result,
                    key=keygen('confirm_with_callback'),
                    width='stretch',
                    on_click=partial(_callback, result),
                ):
                    st.rerun()
            else:
                if not show_confirm_button or place2_1.button(
                    'Confirm',
                    type='primary',
                    disabled=not result,
                    key=keygen('confirm'),
                    width='stretch',
                ):
                    return result


def _current_location(keygen: UniqueKeyGenerator) -> str:
    x = st.selectbox(
        'Current location',
        sorted(State.parent_to_dirnames.keys()),
        accept_new_options=True,
        index=State.tree_select_index_0,
        key=keygen(
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


def _index_new_directory(dirpath: str, focus: bool = True) -> None:
    State.parent_to_dirnames[dirpath] = fs.find_dir_names(dirpath)
    if focus:
        State.tree_select_index_0 = sorted(State.parent_to_dirnames).index(
            dirpath
        )
    State.tree_select_index_1 = 0
    State.tree_select_index_2 = 0


def _single_select(
    parent: str, node_type: T.NodeType = 'file', filter: T.Filter = None
) -> tp.Tuple[str, tp.Optional[tp.Callable[[], None]]]:
    nodes: tp.Sequence[tp.Tuple[str, str]]  # Sequence[Tuple[name, label]]
    if node_type == 'folder':
        nodes = tuple(
            (x, x.replace('__', '\\_\\_'))
            for x in State.parent_to_dirnames[parent]
        )
    else:
        if parent not in State.parent_to_filenames:  # DELETE?
            State.parent_to_filenames[parent] = tuple(
                fs.find_file_names(parent)
            )
        if node_type == 'file':
            nodes = tuple(
                (x, x.replace('__', '\\_\\_'))
                for x in State.parent_to_filenames[parent]
            )
        else:  # 'both', 'both_but_file', 'both_but_folder'
            nodes = ()
            if node_type == 'both' or node_type == 'both_but_folder':
                nodes += tuple(
                    (
                        x,
                        ':material/folder: {}/'.format(
                            x.replace('__', '\\_\\_')
                        ),
                    )
                    for x in State.parent_to_dirnames[parent]
                )
            if node_type == 'both' or node_type == 'both_but_file':
                nodes += tuple(
                    (
                        x,
                        ':material/description: {}'.format(
                            x.replace('__', '\\_\\_')
                        ),
                    )
                    for x in State.parent_to_filenames[parent]
                )

        if filter:
            nodes = tuple(
                (name, label)
                for name, label in nodes
                if name.endswith(filter) or label.endswith('/')
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
        nodes,
        format_func=lambda x: x[1],
        # key=State.keygen('single_select', node_type, str(nodes)),
    )
    if selected:

        def _refresh_selection(index: int) -> None:
            State.tree_select_index_2 = index

        return '{}/{}'.format(parent, selected[0]), partial(
            _refresh_selection, nodes.index(selected[0])
        )
    return '', None


def _subdir_navigation(parent: str) -> str:
    sub_dirnames = tp.cast(tp.List[str], State.parent_to_dirnames[parent])

    row1 = st.container(height='stretch')
    row2 = st.empty()
    row3 = st.container(horizontal=True)

    with row3:
        do_back = st.button(
            ':material/arrow_back:', help='Back', disabled=parent.endswith(':/')
        )
        do_enter = st.button(':material/arrow_forward:', help='Forward')
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
                State.tree_select_index_1 = (
                    sub_dirnames.index(new_folder_name) + 1
                )
            else:
                fs.make_dir('{}/{}'.format(parent, new_folder_name))
                st.toast(':green[Folder "{}" created.]'.format(new_folder_name))
                sub_dirnames.append(new_folder_name)
                sub_dirnames.sort()
                State.tree_select_index_1 = (
                    sub_dirnames.index(new_folder_name) + 1
                )
                st.rerun()

    with row1:
        target_dirname = st.radio(
            'Navigate to subfolder',
            ['..'] + sub_dirnames,
            index=State.tree_select_index_1,
            format_func=lambda x: (
                ':gray(This folder)' if x == '..' else x + '/'
            ),
        )
        result = (
            parent
            if target_dirname is None or target_dirname == '..'
            else '{}/{}'.format(parent.rstrip('/'), target_dirname)
        )

        def change_dir(dirpath: str, relocate_subdir_name: str = '') -> None:
            # np.show('change_dir', dirpath, relocate_subdir_name)
            if State.parent_to_dirnames.get(dirpath) is None:
                _index_new_directory(dirpath)
            if relocate_subdir_name:
                State.tree_select_index_1 = (
                    State.parent_to_dirnames[dirpath].index(
                        relocate_subdir_name
                    )
                    + 1
                )
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

    return result
