import streamlit_canary as sc

v3 = sc.v3


def main():
    projects = sc.Property()

    with v3.Radio(
        'Radio group',
        options=sc.bind(projects),
        format=lambda x: '{} :gray[(v{})]'.format(x['name'], x['version']),
    ):
        ...

    with v3.Button('Change options') as btn:

        @btn.on_click
        def _():
            if projects.get() == (1, 2, 3):
                projects.set((4, 5, 6))
            else:
                projects.set((1, 2, 3))

    with v3.Button('No change but notify') as btn:

        @btn.on_click
        def _():
            projects.on_change.emit()
