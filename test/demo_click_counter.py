"""
Demo: Event-driven click counter (Target API snapshot, NOT runnable yet).

This file is a concept demo for the upcoming event-driven Streamlit framework.
It depends on the v3 API (sc.StateV2, sc.Property, sc.Signal, context-manager
components, sc.run(func, port=...)) which has not been implemented yet. Running
this file will fail with ImportError or AttributeError.

Purpose: pin down the target API contract so Phase 1+ implementations have a
clear target to design against. See the roadmap:
    .trae/documents/event_driven_streamlit_roadmap.md

Run (when v3 lands):
    python test/demo_click_counter.py
"""

import streamlit_canary as sc


# ---------------------------------------------------------------------------
# 1. State definition.
#    `sc.StateV2` is the base class for event-driven state. Each `sc.Property`
#    declared on the class is compiled by the metaclass into a property object
#    that derives six accessors (see comments below).
#    `__version__` controls schema migration: bump it when the property layout
#    changes, and old session state will be discarded/rebuilt.
# ---------------------------------------------------------------------------

class _State(sc.StateV2):
    count = sc.Property(0)
    #   The metaclass derives six accessors reachable from the instance:
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
    with sc.Row():
        # `with sc.Text(...) as txt` creates a persistent Text component whose
        # identity survives across interactions. `txt.text = ...` later patches
        # the existing component in place rather than re-rendering the app.
        with sc.Text('Click count: 0') as txt:

            # `state.count.on_change` is a Signal. `.partial('self')` returns a
            # decorator that binds the receiving Property as the first arg of
            # the handler, so the lambda below receives `cnt` automatically.
            # NOTE: 'self' here refers to the Property object itself (the thing
            # that changed), not the State instance.
            @state.count.on_change.partial('self')
            def _(cnt: sc.Property):
                txt.text = 'Click count: {}'.format(cnt.get())

        with sc.Button(
            'Increase counter',
            type='primary',
        ) as btn:

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
