"""
Binding several sources: the canonical way (runnable).

Run:
    python examples/bind_multi_source.py      # http://localhost:2210

`sc.bind` takes either one source or several:

    doubled = sc.bind(state.rows, lambda n: n * 2)            # the value
    cells = sc.bind((state.rows, state.cols), ....)            # an acc[i]

With several sources the transform receives an *accessor*, indexed in the
tuple order (`acc[0]` is the first source), so the tuple order is just the
slot order. Everything else about the multi-source form follows from four
rules:

1. Bind *independent* sources only, and derive everything else inside the
   transform. A source that can be derived from another source of the same
   bind makes the target read a pair that is only ever half-updated: one of
   the two has already moved while the other has not. The "sloppy" bind below
   shows that, and the log makes it visible.

2. Compute the derived parts in the transform rather than adding more sources:

       sc.bind((state.rows, state.cols), lambda acc: '{}x{}'.format(*acc))

3. When several inputs must change together, batch the writes, so listeners
   see one settled state instead of several. The two preset buttons below do
   the same two `set()`s, with and without a transaction -- the log shows the
   difference (2 entries vs 1).

       with sc.pending_updates():
           state.rows.set(3)
           state.cols.set(4)

   The values are written straight away; only the notifications wait, and each
   changed property is notified once, in the order it was first set.

4. A source that still holds nothing (`sc.Property()` never set) hands the
   transform `sc._undefined`, so guard it when that is possible:

       lambda acc: '?' if acc[1] is sc._undefined else str(acc[1])

`test/event_driven_system/bind_multi_source.py` is the companion experiment:
it pins these rules down, measures how often the transform runs, and shows
that the *bind* order -- not the tuple order -- decides whether a
half-updated pair is ever published.
"""

import streamlit_canary as sc


class _State(sc.StateV2):
    rows = sc.Property(1)
    cols = sc.Property(1)
    __version__ = 0


state = _State()


def _log(log: sc.Property, line: str) -> None:
    """Append one line to a running log (nothing ever removes lines)."""
    log.set('{}{}\n'.format(log.get(), line))


def bind_multi_source_demo():
    sc.set_page_config('Binding several sources')

    # -- the canonical bind -------------------------------------------------
    # Two independent inputs; the derived parts (`cell(s)`) are computed in
    # the transform instead of being extra sources. One sync per change, and
    # the pair it reads is always settled.
    cells = sc.bind(
        (state.rows, state.cols),
        lambda acc: '{} row(s) x {} col(s) = {} cell(s)'.format(
            acc[0], acc[1], acc[0] * acc[1]
        ),
    )

    # -- the sloppy bind ----------------------------------------------------
    # `rows_label` is derived from `state.rows`, yet it is also a *source* of
    # this bind, which reads `state.rows` too. The two sources move at
    # different moments, so the target is re-synced in between -- and it is
    # that in-between value that shows up in the log below.
    #
    # `rows_label` is created first but *bound* last on purpose: a listener
    # is called in registration order, so this makes the report listen to
    # `state.rows` before `rows_label` catches up. Bind it before the report
    # and the half-updated value would go unnoticed -- the value would be the
    # same, but the log would look clean. That is exactly why the rule is
    # "don't mix a value with its own derivative", and not "mind the order".
    rows_label = sc.Property('')
    report = sc.bind(
        (rows_label, state.rows),
        lambda acc: '{} / {} row(s)'.format(acc[0], acc[1]),
    )
    rows_label.bind(state.rows, lambda n: '{} row(s)'.format(n))

    # -- what each bind published, in order ---------------------------------
    cells_log = sc.Property('')
    report_log = sc.Property('')

    @cells.on_change
    def _():
        _log(cells_log, 'cells     {}'.format(cells.get()))

    @report.on_change
    def _():
        _log(report_log, 'report    {}'.format(report.get()))

    # -- ui -----------------------------------------------------------------
    with sc.v3.Container():
        sc.v3.Title('Binding several sources')

        with sc.v3.Row():
            # `sc.bbind` so an edit in the box is written back to the state.
            sc.v3.NumberInput('Rows', sc.bbind(state.rows), min_value=1, step=1)
            sc.v3.NumberInput('Cols', sc.bbind(state.cols), min_value=1, step=1)

        with sc.v3.Row(width='content'):
            each = sc.v3.Button('Preset, set one at a time')
            batched = sc.v3.Button('Preset, one transaction', type='primary')
            reset = sc.v3.Button('Clear the logs')

        @each.on_click
        def _():
            state.rows.set(3)
            state.cols.set(4)

        @batched.on_click
        def _():
            # one transaction: the two inputs change together, so the
            # canonical bind syncs once and the log gains one line
            with sc.pending_updates():
                state.rows.set(3)
                state.cols.set(4)

        @reset.on_click
        def _():
            cells_log.set('')
            report_log.set('')
            state.rows.set(1)
            state.cols.set(1)

        sc.v3.Markdown('---')

        sc.v3.Markdown(
            '**Canonical**: `bind((rows, cols), f)` -- independent sources, '
            'the label computed inside.'
        )
        sc.v3.Text(cells)
        sc.v3.Code(cells_log)

        sc.v3.Markdown(
            '**Sloppy**: `bind((rows_label, rows), f)` -- `rows_label` is '
            'derived from `rows`, so the target is re-synced with a pair that '
            'is half-updated.'
        )
        sc.v3.Text(report)
        sc.v3.Code(report_log)


if __name__ == '__main__':
    sc.run(bind_multi_source_demo, port=2210)
