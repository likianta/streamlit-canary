# Layout

Layout components decide where other components go. They are used as
context managers; every component created inside the block becomes a
child.

```python
with sc.Row('center'):
    sc.Text('Left')
    sc.Button('Right')
```

## Pages

- [Row](./row.md) — horizontal layout
- [Column](./column.md) — vertical layout with a flex weight
- [Container](./container.md) — bordered, sized, scrollable box
- [Expander](./expander.md) — collapsible section
- [Grid](./grid.md) — explicit rows and columns
- [Tabs](./tabs.md) — tab bar with one panel per label
- [Dialog](./dialog.md) — modal dialog
- [Popover](./popover.md) — floating panel behind a trigger
- [Floating](./floating.md) — sticky corner cluster
- [Space](./space.md) — flexible spacer
- [Bottom](./bottom.md) — bottom-anchored container

## Spacing

The layout uses two spacing tokens:

- `--st-hgap` (8px) for horizontal gaps;
- `--st-vgap` (16px) for vertical gaps.

A `Row` spaces its children with the horizontal gap and uses the vertical
gap when it wraps. A `Container` and a `Grid` use the vertical gap between
their children / rows.

## Sizing

Layout components accept the shared size keywords. A `Container` with a
fixed `height` scrolls when its content overflows. `height='stretch'`
fills the parent instead; inside a `Row`, it makes the column span the
row's tallest sibling.
