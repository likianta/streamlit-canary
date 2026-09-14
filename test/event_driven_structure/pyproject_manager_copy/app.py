"""
A copy from `lib/pyproject_manager` but using streamlit-canary components V3.

Run with either of:
    python test/event_driven_structure/pyproject_manager_copy/app.py
    python -m test.event_driven_structure.pyproject_manager_copy.app
"""

if not __package__:
    # Allow running this file directly (relative imports need a package).
    __package__ = 'test.event_driven_structure.pyproject_manager_copy'

import streamlit_canary as sc

from . import dependency_manager
from . import project_actions
from . import projects

v3 = sc.v3


def main() -> None:
    sc.set_page_config('Pyproject Manager', layout='wide', default_theme='dark')
    # v3.Title('Pyproject Manager')
    with v3.Row():
        with v3.Column(width=300):
            projects.ui()
        with v3.Column():
            with v3.Column(border=True):
                project_actions.ui()
            with v3.Column(border=True):
                dependency_manager.ui()


if __name__ == '__main__':
    sc.run(main, port=3001)
