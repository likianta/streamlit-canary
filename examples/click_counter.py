"""
Demo: Event-driven click counter (runnable).

This is the reference demo for the event-driven Streamlit framework. The
kernel (`sc.State`, `sc.Property`, `sc.Signal`), the components
(`sc.Row`, `sc.Text`, `sc.Button`) and the event runtime
(`sc.run(func, port=...)`) are all implemented, so this file runs end-to-end:

    python examples/click_counter.py

Open http://127.0.0.1:2201 in a browser and click the button — the counter
updates in place without a full page reload, because the app function only
runs once and subsequent clicks only execute the registered signal handlers.
"""

import streamlit_canary as sc


class _State(sc.State):
    count = sc.Property(0)
    #   Six accessors reachable from the instance:
    #       1. state.count.get()        -> int           (read current value)
    #       2. state.count.set(value)   -> None          (write + emit on_change)
    #       3. state.count.on_change    -> Signal        (the change signal)
    #       4. state['count']           -> int           (alias of .get())
    #       5. state['count'] = value   -> None          (alias of .set(value))
    #       6. state['on_count']        -> Signal        (alias of .on_change)

    __version__ = 0
    #   Or pass `version=N` to _State(...) when migrating the schema live.


state = _State()
# state = _State(version=1)


def click_counter_demo():
    sc.PageTitle('Click Counter', default_theme='dark')
    with sc.Row('center'):
        # `with sc.Text(...) as txt` creates a persistent Text component
        # whose identity survives across interactions.
        # `txt.text` is itself a `Property` (same model as state), so it is
        # updated via `txt.text.set(...)`, which emits `txt.text.on_change`.
        with sc.Text('Click count: 0') as txt:
            # `state.count.on_change` is a Signal. Using it as a decorator
            # registers the handler. The signal does not pass its owner by
            # default, so `.partial(sc._self)` binds the Property handle as
            # the first argument: `cnt` below is the `count` Property and
            # `cnt.get()` returns its new value.
            @state.count.on_change.partial(sc._self)
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))

        with sc.Button('Increase counter', type='primary') as btn:
            # `btn.on_click` is a Signal. Using it as a decorator registers the
            # handler. When the user clicks the button in the frontend, only
            # this handler runs — no full app re-execution.
            @btn.on_click
            def _():
                # `state['count'] += 1` is sugar for:
                #   state.count.set(state.count.get() + 1)
                # The setter emits `state.count.on_change`, which in turn
                # invokes the handler above, which patches `txt.text`.
                state['count'] += 1


if __name__ == '__main__':
    # python examples/click_counter.py
    sc.run(click_counter_demo, port=2201)
