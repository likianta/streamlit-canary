"""
Demo: Event-driven click counter (runnable).

This is the reference demo for the event-driven Streamlit framework. The
kernel (`sc.StateV2`, `sc.Property`, `sc.Signal`), v3 components
(`sc.v3.Row`, `sc.v3.Text`, `sc.v3.Button`) and the event runtime
(`sc.run(func, port=...)`) are all implemented, so this file runs end-to-end:

    python test/demo_click_counter.py

Open http://127.0.0.1:3001 in a browser and click the button — the counter
updates in place without a full page reload, because the app function only
runs once and subsequent clicks only execute the registered signal handlers.
"""

import streamlit_canary as sc


# ---------------------------------------------------------------------------
# 1. State definition.
#    `sc.StateV2` is the base class for event-driven state. Each `sc.Property`
#    declared on the class derives six accessors (see comments below).
#    `__version__` controls schema migration: bump it when the property layout
#    changes, and old session state will be discarded/rebuilt.
# ---------------------------------------------------------------------------


class _State(sc.StateV2):
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


# ---------------------------------------------------------------------------
# 2. App function. It will be invoked ONCE by the runtime to construct the
#    component tree. After that, user interactions only trigger the signal
#    handlers registered below — the function body is not re-executed.
# ---------------------------------------------------------------------------


def click_counter_demo():
    sc.set_page_config('Click Counter', default_theme='dark')
    # v3 components live under `sc.v3.*` so they don't pollute the stable v1
    # namespace while the event-driven model is still evolving.
    with sc.v3.Row():
        # `with sc.v3.Text(...) as txt` creates a persistent Text component
        # whose identity survives across interactions.
        # `txt.text` is itself a `Property` (same model as state), so it is
        # updated via `txt.text.set(...)`, which emits `txt.text.on_change`.
        with sc.v3.Text('Click count: 0') as txt:
            # `state.count.on_change` is a Signal. Using it as a decorator
            # registers the handler. When `count` changes, the signal emits
            # the Property handle itself as the argument, so `cnt` below is
            # the `count` Property and `cnt.get()` returns its new value.
            @state.count.on_change
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))

        with sc.v3.Button('Increase counter', type='primary') as btn:
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


# ---------------------------------------------------------------------------
# 3. Entry point. The new `sc.run` takes the app function directly and launches
#    the event-driven runtime (no `streamlit run` subprocess).
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # python test/demo_click_counter.py
    sc.run(click_counter_demo, port=3001)
