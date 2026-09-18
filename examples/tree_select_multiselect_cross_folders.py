"""Demo: tree select with single / multiple / multi-cross selection.

`v3.TreeSelectWithInput(selection_mode=...)` carries all three modes now:

    'single'        pick one node (a radio list)
    'multiple'      tick nodes of the folder being browsed
    'multicross'    tick across folders; the picks gather in a bucket
    'any'           all three, switched from a segmented control

This demo drives `multicross` with the default `navigation_mode`, i.e.
`'double_click'`: one click *picks* a row (ticks its box), a double click
*opens* it -- there are no arrow buttons.

    dblclick  `..`       go to the parent folder
    dblclick  `name/`    enter that subfolder
    dblclick  `name`     nothing: a file opens nowhere
    click     any row    tick / untick it, and stay put

`..` can never be ticked (its box is frozen, drawn dimmed): it is a target,
not a node.  And there is no `.` / "this folder" row here -- picking and
moving are no longer fused into a single click, so a row that only existed
to do both has nothing left to say.

Every move keeps the bucket, so picks made in other folders survive -- that
is what makes it a *cross-folder* gathering.  The path input's candidate
dropdown lists the ancestors of the current folder, so any parent is one
pick away too.  Pass `navigation_mode='single_click'` for the older
arrangement, where one click moves and the box alone ticks.

Run it with:

    python examples/tree_select_multiselect_cross_folders.py    # :2201
"""

import json

import streamlit_canary as sc

v3 = sc.v3


def main() -> None:
    sc.set_page_config('Tree Select - Multi / Cross-folders')

    sel = v3.TreeSelectWithInput(
        'Node', '', filter=None, height=420, selection_mode='multicross'
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
