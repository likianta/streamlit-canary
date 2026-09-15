"""Dependency panel: list the selected project's dependencies and manage them."""

import typing as tp

import streamlit_canary as sc
from lk_utils import fs
from lk_utils import run_cmd_args
from neoprint import print

from ._state import state
from ._types import T
from .export import lock_requirements

v3 = sc.v3


def ui() -> None:
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
        ),
        label_visibility='collapsed',
    ) as deps_radio:
        deps_radio.options.bind(
            state.project_dependencies, lambda x: list(x.keys())
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
                mgr['toml_handler'].save()
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
                mgr['toml_handler'].save()
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
                    run_cmd_args(
                        ('uv', 'sync', '--no-install-project'),
                        verbose=True,
                        cwd=state['project']['project_path'],
                    )
                state['project_manager']['todo_sync'] = False
                state['project_manager']['bumped_but_not_synced'].clear()
                # Trigger UI updates.
                state['on_project_manager'].emit()
                deps_radio.options.on_change.emit()

        with v3.Button('Reload pyproject file') as btn:

            @btn.on_click
            def _reload_pyproject():
                print(
                    'reload pyproject.toml',
                    fs.filetime(state['project']['pyproject_file'], str),
                )
                state.reload_pyproject(state['project'])

        with v3.Popover('Export requirements'):
            with v3.Radio('Mirror source', horizontal=True) as host_radio:
                host_radio.options.set(['Tsinghua', 'Aliyun'])
                host_radio.value.set('Tsinghua')

            with v3.Selectbox('Secondary source') as extra_select:
                extra_select.options.set(
                    ['localhost', '172.20.128.100', '47.102.108.149']
                )
                extra_select.value.set('localhost')

            lock_self = v3.Checkbox('Lock self', value=True)

            with v3.Button(
                'Export', type='primary', width='stretch'
            ) as export_btn:

                @export_btn.on_click
                def _export_requirements():
                    proj_info: T.ProjectInfo = state['project']
                    # `uv export` takes a moment: clear the success box and
                    # show a spinner in its place (they share one status area).
                    state['build_message'] = ''
                    state['busy_text'] = 'Exporting requirements...'
                    try:
                        lock_requirements(
                            proj_info,
                            include_self=bool(lock_self.value.get()),
                            primary_host=tp.cast(
                                tp.Literal['aliyun', 'tsinghua'],
                                str(host_radio.value.get()).lower(),
                            ),
                            secondary_host=str(extra_select.value.get()),
                        )
                    except Exception as e:
                        state['build_message'] = (
                            ':red[Export failed: {}]'.format(e)
                        )
                        return
                    finally:
                        state['busy_text'] = ''
                    state['build_message'] = (
                        ':green[Exported to "{}/requirements.lock".]'.format(
                            fs.basename(proj_info['project_path'])
                        )
                    )
