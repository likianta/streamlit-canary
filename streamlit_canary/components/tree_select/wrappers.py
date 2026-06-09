import os
import typing as tp
from collections import defaultdict
from collections import namedtuple

import neoprint as np
import streamlit as st
from lk_utils import fs

from .tree_select import T as T0
from .tree_select import tree_select
from ...duplicate_key_resolver import UniqueKeyGenerator
from ...session import init_state


class T(T0):
    QueryParams = namedtuple(
        'QueryParams', ('start_directory', 'filter', 'node_type', 'callback')
    )


@init_state
class State:
    contexts: tp.Dict[str, tp.Any] = defaultdict(dict)
    keygen: tp.Optional[UniqueKeyGenerator] = None
    query_params: tp.Optional[T.QueryParams] = None
    __version__ = 3


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
            node_type=node_type,
            show_confirm_button=True,
            start_directory=State.query_params.start_directory,
            _callback=State.query_params.callback,
            _keygen=State.keygen,
        )

    popup_dialog()


def tree_select_with_input(
    label: str,
    initial_path: str = '',
    *,
    browse_button_width: tp.Optional[int] = None,
    # callback: tp.Optional[tp.Callable[[str], None]] = None,
    key: str = '',
    multiselect: bool = False,
    node_type: T.NodeType = 'file',
    _extra_widgets: tp.Optional[tp.Callable[[], None]] = None,
    **kwargs,
) -> tp.Optional[str]:
    np.show(':vi', 'tree_select_with_input')
    # if callback is None:
    #     np.show(':pv6', 'callback is required to enable browsing feature')

    ctx = State.contexts[key or 'tree_select:{}'.format(label)]
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
                'result': '',  # DELETE?
                'start_directory': initial_path
                if fs.isdir(initial_path)
                else fs.parent(initial_path),
            }
        )
    keygen = ctx['keygen']

    def _internal_update_user_input(value: str) -> None:
        np.show(':v', 'user selects a path from dialog', value)
        ctx['result'] = value
        ctx['initial_path'] = value
        ctx['start_directory'] = value if fs.isdir(value) else fs.parent(value)
        ctx['keygen'] = UniqueKeyGenerator(
            '_:tree_select:{}:{}'.format(label, value)
        )
        # st.session_state[keygen('user_input')] = value
        # callback(value)

    def _external_update_user_input() -> None:
        value = st.session_state[keygen('user_input')]
        if value:
            path = fs.abspath(value)
            if node_type in ('file', 'both_but_file'):
                if fs.isdir(path):
                    ctx['result'] = ''
                    ctx['start_directory'] = path
                else:
                    ctx['result'] = path
                    ctx['start_directory'] = fs.parent(path)
            elif node_type in ('folder', 'both_but_folder'):
                if fs.isdir(path):
                    ctx['result'] = path
                    ctx['start_directory'] = path
                else:
                    raise Exception('Path should be folder!')
            else:  # both
                ctx['result'] = path
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

    with st.container(horizontal=True, vertical_alignment='bottom'):
        st.text_input(
            label,
            ctx['initial_path'],
            on_change=_external_update_user_input,
            key=keygen('user_input'),
        )
        if _extra_widgets:
            _extra_widgets()
        if st.button(
            'Browse',
            key=keygen('user_browse'),
            width=browse_button_width or 'content',
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
    return ctx['result']


def _do_nothing(_) -> None:
    pass


# ------------------------------------------------------------------------------


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
