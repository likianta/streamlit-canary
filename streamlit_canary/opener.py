import os
import typing as tp


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
