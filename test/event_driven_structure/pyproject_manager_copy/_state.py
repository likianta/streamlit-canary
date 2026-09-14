"""Application state for the pyproject-manager demo."""

import os
import typing as tp
from collections import defaultdict

import streamlit_canary as sc
from lk_utils import fs
from lk_utils import re
from neoprint import print

from ._types import T
from .toml_handler import PyProjTomlHandler


class _State(sc.StateV2):
    build_message: sc.Property[str]
    current_scope: str
    dependency: sc.Property[T.Dependency]
    name_to_project: sc.Property[T.Projects]
    name_to_project_manager: tp.Dict[T.ProjectName, T.DependenciesManager]
    private_published_files: sc.Property[tp.Set[str]]
    project: sc.Property[T.ProjectInfo]
    project_dependencies: sc.Property[T.Dependencies]
    project_manager: sc.Property[T.DependenciesManager]
    project_revamped: sc.Signal[T.ProjectInfo]
    project_selected: sc.Signal[T.ProjectName]
    scope_to_projects: sc.Property[tp.Dict[str, T.Projects]]
    uv_publish_token: sc.Property[str]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.current_scope = 'all'
        self.build_message = sc.Property[str]()
        self.scope_to_projects = sc.Property()
        self.name_to_project = sc.Property()
        self.name_to_project_manager = {}
        self.project = sc.Property()  # current selected project item.
        self.project_manager = sc.Property()
        self.project_dependencies = sc.Property()
        self.dependency = sc.Property()  # current selected dependency item.
        self.private_published_files = sc.Property[tp.Set[str]](set())
        self.project_revamped = sc.Signal()
        self.project_selected = sc.Signal()

        @self.project_selected
        def _selected(proj_name: T.ProjectName) -> None:
            self['project'] = self['name_to_project'][proj_name]
            if proj_name in self.name_to_project_manager:
                # Reuse the analysed manager, so bump/sync flags survive.
                self._use_manager(self.name_to_project_manager[proj_name])
            else:
                self.reload_pyproject(self['project'])

        @self.project_revamped
        def _revamped(proj: T.ProjectInfo) -> None:
            mgr = self.name_to_project_manager.get(proj['name'])
            if mgr is None:
                self.reload_pyproject(proj)
            else:
                # Only the project *version* changed: re-read the file so the
                # toml handler's in-memory lines match the new version, but
                # keep the dependency bump/sync state untouched.
                mgr['toml_handler'].reload()
            # `project` is the very dict we just mutated, so `set()` would not
            # emit; force-refresh the project-derived UI (button texts).
            self['on_project'].emit()

        self.refresh_projects()

        self.uv_publish_token = sc.Property(os.getenv('UV_PUBLISH_TOKEN', ''))
        if not self.uv_publish_token.get():
            print('UV_PUBLISH_TOKEN environment variable is not set', ':v8')

    def refresh_projects(self) -> None:
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
        self.scope_to_projects.set(by_scope)
        # `name_to_project` follows the scope currently chosen in the UI,
        # instead of always falling back to "all".
        if not by_scope.get(self.current_scope):
            self.current_scope = 'all'
        self.name_to_project.set(by_scope[self.current_scope])
        for first in self.name_to_project.get().values():
            # Selecting the project loads (or reuses) its dependency manager,
            # so `project_manager` / `project_dependencies` are never left
            # unset.
            self.project_selected.emit(first['name'])
            break
        else:
            raise Exception('No project in "all" scope!')

    def reload_pyproject(self, project: T.ProjectInfo) -> None:
        """Re-read `project`'s pyproject file and rebuild its manager."""
        mgr = self._analyze_project(project)
        self.name_to_project_manager[project['name']] = mgr
        self._use_manager(mgr)

    def _use_manager(self, mgr: T.DependenciesManager) -> None:
        """Point `project_manager` / `project_dependencies` / `dependency`
        at `mgr`."""
        self['project_manager'] = mgr
        self['project_dependencies'] = mgr['dependencies']
        for one in mgr['dependencies'].values():
            self['dependency'] = one
            break

    def _analyze_project(self, project: T.ProjectInfo) -> T.DependenciesManager:
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
                        v1 := self['name_to_project'][name]['version']
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
        return mgr

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


# The state is instantiated here (not next to `_State`) because building it
# eagerly loads every project's dependencies, which needs `PyProjTomlHandler`
# to already be defined.
state = _State(version=3)
