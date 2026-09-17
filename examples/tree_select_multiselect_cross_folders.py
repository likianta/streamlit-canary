"""Demo: tree select with single / multiple / multi-cross selection.

`v3.TreeSelectWithInput(select_mode=...)` carries all three modes now:

    'single'        pick one node (a radio list)
    'multiple'      tick nodes of the folder being browsed
    'multicross'    tick across folders; the picks gather in a bucket
    'any'           all three, switched from a segmented control

The panel navigates by *clicking* -- there are no arrow buttons.  Its listing
opens with two extra rows, so moving up and down both take one click:

    `..`        go to the parent folder
    `.`         "this folder": taken as a node, but never entered

and the path input's candidate dropdown lists the ancestors of the current
folder, so any parent is one pick away as well.

Run it with:

    python examples/tree_select_multiselect_cross_folders.py    # :2201
"""

import json

import streamlit_canary as sc

v3 = sc.v3


def main() -> None:
    sc.set_page_config('Tree Select - Multi / Cross-folders')

    sel = v3.TreeSelectWithInput(
        'Node', '', filter=None, height=420, select_mode='any'
    )

    with v3.Row():
        btn = v3.Button('Print results', type='primary')
    out = v3.Code('')

    @btn.on_click
    def _print_results() -> None:
        picked = sel.value.get()
        data = {
            'mode': sel.mode.get(),
            # `single` holds one path, the multi modes a list
            'selected': (
                picked
                if isinstance(picked, list)
                else ([picked] if picked else [])
            ),
        }
        print('[tree-select demo] {}'.format(data))
        out.text.set(json.dumps(data, indent=2))


if __name__ == '__main__':
    sc.run(main, port=2201)
