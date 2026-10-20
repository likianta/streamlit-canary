# Grid

A layout with an explicit number of rows and columns.

```python
with sc.Grid(rows=1, cols=2) as grid:
    with next(grid):
        sc.Button('A')
    with next(grid):
        sc.Button('B')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `rows` | `int` | Number of rows, default `1` |
| `cols` | `int` or sequence of floats | Column count or weights, default `2` |
| `columns` | same as `cols` | Alias kept for compatibility |
| `vertical_alignment` | `'top' \| 'center' \| 'bottom'` | Cell content alignment |

Properties: `visible`.

## Addressing cells

Three forms are available:

```python
# 1. Sequential
with sc.Grid(rows=2, cols=2) as grid:
    with next(grid):
        sc.Text('row 0, col 0')
    with next(grid):
        sc.Text('row 0, col 1')

# 2. By coordinate, reusable
with grid[1, 0]:
    sc.Text('row 1, col 0')

# 3. Iteration
for cell in grid:
    with cell:
        sc.Text('...')
```

`next(grid)` and `for cell in grid` walk left to right, then top to
bottom. `grid[row, col]` returns a stable `Cell`; accessing the same
coordinate again reuses it.

## Column weights

`cols` accepts a sequence of weights, mirroring `st.columns((5, 2))`:

```python
with sc.Grid(cols=(5, 2)) as grid:
    ...
```

## Alignment

`vertical_alignment` decides how a cell's content sits in its row when the
columns differ in height.

## Grid flow

A grid defines its rows and columns up front. It is not a masonry layout;
use nested `Row` / `Column` structures when the content should determine
its own height.
