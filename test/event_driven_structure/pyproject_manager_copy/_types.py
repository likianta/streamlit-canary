"""Shared type declarations.

Mirrors the reference app, where `T` lives in `projects.py`; here it is split
out so every module can import it without creating a cycle.
"""

import typing as tp

if tp.TYPE_CHECKING:
    from .toml_handler import PyProjTomlHandler


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
    PackageName = str  # kebab-case, e.g. 'lk-utils'

    ProjectName = PackageName

    Dependencies = tp.Dict[ProjectName, Dependency]
    ProjectInfo = tp.TypedDict(
        'ProjectInfo',
        {
            'build_tool': tp.Literal['poetry', 'uv'],
            'dist_file': str,
            'modification_time': int,
            'name': ProjectName,
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
    Projects = tp.Dict[ProjectName, ProjectInfo]
