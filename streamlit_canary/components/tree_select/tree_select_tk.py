import typing as tp
from lk_utils import fs


# TODO or DELETE: not used.
def tree_select_tk(
    start_directory: str = '',
    title: str = '',
    multiselect: bool = False,
    type: tp.Literal['file', 'folder'] = 'file',
    filter: tp.Iterable[tp.Tuple[str, str]] = (('All files', '*'),),
    action: tp.Literal['open', 'save'] = 'open',
) -> tp.Union[str, tp.Tuple[str, ...]]:
    from tkinter import Tk
    from tkinter import filedialog

    assert not start_directory or fs.isdir(start_directory)

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
