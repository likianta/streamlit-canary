"""Project list panel (the left column)."""

import streamlit_canary as sc
from lk_utils import fs
from neoprint import print

from ._state import state
from ._types import T

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

            @state.project_revamped.partial(state.name_to_project)
            @state['on_name_to_project'].partial(sc._self).emit_now
            def _refresh_labels(
                name_to_project: sc.Property[T.Projects], *_
            ) -> None:
                curr_proj_list['options'] = [
                    _project_key_to_label(index, key, info)
                    for index, (key, info) in enumerate(
                        name_to_project.get().items()
                    )
                ]

            @curr_proj_list['on_value'].partial(sc._value)
            def _(label: str):
                proj_name = label.split()[1]
                state.project_selected.emit(proj_name)

        with v3.Button('Rescan projects', width='stretch') as btn:
            btn.on_click.connect(state.refresh_projects)
