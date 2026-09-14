"""
A copy from `lib/pyproject_manager` but using streamlit-canary components V3.
"""

import os
import typing as tp
from collections import defaultdict
from functools import partial
from time import sleep

import streamlit_canary as sc
from lk_utils import fs
from lk_utils import re

# `run_cmd_args` is only used by the temporarily-disabled code (uv build /
# uv sync / uv publish).  It is kept here so the commented-out blocks
# below stay readable.
from lk_utils import run_cmd_args  # noqa: F401
from neoprint import print

v3 = sc.v3


class T:
    Dependency = tp.TypedDict(
        'Dependency',
        {
            'name': str,
            'operator': str,
            'current_version': str,
            'latest_version': str,
            'is_latest': bool,
            'setter': tp.Callable[[str], None],
            'markers': dict,
        },
    )
    PackageName = str  # kebab-case

    Dependencies = tp.Dict[PackageName, Dependency]
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

    DependenciesManager = tp.TypedDict(
        'DependenciesManager',
        {
            'dependencies': Dependencies,
            'toml_handler': 'PyProjTomlHandler',
            'todo_bump': bool,
            'todo_sync': bool,
            'bumped_but_not_synced': tp.Set[PackageName],
        },
    )
    Projects = tp.Dict[PackageName, ProjectInfo]


class _State(sc.StateV2):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.dependency = sc.Property()  # current selected dependency item.
        self.project = sc.Property()  # current selected project item.
        self.project_by_name = sc.Property()
        self.project_dependencies = sc.Property()
        self.project_manager = sc.Property()
        self.project_manager_by_name = {}
        self.projects_by_scope = sc.Property()

        self.project_dependencies.bind(
            self.project, self._load_project_dependencies
        )
        self.project_manager.bind(
            self.project,
            lambda this: self.project_manager_by_name[this['name']],
        )

        self.refresh_projects()

        self.uv_publish_token = sc.Property(os.getenv('UV_PUBLISH_TOKEN', ''))
        if not self.uv_publish_token.get():
            print('UV_PUBLISH_TOKEN environment variable is not set', ':v8')

    def refresh_projects(self):
        projects = self._list_projects()
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
        self.projects_by_scope.set(by_scope)
        self.project_by_name.set(by_scope['all'])
        for first in self.project_by_name.get().values():
            self.project.set(first)
            break
        else:
            raise Exception('No project in "all" scope!')

    def _list_projects(self) -> T.Projects:
        print('list all projects', ':i')
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

    def _load_project_dependencies(self, project: T.ProjectInfo):
        if project['name'] not in self.project_manager_by_name:
            deps: T.Dependencies = {}
            handler = PyProjTomlHandler(project['pyproject_file'])

            private_sourced_deps = frozenset(
                x for x in project['toml_data']['tool']['uv']['sources']
            )
            # print(sorted(private_sourced_deps), ':nlv')
            try:
                dev_dep_names = frozenset(
                    re.match(r'([-\w]+)', x).sure().group()
                    for x in project['toml_data']['dependency-groups']['dev']
                )
            except KeyError:
                dev_dep_names = frozenset()
            for line in handler.get_dependencies():
                name, ext, opt, ver = (
                    re.match(
                        r'([-\w]+)(?:\[(\w+)])?([!<>=]+)([.\w]+);?',
                        # ^------^     ^---^   ^-------^^------^
                        line.get(),
                    )
                    .sure()
                    .groups()
                )
                deps[name] = tp.cast(
                    T.Dependency,
                    {
                        'name': name,
                        'operator': opt,
                        'current_version': (v0 := ver),
                        'latest_version': (
                            v1 := self['project_by_name'][name]['version']
                            if name in private_sourced_deps
                            and name not in dev_dep_names
                            else None
                        ),
                        'is_latest': (True if v1 is None else v0 == v1),
                        'setter': line.set,
                        'markers': {'extra': ext},
                    },
                )

            mgr: T.DependenciesManager = {
                'dependencies': deps,
                'toml_handler': handler,
                'todo_bump': any((not d['is_latest'] for d in deps.values())),
                'todo_sync': False,
                'bumped_but_not_synced': set(),
            }
            self.project_manager_by_name[project['name']] = mgr
        else:
            deps = self.project_manager_by_name[project['name']]['dependencies']
        for first in deps.values():
            self.dependency.set(first)
            break
        return deps


