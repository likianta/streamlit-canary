"""The tree family, exercised in-process.

Everything here drives the components' own surface -- the mode vocabulary, the
listing engines, the tick math, the location ladder -- instead of a browser,
so it runs in a second and never flakes. What it pins down:

* the mode vocabulary (`'single'` / `'multiple'` / `'multicross'` / `'none'`),
* `SingleTreeSelect`: the flat listing, the ladder, walking in and up,
* `FileTreeView`: the cascade, folding in place, re-rooting on enter,
* the tick math: picking a file, and the multicross cover / un-cover dance
  (tick a folder -> one pick; untick a file inside it -> the folder opens into
  its children minus that file),
* `TreeView`: the filesystem-free model, spelled in `/`-joined node paths,
* `selection_mode='none'`: no boxes drawn, no pick to make, no Confirm bar.

Run: `python test/tree_select_vs.py`
"""

import typing as tp

from streamlit_canary import components_v3 as v3
from streamlit_canary.components_v3.trees import _shared
from streamlit_canary.runtime import render

ROOT = 'test'  # a folder holding both sub-folders and files
good = True


def check(name: str, ok: bool) -> None:
    global good
    print('  [{}] {}'.format('ok' if ok else 'FAIL', name))
    good = ok and good


def section(title: str) -> None:
    print()
    print(title)


def rows_of(tree: tp.Any) -> tp.List[str]:
    """The tree's current rows, as the listing draws them."""
    return tree._multi_list.options.get()


# ---------------------------------------------------------------------------
# the mode vocabulary
# ---------------------------------------------------------------------------

section('mode vocabulary')

check("'none' joins the modes", 'none' in _shared._MODES)
check(
    "'none' picks nothing ('' like single)",
    _shared._empty_value('none') == '',
)
check(
    "'none' is not a multi mode",
    not _shared._is_multi('none'),
)
check(
    "'none' draws the radio rows",
    _shared._is_radio('none') and not _shared._is_radio('multiple'),
)
check(
    'every mode has a label',
    all(m in _shared._MODE_LABELS for m in _shared._MODES),
)


def folders_in(rows: tp.List[str]) -> tp.List[str]:
    return [r for r in rows if r != '..' and r.endswith('/')]


def files_in(rows: tp.List[str]) -> tp.List[str]:
    return [r for r in rows if r != '..' and not r.endswith('/')]


# ---------------------------------------------------------------------------
# SingleTreeSelect: the flat listing
# ---------------------------------------------------------------------------

section('SingleTreeSelect (flat listing)')

flat = v3.SingleTreeSelect('Pick', ROOT)
rows = rows_of(flat)
folders = folders_in(rows)
files = files_in(rows)

check('the first row is `..`', rows[0] == '..')
check('there are folders to walk into', bool(folders))
check('folders come before files', (
    not files or not folders or rows.index(folders[-1]) < rows.index(files[0])
))
check('the ladder ends on the folder itself', (
    flat._location.options.get()[-1] == flat.directory
))

into = flat._option_path(folders[0])
flat._jump(into)
check('walking into a folder re-roots the listing', (
    flat.directory == into and rows_of(flat)[0] == '..'
))
flat._jump(flat._home_dir)
check('home goes back', flat.directory == flat._home_dir)


# ---------------------------------------------------------------------------
# FileTreeView: the cascade
# ---------------------------------------------------------------------------

section('FileTreeView (cascading tree)')

cascade = v3.FileTreeView('Cascade', ROOT)
rows = rows_of(cascade)
folders = folders_in(rows)

check('a folder row is spelled as a path', all(
    r.startswith(cascade.directory) for r in folders
))
check('nothing is folded at first', not cascade._open)
check('every row sits at depth 0 while nothing is open', all(
    cascade._depth_of(r) == 0 for r in rows if r != '..'
))
check('there is a folder to fold', bool(folders))

if folders:
    folder = folders[0]
    folder_path = folder.rstrip('/')
    cascade._open.add(folder_path)
    cascade._refresh_listing()
    rows = rows_of(cascade)
    deeper = [r for r in rows if cascade._depth_of(r) > 0]
    check('folding a folder insets its children', bool(deeper))
    check('the children come right after their folder', (
        rows.index(folder) + 1 < len(rows)
        and cascade._depth_of(rows[rows.index(folder) + 1]) > 0
    ))
    cascade._open.discard(folder_path)
    cascade._refresh_listing()
    check('unfolding drops them again', all(
        cascade._depth_of(r) == 0 for r in rows_of(cascade) if r != '..'
    ))
else:
    check('a folder to fold (needs a non-empty folder here)', False)


# ---------------------------------------------------------------------------
# the tick math (multicross: cover / un-cover)
# ---------------------------------------------------------------------------

section('the tick math')

math_tree = v3.FileTreeView('Math', ROOT, selection_mode='multicross')
rows = rows_of(math_tree)
with_files = [
    f for f in folders_in(rows) if files_in(
        [r for r in math_tree._child_paths(f.rstrip('/'))]
    )
]
check('some folder holds files', bool(with_files))
folder = with_files[0]
kids = math_tree._child_paths(folder.rstrip('/'))
files = [c for c in kids if not c.endswith('/')]

ticked = math_tree._tick([], folder.rstrip('/'))
check('ticking a folder makes it one pick', ticked == [folder.rstrip('/')])
check('the folder reads as ticked', math_tree._is_ticked(folder, ticked))
check('its file reads as ticked through the cover', (
    math_tree._is_ticked(files[0], ticked)
))

