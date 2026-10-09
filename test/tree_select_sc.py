"""
NOTE: This test is not a pixel-fidelity comparison against
`./tree_select_st.py`. They just have similar names, but nothing more
related.
You can solely test this script.

It is the v3 spelling of that scene, and then some: the three path inputs sit
one under the other, each with a readout under it bound to its `value`.

    PathInputPopup      the browser rides in a `Browse` popover; Confirm
                        writes the choice into the box.
    PathInputExpander   the browser unfolds under the box on demand.
    PathInputExpanded   the browser is always under the box; its rows are
                        what `./tree_select_vs.py` walks (the only visible
                        check group on the page).

There is no rerun here, so the readouts follow the picks as they happen,
instead of being read once the way the v1 scene reads its after a rerun.
"""

import typing as tp
from pprint import pformat

import streamlit_canary as sc
from streamlit_canary import components_v3 as v3


def _readout(name: str) -> tp.Callable[[tp.Any], str]:
    """`'<name>: <value>'`, with a list printed the way Python spells one."""
    return lambda value: '{}: {}'.format(
        name, pformat(value) if isinstance(value, list) else (value or '(none)')
    )


def main() -> None:
    with v3.PathInputPopup(
        'Select a script', '.', filter='.py', selection_mode='single'
    ) as popup:
        pass
    v3.Text(sc.bind(popup.value, _readout('Popup')))

    # `tree_style='tree_view'`: both of these hold the folded-in-place tree,
    # so the expander's rows and the expanded one's are the same kind of row
    with v3.PathInputExpander(
        'Expander', '.', filter='.py', tree_style='tree_view'
    ) as expander:
        pass
    v3.Text(sc.bind(expander.value, _readout('Expander')))

    with v3.PathInputExpanded(
        'Expanded',
        'streamlit_canary',
        filter='.py',
        selection_mode='multiple',
        tree_style='tree_view',
    ) as expanded:
        pass
    v3.Text(sc.bind(expanded.value, _readout('Expanded')))


if __name__ == '__main__':
    sc.run(main, port=2201)
