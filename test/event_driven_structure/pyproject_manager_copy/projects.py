"""Project list panel (the left column)."""

import streamlit_canary as sc
from lk_utils import fs
from neoprint import print

from ._state import state

v3 = sc.v3


def ui() -> None:
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
                'Project scope', format_func=_format_scope_key
            ) as scope_sel:
                scope_sel.options.bind(
                    state.scope_to_projects, lambda this: list(this.keys())
                )

                @scope_sel['on_value'].partial(sc._value)
                def _(value: str):
                    state.current_scope = value
                    state['name_to_project'] = state['scope_to_projects'][value]
                    print(
                        'scope: {}'.format(value), len(state['name_to_project'])
                    )

            with v3.Button(
                ':material/autorenew:',
                help='Rescan projects',
                key='refresh_btn',
            ) as btn:
                btn.on_click.connect(state.refresh_projects)

        def _project_key_to_label(key: str) -> str:
            """Render a project key as its numbered label (for `format_func`).

            The radio's option *values* are plain project names, which stay
            stable across version bumps; only the rendered labels change.
            """
            projects = state['name_to_project']
            info = projects[key]
            return ':orange[{number:02}.] {name} :{color}[({version})]'.format(
                number=list(projects).index(key) + 1,
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

        with v3.Radio(
            'Project', format_func=_project_key_to_label
        ) as curr_proj_list:
            curr_proj_list.options.bind(
                state.name_to_project, lambda projects: list(projects)
            )
            curr_proj_list.value.bind(
                state.project, lambda project: project['name']
            )

            @state.project_revamped
            def _refresh_labels(*_) -> None:
                # Option values (project names) are stable, so a version bump
                # only changes the rendered labels: re-emit to rebuild them.
                curr_proj_list.options.on_change.emit()

            @curr_proj_list['on_value'].partial(sc._value)
            def _(proj_name: str) -> None:
                state.project_selected.emit(proj_name)

        with v3.Button('Rescan projects', width='stretch') as btn:
            btn.on_click.connect(state.refresh_projects)
