import os


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
