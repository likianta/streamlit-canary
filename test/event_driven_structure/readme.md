# Event-driven Structure

Here is the conceptual code:

```python
import streamlit_canary as sc

class _State(sc.StateV2):
    count = sc.Property(0)  
    #   ref: lib/qmlease/qtcore/property.py:Property:__init__
    #   it derives six methods:
    #       1. state.count.get: Callable[[], int]
    #       2. state.count.set: Callable[[int], None]
    #       3. state.count.on_change: Signal
    #       4. state['count'] (the `__getitem__` method): same like 
    #           `state.count.get`.
    #       5. state['count'] = value (the `__setitem__` method): same like 
    #           `state.count.set(value)`.
    #       6. state['on_count']: same like `state.count.on_change`.
    
    __version__ = 0
    #   to update the state version, you can either change `__version__` number,
    #   or pass `version=...` to the `__init__` method.

    def __init__(self, **kwargs):
        # in init method, it gets last frame to determine the state id. see also
        # how `sc.init_state` works.
        super().__init__(**kwargs)
        ...

state = _State()
# state = _State(version=1)

def click_counter_demo():
    with sc.v3.Row():
        with sc.v3.Text('Click count: 0') as txt:
            #   `txt.text` is also a `Property` (same model as state), so it
            #   has the same six accessors:
            #       txt.text.get() / txt.text.set(value) / txt.text.on_change
            #       txt['text'] / txt['text'] = value / txt['on_text']
            @state.count.on_change
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))

        with sc.v3.Button(
            'Increase counter',
            type='primary',
        ) as btn:
            @btn.on_click
            def _():
                # state.count.set(state.count.get() + 1)
                state['count'] += 1

if __name__ == '__main__':
    # python test/event_driven_structure.py
    sc.run(click_counter_demo, port=3001)
```
