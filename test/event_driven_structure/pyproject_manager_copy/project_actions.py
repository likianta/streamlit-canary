"""Project-level actions: bump the version, build the wheel, publish."""

import streamlit_canary as sc
from lk_utils import fs
from lk_utils import re
from lk_utils import run_cmd_args

from ._state import state
from ._types import T
from .publish import publish_to_private_index

v3 = sc.v3


def ui() -> None:
    with v3.Grid(columns=2) as grid:
        with grid[0, 0]:  # __getitem__(self, (row, col)) -> CellContainer
            with v3.Button('Bump version...') as btn:

                @state['on_project'].partial(btn, sc._value).emit_now
                def _set_button_text_1(
                    btn: v3.Button, project: T.ProjectInfo
                ) -> None:
                    btn['text'] = (
                        'Bump version\n\n(:{}[{}] -> :gray[{}])'.format(
                            'green'
                            if fs.exist(project['dist_file'])
                            else 'gray',
                            project['version'],
                            _bump_least_version(project['version']),
                        )
                    )

                @state.project_revamped.partial(btn)
                def _(btn: v3.Button, project: T.ProjectInfo):
                    _set_button_text_1(btn, project)

                @btn.on_click
                def _() -> None:
                    proj_info: T.ProjectInfo = state['project']
                    curr_ver = proj_info['version']
                    next_ver = _bump_least_version(curr_ver)

                    pyproj_file = proj_info['pyproject_file']
                    old_content = fs.load(pyproj_file, 'plain')
                    # we just change the line related to the version in the file.
                    new_content = old_content.replace(
                        'version = "{}"'.format(curr_ver),
                        'version = "{}"'.format(next_ver),
                        1,
                    )
                    fs.dump(new_content, pyproj_file, 'plain')

                    # update in-memory state
                    proj_info['version'] = next_ver
                    proj_info['dist_file'] = proj_info['dist_file'].replace(
                        '{}-py3-none-any.whl'.format(curr_ver),
                        '{}-py3-none-any.whl'.format(next_ver),
                    )
                    state.project_revamped.emit(proj_info)

        with grid[0, 1]:
            with v3.Button('Build wheel package...') as btn:

                @state['on_project'].partial(btn, sc._value).emit_now
                def _set_button_text_2(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    btn['text'] = 'Build wheel package\n\n(:{}[{}])'.format(
                        'green' if fs.exist(proj_info['dist_file']) else 'gray',
                        proj_info['version'],
                    )

                @state.project_revamped.partial(btn)
                def _(btn: v3.Button, proj_info: T.ProjectInfo):
                    _set_button_text_2(btn, proj_info)

                @btn.on_click
                def _() -> None:
                    proj_info: T.ProjectInfo = state['project']
                    assert proj_info['build_tool'] == 'uv'
                    run_cmd_args(
                        ('uv', 'build', '--wheel', proj_info['project_path']),
                        verbose=True,
                        cwd=proj_info['project_path'],
                    )
                    state['build_message'] = (
                        'Successfully built :blue[{}].'.format(
                            fs.filename(proj_info['dist_file'])
                        )
                    )
                    # The wheel now exists on disk: refresh the project-derived
                    # UI (button texts + enabled states).
                    state['on_project'].emit()

        with grid[1, 0]:
            with v3.Button(
                'Publish to private host...',
                enabled=sc.bind(state.project, _private_dist_exists),
            ) as btn:

                @state['on_project'].partial(btn, sc._value).emit_now
                def _set_button_text_3(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    proj_published = (
                        proj_info['dist_file']
                        in state['private_published_files']
                    )
                    proj_dist_exists = _private_dist_exists(proj_info)

                    btn['text'] = 'Publish to private host\n\n(:{}[{}])'.format(
                        'green' if proj_published else 'gray',
                        '{}, {}'.format(
                            proj_info['version'],
                            fs.filesize(proj_info['dist_file'], str),
                        )
                        if proj_dist_exists
                        else proj_info['version'],
                    )

                @btn.on_click.partial(sc._self)
                def _(btn: v3.Button) -> None:
                    proj_info: T.ProjectInfo = state['project']
                    dst = proj_info['dist_file']
                    publish_to_private_index(dst)
                    state['private_published_files'].add(dst)
                    _set_button_text_3(btn, proj_info)

        with grid[1, 1]:
            with v3.Button(
                sc.bind(
                    state.project,
                    lambda x: 'Publish to public host (:gray[{}])'.format(
                        x['version']
                    ),
                ),
                enabled=sc.bind(state.uv_publish_token, lambda x: bool(x)),
            ):
                pass  # TODO

    v3.Success(
        state.build_message,
        visible=sc.bind(state.build_message, lambda x: bool(x)),
    )


def _private_dist_exists(project: T.ProjectInfo) -> bool:
    """A wheel can be published once it is on disk or was published before."""
    dist_file = project['dist_file']
    return dist_file in state['private_published_files'] or fs.exist(dist_file)


def _bump_least_version(old_ver: str) -> str:
    """
    example:
        0.12.0   -> 0.12.1
        0.12.1a9 -> 0.12.1a10
        0.12.1b0 -> 0.12.1b1
    """
    a, b, c, d = (
        re.match(r'(\d+)\.(\d+)\.(\d+)([ab]\d+)?', old_ver).sure().groups()
    )
    if d:
        return f'{a}.{b}.{c}{d[0]}{int(d[1:]) + 1}'
    else:
        return f'{a}.{b}.{int(c) + 1}'
