# API Reference

This section documents the Components V3 library, grouped the way
Streamlit groups its own API reference.

Each page follows the same shape:

- what the component is for;
- its constructor arguments;
- its reactive properties and signals;
- a short example.

## Pages

- [Text Elements](./texts.md)
- [Data Elements](./data.md)
- [Chart Elements](./charts.md)
- [Button](./buttons.md)
- [Inputs](./inputs/index.md)
- [Layout](./layouts/index.md)
- [Status Elements](./status.md)
- [Media Elements](./media.md)
- [Page Config](./page-config.md)
- [Trees](./trees/index.md)

## Common keywords

All components accept `width`, `height`, `max_width`, `min_width`,
`max_height`, `min_height`, and `visible`, unless a page says otherwise.
Widgets also accept `key` where a stable identity is useful.

```python
sc.Button('Go', width='stretch', visible=state.ready)
```

Text-like components default to `visible='auto'`, which hides them while
their content is blank.

## Reactive fields

A property is read and written through the same interface everywhere:

```python
comp.value.get()
comp.value.set(new_value)
comp['value']
comp['value'] = new_value
comp['on_value']
```
