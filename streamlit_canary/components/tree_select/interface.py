import os
import streamlit as st
import typing as tp
from lk_utils import fs
from .single_select import single_select_dialog
from .multiple_iselect import State as MSelState
from .multiple_iselect import multiselect_dialog
from .typing import T


def tree_select(
    title: str = '',
    start_directory: str = '',
    multiselect: bool = False,
    node_type: T.NodeType = 'file',
    _more_widgets: tp.Optional[tp.Callable[[], None]] = None,
) -> tp.Union[T.SingleSelectResult, T.MultiSelectResult]:
    if start_directory:
        assert fs.isdir(start_directory)
        start_directory = fs.abspath(start_directory)
    else:
        start_directory = fs.normpath(os.getcwd())

    if not title:
        title = 'Input a {} path'.format(node_type)

    place1 = st.container(horizontal=True, vertical_alignment='bottom')

    with place1:
        path = st.text_input(title, start_directory)
        if _more_widgets:
            _more_widgets()
        if st.button('Browse'):
            if multiselect:
                # TODO
                MSelState.query_params = {
                    'start_directory': start_directory,
                    'node_type': node_type,
                }
                multiselect_dialog()
                return MSelState.result
            else:
                return single_select_dialog(start_directory, node_type)
        else:
            return path


# ------------------------------------------------------------------------------


def ask_files(title='Select files', start_directory: str = '', **kwargs):
    return tree_select(
        title, start_directory, multiselect=True, node_type='file', **kwargs
    )


def ask_folders(title='Select folders', start_directory: str = '', **kwargs):
    return tree_select(
        title, start_directory, multiselect=True, node_type='folder', **kwargs
    )
