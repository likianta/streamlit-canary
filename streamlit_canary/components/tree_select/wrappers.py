import os
import typing as tp
from collections import defaultdict
from collections import deque
from collections import namedtuple
from functools import partial

import streamlit as st
from lk_utils import fs
from neoprint import print  # noqa

from .tree_select import T as T0
from .tree_select import tree_select
from ...keygen import UniqueKeyGenerator
from ...session import init_state


class T(T0):
    QueryParams = namedtuple(
        'QueryParams', ('start_directory', 'filter', 'node_type', 'callback')
    )
    TreeInputCustomization = tp.TypedDict(
        'TreeInputCustomization',
        {
            'browse_button_width': tp.Literal['content', 'stretch'],
            'place0': tp.Callable[[], None],
            'place1': tp.Callable[[], None],
            'place2': tp.Callable[[], None],
            'place3': tp.Callable[[], None],
            #   place 0, 1, 2, 3:
            #       ? [ text_input   ] ? [ recent_button ] ? [ browse_button ] ?
            #       0                  1                   2                   3
            #   usually place1 and place3 are recommended to use.
            'recent_button_width': tp.Literal['content', 'stretch'],
        },
        total=False,
    )


@init_state
class State:
    keygen: tp.Optional[UniqueKeyGenerator] = None
    query_params: tp.Optional[T.QueryParams] = None
    user_states: tp.Dict[str, tp.Any] = defaultdict(dict)
    __version__ = 4


def tree_select_dialog(
    start_directory: str = '',
    filter: T.Filter = None,
    *,
    callback: tp.Callable[[str], None],  # required
    key: str = '',
    multiselect: bool = False,
    node_type: T.NodeType = 'file',
    _keygen: tp.Optional[UniqueKeyGenerator] = None,
    **dialog_options,
) -> None:
    """
    dialog_options:
        title: String
        width: Literal['small', 'medium', 'large']
        more options see `st.dialog:signature`.
    """
    # since st.dialog doesn't support passing parameters, we should store them
    # in State.
    if start_directory:
        start_directory = fs.abspath(start_directory)
    else:
        start_directory = fs.normpath(os.getcwd())

    State.query_params = T.QueryParams(
        start_directory, filter, node_type, callback
    )
    State.keygen = _keygen or UniqueKeyGenerator(
        key or '_:tree_select:{}:{}'.format(start_directory, node_type)
    )

    if 'title' not in dialog_options:
        dialog_options['title'] = 'Select {}{}'.format(
            'file'
            if node_type == 'file'
            else 'folder'
            if node_type == 'folder'
            else 'file or folder'
            if node_type == 'both'
            else 'file'
            if node_type == 'both_but_file'
            else 'folder',
            '(s)'
            if multiselect and node_type == 'both'
            else 's'
            if multiselect
            else '',
        )
    if 'width' not in dialog_options:
        dialog_options['width'] = 'medium'

    @st.dialog(**dialog_options)
    def popup_dialog():
        tree_select(
            filter=State.query_params.filter,
            key=State.keygen('tree_select'),
            node_type=node_type,
            show_confirm_button=True,
            start_directory=State.query_params.start_directory,
            _callback=State.query_params.callback,
            _keygen=State.keygen,
            _scoped=True,
        )

    popup_dialog()


