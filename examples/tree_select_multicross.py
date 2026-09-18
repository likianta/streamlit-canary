"""Demo: tree select with single / multiple / multi-cross selection.

`v3.TreeSelectWithInput(selection_mode=...)` carries all three modes now:

    'single'        pick one node (a radio list)
    'multiple'      tick nodes of the folder being browsed
    'multicross'    tick across folders; the picks gather in a bucket
    'any'           all three, switched from a segmented control

This demo drives `multicross`: one click on a row *picks* it (ticks its box
and stays put), while every folder floats a small `->` beside its text once
the pointer is on the row.  Clicking that arrow walks into the folder (the
text underlines while the pointer is on the arrow, so the pair reads as one
link).  Every arrow sits on the same x -- just past the longest folder name --
so the pointer can be aimed without reading each row first.

    click        any row       tick / untick it, and stay put
    click `->`   `name/`       enter that subfolder
                 `name`        no arrow: a file opens nowhere
    click        `..`          go to the parent folder.  It has no arrow: its
                               box is frozen, so the click has nothing else to
                               do and *is* the gesture

`..` can never be ticked (its box is frozen, drawn dimmed): it is a target,
not a node.  And there is no `.` / "this folder" row here -- there is nothing
to enter, and the location selectbox already picks that folder.

Every move keeps the bucket, so picks made in other folders survive -- that
is what makes it a *cross-folder* gathering.  The panel's toolbar opens with
a location selectbox listing the ancestors of the current folder, so any
parent is one pick away too.

Run it with:

    python examples/tree_select_multicross.py    # :2201
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
