import os
import sys
import typing as t
from inspect import currentframe

from lk_utils import fs
from lk_utils import run_cmd_args

from .flow import post_events


def run(target: t.Callable[[], t.Any], port: int = 3001) -> None:
    if os.getenv('STREAMLIT_SWIFT_RUNNING', '0') == '0':
        os.environ['STREAMLIT_SWIFT_RUNNING'] = '1'
        caller_frame = currentframe().f_back
        caller_file = fs.normpath(caller_frame.f_globals.get('__file__'))
        _check_package_definition_in_source(caller_file)
        assert port != 3000, 'port 3000 is reserved by streamlit'
        
        run_cmd_args(
            (sys.executable, '-m', 'streamlit', 'run', caller_file),
            ('--browser.gatherUsageStats', 'false'),
            ('--global.developmentMode', 'false'),
            ('--runner.magicEnabled', 'false'),
            ('--server.headless', 'true'),
            ('--server.port', port),
            verbose=True,
            blocking=True,
            force_term_color=True,
            cwd=_get_entrance(
                fs.parent(caller_file),
                caller_frame.f_globals['__package__']
            ),
        )
    else:
        target()
        post_events.execute()


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