def tree_select_with_input(
    label: str,
    initial_path: str = '',
    *,
    custom: tp.Optional[T.TreeInputCustomization] = None,
    key: str = '',
    multiselect: bool = False,
    node_type: T.NodeType = 'file',
    show_recent: bool = False,
    **kwargs,
) -> tp.Optional[str]:
    ctx = State.user_states[key or 'tree_select:{}'.format(label)]
    if not ctx:
        # init context
        if initial_path:
            initial_path = fs.abspath(initial_path)
        else:
            initial_path = fs.normpath(os.getcwd())
        ctx.update(
            {
                'initial_path': initial_path,
                'keygen': UniqueKeyGenerator(
                    key or '_:tree_select:{}:{}'.format(label, initial_path)
                ),
                'recent': deque(maxlen=20),
                # TODO
                'result': initial_path
                if node_type == 'file' and fs.isfile(initial_path)
                else '',
                'start_directory': initial_path
                if fs.isdir(initial_path)
                else fs.parent(initial_path),
            }
        )
    keygen = ctx['keygen']

    def _internal_update_user_input(value: str) -> None:
        ctx['result'] = value
        _update_recent_list(value)
        ctx['initial_path'] = value
        ctx['start_directory'] = value if fs.isdir(value) else fs.parent(value)
        ctx['keygen'] = UniqueKeyGenerator(
            '_:tree_select:{}:{}'.format(label, value)
        )
        # st.session_state[keygen('user_input')] = value
        # callback(value)

    def _external_update_user_input(key: str) -> None:
        value = st.session_state[key]
        if value:
            path = fs.abspath(value)
            if node_type in ('file', 'both_but_file'):
                if fs.isdir(path):
                    ctx['result'] = ''
                    ctx['start_directory'] = path
                else:
                    ctx['result'] = path
                    _update_recent_list(path)
                    ctx['start_directory'] = fs.parent(path)
            elif node_type in ('folder', 'both_but_folder'):
                if fs.isdir(path):
                    ctx['result'] = path
                    _update_recent_list(path)
                    ctx['start_directory'] = path
                else:
                    raise Exception('Path should be folder!')
            else:  # both
                ctx['result'] = path
                _update_recent_list(path)
                ctx['start_directory'] = (
                    path if fs.isdir(path) else fs.parent(path)
                )
        else:
            ctx['result'] = ''
            ctx['start_directory'] = (
                ctx['initial_path']
                if fs.isdir(ctx['initial_path'])
                else fs.parent(ctx['initial_path'])
            )
        # if ctx['result']:
        #     callback(ctx['result'])
        #     ctx['result'] = ''

    def _update_recent_list(new_value: str) -> None:
        if show_recent:
            if new_value in ctx['recent']:
                if new_value == ctx['recent'][0]:
                    return
                ctx['recent'].remove(new_value)
            ctx['recent'].appendleft(new_value)

    with st.container(horizontal=True, vertical_alignment='bottom'):
        if custom and custom.get('place0'):
            custom['place0']()
        st.text_input(
            label,
            ctx['initial_path'],
            on_change=partial(
                _external_update_user_input, keygen('user_input')
            ),
            key=keygen('user_input'),
        )
        if custom and custom.get('place1'):
            custom['place1']()
        if show_recent:
            st.menu_button(
                'Recent',
                options=ctx['recent'] or (None,),
                disabled=not ctx['recent'],
                key=keygen('user_recent'),
                on_click=lambda: _internal_update_user_input(
                    st.session_state[keygen('user_recent')]
                ),
                width=custom
                and custom.get('recent_button_width', 'content')
                or 'content',
            )
        if custom and custom.get('place2'):
            custom['place2']()
        if st.button(
            'Browse',
            key=keygen('user_browse'),
            width=custom
            and custom.get('browse_button_width', 'content')
            or 'content',
        ):
            if multiselect:
                raise NotImplementedError
            else:
                return tree_select_dialog(
                    callback=_internal_update_user_input,
                    node_type=node_type,
                    start_directory=ctx['start_directory'],
                    _keygen=keygen,
                    **kwargs,
                )
        if custom and custom.get('place3'):
            custom['place3']()
    return ctx['result']


def _do_nothing(_) -> None:
    pass


# ------------------------------------------------------------------------------
# DELETE?


def ask_files(title='Select files', start_directory: str = '', **kwargs):
    return tree_select(
        title, start_directory, multiselect=True, node_type='file', **kwargs
    )


def ask_folder(title='Select folder', start_directory: str = '', **kwargs):
    return tree_select(
        start_directory=start_directory, node_type='folder', **kwargs
    )


def ask_folders(title='Select folders', start_directory: str = '', **kwargs):
    return tree_select(
        title, start_directory, multiselect=True, node_type='folder', **kwargs
    )
