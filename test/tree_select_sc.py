"""
NOTE: This test is not a pixel-fidelity comparison against
`./tree_select_st.py`. They just have similar names, but nothing more
related.
You can solely test this script.

It is the v3 spelling of that scene, and then some: two panels sit one under
the other, each with a readout bound to its `value`.

    SingleTreeSelectWithInput   the flat panel: one folder on show at a time,
                                walked into with the row's `->` arrow.
    ClassicTreeSelect           the cascading one: every level in one listing,
                                folders folded open in place.

There is no rerun here, so the readouts follow the picks as they happen,
instead of being read once the way the v1 scene reads its after a rerun.
`./tree_select_vs.py` drives this very scene with Playwright.
"""

import streamlit_canary as sc
from pprint import pformat
from streamlit_canary import components_v3 as v3


def main() -> None:
    flat = sc.Property('')

    with v3.SingleTreeSelectWithInput(
        'Select a script', '.', filter='.py', selection_mode='single'
    ) as tree:
        v3.Text(
            sc.bind(flat, lambda path: 'Single: {}'.format(path or '(none)'))
        )

        @tree.value.on_change
        def _on_flat_picked() -> None:
            flat.set(str(tree.value.get()))

    cascaded = sc.Property('')

    with v3.ClassicTreeSelect(
        'Cascading tree',
        'streamlit_canary',
        filter='.py',
        selection_mode='multiple',
    ) as classic:
        v3.Text(
            sc.bind(
                cascaded, lambda value: 'Classic: {}'.format(value or '(none)')
            )
        )

        @classic.value.on_change.partial(sc._value)
        def _on_classic_picked(value) -> None:
            cascaded.set(pformat(value))


if __name__ == '__main__':
    sc.run(main, port=2201)
