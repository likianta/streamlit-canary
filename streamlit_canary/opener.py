import os
import streamlit as st
import typing as tp
from lk_utils import dedent, fs
from .session import init_state


@init_state
class State:
    folders: tp.Dict[str, tp.List[str]] = {
        d.replace('\\', '/'): [] for d in os.listdrives()
    }
    result: tp.List[str] = []
    temp_new_folder_name: str = ''
    tree_select_index_0: int = 0
    tree_select_index_1: int = 0


def file_dialog_tk(
    start_directory: str = '',
    title: str = '',
    multiselect: bool = False,
    type: tp.Literal['file', 'folder'] = 'file',
    filter: tp.Iterable[tp.Tuple[str, str]] = (('All files', '*'),),
    action: tp.Literal['open', 'save'] = 'open',
) -> tp.Union[str, tp.Tuple[str, ...]]:
    from tkinter import Tk
    from tkinter import filedialog

    assert not start_directory or _isdir(start_directory)

    root = Tk()
    root.withdraw()

    if type == 'file':
        if multiselect:
            if action == 'open':
                method = filedialog.askopenfilenames
                if not title:
                    title = 'Select files'
            else:
                raise Exception('cannot save multiple files in a time')
        else:
            if action == 'open':
                method = filedialog.askopenfilename
                if not title:
                    title = 'Select a file'
            else:
                method = filedialog.asksaveasfilename
                if not title:
                    title = 'Save file'
    else:
        if multiselect:
            raise Exception('cannot open/save multiple folders in a time')
        else:
            if action == 'open':
                method = filedialog.askdirectory
                if not title:
                    title = 'Select folder'
            else:
                raise Exception('cannot save folder type')

    kwargs = dict(title=title, initialdir=start_directory)
    if type == 'file':
        kwargs['filetypes'] = filter  # type: ignore

    return method(**kwargs)  # type: ignore


def _ask_path(
    start_directory: str = '',
    title: str = '',
    multiselect: bool = False,
    type: tp.Literal['file', 'folder'] = 'file',
    filter: tp.Iterable[tp.Tuple[str, str]] = (('All files', '*'),),
    action: tp.Literal['open', 'save'] = 'open',
    explicit_confirm_button: bool = True,
    main_container_height: int = 300,
):
    if start_directory:
        assert _isdir(start_directory)
        start_directory = fs.abspath(start_directory)
    else:
        start_directory = fs.normpath(os.getcwd())

    if filter != (('All files', '*'),):
        raise NotImplementedError

    # init title
    if not title:
        if type == 'file':
            if multiselect:
                if action == 'open':
                    title = 'Select files'
                else:
                    raise Exception('cannot save multiple files in a time')
            else:
                if action == 'open':
                    title = 'Select a file'
                else:
                    title = 'Save file'
        else:
            if multiselect:
                raise Exception('cannot open/save multiple folders in a time')
            else:
                if action == 'open':
                    title = 'Select folder'
                else:
                    raise Exception('cannot save folder type')

    # key_prefix = hashlib.md5(start_directory.encode('utf-8')).hexdigest()

    # --------------------------------------------------------------------------

    if start_directory not in State.folders:
        parts = start_directory.split('/')
        temp_list = []
        temp_str = parts[0]
        for p in parts[1:]:
            temp_str += '/' + p
            temp_list.append(temp_str)
        State.folders[start_directory] = temp_list

    if multiselect:
        with st.container(border=True):
            place1 = st.empty()
            place2 = st.empty()

            with place2:
                with st.expander('{} dialog'.format(type.capitalize())):
                    tree_select_st(...)
            with place1:
                if State.result:
                    st.markdown(
                        dedent(
                            """
                            You have selected the following {} {}s:
                            {}
                            """
                        ).format(
                            len(State.result),
                            type,
                            '\n'.join('- {}'.format(p) for p in State.result),
                        )
                    )
                else:
                    st.markdown(
                        ':gray[Please select some {} to continue.]'.format(
                            f'{type}s' if multiselect else type
                        )
                    )
    else:
        with st.container(horizontal=True):
            path = ...