def main():
    sc.set_page_config('Pyproject Manager', layout='wide', default_theme='dark')
    v3.Title('Pyproject Manager')
    with v3.Row():
        with v3.Column(width=300):
            _project_list()
        with v3.Column():
            with v3.Column(border=True):
                _version_bumps()
            with v3.Column(border=True):
                _dependency_manager()


def _dependency_manager():
    v3.Caption('Dependencies')

    def _format_dependency(name: str) -> str:
        dep: T.Dependency = state['project_dependencies'][name]
        if name in state['project_manager']['bumped_but_not_synced']:
            version = ':green[{}]'.format(dep['current_version'])
        elif dep['is_latest']:
            version = dep['current_version']
        else:
            version = ':red[{}] -> :green[{}]'.format(
                dep['current_version'], dep['latest_version']
            )
        return '{} ({})'.format(name, version)

    with v3.Radio(
        sc.bind(
            state.project,
            lambda x: 'Project **{}** dependencies'.format(x['name']),
        )
    ) as deps_radio:
        deps_radio.options.bind(
            state.project_dependencies, lambda x: tuple(x.keys())
        )
        deps_radio.format_func = _format_dependency

        @deps_radio['on_value'].partial(sc._value)
        def _set_dependency(dep_name: str):
            state.dependency.set(state['project_dependencies'][dep_name])

    _spinner = v3.Spinner(visible=False)

    with v3.Row():
        with v3.Button('Bump version') as btn:
            btn.enabled.bind(
                state.dependency, lambda this: not this['is_latest']
            )

            @btn.on_click
            def _bump_this_version():
                dep: T.Dependency = state['dependency']
                mgr: T.DependenciesManager = state['project_manager']
                assert (
                    dep['latest_version'] is not None and not dep['is_latest']
                )
                # Modify the in-memory toml line (not written to disk).
                dep['setter'](
                    '{}{}{}{}'.format(
                        dep['name'],
                        '[{}]'.format(dep['markers']['extra'])
                        if dep['markers']['extra']
                        else '',
                        dep['operator'],
                        dep['latest_version'],
                    )
                )
                dep['current_version'] = dep['latest_version']
                dep['is_latest'] = True
                mgr['bumped_but_not_synced'].add(dep['name'])
                mgr['todo_bump'] = not all(
                    d['is_latest'] for d in mgr['dependencies'].values()
                )
                mgr['todo_sync'] = True
                # NOTE: commented out — writes to pyproject.toml.
                # mgr['toml_handler'].save()
                # Trigger UI updates (in-memory state changed, but the
                # Property holds the same dict object, so we force-emit).
                state['on_dependency'].emit()
                state['on_project_manager'].emit()
                deps_radio.options.on_change.emit()

        with v3.Button('Bump all versions') as btn:
            btn.enabled.bind(
                state.project_manager, lambda this: this['todo_bump']
            )

            @btn.on_click
            def _bump_all_versions():
                mgr: T.DependenciesManager = state['project_manager']
                deps: T.Dependencies = mgr['dependencies']
                for dep in deps.values():
                    if not dep['is_latest']:
                        dep['setter'](
                            '{}{}{}{}'.format(
                                dep['name'],
                                '[{}]'.format(dep['markers']['extra'])
                                if dep['markers']['extra']
                                else '',
                                dep['operator'],
                                dep['latest_version'],
                            )
                        )
                        dep['current_version'] = dep['latest_version']
                        dep['is_latest'] = True
                        mgr['bumped_but_not_synced'].add(dep['name'])
                mgr['todo_bump'] = False
                mgr['todo_sync'] = True
                # NOTE: commented out — writes to pyproject.toml.
                # mgr['toml_handler'].save()
                # print('file updated', state['project']['pyproject_file'])
                # Trigger UI updates.
                state['on_dependency'].emit()
                state['on_project_manager'].emit()
                deps_radio.options.on_change.emit()

        with v3.Button(
            'Sync & lock',
            enabled=sc.bind(
                state.project_manager, lambda this: this['todo_sync']
            ),
        ) as btn:

            @btn.on_click
            def _sync_and_lock():
                # This function will take several seconds.
                assert state['project_manager']['todo_sync']
                with _spinner('Syncing...'):
                    # NOTE: commented out — runs `uv sync` which mutates
                    # the environment.
                    # run_cmd_args(
                    #     ('uv', 'sync', '--no-install-project'),
                    #     verbose=True,
                    #     cwd=state['project']['project_path'],
                    # )
                    sleep(3)
                state['project_manager']['todo_sync'] = False
                state['project_manager']['bumped_but_not_synced'].clear()
                # Trigger UI updates.
                state['on_project_manager'].emit()
                deps_radio.options.on_change.emit()