after = math_tree._untick(ticked, files[0])
check('unticking a file opens the folder into its children',
      files[0] not in after and folder.rstrip('/') not in after)
check('...leaving exactly the other files', (
    sorted(after) == sorted(c for c in kids if c != files[0])
))
check('...and the unticked file is out', not math_tree._is_ticked(
    files[0], after
))
check('...while its siblings stay ticked', math_tree._is_ticked(
    files[1] if len(files) > 1 else after[0], after
))

single = v3.SingleTreeSelect('One', ROOT)
check('`single` picks still work', (
    single._multi_list is not None and single.mode.get() == 'single'
))


# ---------------------------------------------------------------------------
# TreeView: the filesystem-free model
# ---------------------------------------------------------------------------

section('TreeView (static model)')

model = v3.TreeView('Distribution', {
    'A': {'B': None, 'C': {}, 'D': {'E': None, 'F': None, 'G': {}}}
})

check('opens on the model root', model.directory == 'A')
check('the ladder starts at the root', model._location.options.get() == ['A'])
check('the root draws no `..`', rows_of(model) == ['A/C/', 'A/D/', 'A/B'])

model._jump('A/D/G')
check('walking into G grows the ladder', (
    model._location.options.get() == ['A', 'A/D', 'A/D/G']
))
check('away from the root `..` comes back', rows_of(model) == ['..'])

model._jump('A/D')
check('walking back up shortens it', (
    model._location.options.get() == ['A', 'A/D']
))
check('a leaf has no "enter" arrow', not model._is_enterable('A/B'))
check('a folder does', model._is_enterable('A/D/'))

empty = v3.TreeView('Empty', None)
check('an empty model lists nothing at all -- not even `..`',
      rows_of(empty) == [])


# ---------------------------------------------------------------------------
# selection_mode='none'
# ---------------------------------------------------------------------------

section("selection_mode='none'")

none_tree = v3.TreeView('None', {'A': {'B': None, 'D': {}}},
                        selection_mode='none')
html = render._render_radio_group(none_tree._single_list)

check('the box is not drawn', 'st-radio-circle' not in html)
check('the rows are still there', 'st-radio-item' in html)
check('the rows are frozen (a click cannot tick)', (
    'is-box-disabled' in html and 'disabled' in html
))
check('the Confirm bar is hidden', not none_tree.widgets[
    'confirm_button'
].visible.get())
check('nothing is picked', none_tree.value.get() == '')

single_tree = v3.TreeView('Plain', {'A': {'B': None}})
plain_html = render._render_radio_group(single_tree._single_list)
check('a normal listing still draws its box', 'st-radio-circle' in plain_html)
check('...and still confirms', single_tree.widgets[
    'confirm_button'
].visible.get())


# ---------------------------------------------------------------------------
# the distribution tree (the app's assets picker)
# ---------------------------------------------------------------------------

section('the distribution tree (assets picker)')

import importlib  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

app = importlib.import_module(
    'test.rewrite_third_party_projects.depsland_app_builder_copy.app_sc'
)

# A throwaway project: `pkg/` holds a file and an empty folder, plus a
# top-level file and a path that is not on disk at all.
project = tempfile.mkdtemp()
root = os.path.basename(project)
os.makedirs(os.path.join(project, 'pkg', 'empty'))
for rel in ('pkg/a.py', 'readme.md'):
    with open(os.path.join(project, *rel.split('/')), 'w') as f:
        f.write('')

# an empty model draws no row at all -- not even the walk-up
dst = v3.TreeView('Distribution', {}, selection_mode='none')
check('a fresh distribution tree draws nothing (no `..`)',
      rows_of(dst) == [])

model, assets = app._build_assets([], project)
check('no picks -> an empty model', model == {} and assets == [])

# a picked folder stands for its whole subtree
model, assets = app._build_assets([os.path.join(project, 'pkg')], project)
check('a picked folder keeps its whole subtree', model == {
    root: {'pkg': {'empty': {}, 'a.py': None}}
})
check('...while the manifest keeps the folder itself', assets == ['pkg'])

model, assets = app._build_assets(
    [os.path.join(project, 'pkg', 'empty')], project
)
check('an empty folder is marked `:0`', assets == ['pkg/empty:0'])
check('...and shows as a bare folder node', model == {
    root: {'pkg': {'empty': {}}}
})

model, assets = app._build_assets(
    [os.path.join(project, 'readme.md')], project
)
check('a picked file is a leaf', model == {root: {'readme.md': None}})

model, assets = app._build_assets(['pkg'], project)
check('a relative path resolves against the project', model == {
    root: {'pkg': {'empty': {}, 'a.py': None}}
})

model, assets = app._build_assets(['dist', 'dist/charts'], project)
check('a path not on disk becomes a folder to be made', model == {
    root: {'dist': {'charts': {}}}
})

dst.data.set(app._build_assets([os.path.join(project, 'pkg')], project)[0])
rows = rows_of(dst)
check('feeding picks draws the tree (no `..` at the root)',
      rows == ['{}/pkg/'.format(root)])
dst.data.set({})
check('clearing the model empties the tree again', rows_of(dst) == [])

shutil.rmtree(project)


# ---------------------------------------------------------------------------

print()
print('RESULT:', 'ok' if good else 'FAILED')
raise SystemExit(0 if good else 1)
