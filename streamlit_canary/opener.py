import os


def open_file(path):
    os.startfile(os.path.abspath(path))


open_folder = open_file
