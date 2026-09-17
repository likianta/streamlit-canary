import streamlit_canary as sc
from faker import Faker

v3 = sc.v3
fk = Faker()


def main():
    deps = sc.Property([fk.word() for _ in range(10)])
    with v3.RadioGroup(
        'Dependencies',
        sc.bind(deps),  # options
        format=lambda x: 'Dependency {}'.format(x),
    ):
        pass

    with v3.Button('Update dependencies') as btn:

        @btn.on_click
        def _():
            deps.set([fk.word() for _ in range(10)])


if __name__ == '__main__':
    # python test/event_driven_system/update_radio_options.py
    sc.run(main, port=2201)