def _project_list():
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
        with v3.Row(vertical_alignment='bottom'):

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
                'Project scope', format_func=_format_scope_key, key='scope_sel'
            ) as scope_sel:
                scope_sel.options.bind(
                    state.projects_by_scope, lambda this: list(this.keys())
                )

                @scope_sel['on_value'].partial(sc._value).emit_now
                def _(value: str):
                    state['project_by_name'] = state['projects_by_scope'][value]
                    print(
                        'scope: {}'.format(value), len(state['project_by_name'])
                    )

            with v3.Button(
                ':material/autorenew:',
                help='Rescan projects',
                key='refresh_btn',
            ) as btn:
                btn.on_click.connect(state.refresh_projects)

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

            curr_proj_list.options.bind(
                state.project_by_name,
                lambda this: [
                    _project_key_to_label(index, key, info)
                    for index, (key, info) in enumerate(this.items())
                ],
            )

            @curr_proj_list['on_value'].partial(sc._value)
            def _(label: str):
                proj_name = label.split()[1]
                state['project'] = state['project_by_name'][proj_name]

        with v3.Button('Rescan projects', width='stretch') as btn:
            btn.on_click.connect(state.refresh_projects)


def _version_bumps():
    with v3.Grid(columns=2) as grid:
        with grid[0, 0]:  # __getitem__(self, (row, col)) -> CellContainer
            with v3.Button('...') as btn:

                @(state['on_project'].partial(btn, sc._value).emit_now)
                def _set_button_text(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    btn['text'] = (
                        'Bump version\n\n(:{}[{}] -> :gray[{}])'.format(
                            'green'
                            if fs.exist(proj_info['dist_file'])
                            else 'gray',
                            proj_info['version'],
                            _bump_least_version(proj_info['version']),
                        )
                    )

                @btn.on_click
                def _() -> None:
                    proj_info = state['project']
                    curr_ver = proj_info['version']
                    next_ver = _bump_least_version(curr_ver)
                    # NOTE: commented out — writes to pyproject.toml.
                    # pyproj_file = proj_info['pyproject_file']
                    # old_content = fs.load(pyproj_file, 'plain')
                    # new_content = old_content.replace(
                    #     'version = "{}"'.format(curr_ver),
                    #     'version = "{}"'.format(next_ver),
                    #     1,
                    # )
                    # fs.dump(new_content, pyproj_file, 'plain')
                    # Update in-memory state.
                    proj_info['version'] = next_ver
                    proj_info['dist_file'] = proj_info['dist_file'].replace(
                        '{}-py3-none-any.whl'.format(curr_ver),
                        '{}-py3-none-any.whl'.format(next_ver),
                    )
                    # Trigger UI updates (Grid button texts + project
                    # radio labels).
                    state['on_project'].emit()
                    state['on_project_by_name'].emit()
                    print(
                        'bumped version in memory: {} -> {}'.format(
                            curr_ver, next_ver
                        )
                    )

        with grid[0, 1]:
            with v3.Button('...') as btn:

                @(state['on_project'].partial(btn, sc._value).emit_now)
                def _set_button_text(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    btn['text'] = 'Build wheel\n\n(:{}[{}])'.format(
                        'green' if fs.exist(proj_info['dist_file']) else 'gray',
                        proj_info['version'],
                    )

                @btn.on_click
                def _() -> None:
                    proj_info = state['project']
                    # NOTE: commented out — runs `uv build --wheel`.
                    # if proj_info['build_tool'] == 'uv':
                    #     run_cmd_args(
                    #         ('uv', 'build', '--wheel'),
                    #         verbose=True,
                    #         cwd=proj_info['project_path'],
                    #     )
                    # else:
                    #     run_cmd_args(
                    #         ('poetry', 'build', '-f', 'wheel'),
                    #         verbose=True,
                    #         cwd=proj_info['project_path'],
                    #     )
                    print(
                        '(skipped) build wheel: {} {}'.format(
                            proj_info['name'], proj_info['version']
                        )
                    )

        with grid[1, 0]:
            with v3.Button('...') as btn:

                @(state['on_project'].partial(btn, sc._value).emit_now)
                def _set_button_text(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    btn['text'] = 'Publish to private host\n\n(:{}[{}])'.format(
                        'green' if fs.exist(proj_info['dist_file']) else 'gray',
                        proj_info['version'],
                    )

                @btn.on_click
                def _() -> None:
                    proj_info = state['project']
                    # NOTE: commented out — uploads to private host.
                    # url = 'http://{}/{}/{}'.format(
                    #     'localhost:2132',
                    #     fs.filename(dist_file)
                    #     .split('-')[0]
                    #     .replace('_', '-'),
                    #     fs.filename(dist_file),
                    # )
                    # with open(dist_file, 'rb') as f:
                    #     requests.put(url, data=f)
                    print(
                        '(skipped) publish to private host: {} {}'.format(
                            proj_info['name'], proj_info['version']
                        )
                    )

        with grid[1, 1]:
            with v3.Button('...') as btn:

                @(state['on_project'].partial(btn, sc._value).emit_now)
                def _set_button_text(
                    btn: v3.Button, proj_info: T.ProjectInfo
                ) -> None:
                    btn['text'] = 'Publish to public host\n\n(:{}[{}])'.format(
                        'green' if fs.exist(proj_info['dist_file']) else 'gray',
                        proj_info['version'],
                    )

                @btn.on_click
                def _() -> None:
                    proj_info = state['project']
                    # NOTE: commented out — runs `uv publish` (network push).
                    # run_cmd_args(
                    #     (
                    #         'uv', 'publish', '--token', token,
                    #         proj_info['dist_file'],
                    #     ),
                    #     verbose=True,
                    #     cwd=proj_info['project_path'],
                    # )
                    print(
                        '(skipped) publish to public host: {} {}'.format(
                            proj_info['name'], proj_info['version']
                        )
                    )


# ------------------------------------------------------------------------------


class PyProjTomlHandler:
    def __init__(self, toml_file: str) -> None:
        self._file = toml_file
        self._text = fs.load(toml_file, 'plain')
        self._lines = self._text.splitlines()

    def get_dependencies(self) -> tp.Iterator['_LineHandler']:
        def _get(text: str) -> str:
            return text

        def _set(text: str, index: int, cmt: str = '') -> None:
            self._lines[index] = '    "{}",{}'.format(text, cmt)

        # # fmt: off
        # body_part = (
        #     re.slice(self._text)
        #     .find('dependencies = [').end().cut()
        #     .find(']').cut()
        #     .slice()
        # )
        # # fmt: on
        # lines = (x.lstrip() for x in body_part.splitlines())
        # for i, line in enumerate(lines):  # FIXME: `i` is not correct.
        #     if line.startswith('#'):
        #         continue
        #     else:
        #         assert (m := re.fullmatch(r' {4}"(.+)",( +#.+)?', line))
        #         # yield m.group(1)
        #         yield LineHandler(
        #             partial(_get, m.group(1)),
        #             partial(_set, index=i, cmt=m.group(2) or ''),
        #         )

        flag = 'START'
        for i, line in enumerate(self._lines):
            try:
                if flag == 'START':
                    if line.startswith('dependencies'):
                        flag = 'DEPENDENCIES'
                    continue
                if flag == 'DEPENDENCIES':
                    if line.startswith(']'):
                        flag = 'END'
                        break
                    elif line.strip() == '' or line.lstrip().startswith('#'):
                        continue
                    else:
                        assert (m := re.fullmatch(r' {4}"(.+)",( +#.+)?', line))
                        # yield m.group(1)
                        yield _LineHandler(
                            partial(_get, m.group(1)),
                            partial(_set, index=i, cmt=m.group(2) or ''),
                        )
            except Exception as e:
                e.add_note(
                    str(
                        {
                            'file': self._file,
                            'line_number': i + 1,
                            'line_content': line,
                        }
                    )
                )
                raise
        assert flag == 'END'

    def save(self) -> None:
        fs.dump(self._lines, self._file, 'plain')


class _LineHandler:
    def __init__(
        self, getter: tp.Callable[[], str], setter: tp.Callable[[str], None]
    ) -> None:
        self._getter = getter
        self._setter = setter

    @property
    def text(self) -> str:
        return self._getter()

    def get(self) -> str:
        return self._getter()

    def set(self, value: str) -> None:
        self._setter(value)


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


def _thick_button(primary_label, secondary_label, **kwargs):
    return v3.Button(
        '{}\n\n{}'.format(primary_label, secondary_label),
        width='stretch',
        **kwargs,
    )


# The state is instantiated here (not next to `_State`) because building it
# eagerly loads every project's dependencies, which needs `PyProjTomlHandler`
# to already be defined.
state = _State(version=3)


if __name__ == '__main__':
    sc.run(main, port=3001)
