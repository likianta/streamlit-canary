import sys
from argsense import cli

from lk_utils import run_cmd_args


@cli
def run(file: str, port: int) -> None:
    run_cmd_args(
        (
            (sys.executable, '-m', 'streamlit', 'run', file),
            ('--browser.gatherUsageStats', 'false'),
            ('--global.developmentMode', 'false'),
            ('--server.headless', 'true'),
            ('--server.port', str(port)),
        ),
        verbose=True,
        blocking=True,
    )


if __name__ == '__main__':
    # python -m streamlit_canary run <file> <port>
    cli.run()
