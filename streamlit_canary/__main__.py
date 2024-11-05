import sys
from argsense import cli

from lk_utils import run_cmd_args
from .runner import _check_package_definition_in_source


@cli.cmd()
def run(file: str, port: int) -> None:
    _check_package_definition_in_source(file)
    run_cmd_args(
        (sys.executable, '-m', 'streamlit', 'run', file),
        ('--browser.gatherUsageStats', 'false'),
        ('--global.developmentMode', 'false'),
        ('--server.headless', 'true'),
        ('--server.port', port),
        verbose=True,
        blocking=True,
    )


if __name__ == '__main__':
    # pox -m streamlit_swift run <file> <port>
    cli.run()
