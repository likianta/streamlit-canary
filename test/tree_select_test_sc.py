"""
NOTE: This test is not a pixel-fidelity comparison against
`./tree_select_test_st.py`. They just have similar names, but nothing more
related.
You can solely test this script.

It is the v3 spelling of that scene: pick a script through
`v3.TreeSelectWithInput` and watch the pick come back out of `value`. There is
no rerun here, so the readout is bound to the value and follows it, instead of
being read once the way the v1 scene reads it after its rerun.
"""

import streamlit_canary as sc
from streamlit_canary import components_v3 as v3


def main() -> None:
    picked = sc.Property('')

    with v3.TreeSelectWithInput(
        'Select a script', '.', filter='.py', selection_mode='single'
    ) as tree:
        v3.Text(
            sc.bind(picked, lambda path: 'Picked: {}'.format(path or '(none)'))
        )

        @tree.value.on_change
        def _on_picked() -> None:
            picked.set(str(tree.value.get()))


if __name__ == '__main__':
    sc.run(main, port=2201)