def tree_select_st(
    multiselect: bool = False,
    type: tp.Literal['file', 'folder'] = 'file',
    filter: tp.Iterable[tp.Tuple[str, str]] = (('All files', '*'),),
    action: tp.Literal['open', 'save'] = 'open',
    main_container_height: int = 300,
) -> None:
    place1 = st.empty()
    place2 = st.empty()

    def _sync_new_folder_name() -> None:
        State.temp_new_folder_name = st.session_state['new_folder_input']

    with place2:
        with st.container(horizontal=True):
            do_confirm = st.button('Confirm', type='primary')
            do_back = st.button(':material/arrow_back:', key='back')
            do_enter = st.button(':material/arrow_forward:', key='enter')
            do_refresh = st.button('Refresh tree')
            if st.button('New folder'):
                new_folder_name = st.text_input(
                    'Input folder name',
                    label_visibility='collapsed',
                    key='new_folder_input',
                    on_change=_sync_new_folder_name,
                )
            else:
                new_folder_name = State.temp_new_folder_name
                State.temp_new_folder_name = ''

    with place1:
        with st.container():
            currdir = st.selectbox(
                'Current location',
                sorted(State.folders.keys()),
                index=State.tree_select_index_0,
            )

            subdirs = State.folders[currdir]
            if do_refresh or (not subdirs and currdir.endswith(':/')):
                subdirs.clear()
                subdirs.extend(fs.find_dir_names(currdir))

            if new_folder_name:
                if new_folder_name in subdirs:
                    st.toast(
                        ':red[Failed to create new folder: duplicate name!]',
                        duration='long',
                    )
                    State.tree_select_index_1 = subdirs.index(new_folder_name)
                else:
                    fs.make_dir('{}/{}'.format(currdir, new_folder_name))
                    st.toast(
                        ':green[Folder "{}" created.]'.format(new_folder_name)
                    )
                    subdirs.append(new_folder_name)
                    subdirs.sort()
                    State.tree_select_index_1 = subdirs.index(new_folder_name)
                    st.rerun()

            with st.container(height=main_container_height):
                if multiselect:
                    ...
                else:
                    target_dirname = st.radio(
                        'Select folder', subdirs, index=State.tree_select_index_1
                    )
                    result = (
                        target_dirname is None
                        and currdir
                        or '{}/{}'.format(currdir, target_dirname)
                    )

            def change_dir(
                dirpath: str, relocate_subdir_name: str = ''
            ) -> None:
                if dirpath not in State.folders:
                    State.folders[dirpath] = fs.find_dir_names(dirpath)
                State.tree_select_index_0 = sorted(State.folders).index(dirpath)
                if relocate_subdir_name:
                    State.tree_select_index_1 = State.folders[dirpath].index(
                        relocate_subdir_name
                    )
                else:
                    State.tree_select_index_1 = 0
                st.rerun()

            if do_back:
                a, b = currdir.rsplit('/', 1)
                change_dir(a, relocate_subdir_name=b)
            elif do_enter and result != currdir:
                change_dir(result)
            else:
                a, b = result.rsplit('/', 1)
                st.markdown('You selected: **{}/:blue[{}]**'.format(a, b))

    if do_confirm:
        State.installation_path = (
            result.endswith('/Depsland') and result or result + '/Depsland'
        )
        st.rerun()


# ------------------------------------------------------------------------------


def open_file(path: str) -> None:
    assert _isfile(path)
    os.startfile(os.path.abspath(path))


def open_folder(path: str) -> None:
    assert _isdir(path)
    os.startfile(os.path.abspath(path))


def _isdir(path: str) -> bool:
    if os.path.islink(path):
        return os.path.isdir(os.path.realpath(path))
    return os.path.isdir(path)


def _isfile(path: str) -> bool:
    if os.path.islink(path):
        return os.path.isfile(os.path.realpath(path))
    return os.path.isfile(path)
