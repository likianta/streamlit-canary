import os
import shlex
import sys
import typing as t

from lk_utils import fs
from lk_utils import run_cmd_args
from lk_utils.subproc import Popen


def run(
    target: str, port: int = 3001, subthread: bool = False
) -> t.Union[str, Popen]:
    return run_cmd_args(
        (sys.executable, '-m', 'streamlit', 'run'),
        ('--browser.gatherUsageStats', 'false'),
        ('--global.developmentMode', 'false'),
        ('--runner.magicEnabled', 'false'),
        ('--server.headless', 'true'),
        ('--server.port', port),
        shlex.split(target),
        #   'xxx.py'              -> ['xxx.py']
        #   'xxx.py -- arg1 arg2' -> ['xxx.py', '--', 'arg1', 'arg2']
        verbose=True,
        blocking=not subthread,
        force_term_color=True,
        # cwd=_get_entrance(
        #     fs.parent(caller_file),
        #     caller_frame.f_globals['__package__']
        # ),
    )


# DELETE
def _check_package_definition_in_source(source_file: str) -> None:
    """
    if source has imported relative module, it must have defined `__package__` -
    in first of lines.
    """
    source_code = fs.load(source_file, 'plain')
    temp = []
    for i, line in enumerate(source_code.splitlines()):
        line = line.lstrip()
        if line.startswith((
            'if __name__ == "__main__"', "if __name__ == '__main__'"
        )):
            temp.append(line)
        if line.startswith(('from .', 'import .')):
            assert any(x.startswith('__package__ = ') for x in temp), (temp, i)
            return
        if temp:
            temp.append(line)


def _get_entrance(caller_dir: str, package_info: str) -> str:
    if (x := fs.normpath(os.getcwd())) != caller_dir:
        return x
    else:
        assert caller_dir.endswith(x := package_info.replace('.', '/'))
        return caller_dir[:-len(x)]
