"""
A copy from `lib/pyproject_manager` but using streamlit-canary components V3.
"""

import os
import typing as tp
from collections import defaultdict

import streamlit_canary as sc
from lk_utils import fs
from neoprint import print

v3 = sc.v3


class T:
    PackageName = str  # kebab-case
    ProjectInfo = tp.TypedDict(
        'ProjectInfo',
        {
            'build_tool': tp.Literal['poetry', 'uv'],
            'dist_file': str,
            'modification_time': int,
            'name': PackageName,
            'project_path': str,
            'pyproject_file': str,
            'toml_data': dict,
            'version': str,
        },
    )
    Projects = tp.Dict[PackageName, ProjectInfo]


class _State(sc.StateV2):
    def __init__(self) -> None:
        super().__init__()
        self.current_projects = sc.Property({})
        self.project_by_scope = sc.Property(defaultdict(dict))
        self.uv_publish_token = sc.Property(os.getenv('UV_PUBLISH_TOKEN', ''))
        if not self.uv_publish_token.get():
            print('UV_PUBLISH_TOKEN environment variable is not set', ':v8')


state = _State()


def main():
    sc.set_page_config('Pyproject Manager', layout='wide')
    v3.Title('Pyproject Manager')
    with v3.Column(width=500):
        _project_list()


def _project_list():
    if not state['project_by_scope']:
        _rescan_projects()

    """
    UI illustration:
        ╭────────────────────────────────────────────────────╮
        │╭────────────────────────────────╮╭────────────────╮│
        ││ Selectbox:SelectScope          ││ Button:Refresh ││
        │╰────────────────────────────────╯╰────────────────╯│
        │╭──────────────────────────────────────────────────╮│
        ││ Radio:ProjectList                                ││
        ││ - RadioItem:Entry1                               ││
        ││ - RadioItem:Entry2                               ││
        ││ - RadioItem:Entry3                               ││
        ││ - RadioItem:...                                  ││
        ││                                                  ││
        ││                                                  ││
        ││                                                  ││
        ││                                                  ││
        ││                                                  ││
        │╰──────────────────────────────────────────────────╯│
        │╭──────────────────────────────────────────────────╮│
        ││ LongButton:Refresh                               ││
        │╰──────────────────────────────────────────────────╯│
        ╰────────────────────────────────────────────────────╯
    """

    with v3.Column(border=True):
        with v3.Row():

            def _format_scope_key(key: str) -> str:
                return (
                    'All'
                    if key == 'all'
                    else 'Personal (dev.master.likianta)'
                    if key == 'personal'
                    else 'Company (com.jlsemi.likianta)'
                    if key == 'company'
                    else 'Other'
                )

            with v3.Selectbox(
                'Project scope', format_func=_format_scope_key
            ) as scope_sel:
                scope_sel.options.bind(
                    state.project_by_scope, lambda this: list(this.keys())
                )

                @scope_sel['on_value'].emit_now
                def _(value: sc.Property):
                    state['current_projects'] = state['project_by_scope'][
                        value.get()
                    ]
                    print(
                        'scope: {}'.format(value.get()),
                        len(state['current_projects']),
                    )

            with v3.Button(
                ':material/autorenew:', help='Rescan projects'
            ) as btn:
                btn.on_click.connect(_rescan_projects)

        with v3.Radio('Project') as curr_proj_list:

            def _project_key_to_label(
                index: int, key: str, info: T.ProjectInfo
            ) -> str:
                return (
                    ':orange[{number:02}.] {name} :{color}[({version})]'.format(
                        number=index + 1,
                        name=key,
                        color='green'
                        if fs.exist(
                            '{}/dist/{}-{}-py3-none-any.whl'.format(
                                info['project_path'],
                                info['name'].replace('-', '_'),
                                info['version'],
                            )
                        )
                        else 'gray',
                        version=info['version'],
                    )
                )

            # Pre-compute key→label mapping; the radio's format_func looks
            # up the label by key.
            def _radio_format(key: str) -> str:
                projects = state.current_projects.get()
                if not projects or key not in projects:
                    return key
                index = list(projects.keys()).index(key)
                return _project_key_to_label(index, key, projects[key])

            curr_proj_list._format_func = _radio_format
            curr_proj_list.options.bind(
                state.current_projects, lambda this: list(this.keys())
            )

        with v3.Button('Refresh', width='stretch') as btn:
            btn.on_click.connect(_rescan_projects)


def _rescan_projects():
    projects = _list_projects()
    by_scope = defaultdict(dict)
    by_scope['all'] = projects
    for name, info in projects.items():
        scope = (
            'company'
            if 'com.jlsemi.likianta' in info['project_path']
            else 'personal'
            if 'dev.master.likianta' in info['project_path']
            else 'other'
        )
        by_scope[scope][name] = info
    # Use `.set()` so that Property.on_change fires and bound widgets
    # (e.g. `scope_sel.options.bind(state.project_by_scope, ...)`) sync.
    state['project_by_scope'] = by_scope


def _list_projects() -> T.Projects:
    projects = {}
    for path in fs.load(fs.here('watched_projects.yaml')):
        pyproj = fs.load('{}/pyproject.toml'.format(path))
        if 'project' in pyproj:
            name = pyproj['project']['name']
            version = pyproj['project']['version']
        else:
            name = pyproj['tool']['poetry']['name']
            version = pyproj['tool']['poetry']['version']
        assert '_' not in name, ('Name should be in kebab-case', name)
        projects[name] = {
            'name': name,
            'version': version,
            'project_path': path,
            'pyproject_file': '{}/pyproject.toml'.format(path),
            'modification_time': tp.cast(int, fs.filetime(path)),
            'toml_data': pyproj,
            'dist_file': '{}/dist/{}-{}-py3-none-any.whl'.format(
                path, name.replace('-', '_'), version
            ),
            'build_tool': 'poetry'
            if 'poetry' in pyproj['tool']
            and 'dependencies' in pyproj['tool']['poetry']
            else 'uv',
        }
    return dict(sorted(projects.items()))


if __name__ == '__main__':
    sc.run(main, port=3001)
